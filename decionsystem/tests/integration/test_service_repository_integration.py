import json, math, pandas as pd, pytest, geopandas as gpd
from unittest.mock import patch
from src.repository.geo_repository import GeoRepository
from src.repository.features_repository import FeaturesRepository
from src.repository.pvgis_client import PVGISClient
from src.servicii.optimization_service import OptimizationService

def _write_csv(path,nuts_ids,prefix,val):
    data={"NUTS_ID":nuts_ids}
    for m in range(1,13): data[f"{prefix}_m{m:02d}"]=[val]*len(nuts_ids)
    data[f"{prefix}_mean"]=[val]*len(nuts_ids)
    pd.DataFrame(data).to_csv(path,index=False)

@pytest.fixture
def tmp_cfg(tmp_path,cfg):
    cloud=tmp_path/"cloud.csv"; albedo=tmp_path/"albedo.csv"; land=tmp_path/"land.csv"
    _write_csv(cloud,["RO011","RO012"],"cloud",0.30)
    _write_csv(albedo,["RO011","RO012"],"albedo",0.15)
    pd.DataFrame({"NUTS_ID":["RO011","RO012"],"available_ha":[120.0,45.0]}).to_csv(land,index=False)
    cfg["features"]["cloud_csv"]=str(cloud); cfg["features"]["albedo_csv"]=str(albedo)
    cfg["land"]["available_land_csv"]=str(land); cfg["run"]["cache_dir"]=str(tmp_path)
    return cfg

@pytest.fixture
def wired(tmp_cfg,two_county_gdf,two_substation_gdf):
    geo=GeoRepository(tmp_cfg); feat=FeaturesRepository(tmp_cfg); pvgis=PVGISClient(tmp_cfg)
    for lat,lon in [(46.5,24.5),(45.5,26.5)]:
        pvgis._cache[pvgis._build_cache_key(lat,lon)]={"Ey":1400.0,"Em":[116.0]*12}
    svc=OptimizationService(tmp_cfg,geo,feat,pvgis)
    svc._geo.load_counties=lambda:two_county_gdf.to_crs("EPSG:3035")
    svc._geo.load_substations=lambda:two_substation_gdf.to_crs("EPSG:3035")
    return svc

class TestFeaturesContract:
    def test_cloud_means_precomputed(self,tmp_cfg):
        repo=FeaturesRepository(tmp_cfg)
        assert all(not math.isnan(v) for v in repo.cloud_country_means.values())
        assert repo.cloud_country_means[1]==pytest.approx(0.30)
    def test_get_county_row_all_monthly_cols(self,tmp_cfg):
        row=FeaturesRepository(tmp_cfg).get_county_row("RO011","cloud")
        assert all(f"cloud_m{m:02d}" in row.index for m in range(1,13))

class TestGeoContract:
    def test_land_map_values(self,tmp_cfg):
        land=GeoRepository(tmp_cfg).load_land_map()
        assert land["RO011"]==pytest.approx(120.0) and land["RO012"]==pytest.approx(45.0)

class TestPVGISCacheContract:
    def test_cache_hit_no_network(self,tmp_cfg):
        c=PVGISClient(tmp_cfg); key=c._build_cache_key(46.0,24.0)
        c._cache[key]={"Ey":1350.0,"Em":[112.0]*12}
        with patch.object(c._session,"get") as m: Ey,_=c.get_pvcalc(46.0,24.0)
        m.assert_not_called(); assert Ey==pytest.approx(1350.0)
    def test_cache_persists_across_instances(self,tmp_cfg):
        c1=PVGISClient(tmp_cfg); key=c1._build_cache_key(46.0,24.0)
        c1._cache[key]={"Ey":1111.0,"Em":[92.0]*12}; c1.save_cache()
        c2=PVGISClient(tmp_cfg)
        assert key in c2._cache and c2._cache[key]["Ey"]==pytest.approx(1111.0)

class TestRunEvaluationEndToEnd:
    def _run(self,svc,mt="pvgis",p1="energy",p2="yield",p3="space"):
        return svc.run_evaluation(60.0,mt,p1,p2,p3)
    def test_two_rows(self,wired): assert len(self._run(wired))==2
    def test_required_columns(self,wired):
        assert {"county_id","eligible","annual_energy_kWh","Ey_used_kWh_per_kWp","nearest_substation_km"}.issubset(set(self._run(wired).columns))
    def test_ey_positive(self,wired):
        assert (self._run(wired)["Ey_used_kWh_per_kWp"].dropna()>0).all()
    def test_eligible_before_ineligible(self,wired):
        df=self._run(wired)
        eli=df[df["eligible"]==True]; ineli=df[df["eligible"]==False]
        if len(eli)>0 and len(ineli)>0:
            assert eli.index.min()<ineli.index.min()
    def test_energy_priority_sorts_descending(self,wired):
        df=self._run(wired,p1="energy")
        elig=df[df["eligible"]==True].reset_index(drop=True)
        if len(elig)>=2:
            assert elig["annual_energy_kWh"].iloc[0]>=elig["annual_energy_kWh"].iloc[1]
