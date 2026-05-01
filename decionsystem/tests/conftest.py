import math, numpy as np, pandas as pd, pytest
import geopandas as gpd
from shapely.geometry import Point, Polygon

@pytest.fixture
def cfg():
    return {
        "project": {"nuts_gpkg_path": "fake/path.gpkg","nuts_layer": None,
                    "country": "RO","nuts_level": 3,"crs_area_distance": "EPSG:3035"},
        "grid_proxy": {"substations_geojson": None,"substations_glob": None},
        "land": {"available_land_csv": None},
        "counties": {"RO011": {"available_ha": 80.0},"RO012": {"available_ha": 40.0}},
        "features": {"cloud_csv": "fake/cloud.csv","albedo_csv": "fake/albedo.csv"},
        "run": {"cache_dir": "/tmp/resol_test_cache","pvgis_cache_file": "pvgis_cache.json"},
        "pv_model": {
            "api_base": "https://re.jrc.ec.europa.eu/api/v5_2",
            "fallback_Ey_kWh_per_kWp": 1300,
            "system": {"loss_percent": 14,"tilt_deg": 35,"azimuth_deg": 0,
                       "pvtechchoice": "crystSi","mountingplace": "free"},
        },
        "panel": {"p_stc_kwp": 0.45,"ground_coverage_ratio": 0.45,"length_m": 2.10,"width_m": 1.05},
        "constraints": {"grid": {"nearest_substation_max_km": 15.0,"radius_km": 25.0,
                                  "min_substations_within_radius": 3,"require_grid": True}},
        "satellite_correction": {"gamma_albedo": 0.05},
        "surrogate_teacher": {"enabled": False,"model_out": "models/pvgis_surrogate.joblib"},
    }

@pytest.fixture
def two_county_gdf():
    poly1 = Polygon([(24.0,46.0),(25.0,46.0),(25.0,47.0),(24.0,47.0)])
    poly2 = Polygon([(26.0,45.0),(27.0,45.0),(27.0,46.0),(26.0,46.0)])
    return gpd.GeoDataFrame(
        {"NUTS_ID":["RO011","RO012"],"NAME_LATN":["Bihor","Cluj"],
         "CNTR_CODE":["RO","RO"],"LEVL_CODE":[3,3]},
        geometry=[poly1,poly2], crs="EPSG:4326")

@pytest.fixture
def two_substation_gdf():
    return gpd.GeoDataFrame(geometry=[Point(24.5,46.5),Point(26.5,45.5)], crs="EPSG:4326")

@pytest.fixture
def cloud_df():
    data = {"NUTS_ID":["RO011","RO012"]}
    for m in range(1,13): data[f"cloud_m{m:02d}"] = [0.30,0.50]
    data["cloud_mean"] = [0.35,0.45]
    return pd.DataFrame(data).set_index("NUTS_ID")

@pytest.fixture
def albedo_df():
    data = {"NUTS_ID":["RO011","RO012"]}
    for m in range(1,13): data[f"albedo_m{m:02d}"] = [0.15,0.20]
    data["albedo_mean"] = [0.16,0.19]
    return pd.DataFrame(data).set_index("NUTS_ID")
