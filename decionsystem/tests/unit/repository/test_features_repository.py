import math, numpy as np, pandas as pd, pytest
from unittest.mock import patch
from src.repository.features_repository import FeaturesRepository

class TestNormalizeFraction:
    @pytest.mark.parametrize("val,expected",[
        (None,float("nan")),("abc",float("nan")),(float("nan"),float("nan")),
        (0.0,0.0),(1.0,1.0),(0.5,0.5),(50.0,0.5),(100.0,1.0),(110.0,1.0),(-0.1,0.0),
    ])
    def test_parametrized(self,val,expected):
        r = FeaturesRepository.normalize_fraction(val)
        if math.isnan(expected): assert math.isnan(r)
        else: assert r == pytest.approx(expected,abs=1e-6)
    def test_above_threshold_divides_by_100(self):
        assert FeaturesRepository.normalize_fraction(1.6) == pytest.approx(0.016,abs=1e-6)
    def test_at_threshold_clips_to_1(self):
        assert FeaturesRepository.normalize_fraction(1.5) == pytest.approx(1.0)
    def test_integer_accepted(self):
        assert FeaturesRepository.normalize_fraction(1) == pytest.approx(1.0)

def _make_repo(cloud_df=None,albedo_df=None):
    empty = pd.DataFrame()
    with patch.object(FeaturesRepository,"_load_table",
                      side_effect=[cloud_df if cloud_df is not None else empty,
                                   albedo_df if albedo_df is not None else empty]):
        return FeaturesRepository({"features":{"cloud_csv":"c.csv","albedo_csv":"a.csv"}})

class TestLoadTable:
    def test_missing_file_empty(self): assert _make_repo().cloud_df.empty
    def test_csv_without_nuts_id_empty(self,tmp_path):
        csv=tmp_path/"b.csv"; csv.write_text("col1,col2\n1,2\n")
        repo=FeaturesRepository({"features":{"cloud_csv":str(csv),"albedo_csv":str(csv)}})
        assert repo.cloud_df.empty
    def test_valid_csv_indexed(self,tmp_path):
        csv=tmp_path/"c.csv"; csv.write_text("NUTS_ID,cloud_m01\nRO011,0.3\nRO012,0.5\n")
        repo=FeaturesRepository({"features":{"cloud_csv":str(csv),"albedo_csv":str(csv)}})
        assert "RO011" in repo.cloud_df.index

class TestBuildCountryMonthMeans:
    def test_empty_all_nan(self): repo=_make_repo(); assert all(math.isnan(v) for v in repo.cloud_country_means.values())
    def test_missing_month_col_is_nan(self,cloud_df,albedo_df):
        repo=_make_repo(cloud_df.drop(columns=["cloud_m06"]),albedo_df)
        assert math.isnan(repo.cloud_country_means[6]) and not math.isnan(repo.cloud_country_means[1])
    def test_correct_mean(self,cloud_df,albedo_df):
        repo=_make_repo(cloud_df,albedo_df)
        assert repo.cloud_country_means[1] == pytest.approx(0.40,abs=1e-6)
    def test_all_12_months_present(self,cloud_df,albedo_df):
        repo=_make_repo(cloud_df,albedo_df)
        assert set(repo.cloud_country_means)==set(range(1,13))

class TestGetCountyRow:
    def test_existing_county(self,cloud_df,albedo_df):
        repo=_make_repo(cloud_df,albedo_df)
        row=repo.get_county_row("RO011","cloud")
        assert row is not None and row["cloud_m01"]==pytest.approx(0.30)
    def test_missing_county_none(self,cloud_df,albedo_df):
        assert _make_repo(cloud_df,albedo_df).get_county_row("RO999","cloud") is None
    def test_albedo_type(self,cloud_df,albedo_df):
        row=_make_repo(cloud_df,albedo_df).get_county_row("RO011","albedo")
        assert row is not None and row["albedo_m01"]==pytest.approx(0.15)
    def test_empty_df_returns_none(self):
        assert _make_repo().get_county_row("RO011","cloud") is None
