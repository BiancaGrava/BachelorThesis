import json
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import requests
import yaml
from joblib import dump
from sklearn.ensemble import RandomForestRegressor

def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

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

def pvgis_ey_rep(lat, lon, cfg, session, cache):
    sys = cfg["pv_model"]["system"]
    base = cfg["pv_model"]["api_base"].rstrip("/")
    url = f"{base}/PVcalc"
    key = f"{lat:.5f},{lon:.5f}|pp=1|loss={sys['loss_percent']}|tilt={sys['tilt_deg']}|az={sys['azimuth_deg']}|tech={sys['pvtechchoice']}|mount={sys['mountingplace']}"
    if key in cache:
        return float(cache[key])
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

def main():
    cfg = load_config()
    tcfg = cfg["surrogate_teacher"]

    targets = pd.read_csv(tcfg["out_county_targets_csv"])
    cloud = pd.read_csv(cfg["features"]["cloud_csv"])
    albedo = pd.read_csv(cfg["features"]["albedo_csv"])

    df = targets.merge(cloud, on="NUTS_ID", how="left").merge(albedo, on="NUTS_ID", how="left")

    counties = load_counties(cfg)
    session = requests.Session()

    cache_path = Path(cfg["run"]["cache_dir"]) / "pvgis_rep_cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = load_cache(cache_path)

    rep_Ey = {}
    for _, row in counties.iterrows():
        nuts = row["NUTS_ID"]
        rep = row.geometry.representative_point()
        lat, lon = float(rep.y), float(rep.x)
        try:
            rep_Ey[nuts] = pvgis_ey_rep(lat, lon, cfg, session, cache)
        except Exception:
            rep_Ey[nuts] = np.nan

    save_cache(cache_path, cache)
    df["Ey_rep_kWh_per_kWp"] = df["NUTS_ID"].map(rep_Ey)

    min_ok = int(tcfg.get("min_points_ok", 3))
    df = df[df["n_points"] >= min_ok].copy()
    df = df.dropna(subset=["Ey_mean_kWh_per_kWp", "Ey_rep_kWh_per_kWp"])

    mode = tcfg.get("mode", "factor")
    if mode == "factor":
        df["y"] = df["Ey_mean_kWh_per_kWp"] / df["Ey_rep_kWh_per_kWp"]
    else:
        df["y"] = df["Ey_mean_kWh_per_kWp"]

    feat_cols = ["Ey_rep_kWh_per_kWp", "cloud_mean", "albedo_mean"]
    X = df[feat_cols].fillna(df[feat_cols].mean())
    y = df["y"].values

    model = RandomForestRegressor(
        n_estimators=300,
        random_state=42,
        max_depth=6,
        min_samples_leaf=2,
    )
    model.fit(X, y)

    out_path = Path(tcfg["model_out"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dump({"model": model, "feat_cols": feat_cols, "mode": mode}, out_path)

    print("Trained surrogate. Saved:", out_path.resolve())
    print("Training rows:", len(df))
    print(df[["NUTS_ID","Ey_rep_kWh_per_kWp","Ey_mean_kWh_per_kWp","y"]].head())

if __name__ == "__main__":
    main()
