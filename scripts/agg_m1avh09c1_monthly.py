#!/usr/bin/env python3
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

import numpy as np
import rasterio
from rasterio.windows import from_bounds

# Filename contains ".AYYYYDDD." e.g. M1_AVH09C1.A2020001.006.2022314114906.nc
DATE_RE = re.compile(r"\.A(\d{4})(\d{3})\.")

def doy_to_ymd(year: int, doy: int) -> datetime:
    return datetime(year, 1, 1) + timedelta(days=doy - 1)

def pick_sds(container_path: Path, keyword: str) -> str:
    """Find a subdataset whose name contains keyword (case-insensitive)."""
    with rasterio.open(container_path) as ds:
        for s in ds.subdatasets:
            if keyword.lower() in s.lower():
                return s
    raise RuntimeError(f"Subdataset '{keyword}' not found in {container_path.name}")

def qa_keep_mask(qa: np.ndarray) -> np.ndarray:
    """
    LTDR QA bits (from LTDR docs):
      bit 7: Channels 1-5 valid (1=yes)
      bit 6: Pixel at night (1=yes)
      bit 1: Pixel is cloudy (1=yes)
      bit 0: Pixel is partly cloudy (1=yes)
    Keep: valid==1 and night==0 and cloudy==0 and partly==0
    """
    valid = (qa >> 7) & 1
    night = (qa >> 6) & 1
    cloudy = (qa >> 1) & 1
    partly = (qa >> 0) & 1
    return (valid == 1) & (night == 0) & (cloudy == 0) & (partly == 0)

def main():
    in_dir = Path("data/raw/ltdr_m1_avh09c1")
    out_dir = Path("data/ltdr_albedo_tif")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Match MOD period: 2022–2025 (change if you want)
    YEARS = set([2022, 2023, 2024, 2025])

    # Romania bbox (EPSG:4326). You can tighten it using your nuts3_ro.gpkg bounds later.
    minx, miny, maxx, maxy = 20.0, 43.5, 30.0, 48.5

    files = sorted(in_dir.rglob("*.nc"))
    if not files:
        raise SystemExit(f"No .nc files found under {in_dir.resolve()}")

    # Group files by month
    groups = defaultdict(list)
    for fp in files:
        m = DATE_RE.search(fp.name)
        if not m:
            continue
        y, doy = int(m.group(1)), int(m.group(2))
        if y not in YEARS:
            continue
        yyyymm = doy_to_ymd(y, doy).strftime("%Y%m")
        groups[yyyymm].append(fp)

    if not groups:
        raise SystemExit("No files matched selected years. Check filename pattern includes '.AYYYYDDD.'")

    # Process each month
    for yyyymm, fps in sorted(groups.items()):
        print(f"[{yyyymm}] daily_files={len(fps)}")

        # Find SDS paths once (consistent within product)
        sref_sds = pick_sds(fps[0], "SREFL_CH1")
        qa_sds   = pick_sds(fps[0], "QA")

        # Determine ROI window + metadata from first file
        with rasterio.open(sref_sds) as src0:
            win = from_bounds(minx, miny, maxx, maxy, transform=src0.transform)
            win = win.round_offsets().round_lengths()

            meta = src0.meta.copy()
            meta.update({
                "driver": "GTiff",
                "height": int(win.height),
                "width": int(win.width),
                "transform": rasterio.windows.transform(win, src0.transform),
                "count": 1,
                "dtype": "float32",
                "nodata": -9999.0,
            })

        sum_arr = None
        cnt_arr = None

        for fp in fps:
            sref_sds = pick_sds(fp, "SREFL_CH1")
            qa_sds   = pick_sds(fp, "QA")

            with rasterio.open(sref_sds) as sr, rasterio.open(qa_sds) as qa:
                a = sr.read(1, window=win).astype(np.float32)
                q = qa.read(1, window=win).astype(np.int32)

            # Fill → NaN
            a = np.where(a == -9999, np.nan, a)

            # Scale reflectance: raw / 10000.0 (LTDR)
            a = a / 10000.0

            # Apply QA mask
            keep = qa_keep_mask(q)
            a = np.where(keep, a, np.nan)

            if sum_arr is None:
                sum_arr = np.zeros_like(a, dtype=np.float64)
                cnt_arr = np.zeros_like(a, dtype=np.int32)

            good = np.isfinite(a)
            sum_arr[good] += a[good]
            cnt_arr[good] += 1

        mean = np.full_like(sum_arr, -9999.0, dtype=np.float32)
        good = cnt_arr > 0
        mean[good] = (sum_arr[good] / cnt_arr[good]).astype(np.float32)

        out_path = out_dir / f"albedo_{yyyymm}.tif"
        with rasterio.open(out_path, "w", **meta) as dst:
            dst.write(mean, 1)

        print(f"  wrote {out_path}  (valid_px_mean={float(np.mean(good)):.3f})")

if __name__ == "__main__":
    main()
