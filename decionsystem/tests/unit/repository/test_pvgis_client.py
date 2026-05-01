import json, math, pytest
from unittest.mock import patch, MagicMock
from src.repository.pvgis_client import PVGISClient

@pytest.fixture
def client(cfg,tmp_path):
    cfg["run"]["cache_dir"]=str(tmp_path); return PVGISClient(cfg)

@pytest.fixture
def pvgis_response():
    return {"outputs":{"totals":{"fixed":{"E_y":1450.0}},
            "monthly":{"fixed":[{"month":m,"E_m":100.0+m} for m in range(1,13)]}}}

class TestCacheKey:
    def test_same_inputs_same_key(self,client):
        assert client._build_cache_key(46.0,24.0)==client._build_cache_key(46.0,24.0)
    def test_different_lat_different_key(self,client):
        assert client._build_cache_key(46.0,24.0)!=client._build_cache_key(47.0,24.0)
    def test_key_contains_coords(self,client):
        k=client._build_cache_key(46.12345,24.98765)
        assert "46.12345" in k and "24.98765" in k

class TestGetPvcalc:
    def test_cache_hit_no_http(self,client):
        key=client._build_cache_key(46.0,24.0)
        client._cache[key]={"Ey":1400.0,"Em":[100.0]*12}
        with patch.object(client,"_fetch") as m:
            Ey,Em=client.get_pvcalc(46.0,24.0)
        m.assert_not_called(); assert Ey==pytest.approx(1400.0)
    def test_cache_miss_stores_result(self,client,pvgis_response):
        with patch.object(client,"_fetch",return_value=pvgis_response):
            Ey,Em=client.get_pvcalc(46.0,24.0)
        assert Ey==pytest.approx(1450.0) and len(Em)==12
        assert client._build_cache_key(46.0,24.0) in client._cache
    def test_monthly_values_correct(self,client,pvgis_response):
        with patch.object(client,"_fetch",return_value=pvgis_response):
            _,Em=client.get_pvcalc(46.0,24.0)
        assert Em[0]==pytest.approx(101.0) and Em[11]==pytest.approx(112.0)
    def test_missing_monthly_all_nan(self,client):
        resp={"outputs":{"totals":{"fixed":{"E_y":1200.0}},"monthly":{}}}
        with patch.object(client,"_fetch",return_value=resp):
            _,Em=client.get_pvcalc(46.0,24.0)
        assert all(math.isnan(v) for v in Em)

class TestSaveCache:
    def test_save_and_reload(self,client,pvgis_response):
        with patch.object(client,"_fetch",return_value=pvgis_response):
            client.get_pvcalc(46.0,24.0)
        client.save_cache()
        assert client._cache_path.exists()
        assert len(json.loads(client._cache_path.read_text()))==1
    def test_empty_cache_saves_empty_json(self,client):
        client.save_cache()
        assert json.loads(client._cache_path.read_text())=={}

class TestFetch:
    def test_raises_on_http_error(self,client):
        mock_resp=MagicMock()
        mock_resp.raise_for_status.side_effect=Exception("500")
        with patch.object(client._session,"get",return_value=mock_resp):
            with pytest.raises(Exception,match="500"): client._fetch(46.0,24.0)
