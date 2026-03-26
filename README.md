# BachelorThesis
REgional SOLutions - optimizing regional position based on solar forecasting


*Methodology: Data, Acquisition, Preprocessing, Experiments, and Validation*
1. Data sources and what each contributes
1.1 PVGIS (Photovoltaic Geographical Information System) – baseline PV yield (teacher & baseline)
PVGIS provides solar radiation and PV system performance estimates for any location, accessible through a non interactive API with tool endpoints such as PVcalc, seriescalc, and tmy. 
In this work, PVGIS is used in two roles: [fiona.readthedocs.io], [github.com]
1.	as the baseline PV yield estimate at each county’s representative point (rep point PVGIS), and
2.	as a teacher model to generate pseudo ground truth county targets by averaging PVGIS results over multiple sampled points inside each county. [fiona.readthedocs.io], [github.com]
PVGIS APIs are subject to rate limits (30 calls/second per IP), and overload responses (e.g., HTTP 529) may occur when the server is busy; therefore caching and request throttling are necessary for reproducible runs. [fiona.readthedocs.io]

1.2 MODIS MOD08_M3 – monthly gridded cloud fraction (satellite feature)
MOD08_M3 is a monthly Level 3 gridded MODIS atmosphere product with a global 1°×1° latitude–longitude grid (360×180 pixels). 
From this product, monthly cloud fraction is extracted as a county level feature (after reprojection/subsetting and aggregation). [pyeplan.sps-lab.org] [pyeplan.sps-lab.org], [geopandas.org]
The key dataset used is the cloud fraction SDS (e.g., Cloud_Fraction_Mean_Mean or Cloud_Fraction_Day_Mean_Mean). In MOD08 band definitions, cloud fraction values are stored as integers 0–10000 with scale factor 10−410^{-4}10−4 (i.e., 0–1 fraction after scaling). [geopandas.org]

1.3 LTDR (AVHRR) M1_AVH09C1 – daily surface reflectance, aggregated to monthly “albedo proxy”
The Long Term Data Record (LTDR) project distributes daily surface reflectance products such as M1_AVH09C1, containing BRDF corrected surface reflectance channels and QA information. 
From M1_AVH09C1, a monthly mean surface reflectance proxy (called “albedo proxy” in this thesis) is computed over Romania, then aggregated to county features. The LTDR documentation specifies that surface reflectance channels (e.g., SREFL_CH1) are stored as 2 byte integers scaled by 10410^4104 with fill value −9999-9999−9999.
The QA bitfield provides flags for valid pixels, night, and cloudiness (cloudy/partly cloudy), enabling quality filtering before computing monthly means. [uoradea-my...epoint.com], [github.com]

1.4 Romanian county boundaries (NUTS 3)
Romanian counties are represented using a NUTS 3 GeoPackage layer (nuts3_ro.gpkg), used to:
•	compute county representative points (for PVGIS calls), and
•	spatially aggregate raster features (cloud/albedo) to county level climatologies.

1.5 Grid proxy: electrical substations (optional constraint layer)
Substation point GeoJSONs are used as a grid proximity proxy, computing nearest distance and count within a radius. This is a feasibility filter (constraints) rather than a yield predictor.

2. Data acquisition (how data was obtained)
2.1 PVGIS API acquisition
PVGIS results are requested via the non interactive API endpoint format:
https://re.jrc.ec.europa.eu/api/v5_3/{tool_name}?param=value...\texttt{https://re.jrc.ec.europa.eu/api/v5\_3/\{tool\_name\}?param=value...}https://re.jrc.ec.europa.eu/api/v5_3/{tool_name}?param=value...
where tool_name includes PVcalc among other tools. [fiona.readthedocs.io]
To avoid exceeding PVGIS request limits (429) and overload (529), calls are throttled and cached locally. [fiona.readthedocs.io]

2.2 MOD08_M3 acquisition (LAADS DAAC)
MOD08_M3 files are obtained from LAADS DAAC (Collection 6.1), which stores monthly gridded HDF files. MOD08_M3 is documented as a monthly gridded product stored in HDF format and derived from daily global joint products. [pyeplan.sps-lab.org]

2.3 M1_AVH09C1 acquisition (LAADS DAAC / LTDR)
M1_AVH09C1 daily products (in NetCDF or HDF container formats depending on distribution) are acquired from the LAADS DAAC LTDR archive. The product provides daily surface reflectance and QA needed for monthly compositing. [uoradea-my...epoint.com], [github.com]

