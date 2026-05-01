import pytest
from src.domeniu.models import EvaluationResult, PanelConfig, GridConstraints, CountyFeatures

class TestPanelConfig:
    def test_area_m2_correct(self):
        pc = PanelConfig(p_stc_kwp=0.45,ground_coverage_ratio=0.45,length_m=2.10,width_m=1.05)
        assert pc.area_m2 == pytest.approx(2.205)
    def test_frozen_immutable(self):
        pc = PanelConfig(p_stc_kwp=0.45,ground_coverage_ratio=0.45,length_m=2.10,width_m=1.05)
        with pytest.raises((AttributeError,TypeError)): pc.p_stc_kwp = 1.0
    def test_area_scales_with_dimensions(self):
        pc = PanelConfig(p_stc_kwp=1.0,ground_coverage_ratio=0.5,length_m=3.0,width_m=2.0)
        assert pc.area_m2 == pytest.approx(6.0)

class TestGridConstraints:
    def test_default_require_grid_is_true(self):
        gc = GridConstraints(nearest_substation_max_km=15.0,radius_km=25.0,min_substations_within_radius=3)
        assert gc.require_grid is True
    def test_frozen_immutable(self):
        gc = GridConstraints(nearest_substation_max_km=15.0,radius_km=25.0,min_substations_within_radius=3)
        with pytest.raises((AttributeError,TypeError)): gc.radius_km = 99.0
    def test_require_grid_can_be_false(self):
        gc = GridConstraints(nearest_substation_max_km=15.0,radius_km=25.0,min_substations_within_radius=3,require_grid=False)
        assert gc.require_grid is False

class TestCountyFeatures:
    def test_instantiation_defaults_none(self):
        cf = CountyFeatures(county_id="RO011",cloud_monthly=[0.3]*12,albedo_monthly=[0.15]*12)
        assert cf.cloud_mean is None and cf.albedo_mean is None
    def test_with_means(self):
        cf = CountyFeatures("RO011",[0.3]*12,[0.15]*12,cloud_mean=0.3,albedo_mean=0.15)
        assert cf.cloud_mean == pytest.approx(0.3)

class TestEvaluationResult:
    def _make(self,**kw):
        d = dict(county_id="RO011",county_name="Bihor",available_ha=100.0,requested_xpv_ha=60.0,
                 effective_ha_used=60.0,missing_ha_to_fit=0.0,land_ok=True,grid_ok=True,eligible=True,
                 nearest_substation_km=8.5,substations_within_radius=4,lat=46.9,lon=22.3,
                 pvgis_Ey_kWh_per_kWp=1400.0,sat_corrected_Ey_kWh_per_kWp=1380.0,
                 surrogate_Ey_kWh_per_kWp=1390.0,Ey_used_kWh_per_kWp=1390.0,
                 panel_kWp=0.45,n_panels_used=12000,annual_energy_kWh=7_506_000.0)
        d.update(kw); return EvaluationResult(**d)
    def test_optional_fields_default_none(self):
        r = self._make(); assert r.cloud_mean is None and r.error is None
    def test_error_field(self):
        r = self._make(error="PVGIS timeout"); assert r.error == "PVGIS timeout"
    def test_ineligible_land(self):
        r = self._make(land_ok=False,eligible=False); assert not r.eligible
    def test_ineligible_grid(self):
        r = self._make(grid_ok=False,eligible=False); assert not r.eligible
