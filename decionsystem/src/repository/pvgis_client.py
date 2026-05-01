"""
repository/pvgis_client.py
HTTP client for the PVGIS PVcalc API with JSON disk cache.
"""
from __future__ import annotations

import json
import numpy as np
import requests
from pathlib import Path
from typing import List, Tuple


class PVGISClient:
    """
    Thin HTTP wrapper around the PVGIS PVcalc endpoint.

    Responsibilities
    ----------------
    - Build parameterised API requests from PV system config.
    - Maintain a deterministic disk cache keyed on (lat, lon, system params).
    - Return annual energy yield (Ey) and monthly vector (Em) per kWp.
    """

    def __init__(self, cfg: dict) -> None:
        self._cfg = cfg
        self._session = requests.Session()

        cache_dir = Path(cfg["run"]["cache_dir"])
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path = cache_dir / cfg["run"]["pvgis_cache_file"]
        self._cache: dict = self._load_cache()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_pvcalc(self, lat: float, lon: float) -> Tuple[float, List[float]]:
        """
        Query the PVGIS PVcalc endpoint for *lat*/*lon*.

        Returns
        -------
        Ey : float
            Annual specific energy yield (kWh/kWp).
        Em : list[float]
            Monthly specific energy yield vector, length 12.
        """
        key = self._build_cache_key(lat, lon)
        if key in self._cache:
            return self._cache[key]["Ey"], self._cache[key]["Em"]

        data = self._fetch(lat, lon)
        Ey, Em = self._parse_response(data)
        self._cache[key] = {"Ey": Ey, "Em": Em}
        return Ey, Em

    def save_cache(self) -> None:
        """Persist in-memory cache to disk."""
        self._cache_path.write_text(
            json.dumps(self._cache, indent=2), encoding="utf-8"
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _load_cache(self) -> dict:
        if self._cache_path.exists():
            return json.loads(self._cache_path.read_text(encoding="utf-8"))
        return {}

    def _build_cache_key(self, lat: float, lon: float) -> str:
        sys = self._cfg["pv_model"]["system"]
        return (
            f"{lat:.5f},{lon:.5f}|pp=1"
            f"|loss={sys['loss_percent']}|tilt={sys['tilt_deg']}"
            f"|az={sys['azimuth_deg']}|tech={sys['pvtechchoice']}"
            f"|mount={sys['mountingplace']}"
        )

    def _fetch(self, lat: float, lon: float) -> dict:
        sys = self._cfg["pv_model"]["system"]
        base = self._cfg["pv_model"]["api_base"].rstrip("/")
        params = {
            "lat": lat,
            "lon": lon,
            "peakpower": 1.0,
            "loss": sys["loss_percent"],
            "angle": sys["tilt_deg"],
            "aspect": sys["azimuth_deg"],
            "pvtechchoice": sys["pvtechchoice"],
            "mountingplace": sys["mountingplace"],
            "outputformat": "json",
        }
        r = self._session.get(f"{base}/PVcalc", params=params, timeout=60)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _parse_response(data: dict) -> Tuple[float, List[float]]:
        Ey = float(data["outputs"]["totals"]["fixed"]["E_y"])
        Em: List[float] = [np.nan] * 12
        try:
            for rec in data["outputs"]["monthly"]["fixed"]:
                m = int(rec["month"])
                Em[m - 1] = float(rec["E_m"])
        except Exception:
            pass
        return Ey, Em