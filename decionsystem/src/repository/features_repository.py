"""
repository/features_repository.py
Loads and normalises cloud-cover and albedo feature tables (CSV → NUTS-3 index).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Optional


class FeaturesRepository:
    """
    Data-access object for satellite-derived feature CSVs.

    Responsibilities
    ----------------
    - Load cloud and albedo CSVs indexed by NUTS_ID.
    - Normalise raw values to the [0, 1] fraction range.
    - Pre-compute country-level monthly mean vectors used by
      OptimizationService for satellite corrections.
    """

    def __init__(self, cfg: dict) -> None:
        self._cfg = cfg
        self.cloud_df: pd.DataFrame = self._load_table(cfg["features"]["cloud_csv"])
        self.albedo_df: pd.DataFrame = self._load_table(cfg["features"]["albedo_csv"])
        self.cloud_country_means: Dict[int, float] = self._build_country_month_means(
            self.cloud_df, "cloud"
        )
        self.albedo_country_means: Dict[int, float] = self._build_country_month_means(
            self.albedo_df, "albedo"
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def get_county_row(self, county_id: str, feature_type: str) -> Optional[pd.Series]:
        """Return the raw feature row for *county_id*; ``None`` if not found."""
        df = self.cloud_df if feature_type == "cloud" else self.albedo_df
        if not df.empty and county_id in df.index:
            return df.loc[county_id]
        return None

    @staticmethod
    def normalize_fraction(x) -> float:
        """
        Coerce *x* to a float in [0, 1].
        Values > 1.5 are assumed to be percentages and divided by 100.
        Returns ``np.nan`` for missing or non-numeric inputs.
        """
        if x is None:
            return np.nan
        try:
            x = float(x)
        except (TypeError, ValueError):
            return np.nan
        if np.isnan(x):
            return np.nan
        if x > 1.5:
            x /= 100.0
        return float(np.clip(x, 0.0, 1.0))

    # ── Private helpers ───────────────────────────────────────────────────────

    def _load_table(self, path: str) -> pd.DataFrame:
        p = Path(path)
        if not p.exists():
            return pd.DataFrame()
        df = pd.read_csv(p)
        if "NUTS_ID" in df.columns:
            return df.set_index("NUTS_ID")
        return pd.DataFrame()

    def _build_country_month_means(
        self, feat_df: pd.DataFrame, prefix: str
    ) -> Dict[int, float]:
        """Pre-compute the national monthly mean for satellite-correction factors."""
        if feat_df.empty:
            return {m: np.nan for m in range(1, 13)}
        means: Dict[int, float] = {}
        for m in range(1, 13):
            col = f"{prefix}_m{m:02d}"
            if col not in feat_df.columns:
                means[m] = np.nan
                continue
            vals = feat_df[col].apply(self.normalize_fraction)
            finite = vals.values[np.isfinite(vals.values)]
            means[m] = float(np.nanmean(finite)) if len(finite) > 0 else np.nan
        return means