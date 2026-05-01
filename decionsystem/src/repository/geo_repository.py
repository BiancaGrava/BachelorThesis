"""
repository/geo_repository.py
Spatial data access: NUTS-3 boundaries, electrical substations, land availability.
"""
from __future__ import annotations

import fiona
import pandas as pd
import geopandas as gpd
from glob import glob
from pathlib import Path
from shapely.geometry.base import BaseGeometry
from typing import Dict, List, Optional


class GeoRepository:
    """
    Data-access object for all geospatial data sources.

    Data sources
    ------------
    - GeoPackage  : NUTS-3 county boundaries (filtered by country + NUTS level).
    - GeoJSON/glob: electrical substation points.
    - CSV         : available land area per NUTS-3 county (hectares).
    """

    def __init__(self, cfg: dict) -> None:
        self._cfg = cfg

    # ── Public API ────

    def load_counties(self) -> gpd.GeoDataFrame:
        """Load and filter NUTS-3 county polygons for the configured country."""
        gpkg_path = self._cfg["project"]["nuts_gpkg_path"]
        layer = self._guess_nuts_layer(gpkg_path, self._cfg["project"].get("nuts_layer"))

        gdf = gpd.read_file(gpkg_path, layer=layer) if layer else gpd.read_file(gpkg_path)

        if "CNTR_CODE" in gdf.columns:
            gdf = gdf[gdf["CNTR_CODE"] == self._cfg["project"]["country"]].copy()
        if "LEVL_CODE" in gdf.columns:
            gdf = gdf[gdf["LEVL_CODE"] == self._cfg["project"]["nuts_level"]].copy()
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")

        return gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()

    def load_substations(self) -> gpd.GeoDataFrame:
        """Load electrical substation points, merging all matching files."""
        files = self._resolve_substation_files()
        frames: List[gpd.GeoDataFrame] = []
        for fp in files:
            try:
                g = gpd.read_file(fp)
                if g.crs is None:
                    g = g.set_crs("EPSG:4326")
                frames.append(self._sanitize_points(g[["geometry"]].copy()))
            except Exception:
                continue

        if not frames:
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

        out = pd.concat(frames, ignore_index=True)
        return self._sanitize_points(
            gpd.GeoDataFrame(out, geometry="geometry", crs=frames[0].crs)
        )

    def load_land_map(self) -> Dict[str, float]:
        """
        Return a mapping of NUTS_ID → available hectares.
        Falls back to config.yaml hardcoded values when the CSV is absent.
        """
        csv_path_str = self._cfg.get("land", {}).get("available_land_csv")
        if csv_path_str:
            csv_path = Path(csv_path_str)
            if csv_path.exists():
                land_df = pd.read_csv(csv_path)
                if {"NUTS_ID", "available_ha"}.issubset(land_df.columns):
                    print(f"| GeoRepository | Loaded land data from: {csv_path.name}")
                    return dict(zip(land_df["NUTS_ID"], land_df["available_ha"]))

        print("| GeoRepository | WARNING: CSV not found – using config fallback values.")
        counties_cfg = self._cfg.get("counties", {}) or {}
        return {
            nuts_id: float(rec.get("available_ha", 0.0))
            for nuts_id, rec in counties_cfg.items()
            if isinstance(rec, dict)
        }

    # ── Private helpers ───

    def _guess_nuts_layer(self, gpkg_path: str, preferred: Optional[str] = None) -> Optional[str]:
        if preferred:
            return preferred
        try:
            layers = list(fiona.listlayers(gpkg_path))
            return layers[0] if layers else None
        except Exception:
            return None

    def _resolve_substation_files(self) -> List[str]:
        explicit = self._cfg["grid_proxy"].get("substations_geojson")
        if explicit and Path(explicit).exists():
            return [explicit]
        pattern = self._cfg["grid_proxy"].get("substations_glob")
        return sorted(glob(pattern)) if pattern else []

    @staticmethod
    def _sanitize_points(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Ensure every geometry is a valid Point; convert polygons to centroids."""
        if gdf.empty:
            return gdf
        gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
        gdf = gdf[gdf.geometry.apply(lambda x: isinstance(x, BaseGeometry))].copy()
        gdf["geometry"] = gdf.geometry.apply(
            lambda g: g if g.geom_type == "Point" else g.representative_point()
        )
        return gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()