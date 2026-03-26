from pathlib import Path
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.mask import mask
import yaml


def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def guess_nuts_layer(gpkg_path: str, preferred=None):
    layers = gpd.list_layers(gpkg_path)
    if preferred:
        return preferred
    return layers.iloc[0]["name"] if len(layers) else None


def main():
    cfg = load_config("config.yaml")
    tif_path = Path(cfg["corine"]["raster_path"])
    if not tif_path.exists():
        raise FileNotFoundError(tif_path)

    nuts_path = cfg["project"]["nuts_gpkg_path"]
    layer = guess_nuts_layer(nuts_path, cfg["project"].get("nuts_layer"))
    nuts = gpd.read_file(nuts_path, layer=layer)

    if "CNTR_CODE" in nuts.columns:
        nuts = nuts[nuts["CNTR_CODE"] == cfg["project"]["country"]].copy()
    if "LEVL_CODE" in nuts.columns:
        nuts = nuts[nuts["LEVL_CODE"] == cfg["project"]["nuts_level"]].copy()

    # pick one county to inspect (e.g., first row)
    row = nuts.iloc[0]

    with rasterio.open(tif_path) as src:
        nuts = nuts.to_crs(src.crs)
        geom = [nuts.iloc[0].geometry.__geo_interface__]
        data, _ = mask(src, geom, crop=True, filled=True, nodata=src.nodata)
        arr = data[0]

        if src.nodata is not None:
            arr = arr[arr != src.nodata]

        unique = np.unique(arr)
        print("Raster:", tif_path)
        print("CRS:", src.crs)
        print("Nodata:", src.nodata)
        print("Unique values count:", unique.size)
        print("Min/Max:", unique.min(), unique.max())
        print("First 50 unique values:", unique[:50])


if __name__ == "__main__":
    main()