import json, time, math, random
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import requests
import yaml

def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)
    return p

def load_cache(path: Path):
    return json.loads(path.read_text()) if path.exists() else {}

def save_cache(path: Path, cache: dict):
    path.write_text(json.dumps(cache, indent=2))

def guess_nuts_layer(gpkg_path: str, preferred=None):
    layers = gpd.list_layers(gpkg_path)
    if preferred:
        return preferred
    return layers.iloc[0]["name"] if len(layers) else None

def load_counties(cfg):
    gpkg_path = cfg["project"]["nuts_gpkg_path"]
    layer = guess_nuts_layer(gpkg_path, cfg["project"].get("nuts_layer"))
    gdf = gpd.read_file(gpkg_path, layer=layer)
    if "CNTR_CODE" in gdf.columns:
        gdf = gdf[gdf["CNTR_CODE"] == cfg["project"]["country"]].copy()
    if "LEVL_CODE" in gdf.columns:
        gdf = gdf[gdf["LEVL_CODE"] == cfg["project"]["nuts_level"]].copy()
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs("EPSG:4326")

def pvgis_pvcalc(lat, lon, cfg, session, cache):
    sys = cfg["pv_model"]["system"]
    base = cfg["pv_model"]["api_base"].rstrip("/")
    url = f"{base}/PVcalc"
    key = f"{lat:.5f},{lon:.5f}|pp=1|loss={sys['loss_percent']}|tilt={sys['tilt_deg']}|az={sys['azimuth_deg']}|tech={sys['pvtechchoice']}|mount={sys['mountingplace']}"
    if key in cache:
        return cache[key]
    params = {
        "lat": lat, "lon": lon,
        "peakpower": 1.0,
        "loss": sys["loss_percent"],
        "angle": sys["tilt_deg"],
        "aspect": sys["azimuth_deg"],
        "pvtechchoice": sys["pvtechchoice"],
        "mountingplace": sys["mountingplace"],
        "outputformat": "json",
    }
    r = session.get(url, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    Ey = float(data["outputs"]["totals"]["fixed"]["E_y"])
    cache[key] = Ey
    return Ey

def random_points_in_polygon(poly, k, rng):
    minx, miny, maxx, maxy = poly.bounds
    pts = []
    tries = 0
    while len(pts) < k and tries < k * 2000:
        x = rng.uniform(minx, maxx)
        y = rng.uniform(miny, maxy)
        p = gpd.points_from_xy([x], [y])[0]
        if poly.contains(p):
            pts.append((y, x))  # lat, lon
        tries += 1
    return pts

def main():
    cfg = load_config()
    tcfg = cfg["surrogate_teacher"]

    counties = load_counties(cfg)
    k = int(tcfg["k_points_per_county"])
    seed = int(tcfg.get("seed", 42))
    rng = random.Random(seed)

    cache_dir = ensure_dir(Path(cfg["run"]["cache_dir"]))
    cache_path = cache_dir / "pvgis_teacher_cache.json"
    cache = load_cache(cache_path)

    out_targets = Path(tcfg["out_county_targets_csv"])
    ensure_dir(out_targets.parent)

    session = requests.Session()
    sleep_s = float(cfg["run"].get("request_sleep_s", 0.1))  # be gentle

    rows = []
    for _, row in counties.iterrows():
        nuts = row["NUTS_ID"]
        poly = row.geometry
        pts = random_points_in_polygon(poly, k, rng)

        Ey_vals = []
        for lat, lon in pts:
            try:
                Ey = pvgis_pvcalc(lat, lon, cfg, session, cache)
                Ey_vals.append(Ey)
            except Exception:
                continue
            if sleep_s > 0:
                time.sleep(sleep_s)

        if len(Ey_vals) == 0:
            Ey_mean = np.nan
        else:
            Ey_mean = float(np.mean(Ey_vals))

        rows.append({
            "NUTS_ID": nuts,
            "n_points": len(Ey_vals),
            "Ey_mean_kWh_per_kWp": Ey_mean,
        })

    save_cache(cache_path, cache)
    df = pd.DataFrame(rows)
    df.to_csv(out_targets, index=False)
    print("Saved:", out_targets.resolve())
    print(df.describe(include="all"))

if __name__ == "__main__":
    main()
