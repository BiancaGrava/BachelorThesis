"""
servicii/optimization_service.py
Core domain service: evaluates and ranks NUTS-3 counties for PV park siting.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
import geopandas as gpd
from joblib import load as joblib_load
from pathlib import Path
from typing import List, Optional, Tuple

from src.domeniu.models import EvaluationResult, PanelConfig, GridConstraints
from src.repository.geo_repository import GeoRepository
from src.repository.features_repository import FeaturesRepository
from src.repository.pvgis_client import PVGISClient


class OptimizationService:
    """
    Orchestrates the county-level PV siting evaluation pipeline.

    Pipeline stages
    ---------------
    1. Load spatial data (counties, substations, land map) via repositories.
    2. For each county: fetch PVGIS energy yield, apply satellite corrections,
       optionally predict with a surrogate Random-Forest model.
    3. Apply land and grid eligibility constraints.
    4. Rank eligible (then ineligible) counties by multi-criteria priority.

    Dependencies (injected via constructor)
    ----------------------------------------
    geo_repo       : GeoRepository
    features_repo  : FeaturesRepository
    pvgis_client   : PVGISClient
    """

    def __init__(
        self,
        cfg: dict,
        geo_repo: GeoRepository,
        features_repo: FeaturesRepository,
        pvgis_client: PVGISClient,
    ) -> None:
        self._cfg = cfg
        self._geo = geo_repo
        self._features = features_repo
        self._pvgis = pvgis_client
        self._sur_bundle: Optional[dict] = self._load_surrogate_model()

    # ── Public API ────────────────────────────────────────────────────────────

    def run_evaluation(
        self,
        xpv_ha: float,
        model_type: str,
        prio1: str,
        prio2: str,
        prio3: str,
    ) -> pd.DataFrame:
        """
        Evaluate all counties and return a ranked DataFrame.

        Parameters
        ----------
        xpv_ha      : requested project area in hectares.
        model_type  : one of ``'pvgis'``, ``'satellite'``, ``'rf'``.
        prio1-3     : ranking criterion keys (``'energy'``, ``'yield'``,
                      ``'grid'``, ``'space'``).
        """
        panel_cfg, grid_cfg = self._load_configs()
        counties_proj = self._geo.load_counties().to_crs(
            self._cfg["project"]["crs_area_distance"]
        )
        sub_pts = (
            self._geo.load_substations()
            .to_crs(self._cfg["project"]["crs_area_distance"])
            .geometry.tolist()
        )
        land_map = self._geo.load_land_map()

        results: List[EvaluationResult] = []
        for _, row in counties_proj.iterrows():
            result = self._evaluate_county(
                row, xpv_ha, model_type, panel_cfg, grid_cfg, sub_pts, land_map
            )
            results.append(result)

        self._pvgis.save_cache()
        return self._rank_results(results, prio1, prio2, prio3)

    # ── Private: configuration loading ───────────────────────────────────────

    def _load_configs(self) -> Tuple[PanelConfig, GridConstraints]:
        p = self._cfg["panel"]
        panel_cfg = PanelConfig(
            p_stc_kwp=float(p["p_stc_kwp"]),
            ground_coverage_ratio=float(p["ground_coverage_ratio"]),
            length_m=float(p["length_m"]),
            width_m=float(p["width_m"]),
        )
        g = self._cfg["constraints"]["grid"]
        grid_cfg = GridConstraints(
            nearest_substation_max_km=float(g["nearest_substation_max_km"]),
            radius_km=float(g["radius_km"]),
            min_substations_within_radius=int(g["min_substations_within_radius"]),
            require_grid=bool(g.get("require_grid", True)),
        )
        return panel_cfg, grid_cfg

    def _load_surrogate_model(self) -> Optional[dict]:
        st_cfg = self._cfg.get("surrogate_teacher", {}) or {}
        if not bool(st_cfg.get("enabled", False)):
            return None
        model_path = Path(st_cfg.get("model_out", "models/pvgis_surrogate.joblib"))
        return joblib_load(model_path) if model_path.exists() else None

    # ── Private: per-county evaluation ───────────────────────────────────────

    def _evaluate_county(
        self,
        row: pd.Series,
        xpv_ha: float,
        model_type: str,
        panel_cfg: PanelConfig,
        grid_cfg: GridConstraints,
        sub_pts: list,
        land_map: dict,
    ) -> EvaluationResult:
        county_id: str = row["NUTS_ID"]
        county_name: str = row.get("NAME_LATN", county_id)
        available_ha: float = float(land_map.get(county_id, 0.0))

        lat, lon = self._county_centroid_wgs84(row, self._geo.load_counties().crs)

        Ey_pvgis, Em_pvgis, error = self._fetch_pvgis(lat, lon)
        cloud_row = self._features.get_county_row(county_id, "cloud")
        albedo_row = self._features.get_county_row(county_id, "albedo")

        Ey_corr = self._corrected_annual_from_satellite(Em_pvgis, cloud_row, albedo_row)
        Ey_sur = self._predict_surrogate(Ey_pvgis, cloud_row, albedo_row)
        Ey_used = self._select_energy_model(model_type, Ey_pvgis, Ey_corr, Ey_sur)

        eff_ha = min(xpv_ha, available_ha)
        n_panels = self._compute_panel_count(eff_ha, panel_cfg)
        annual_energy = float(Ey_used) * panel_cfg.p_stc_kwp * n_panels

        d_km, cnt = self._grid_metrics(row.geometry.representative_point(), sub_pts, grid_cfg.radius_km * 1000.0)
        land_ok = available_ha >= xpv_ha
        grid_ok = self._check_grid(d_km, cnt, grid_cfg)

        c_mean = self._features.normalize_fraction(
            cloud_row["cloud_mean"]
        ) if cloud_row is not None and "cloud_mean" in cloud_row.index else None
        a_mean = self._features.normalize_fraction(
            albedo_row["albedo_mean"]
        ) if albedo_row is not None and "albedo_mean" in albedo_row.index else None

        return EvaluationResult(
            county_id=county_id,
            county_name=county_name,
            available_ha=available_ha,
            requested_xpv_ha=xpv_ha,
            effective_ha_used=eff_ha,
            missing_ha_to_fit=max(xpv_ha - available_ha, 0.0),
            land_ok=land_ok,
            grid_ok=grid_ok,
            eligible=(land_ok and grid_ok),
            nearest_substation_km=d_km if math.isfinite(d_km) else None,
            substations_within_radius=cnt,
            lat=lat,
            lon=lon,
            pvgis_Ey_kWh_per_kWp=float(Ey_pvgis) if np.isfinite(Ey_pvgis) else None,
            sat_corrected_Ey_kWh_per_kWp=float(Ey_corr) if np.isfinite(Ey_corr) else None,
            surrogate_Ey_kWh_per_kWp=float(Ey_sur) if Ey_sur is not None and np.isfinite(Ey_sur) else None,
            Ey_used_kWh_per_kWp=float(Ey_used) if np.isfinite(Ey_used) else None,
            panel_kWp=panel_cfg.p_stc_kwp,
            n_panels_used=int(n_panels),
            annual_energy_kWh=annual_energy,
            cloud_mean=c_mean,
            albedo_mean=a_mean,
            error=error,
        )

    # ── Private: helpers ──────────────────────────────────────────────────────

    def _county_centroid_wgs84(self, row: pd.Series, source_crs) -> Tuple[float, float]:
        rep = row.geometry.representative_point()
        rep_wgs = gpd.GeoSeries([rep], crs=source_crs).to_crs("EPSG:4326").iloc[0]
        return float(rep_wgs.y), float(rep_wgs.x)

    def _fetch_pvgis(
        self, lat: float, lon: float
    ) -> Tuple[float, list, Optional[str]]:
        try:
            Ey, Em = self._pvgis.get_pvcalc(lat, lon)
            return Ey, Em, None
        except Exception as e:
            fallback = float(self._cfg["pv_model"].get("fallback_Ey_kWh_per_kWp", 1300))
            return fallback, [np.nan] * 12, f"PVGIS failed: {e}"

    def _corrected_annual_from_satellite(self, Em_pvgis, cloud_row, albedo_row) -> float:
        gamma_albedo = float(
            self._cfg.get("satellite_correction", {}).get("gamma_albedo", 0.05)
        )
        if Em_pvgis is None or not np.isfinite(np.array(Em_pvgis, dtype=float)).any():
            return np.nan

        Em_corr = []
        for m in range(1, 13):
            base = Em_pvgis[m - 1]
            if not np.isfinite(base):
                Em_corr.append(np.nan)
                continue

            f_cloud = self._cloud_factor(m, cloud_row)
            f_alb = self._albedo_factor(m, albedo_row, gamma_albedo)
            Em_corr.append(base * f_cloud * f_alb)

        return float(np.nansum(np.array(Em_corr, dtype=float)))

    def _cloud_factor(self, month: int, cloud_row) -> float:
        if cloud_row is None:
            return 1.0
        col = f"cloud_m{month:02d}"
        if col not in cloud_row.index or pd.isna(cloud_row[col]):
            return 1.0
        cloud = self._features.normalize_fraction(cloud_row[col])
        clear = 1.0 - cloud
        cloud_mu = self._features.cloud_country_means.get(month, np.nan)
        clear_mu = 1.0 - cloud_mu if np.isfinite(cloud_mu) else np.nan
        if not np.isfinite(clear_mu) or clear_mu <= 0.02:
            return 1.0
        return float(np.clip(clear / clear_mu, 0.90, 1.10))

    def _albedo_factor(self, month: int, albedo_row, gamma: float) -> float:
        if albedo_row is None:
            return 1.0
        col = f"albedo_m{month:02d}"
        if col not in albedo_row.index or pd.isna(albedo_row[col]):
            return 1.0
        alb = self._features.normalize_fraction(albedo_row[col])
        alb_mu = self._features.albedo_country_means.get(month, np.nan)
        if not np.isfinite(alb_mu):
            return 1.0
        return float(np.clip(1.0 + gamma * float(alb - alb_mu), 0.95, 1.05))

    def _predict_surrogate(self, Ey_pvgis: float, cloud_row, albedo_row) -> Optional[float]:
        if self._sur_bundle is None or not np.isfinite(Ey_pvgis):
            return None
        feat_cols = self._sur_bundle.get("feat_cols", [])
        mode = self._sur_bundle.get("mode", "factor")

        c_mean = (
            self._features.normalize_fraction(cloud_row["cloud_mean"])
            if cloud_row is not None and "cloud_mean" in cloud_row.index
            else np.nan)
        a_mean = (
            self._features.normalize_fraction(albedo_row["albedo_mean"])
            if albedo_row is not None and "albedo_mean" in albedo_row.index
            else np.nan
        )
        X = pd.DataFrame([{"Ey_rep_kWh_per_kWp": float(Ey_pvgis), "cloud_mean": c_mean, "albedo_mean": a_mean}])
        if feat_cols:
            X = X.reindex(columns=feat_cols)
        X = X.fillna(X.mean(numeric_only=True))
        try:
            pred = float(self._sur_bundle["model"].predict(X)[0])
            return float(Ey_pvgis) * pred if mode == "factor" else pred
        except Exception:
            return None

    @staticmethod
    def _select_energy_model(
        model_type: str,
        Ey_pvgis: float,
        Ey_corr: float,
        Ey_sur: Optional[float],
    ) -> float:
        if model_type == "rf" and Ey_sur is not None and Ey_sur > 0:
            return Ey_sur
        if model_type in ("satellite", "rf") and np.isfinite(Ey_corr) and Ey_corr > 0:
            return Ey_corr
        return Ey_pvgis

    @staticmethod
    def _compute_panel_count(eff_ha: float, panel_cfg: PanelConfig) -> int:
        if eff_ha <= 0:
            return 0
        return math.floor((eff_ha * 10_000.0 * panel_cfg.ground_coverage_ratio) / panel_cfg.area_m2)

    @staticmethod
    def _grid_metrics(rep_point, substation_points: list, radius_m: float) -> Tuple[float, int]:
        if not substation_points:
            return float("inf"), 0
        dists = [rep_point.distance(p) for p in substation_points]
        d_min = min(dists)
        cnt = sum(1 for d in dists if d <= radius_m)
        return d_min / 1000.0, cnt

    @staticmethod
    def _check_grid(d_km: float, cnt: int, grid_cfg: GridConstraints) -> bool:
        if not grid_cfg.require_grid:
            return True
        return (d_km <= grid_cfg.nearest_substation_max_km) and (cnt >= grid_cfg.min_substations_within_radius)

    @staticmethod
    def _rank_results(
        results: List[EvaluationResult], prio1: str, prio2: str, prio3: str
    ) -> pd.DataFrame:
        crit_map = {
            "energy": ("annual_energy_kWh", False),
            "yield":  ("Ey_used_kWh_per_kWp", False),
            "grid":   ("nearest_substation_km", True),
            "space":  ("available_ha", False),
        }
        df = pd.DataFrame([vars(r) for r in results])
        df_eligible = df[df["eligible"]].copy()
        df_nofit = df[~df["eligible"]].copy()

        sort_cols, asc_orders = [], []
        for p in [prio1, prio2, prio3]:
            col, asc = crit_map[p]
            if col not in sort_cols:
                sort_cols.append(col)
                asc_orders.append(asc)
        for fb in ("annual_energy_kWh", "Ey_used_kWh_per_kWp"):
            if fb not in sort_cols:
                sort_cols.append(fb)
                asc_orders.append(False)

        if not df_eligible.empty:
            df_eligible = df_eligible.sort_values(by=sort_cols, ascending=asc_orders)
        if not df_nofit.empty:
            df_nofit = df_nofit.sort_values(by=sort_cols, ascending=asc_orders)

        return pd.concat([df_eligible, df_nofit]).reset_index(drop=True)