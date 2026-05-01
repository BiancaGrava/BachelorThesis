import math, numpy as np, pandas as pd, pytest
from unittest.mock import MagicMock, patch
from shapely.geometry import Point
from src.domeniu.models import EvaluationResult, PanelConfig, GridConstraints
from src.servicii.optimization_service import OptimizationService

@pytest.fixture
def service(cfg):
    geo=MagicMock(); feat=MagicMock(); pvgis=MagicMock()
    feat.cloud_country_means={m:0.35 for m in range(1,13)}
    feat.albedo_country_means={m:0.18 for m in range(1,13)}
    return OptimizationService(cfg,geo,feat,pvgis)

@pytest.fixture
def panel_cfg():
    return PanelConfig(p_stc_kwp=0.45,ground_coverage_ratio=0.45,length_m=2.10,width_m=1.05)

@pytest.fixture
def grid_cfg():
    return GridConstraints(nearest_substation_max_km=15.0,radius_km=25.0,min_substations_within_radius=3,require_grid=True)

class TestComputePanelCount:
    def test_zero_ha(self,panel_cfg): assert OptimizationService._compute_panel_count(0.0,panel_cfg)==0
    def test_negative_ha(self,panel_cfg): assert OptimizationService._compute_panel_count(-5.0,panel_cfg)==0
    def test_positive_floor(self,panel_cfg):
        n=OptimizationService._compute_panel_count(60.0,panel_cfg)
        assert isinstance(n,int) and n==122448
    def test_small_area_positive(self,panel_cfg):
        assert OptimizationService._compute_panel_count(1.0,panel_cfg)>0

class TestGridMetrics:
    def test_empty_subs(self):
        d,c=OptimizationService._grid_metrics(Point(0,0),[],25000.0)
        assert math.isinf(d) and c==0
    def test_single_sub_distance(self):
        d,c=OptimizationService._grid_metrics(Point(0,0),[Point(10000,0)],25000.0)
        assert d==pytest.approx(10.0,abs=0.01) and c==1
    def test_outside_radius_not_counted(self):
        _,c=OptimizationService._grid_metrics(Point(0,0),[Point(30000,0)],25000.0)
        assert c==0
    def test_min_of_multiple(self):
        d,c=OptimizationService._grid_metrics(Point(0,0),[Point(5000,0),Point(20000,0),Point(10000,0)],25000.0)
        assert d==pytest.approx(5.0,abs=0.01) and c==3

class TestCheckGrid:
    def test_both_met(self,grid_cfg): assert OptimizationService._check_grid(10.0,4,grid_cfg) is True
    def test_distance_fail(self,grid_cfg): assert OptimizationService._check_grid(20.0,4,grid_cfg) is False
    def test_count_fail(self,grid_cfg): assert OptimizationService._check_grid(10.0,2,grid_cfg) is False
    def test_both_fail(self,grid_cfg): assert OptimizationService._check_grid(20.0,1,grid_cfg) is False
    def test_require_false_always_true(self):
        gc=GridConstraints(nearest_substation_max_km=1.0,radius_km=1.0,min_substations_within_radius=100,require_grid=False)
        assert OptimizationService._check_grid(999.0,0,gc) is True
    def test_exact_boundary_passes(self,grid_cfg): assert OptimizationService._check_grid(15.0,3,grid_cfg) is True
    def test_just_over_boundary_fails(self,grid_cfg): assert OptimizationService._check_grid(15.001,3,grid_cfg) is False

class TestSelectEnergyModel:
    def test_rf_uses_surrogate(self): assert OptimizationService._select_energy_model("rf",1400.0,1380.0,1390.0)==pytest.approx(1390.0)
    def test_rf_fallback_satellite(self): assert OptimizationService._select_energy_model("rf",1400.0,1380.0,None)==pytest.approx(1380.0)
    def test_rf_fallback_pvgis(self): assert OptimizationService._select_energy_model("rf",1400.0,float("nan"),None)==pytest.approx(1400.0)
    def test_satellite_uses_corrected(self): assert OptimizationService._select_energy_model("satellite",1400.0,1380.0,None)==pytest.approx(1380.0)
    def test_pvgis_always_base(self): assert OptimizationService._select_energy_model("pvgis",1400.0,1380.0,1390.0)==pytest.approx(1400.0)
    def test_rf_zero_sur_falls_to_satellite(self): assert OptimizationService._select_energy_model("rf",1400.0,1380.0,0.0)==pytest.approx(1380.0)

