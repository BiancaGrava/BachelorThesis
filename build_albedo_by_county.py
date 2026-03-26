#!/usr/bin/env python3
import re
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask
import yaml

DATE_RE = re.compile(r"((?:19|20)\d{2})[_-]?(0[1-9]|1[0-2])")

def parse_yyyymm(path: Path) -> str:
    m = DATE_RE.search(path.name)
    if not m:
        raise ValueError(f"Cannot find YYYYMM in filename: {path.name}")
    return f"{m.group(1)}{m.group(2)}"

def county_means_for_raster(raster_path: Path, counties: gpd.GeoDataFrame, id_col="NUTS_ID"):
    out = []
    with rasterio.open(raster_path) as src:
        c = counties.to_crs(src.crs) if counties.crs != src.crs else counties
        for _, row in c.iterrows():
            geom = [row.geometry]
            try:
                data, _ = mask(src, geom, crop=True, filled=False)
                arr = data[0].astype("float64")

                if src.nodata is not None:
                    arr = np.where(arr == src.nodata, np.nan, arr)

                arr = np.where(np.ma.getmaskarray(data[0]), np.nan, arr)
                mean = float(np.nanmean(arr)) if np.isfinite(arr).any() else np.nan
            except Exception:
                mean = np.nan

            out.append((row[id_col], mean))
    return out

def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    cfg = load_config("config.yaml")

    gpkg = cfg["project"]["nuts_gpkg_path"]
    alb_dir = Path(cfg["features_build"]["albedo_tif_dir"])
    out_csv = Path(cfg["features"]["albedo_csv"])
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    counties = gpd.read_file(gpkg)
    if counties.crs is None:
        counties = counties.set_crs("EPSG:4326")

    records = []
    for tif in sorted(alb_dir.glob("*.tif")):
        yyyymm = parse_yyyymm(tif)
        month = int(yyyymm[4:6])

        pairs = county_means_for_raster(tif, counties)
        for nuts_id, val in pairs:
            records.append({"NUTS_ID": nuts_id, "month": month, "value": val})

    df = pd.DataFrame(records).dropna(subset=["value"])
    pivot = df.groupby(["NUTS_ID", "month"])["value"].mean().unstack("month")
    pivot = pivot.reindex(columns=range(1, 13))

    out = pd.DataFrame({"NUTS_ID": pivot.index})
    out["albedo_mean"] = pivot.mean(axis=1, skipna=True).values
    for m in range(1, 13):
        out[f"albedo_m{m:02d}"] = pivot[m].values

    out.to_csv(out_csv, index=False, encoding="utf-8")
    print(f"Saved: {out_csv.resolve()} (rows={len(out)})")

if __name__ == "__main__":
    main()