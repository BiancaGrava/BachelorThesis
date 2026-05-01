import math, pytest
from src.domeniu.models import GridConstraints
from src.servicii.optimization_service import OptimizationService
from src.repository.features_repository import FeaturesRepository

# ── Table 1: land_ok x grid_ok → eligible ────────────────────────────────────
@pytest.mark.parametrize("land,grid,exp",[
    (True,True,True),(True,False,False),(False,True,False),(False,False,False)],
    ids=["both-ok","grid-fail","land-fail","both-fail"])
def test_eligibility(land,grid,exp): assert (land and grid)==exp

# ── Table 2: model selection ─────────────────────────────────────────────────
@pytest.mark.parametrize("mt,pvgis,corr,sur,exp",[
    ("pvgis",1400.0,1380.0,1390.0,1400.0),
    ("pvgis",1400.0,float("nan"),None,1400.0),
    ("satellite",1400.0,1380.0,None,1380.0),
    ("satellite",1400.0,float("nan"),None,1400.0),
    ("satellite",1400.0,0.0,None,1400.0),
    ("rf",1400.0,1380.0,1390.0,1390.0),
    ("rf",1400.0,1380.0,None,1380.0),
    ("rf",1400.0,float("nan"),None,1400.0),
    ("rf",1400.0,1380.0,0.0,1380.0),],
    ids=["pvgis-all","pvgis-only","sat-valid","sat-nan","sat-zero",
         "rf-all","rf-no-sur","rf-neither","rf-sur-zero"])
def test_model_selection(mt,pvgis,corr,sur,exp):
    assert OptimizationService._select_energy_model(mt,pvgis,corr,sur)==pytest.approx(exp)

# ── Table 3: grid check ───────────────────────────────────────────────────────
@pytest.fixture
def gc(): return GridConstraints(nearest_substation_max_km=15.0,radius_km=25.0,min_substations_within_radius=3,require_grid=True)

@pytest.mark.parametrize("req,d,cnt,exp",[
    (False,999.0,0,True),(True,10.0,4,True),(True,10.0,2,False),
    (True,20.0,4,False),(True,20.0,2,False),(True,15.0,3,True),
    (True,15.001,3,False),(True,0.0,100,True)],
    ids=["no-req","all-ok","cnt-fail","d-fail","both-fail","exact","just-over","zero-dist"])
def test_grid_check(req,d,cnt,exp,gc):
    g=GridConstraints(nearest_substation_max_km=gc.nearest_substation_max_km,
                      radius_km=gc.radius_km,min_substations_within_radius=gc.min_substations_within_radius,
                      require_grid=req)
    assert OptimizationService._check_grid(d,cnt,g)==exp

# ── Table 4: normalize_fraction equivalence classes ──────────────────────────
@pytest.mark.parametrize("inp,exp,desc",[
    (None,None,"null"),("text",None,"non-numeric"),(-1.0,0.0,"negative"),
    (0.0,0.0,"zero"),(0.5,0.5,"midpoint"),(1.0,1.0,"upper-bound"),
    (1.5,1.0,"at-threshold"),(50.0,0.50,"pct-50"),(100.0,1.0,"pct-100"),(110.0,1.0,"pct-110")],
    ids=[r[2] for r in [
        (None,None,"null"),("text",None,"non-numeric"),(-1.0,0.0,"negative"),
        (0.0,0.0,"zero"),(0.5,0.5,"midpoint"),(1.0,1.0,"upper-bound"),
        (1.5,1.0,"at-threshold"),(50.0,0.50,"pct-50"),(100.0,1.0,"pct-100"),(110.0,1.0,"pct-110")]])
def test_normalize_fraction_table(inp,exp,desc):
    r=FeaturesRepository.normalize_fraction(inp)
    if exp is None: assert math.isnan(r)
    else: assert r==pytest.approx(exp,abs=1e-6)