class TestCorrectionFactors:
    def test_cloud_none_row_returns_1(self,service): assert service._cloud_factor(1,None)==pytest.approx(1.0)
    def test_cloud_missing_col_returns_1(self,service):
        assert service._cloud_factor(1,pd.Series({"cloud_m99":0.3}))==pytest.approx(1.0)
    def test_cloud_clamped_above(self,service):
        service._features.cloud_country_means[1]=0.80
        assert service._cloud_factor(1,pd.Series({"cloud_m01":0.05}))<=1.10
    def test_cloud_clamped_below(self,service):
        service._features.cloud_country_means[1]=0.05
        assert service._cloud_factor(1,pd.Series({"cloud_m01":0.95}))>=0.90
    def test_albedo_none_row_returns_1(self,service): assert service._albedo_factor(1,None,0.05)==pytest.approx(1.0)
    def test_albedo_above_national_above_1(self,service):
        service._features.albedo_country_means[1]=0.15
        assert service._albedo_factor(1,pd.Series({"albedo_m01":0.20}),0.05)>1.0
    def test_albedo_clamped_095_105(self,service):
        service._features.albedo_country_means[1]=0.10
        r=service._albedo_factor(1,pd.Series({"albedo_m01":0.99}),0.05)
        assert 0.95<=r<=1.05

class TestCorrectedAnnual:
    def test_none_em_nan(self,service): assert math.isnan(service._corrected_annual_from_satellite(None,None,None))
    def test_all_nan_em_nan(self,service): assert math.isnan(service._corrected_annual_from_satellite([float("nan")]*12,None,None))
    def test_no_satellite_sums_unchanged(self,service):
        assert service._corrected_annual_from_satellite([100.0]*12,None,None)==pytest.approx(1200.0)

class TestRankResults:
    def _r(self,cid,eligible,energy,Ey,d,ha):
        return EvaluationResult(county_id=cid,county_name=cid,available_ha=ha,requested_xpv_ha=60.0,
            effective_ha_used=min(60.0,ha),missing_ha_to_fit=max(0,60.0-ha),
            land_ok=ha>=60.0,grid_ok=d<=15.0,eligible=eligible,nearest_substation_km=d,
            substations_within_radius=3,lat=46.0,lon=24.0,pvgis_Ey_kWh_per_kWp=Ey,
            sat_corrected_Ey_kWh_per_kWp=None,surrogate_Ey_kWh_per_kWp=None,
            Ey_used_kWh_per_kWp=Ey,panel_kWp=0.45,n_panels_used=10000,annual_energy_kWh=energy)
    def test_eligible_first(self):
        df=OptimizationService._rank_results([self._r("A",False,5e6,1200,20,30),self._r("B",True,3e6,1100,10,80)],"energy","yield","space")
        assert df.iloc[0]["county_id"]=="B"
    def test_energy_desc(self):
        df=OptimizationService._rank_results([self._r("A",True,3e6,1100,5,80),self._r("B",True,7e6,1300,5,80)],"energy","yield","space")
        assert df.iloc[0]["county_id"]=="B"
    def test_grid_asc(self):
        df=OptimizationService._rank_results([self._r("A",True,5e6,1200,12,80),self._r("B",True,5e6,1200,3,80)],"grid","energy","space")
        assert df.iloc[0]["county_id"]=="B"
    def test_returns_dataframe(self):
        df=OptimizationService._rank_results([self._r("A",True,5e6,1200,5,80)],"energy","yield","space")
        assert isinstance(df,pd.DataFrame) and len(df)==1