3. Preprocessing and feature construction (detailed)
3.1 MOD08_M3 cloud fraction preprocessing
1.	Subdataset selection: the SDS Cloud_Fraction_Mean_Mean (or daytime equivalent) is selected. [geopandas.org]
2.	Scaling: raw integer values are converted to fractions:
CF=CFraw10000CF = \frac{CF_{raw}}{10000}CF=10000CFraw
consistent with MOD08 cloud fraction scaling definitions (0–10000 with scale 0.0001). 
3) GeoTIFF export: the cloud fraction layer is exported to GeoTIFF (EPSG:4326) for each month.
4) County aggregation: each monthly raster is spatially aggregated to county polygons (mean over pixels intersecting each county).
5) Monthly climatology features: per county, store cloud_m01…cloud_m12 and cloud_mean (mean over available months/years). [geopandas.org]
Note on resolution and interpretation: MOD08_M3 is 1°×1° (~100 km), so county level aggregation is interpreted as a coarse climatological indicator rather than a site scale cloud measurement. [pyeplan.sps-lab.org]

3.2 LTDR M1_AVH09C1 preprocessing (daily → monthly mean)
1.	SDS selection: SREFL_CH1 (and QA) are extracted for each daily file. [uoradea-my...epoint.com]
2.	Scaling and nodata: reflectance is converted to physical reflectance:
SR={SRraw10000if SRraw≠−9999NaNif SRraw=−9999SR = \begin{cases} \frac{SR_{raw}}{10000} & \text{if } SR_{raw} \neq -9999 \\ \text{NaN} & \text{if } SR_{raw} = -9999 \end{cases}SR={10000SRrawNaNif SRraw=−9999if SRraw=−9999
as specified for LTDR surface reflectance (scaled by 10410^4104, fill −9999-9999−9999).
3) QA masking: pixels are kept only when QA indicates valid daytime non cloudy observations. The QA field definition includes flags such as night, cloudy, partly cloudy, and validity.
4) Monthly compositing (mean): for each month mmm, compute:
ALB_proxym=∑SRiNvalidALB\_proxy_m = \frac{\sum SR_{i}}{N_{valid}}ALB_proxym=Nvalid∑SRi
over all valid pixels/days in that month within the Romania bounding box.
5) GeoTIFF export: write monthly GeoTIFF albedo_YYYYMM.tif (EPSG:4326).
6) County aggregation: spatially aggregate monthly rasters to county polygons → features albedo_m01…albedo_m12, albedo_mean.
Interpretation: the LTDR reflectance product is a consistent climate record (daily surface reflectance), making monthly means meaningful for spatial comparison, while QA filtering reduces contamination from clouds/night. [uoradea-my...epoint.com]

3.3 PVGIS preprocessing (rep point PV yield)
For each county, a representative point is computed from the county polygon, transformed to WGS84 (EPSG:4326), then sent to PVGIS PVcalc. PVGIS returns:
•	annual yield EyE_yEy (kWh/kWp/year) and
•	monthly yields EmE_mEm (kWh/kWp/month). [fiona.readthedocs.io], [github.com]
Caching is used to avoid repeated calls for the same lat/lon and system parameters, consistent with PVGIS API usage constraints. [fiona.readthedocs.io]

4. Formulas used in the implementation
4.1 PVGIS annual yield and plant energy calculation
PVGIS outputs annual specific yield:
Ey  [kWh/kWp/year]E_y \; [\text{kWh/kWp/year}]Ey[kWh/kWp/year]
For a plant composed of NNN panels of size PpanelP_{panel}Ppanel (kWp/panel), the annual energy is:
Eannual  [kWh]=Ey⋅Ppanel⋅NE_{annual}\;[\text{kWh}] = E_y \cdot P_{panel} \cdot NEannual[kWh]=Ey⋅Ppanel⋅N
Panels count is derived from available land and ground coverage ratio (GCR):
•	area available in m²:
A=10000⋅available_haA = 10000 \cdot \text{available\_ha}A=10000⋅available_ha
•	effective PV-covered area:
APV=A⋅GCRA_{PV} = A \cdot GCRAPV=A⋅GCR
•	panel footprint:
Apanel=Lpanel⋅WpanelA_{panel} = L_{panel} \cdot W_{panel}Apanel=Lpanel⋅Wpanel
•	number of panels:
N=⌊APVApanel⌋N = \left\lfloor \frac{A_{PV}}{A_{panel}} \right\rfloorN=⌊ApanelAPV⌋

