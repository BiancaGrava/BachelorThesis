"""
domeniu/models.py
Domain-layer value objects and result dataclasses.
No framework dependencies. Pure Python.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass(frozen=True)
class PanelConfig:
    """Immutable panel specification read from config."""
    p_stc_kwp: float
    ground_coverage_ratio: float
    length_m: float
    width_m: float

    @property
    def area_m2(self) -> float:
        return self.length_m * self.width_m


@dataclass(frozen=True)
class GridConstraints:
    """Immutable grid-proximity constraints read from config."""
    nearest_substation_max_km: float
    radius_km: float
    min_substations_within_radius: int
    require_grid: bool = True


@dataclass
class CountyFeatures:
    """Intermediate value object carrying per-county satellite features."""
    county_id: str
    cloud_monthly: List[Optional[float]]   # length-12
    albedo_monthly: List[Optional[float]]  # length-12
    cloud_mean: Optional[float] = None
    albedo_mean: Optional[float] = None


@dataclass
class EvaluationResult:
    """
    Final optimisation result for one NUTS-3 county.
    Produced by OptimizationService, consumed by the presentation layer.
    """
    county_id: str
    county_name: str

    # ── Land ───
    available_ha: float
    requested_xpv_ha: float
    effective_ha_used: float
    missing_ha_to_fit: float
    land_ok: bool

    # ── Grid ────
    grid_ok: bool
    nearest_substation_km: Optional[float]
    substations_within_radius: int

    # ── Eligibility ───
    eligible: bool

    # ── Location ───
    lat: float
    lon: float

    # ── Energy model outputs ───
    pvgis_Ey_kWh_per_kWp: Optional[float]
    sat_corrected_Ey_kWh_per_kWp: Optional[float]
    surrogate_Ey_kWh_per_kWp: Optional[float]
    Ey_used_kWh_per_kWp: Optional[float]

    # ── Production ───
    panel_kWp: float
    n_panels_used: int
    annual_energy_kWh: float

    # ── Satellite feature summary ──
    cloud_mean: Optional[float] = None
    albedo_mean: Optional[float] = None

    # ── Diagnostics ─────
    error: Optional[str] = None