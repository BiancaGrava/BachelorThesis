import pytest, geopandas as gpd
from shapely.geometry import Point, Polygon
from unittest.mock import patch
from src.repository.geo_repository import GeoRepository

class TestGuessNutsLayer:
    def test_preferred_returned(self,cfg):
        assert GeoRepository(cfg)._guess_nuts_layer("x.gpkg",preferred="L") == "L"
    def test_first_fiona_layer(self,cfg):
        with patch("fiona.listlayers",return_value=["A","B"]):
            assert GeoRepository(cfg)._guess_nuts_layer("x.gpkg") == "A"
    def test_none_when_empty(self,cfg):
        with patch("fiona.listlayers",return_value=[]):
            assert GeoRepository(cfg)._guess_nuts_layer("x.gpkg") is None
    def test_none_on_exception(self,cfg):
        with patch("fiona.listlayers",side_effect=Exception("bad")):
            assert GeoRepository(cfg)._guess_nuts_layer("x.gpkg") is None

class TestSanitizePoints:
    def test_empty_returns_empty(self,cfg):
        r=GeoRepository(cfg)._sanitize_points(gpd.GeoDataFrame(geometry=[],crs="EPSG:4326"))
        assert r.empty
    def test_point_unchanged(self,cfg):
        gdf=gpd.GeoDataFrame(geometry=[Point(24,46)],crs="EPSG:4326")
        r=GeoRepository(cfg)._sanitize_points(gdf)
        assert r.geometry.iloc[0].geom_type=="Point"
    def test_polygon_to_point(self,cfg):
        poly=Polygon([(0,0),(1,0),(1,1),(0,1)])
        gdf=gpd.GeoDataFrame(geometry=[poly],crs="EPSG:4326")
        r=GeoRepository(cfg)._sanitize_points(gdf)
        assert r.geometry.iloc[0].geom_type=="Point"
    def test_null_geometry_dropped(self,cfg):
        gdf=gpd.GeoDataFrame(geometry=[Point(1,1),None],crs="EPSG:4326")
        assert len(GeoRepository(cfg)._sanitize_points(gdf))==1

class TestLoadCounties:
    def test_filters_country_level(self,cfg,two_county_gdf):
        with patch("geopandas.read_file",return_value=two_county_gdf),             patch("fiona.listlayers",return_value=["nuts"]):
            r=GeoRepository(cfg).load_counties()
        assert set(r["NUTS_ID"])=={"RO011","RO012"}
    def test_sets_crs_when_none(self,cfg,two_county_gdf):
        gdf=two_county_gdf.set_crs(None,allow_override=True)
        with patch("geopandas.read_file",return_value=gdf),             patch("fiona.listlayers",return_value=["nuts"]):
            assert GeoRepository(cfg).load_counties().crs is not None
    def test_drops_null_geom(self,cfg,two_county_gdf):
        two_county_gdf.loc[0,"geometry"]=None
        with patch("geopandas.read_file",return_value=two_county_gdf),             patch("fiona.listlayers",return_value=["nuts"]):
            assert len(GeoRepository(cfg).load_counties())==1

class TestLoadLandMap:
    def test_reads_csv(self,cfg,tmp_path):
        csv=tmp_path/"land.csv"; csv.write_text("NUTS_ID,available_ha\nRO011,120.0\nRO012,55.0\n")
        cfg["land"]["available_land_csv"]=str(csv)
        r=GeoRepository(cfg).load_land_map()
        assert r["RO011"]==pytest.approx(120.0) and r["RO012"]==pytest.approx(55.0)
    def test_fallback_to_config_missing_csv(self,cfg):
        cfg["land"]["available_land_csv"]="/nonexistent.csv"
        r=GeoRepository(cfg).load_land_map()
        assert r["RO011"]==pytest.approx(80.0)
    def test_fallback_none_path(self,cfg):
        r=GeoRepository(cfg).load_land_map(); assert "RO011" in r
    def test_empty_counties_config(self,cfg):
        cfg["land"]["available_land_csv"]=None; cfg["counties"]={}
        assert GeoRepository(cfg).load_land_map()=={}

class TestLoadSubstations:
    def test_empty_when_unconfigured(self,cfg):
        r=GeoRepository(cfg).load_substations()
        assert r.empty and r.crs.to_epsg()==4326
    def test_loads_explicit_geojson(self,cfg,two_substation_gdf,tmp_path):
        fp=tmp_path/"subs.geojson"; two_substation_gdf.to_file(fp,driver="GeoJSON")
        cfg["grid_proxy"]["substations_geojson"]=str(fp)
        assert len(GeoRepository(cfg).load_substations())==2
    def test_skips_broken_file(self,cfg,tmp_path):
        bad=tmp_path/"broken.geojson"; bad.write_text("not json")
        cfg["grid_proxy"]["substations_geojson"]=str(bad)
        assert GeoRepository(cfg).load_substations().empty