4.2 Satellite heuristic correction (monthly)
The code applies a conservative month-wise correction to PVGIS monthly energy EmE_mEm:
Cloud factor (relative clear-sky fraction):
fcloud,m=1−CFcounty,m1−CFμ,mf_{cloud,m} = \frac{1 - CF_{county,m}}{1 - CF_{\mu,m}}fcloud,m=1−CFμ,m1−CFcounty,m
where CFμ,mCF_{\mu,m}CFμ,m is the country wide mean cloud fraction for month mmm. Cloud fraction is taken from MOD08_M3 monthly cloud fraction SDS. [geopandas.org], [pyeplan.sps-lab.org]
To prevent overcorrection, the factor is clamped:
fcloud,m←clip(fcloud,m,0.80,1.20)f_{cloud,m} \leftarrow \text{clip}(f_{cloud,m}, 0.80, 1.20)fcloud,m←clip(fcloud,m,0.80,1.20)
Albedo proxy factor (small adjustment):
falb,m=1+γ (ALBcounty,m−ALBμ,m)f_{alb,m} = 1 + \gamma\,(ALB_{county,m} - ALB_{\mu,m})falb,m=1+γ(ALBcounty,m−ALBμ,m)
with conservative clamping:
falb,m←clip(falb,m,0.95,1.05)f_{alb,m} \leftarrow \text{clip}(f_{alb,m}, 0.95, 1.05)falb,m←clip(falb,m,0.95,1.05)
Corrected monthly energy:
Em′=Em⋅fcloud,m⋅falb,mE'_{m} = E_{m} \cdot f_{cloud,m} \cdot f_{alb,m}Em′=Em⋅fcloud,m⋅falb,m
and corrected annual yield is:
Ey′=∑m=112Em′E'_y = \sum_{m=1}^{12} E'_mEy′=m=1∑12Em′

4.3 PVGIS teacher targets (county mean PVGIS)
To create a county “teacher” target, KKK random points are sampled inside each county polygon and PVGIS PVcalc is called at each point:
Ecountyteacher=1K∑i=1KEPVGIS(lati,loni)E^{teacher}_{county} = \frac{1}{K}\sum_{i=1}^{K} E^{PVGIS}(lat_i,lon_i)Ecountyteacher=K1i=1∑KEPVGIS(lati,loni)
PVGIS supports non interactive API access; rate limits and overload conditions justify caching and throttling during this step. [fiona.readthedocs.io]

4.4 Trained surrogate model (teacher–student)
A supervised model is trained to approximate the teacher target from a small feature vector. Two common modes:
Factor mode (used in this thesis):
y=EcountyteacherErepPVGISy = \frac{E^{teacher}_{county}}{E^{PVGIS}_{rep}}y=ErepPVGISEcountyteacher
The model predicts y^\hat{y}y^, and county yield becomes:
Ecountysurrogate=ErepPVGIS⋅y^E^{surrogate}_{county} = E^{PVGIS}_{rep} \cdot \hat{y}Ecountysurrogate=ErepPVGIS⋅y^
This keeps the pipeline structure unchanged while replacing the yield source with a learned correction consistent with PVGIS as teacher. [fiona.readthedocs.io], [github.com]

5. Experiments performed (what each experiment did)
Experiment 1 — PVGIS baseline ranking
•	For each county rep-point, call PVGIS PVcalc to obtain EyE_yEy. [fiona.readthedocs.io], [github.com]
•	Compute panel count from available land and GCR.
•	Apply feasibility constraints (land threshold + grid proximity).
•	Rank eligible counties by annual energy.
Output: baseline ranked_counties.csv using pvgis_Ey_kWh_per_kWp.

Experiment 2 — Satellite heuristic correction of PVGIS
•	Use MOD08_M3 monthly cloud fraction and LTDR monthly reflectance proxy to compute county climatologies. [pyeplan.sps-lab.org], [geopandas.org], [uoradea-my...epoint.com]
•	Apply the month-wise correction Em′=Em⋅fcloud,m⋅falb,mE'_m = E_m \cdot f_{cloud,m}\cdot f_{alb,m}Em′=Em⋅fcloud,m⋅falb,m, producing sat_corrected_Ey_kWh_per_kWp.
•	Rank counties using corrected yields.
Purpose: introduce physically motivated satellite-derived relative adjustments at county scale, with conservative clamping.

