from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask
import yaml
from dbfread import DBF


def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def guess_nuts_layer(gpkg_path: str, preferred=None):
    layers = gpd.list_layers(gpkg_path)
    if preferred:
        return preferred
    return layers.iloc[0]["name"] if len(layers) else None


def find_vat_dbf(tif_path: Path) -> Path:
    """
    Your download uses a sidecar file named like:
      U2018_CLC2018_V2020_20u1.tif.vat.dbf
    So we build that exact filename.
    """
    vat = Path(str(tif_path) + ".vat.dbf")
    if vat.exists():
        return vat

    candidates = list(tif_path.parent.glob("*.vat.dbf"))
    if candidates:
        return candidates[0]

    raise FileNotFoundError(
        f"VAT DBF not found next to raster.\n"
        f"Expected: {vat}\n"
        f"Or any '*.vat.dbf' in {tif_path.parent}"
    )


def load_vat_mapping(vat_dbf: Path):
    """
    Build mapping: raster_index_value -> CORINE_code
    Field names vary, so we detect columns automatically.

    Typical patterns:
      - raster index value column: VALUE / GRID_CODE / DN
      - CLC code column: CODE_18 / CLC_CODE / CODE
    """
    table = DBF(str(vat_dbf), load=True)
    fields = table.field_names
    fields_lower = [f.lower() for f in fields]

    def pick_col(names):
        for n in names:
            if n.lower() in fields_lower:
                return fields[fields_lower.index(n.lower())]
        return None

    value_col = pick_col(["VALUE", "GRID_CODE", "DN"])
    code_col = pick_col(["CODE_18", "CLC_CODE", "CODE", "CLASS"])

    if value_col is None or code_col is None:
        raise RuntimeError(
            f"Could not detect VAT columns in {vat_dbf}.\n"
            f"Fields found: {fields}\n"
            f"Please paste these fields here and I’ll adjust the detector."
        )

    mapping = {}
    for r in table:
        v = int(r[value_col])
        try:
            c = int(str(r[code_col]).strip())
        except ValueError:
            continue
        mapping[v] = c

    if not mapping:
        raise RuntimeError(f"Parsed VAT mapping is empty. Fields: {fields}")

    return mapping, value_col, code_col, fields


def main():
    cfg = load_config("config.yaml")

    tif_path = Path(cfg["corine"]["raster_path"])
    allowed_codes = set(cfg["corine"]["allowed_codes"])

    if not tif_path.exists():
        raise FileNotFoundError(f"CORINE raster not found: {tif_path}")

    vat_dbf = find_vat_dbf(tif_path)
    mapping, value_col, code_col, fields = load_vat_mapping(vat_dbf)

    allowed_indices = {idx for idx, code in mapping.items() if code in allowed_codes}

    print(f"Using CORINE raster: {tif_path}")
    print(f"Using VAT table: {vat_dbf}")
    print(f"VAT fields: {fields}")
    print(f"Mapping columns: {value_col} -> {code_col}")
    print(f"Allowed CORINE codes: {sorted(list(allowed_codes))}")
    print(f"Allowed raster indices derived from VAT: {sorted(list(allowed_indices))[:30]} ... (total {len(allowed_indices)})")

    nuts_path = cfg["project"]["nuts_gpkg_path"]
    layer = guess_nuts_layer(nuts_path, cfg["project"].get("nuts_layer"))
    nuts = gpd.read_file(nuts_path, layer=layer)

    if "CNTR_CODE" in nuts.columns:
        nuts = nuts[nuts["CNTR_CODE"] == cfg["project"]["country"]].copy()
    if "LEVL_CODE" in nuts.columns:
        nuts = nuts[nuts["LEVL_CODE"] == cfg["project"]["nuts_level"]].copy()

    if "NUTS_ID" not in nuts.columns:
        raise RuntimeError("Expected NUTS_ID column in your NUTS layer.")

    nuts = nuts[nuts.geometry.notna() & ~nuts.geometry.is_empty].copy()

    out_dir = Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "available_land_by_nuts3.csv"

    with rasterio.open(tif_path) as src:
        nuts = nuts.to_crs(src.crs)

        pixel_area_ha = (abs(src.transform.a) * abs(src.transform.e)) / 10000.0
        print(f"Raster CRS: {src.crs}")
        print(f"Nodata: {src.nodata}")
        print(f"Pixel area (ha): {pixel_area_ha:.3f}")

        rows = []
        for _, row in nuts.iterrows():
            geom = [row.geometry.__geo_interface__]
            data, _ = mask(src, geom, crop=True, filled=True, nodata=src.nodata)
            arr = data[0]

            if src.nodata is not None:
                arr = arr[arr != src.nodata]

            eligible_pixels = int(np.isin(arr, list(allowed_indices)).sum()) if arr.size else 0
            available_ha = float(eligible_pixels * pixel_area_ha)

            rows.append({
                "NUTS_ID": row["NUTS_ID"],
                "available_ha": available_ha,
                "eligible_pixels": eligible_pixels,
                "pixel_area_ha": float(pixel_area_ha)
            })

    df = pd.DataFrame(rows).sort_values("NUTS_ID")
    df.to_csv(out_csv, index=False, encoding="utf-8")

    print(f"\nSaved: {out_csv.resolve()}")
    print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