Experiment 3 — PVGIS teacher dataset (county mean PVGIS)
•	Sample KKK points per county polygon.
•	Query PVGIS PVcalc at each point.
•	Average to create EcountyteacherE^{teacher}_{county}Ecountyteacher. [fiona.readthedocs.io]
Purpose: create a more representative county-level PVGIS target than a single rep point.

Experiment 4 — Trained surrogate (“student”) and final ranking
•	Train a regression model to predict teacher factor y=Ecountyteacher/ErepPVGISy = E^{teacher}_{county} / E^{PVGIS}_{rep}y=Ecountyteacher/ErepPVGIS.
•	In main.py, replace EyE_yEy used for ranking with: 
o	EcountysurrogateE^{surrogate}_{county}Ecountysurrogate when available,
o	otherwise satellite-corrected PVGIS,
o	otherwise raw PVGIS.
Purpose: provide a learned county-level PV yield estimate (still PVGIS-based) with higher methodological depth and still manageable compute.

6. Metrics and measurements to assess accuracy and credibility
Because PVGIS and satellite products are not ground-truth power meter measurements, “accuracy” must be discussed carefully. The following metrics are appropriate depending on what reference data you can access:
6.1 Internal validation (surrogate vs teacher)
If you use PVGIS teacher targets (county mean PVGIS) as labels, you can evaluate:
•	MAE: mean absolute error between surrogate predicted and teacher targets
•	RMSE: root mean squared error
•	R2R^2R2: coefficient of determination
•	Relative error (%): ∣Esur−Eteacher∣Eteacher×100\frac{|E^{sur} - E^{teacher}|}{E^{teacher}}\times 100Eteacher∣Esur−Eteacher∣×100
Use k fold cross validation over counties to show generalization (e.g., 5-fold CV). This validates that the surrogate reproduces the teacher mapping and is not overfitting to a small set of counties.
6.2 External validation (best if available): real PV production or irradiance references
To claim real-world improvement, compare your county rankings against:
•	Measured plant yield (kWh/kWp) from publicly reported PV plants or operator data (even a small sample improves thesis strength).
•	National/regional solar resource maps or independent irradiance datasets (if accessible).
•	Temporal sanity: if a county is known to have persistent cloudiness, the model should reduce yields.
Recommended metrics if you have plant data:
•	Bias: mean error
•	MAPE: mean absolute percentage error
•	Spearman rank correlation between predicted county ranking and observed yield ranking (good for “best county” claims).
6.3 Robustness / sensitivity (no extra data required)
Even without external ground truth, you can strengthen credibility by showing:
•	Stability under parameter changes: 
o	Vary KKK (e.g., 4 vs 6 points per county teacher) and show that the top counties remain similar.
•	Effect size reporting: 
o	Distribution of correction factors y^\hat{y}y^ and/or monthly fcloud,mf_{cloud,m}fcloud,m showing corrections remain within conservative bounds.
•	Ablation study: 
o	Compare results using: 
1.	PVGIS baseline only,
2.	satellite heuristic,
3.	surrogate, and report how much the top-N changes and why.
6.4 API operational correctness
Document that PVGIS limits require:
•	caching,
•	throttling of requests,
•	retry behavior for overload conditions. 
This supports reproducibility and methodological rigor for any API-driven analysis. [fiona.readthedocs.io]

7. Summary of the final pipeline
1.	Acquire and preprocess satellite products: 
o	MOD08_M3 monthly cloud fraction → county monthly climatology. [pyeplan.sps-lab.org], [geopandas.org]
o	M1_AVH09C1 daily reflectance → QA-masked monthly mean → county monthly climatology. [uoradea-my...epoint.com]
2.	Compute PVGIS baseline per county rep-point via API. [fiona.readthedocs.io], [github.com]
3.	Experiment 2: apply conservative satellite heuristic correction.
4.	Experiment 3: generate PVGIS teacher targets by within-county sampling. [fiona.readthedocs.io]
5.	Experiment 4: train and apply surrogate model; rank counties using surrogate yields.

