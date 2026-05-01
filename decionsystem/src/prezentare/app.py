import dash
from dash import dcc, html, Input, Output, State, ctx
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json
import yaml

from src.repository.geo_repository import GeoRepository
from src.repository.features_repository import FeaturesRepository
from src.repository.pvgis_client import PVGISClient
from src.servicii.optimization_service import OptimizationService

with open("config.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

geo_repo = GeoRepository(cfg)
features_repo = FeaturesRepository(cfg)
pvgis_client = PVGISClient(cfg)
opt_service = OptimizationService(cfg, geo_repo, features_repo, pvgis_client)

try:
    gdf_nuts3 = geo_repo.load_counties().to_crs("EPSG:4326")
    geojson_nuts3 = json.loads(gdf_nuts3.to_json())

    df_blank = pd.DataFrame({
        'NUTS_ID': gdf_nuts3['NUTS_ID'],
        'Nume': gdf_nuts3['NAME_LATN'] if 'NAME_LATN' in gdf_nuts3.columns else gdf_nuts3['NUTS_ID'],
        'Valoare': 0
    })

    land_map = geo_repo.load_land_map()
    MAX_XPV_HA = max(land_map.values()) if land_map else 100
    HAS_GEODATA = True
except Exception as e:
    print(f"Eroare la încărcarea hărții NUTS3: {e}")
    HAS_GEODATA = False
    MAX_XPV_HA = 100
    geojson_nuts3 = {}
    df_blank = pd.DataFrame()

TARI_RO = {
    'Afghanistan': 'Afganistan', 'Albania': 'Albania', 'Algeria': 'Algeria', 'Angola': 'Angola',
    'Argentina': 'Argentina', 'Australia': 'Australia', 'Austria': 'Austria', 'Bahrain': 'Bahrain',
    'Bangladesh': 'Bangladesh', 'Belgium': 'Belgia', 'Benin': 'Benin', 'Bolivia': 'Bolivia',
    'Bosnia and Herzegovina': 'Bosnia și Herțegovina', 'Botswana': 'Botswana', 'Brazil': 'Brazilia',
    'Bulgaria': 'Bulgaria', 'Burkina Faso': 'Burkina Faso', 'Burundi': 'Burundi', 'Cambodia': 'Cambodgia',
    'Cameroon': 'Camerun', 'Canada': 'Canada', 'Central African Republic': 'Rep. Centrafricană',
    'Chad': 'Ciad', 'Chile': 'Chile', 'China': 'China', 'Colombia': 'Columbia', 'Comoros': 'Comore',
    'Congo, Dem. Rep.': 'R.D. Congo', 'Congo, Rep.': 'Congo', 'Costa Rica': 'Costa Rica',
    "Cote d'Ivoire": 'Coasta de Fildeș', 'Croatia': 'Croația', 'Cuba': 'Cuba', 'Czech Republic': 'Cehia',
    'Denmark': 'Danemarca', 'Djibouti': 'Djibouti', 'Dominican Republic': 'Rep. Dominicană',
    'Ecuador': 'Ecuador', 'Egypt': 'Egipt', 'El Salvador': 'El Salvador', 'Equatorial Guinea': 'Guineea Ecuatorială',
    'Eritrea': 'Eritreea', 'Ethiopia': 'Etiopia', 'Finland': 'Finlanda', 'France': 'Franța', 'Gabon': 'Gabon',
    'Gambia': 'Gambia', 'Germany': 'Germania', 'Ghana': 'Ghana', 'Greece': 'Grecia', 'Guatemala': 'Guatemala',
    'Guinea': 'Guineea', 'Guinea-Bissau': 'Guineea-Bissau', 'Haiti': 'Haiti', 'Honduras': 'Honduras',
    'Hong Kong, China': 'Hong Kong', 'Hungary': 'Ungaria', 'Iceland': 'Islanda', 'India': 'India',
    'Indonesia': 'Indonezia', 'Iran': 'Iran', 'Iraq': 'Irak', 'Ireland': 'Irlanda', 'Israel': 'Israel',
    'Italy': 'Italia', 'Jamaica': 'Jamaica', 'Japan': 'Japonia', 'Jordan': 'Iordania', 'Kenya': 'Kenya',
    'Korea, Dem. Rep.': 'Coreea de Nord', 'Korea, Rep.': 'Coreea de Sud', 'Kuwait': 'Kuweit',
    'Lebanon': 'Liban', 'Lesotho': 'Lesotho', 'Liberia': 'Liberia', 'Libya': 'Libia', 'Madagascar': 'Madagascar',
    'Malawi': 'Malawi', 'Malaysia': 'Malaezia', 'Mali': 'Mali', 'Mauritania': 'Mauritania', 'Mauritius': 'Mauritius',
    'Mexico': 'Mexic', 'Mongolia': 'Mongolia', 'Montenegro': 'Muntenegru', 'Morocco': 'Maroc',
    'Mozambique': 'Mozambic', 'Myanmar': 'Myanmar', 'Namibia': 'Namibia', 'Nepal': 'Nepal',
    'Netherlands': 'Țările de Jos', 'New Zealand': 'Noua Zeelandă', 'Nicaragua': 'Nicaragua', 'Niger': 'Niger',
    'Nigeria': 'Nigeria', 'Norway': 'Norvegia', 'Oman': 'Oman', 'Pakistan': 'Pakistan', 'Panama': 'Panama',
    'Paraguay': 'Paraguay', 'Peru': 'Peru', 'Philippines': 'Filipine', 'Poland': 'Polonia', 'Portugal': 'Portugalia',
    'Puerto Rico': 'Puerto Rico', 'Reunion': 'Reunion', 'Romania': 'România', 'Rwanda': 'Rwanda',
    'Sao Tome and Principe': 'Sao Tome și Principe', 'Saudi Arabia': 'Arabia Saudită', 'Senegal': 'Senegal',
    'Serbia': 'Serbia', 'Sierra Leone': 'Sierra Leone', 'Singapore': 'Singapore', 'Slovak Republic': 'Slovacia',
    'Slovenia': 'Slovenia', 'Somalia': 'Somalia', 'South Africa': 'Africa de Sud', 'Spain': 'Spania',
    'Sri Lanka': 'Sri Lanka', 'Sudan': 'Sudan', 'Swaziland': 'Eswatini', 'Sweden': 'Suedia',
    'Switzerland': 'Elveția', 'Syria': 'Siria', 'Taiwan': 'Taiwan', 'Tanzania': 'Tanzania', 'Thailand': 'Thailanda',
    'Togo': 'Togo', 'Trinidad and Tobago': 'Trinidad și Tobago', 'Tunisia': 'Tunisia', 'Turkey': 'Turcia',
    'Uganda': 'Uganda', 'United Kingdom': 'Marea Britanie', 'United States': 'Statele Unite', 'Uruguay': 'Uruguay',
    'Venezuela': 'Venezuela', 'Vietnam': 'Vietnam', 'West Bank and Gaza': 'Cisiordania și Gaza',
    'Yemen, Rep.': 'Yemen', 'Zambia': 'Zambia', 'Zimbabwe': 'Zimbabwe'
}

df_world = px.data.gapminder().query("year==2007")
df_world['country'] = df_world['country'].map(TARI_RO).fillna(df_world['country'])

CRITERII_OPTIONS = [
    {'label': 'Energie Anuală', 'value': 'energy'},
    {'label': 'Eficiență (Yield)', 'value': 'yield'},
    {'label': 'Distanță Rețea', 'value': 'grid'},
    {'label': 'Spațiu Extindere', 'value': 'space'}
]

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY], suppress_callback_exceptions=True)

app.layout = html.Div([
    dcc.Store(id='app-state',
              data={'view': 'world', 'added': ['România'], 'current_country': None, 'mode': 'normal', 'msg_text': '',
                    'msg_color': 'black'}),
    dcc.Store(id='evaluation-results', data=None),

    html.Div(id='world-view', style={'display': 'block'}, children=[
        html.H1("Sistem Inteligent de Optimizare PV", style={'textAlign': 'center', 'marginTop': '20px'}),
        html.Div([
            dbc.Button("Adaugă Țară", id='btn-add-country', color="primary", className="me-3"),
            html.Span(id='world-msg')
        ], style={'margin': '20px 40px', 'display': 'flex', 'alignItems': 'center'}),
        dcc.Graph(id='world-map', style={'height': '75vh'})
    ]),

    html.Div(id='country-view', style={'display': 'none'}, children=[
        dbc.Row([
            dbc.Col(html.H2(id='country-title', style={'margin': '0'}), width=9),
            dbc.Col([
                dbc.Button("Înapoi la Harta Lumii", id='btn-back', outline=True, color="dark", className="float-end")
            ], width=3, style={'display': 'flex', 'justifyContent': 'flex-end', 'alignItems': 'center'})
        ], style={'padding': '15px 20px', 'backgroundColor': '#d4b104', 'borderBottom': '2px solid #b39503'}),

        html.Div(id='controls-panel', children=[
            # Rândul 1: Spațiu, NR. EXTRA, Model și Buton Evaluare
            dbc.Row([
                dbc.Col([
                    html.Label("Suprafață Proiect (ha):", style={'fontWeight': 'bold'}),
                    dcc.Input(id='xpv-input', type='number', value=60, min=2, step=1, className="form-control"),
                    html.Small(id='xpv-hint', className="text-muted")
                ], width=3),
                dbc.Col([
                    html.Label("Nr. Județe Extra:", style={'fontWeight': 'bold'}),
                    dcc.Input(id='extra-input', type='number', value=6, min=0, step=1, className="form-control"),
                    html.Small("Alternative roșii", className="text-muted")
                ], width=2),
                dbc.Col([
                    html.Label("Model Evaluare:", style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='model-selector',
                        options=[
                            {'label': 'PVGIS only', 'value': 'pvgis'},
                            {'label': 'Satellite data correction', 'value': 'satellite'},
                            {'label': 'Random Forest-based ranking', 'value': 'rf'}
                        ],
                        value='pvgis', clearable=False
                    )
                ], width=4),
                dbc.Col([
                    html.Br(),
                    dbc.Button("Începe Evaluarea", id='btn-start-eval', color="success", className="w-100", size="md")
                ], width=3),
            ]),

            # Rândul 2: Cele 3 Priorități
            dbc.Row([
                dbc.Col([
                    html.Label("Prioritate 1:", style={'fontWeight': 'bold', 'marginTop': '10px'}),
                    dcc.Dropdown(id='prio-1', options=CRITERII_OPTIONS, value='energy', clearable=False)
                ], width=4),
                dbc.Col([
                    html.Label("Prioritate 2:", style={'fontWeight': 'bold', 'marginTop': '10px'}),
                    dcc.Dropdown(id='prio-2', options=CRITERII_OPTIONS, value='yield', clearable=False)
                ], width=4),
                dbc.Col([
                    html.Label("Prioritate 3:", style={'fontWeight': 'bold', 'marginTop': '10px'}),
                    dcc.Dropdown(id='prio-3', options=CRITERII_OPTIONS, value='space', clearable=False)
                ], width=4),
            ], style={'marginTop': '10px'})
        ], style={'padding': '15px 20px', 'backgroundColor': '#fcfcfc', 'borderBottom': '1px solid #eee'}),

        # CONTAINER HARTĂ + LEGENDĂ PLUTITOARE
        html.Div([
            dcc.Loading(
                id="loading-eval", type="default",
                children=[dcc.Graph(id='country-specific-map', style={'height': '65vh'})]
            ),

            # Legenda Plutitoare Mutată la Dreapta
            html.Div([
                html.H6("Legendă",
                        style={'fontWeight': 'bold', 'borderBottom': '1px solid #999', 'paddingBottom': '5px',
                               'marginBottom': '10px', 'fontSize': '14px', 'color': '#222'}),

                # Element Verde
                html.Div([
                    html.Div(style={'width': '16px', 'height': '16px', 'backgroundColor': '#009e61',
                                    'display': 'inline-block', 'verticalAlign': 'middle', 'marginRight': '8px',
                                    'borderRadius': '4px'}),
                    html.Span("Județ Optim (Locul 1)",
                              style={'fontWeight': 'bold', 'verticalAlign': 'middle', 'color': '#006633',
                                     'fontSize': '13px'})
                ], style={'marginBottom': '8px'}),

                # Element Galben
                html.Div([
                    html.Div(style={'width': '16px', 'height': '16px', 'backgroundColor': '#d4b104',
                                    'display': 'inline-block', 'verticalAlign': 'middle', 'marginRight': '8px',
                                    'borderRadius': '4px'}),
                    html.Span("Clasament (Opțiuni Bune)",
                              style={'fontWeight': 'bold', 'verticalAlign': 'middle', 'color': '#8f7702',
                                     'fontSize': '13px'})
                ], style={'marginBottom': '8px'}),

                # Element Roșu
                html.Div([
                    html.Div(style={'width': '16px', 'height': '16px', 'backgroundColor': '#db0202',
                                    'display': 'inline-block', 'verticalAlign': 'middle', 'marginRight': '8px',
                                    'borderRadius': '4px'}),
                    html.Span("Județe Extra (Avertisment)",
                              style={'fontWeight': 'bold', 'verticalAlign': 'middle', 'color': '#990101',
                                     'fontSize': '13px'})
                ], style={'marginBottom': '3px'}),

                html.Small("Eșuează un criteriu de spațiu sau rețea.",
                           style={'display': 'block', 'color': '#333', 'marginLeft': '24px', 'lineHeight': '1.1',
                                  'fontSize': '11px'})

            ], style={
                'position': 'absolute',
                'top': '50px',  # Plasată sus, dar suficient de jos cât să nu acopere butoanele Plotly (Zoom/Pan)
                'right': '25px',  # Plasată pe partea dreaptă
                'backgroundColor': 'rgba(150, 150, 150, 0.45)',  # Gri vizibil mai închis, fundal mai transparent
                'borderRadius': '12px',
                'padding': '12px 15px',
                'zIndex': 1000,
                'boxShadow': '0 4px 8px rgba(0,0,0,0.1)'
            })

        ], style={'position': 'relative', 'backgroundColor': '#fff'})
    ]),

    # BARA DE JOS
    html.Div(id='stats-bar', style={'display': 'none'}, children=[
        html.H5("Statistici Județ Selectat", id='stats-title', style={'margin': '0', 'fontWeight': 'bold'}),
        html.Div(id='stats-text', style={'margin': '5px 0 0 0', 'fontSize': '15px'})
    ])
])


@app.callback(
    Output('app-state', 'data'),
    Input('world-map', 'clickData'),
    Input('btn-add-country', 'n_clicks'),
    Input('btn-back', 'n_clicks'),
    State('app-state', 'data'),
    prevent_initial_call=True
)
def handle_interactions(clickData, add_clicks, back_clicks, state):
    trigger = ctx.triggered_id
    if trigger == 'btn-back':
        state.update({'view': 'world', 'current_country': None, 'mode': 'normal', 'msg_text': ''})
    elif trigger == 'btn-add-country':
        state.update({'mode': 'add', 'msg_text': 'Selectează o țară de pe hartă pentru a o integra în sistem.',
                      'msg_color': '#0056b3'})
    elif trigger == 'world-map' and clickData:
        country_name = clickData['points'][0]['hovertext']
        if state.get('mode') == 'add':
            if country_name not in state['added']:
                state['added'].append(country_name)
                state.update({'msg_text': f'Țara {country_name} a fost integrată cu succes!', 'msg_color': '#009e61'})
            else:
                state.update({'msg_text': f'{country_name} este deja integrată.', 'msg_color': '#d4b104'})
            state['mode'] = 'normal'
        else:
            if country_name in state['added']:
                state.update({'view': 'country', 'current_country': country_name, 'msg_text': ''})
            else:
                state.update(
                    {'msg_text': f'"{country_name}" nu este integrată în sistem. Apasă pe "Adaugă Țară" mai întâi.',
                     'msg_color': '#db0202'})
    return state


@app.callback(
    Output('world-view', 'style'), Output('country-view', 'style'), Output('controls-panel', 'style'),
    Output('stats-bar', 'style'), Output('stats-title', 'children'), Output('stats-text', 'children'),
    Output('world-map', 'figure'), Output('country-specific-map', 'figure'), Output('country-title', 'children'),
    Output('xpv-hint', 'children'), Output('world-msg', 'children'), Output('world-msg', 'style'),
    Input('app-state', 'data')
)
def update_ui(state):
    view = state['view']
    current_country = state['current_country']

    df_world['color'] = df_world['country'].apply(
        lambda x: 'Integrată (Date Disponibile)' if x in state['added'] else 'Neintegrată')
    fig_world = px.choropleth(df_world, locations="iso_alpha", color="color",
                              color_discrete_map={'Integrată (Date Disponibile)': '#2ecc71', 'Neintegrată': '#e0e0e0'},
                              hover_name="country")
    fig_world.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, showlegend=True,
                            legend=dict(yanchor="bottom", y=0.05, xanchor="left", x=0.05))
    fig_world.update_geos(showframe=False, showcoastlines=True, projection_type="equirectangular")
    fig_world.update_traces(hovertemplate="<b>%{hovertext}</b><extra></extra>",
                            hoverlabel=dict(bgcolor="#ff7b00", bordercolor="#ffffff",
                                            font=dict(color="white", size=16, family="Arial")))

    fig_country = go.Figure()
    stats_border, stats_bg, stats_title, stats_text, controls_style, xpv_hint = '2px solid #dee2e6', '#f8f9fa', "Statistici", "", {
        'display': 'none'}, ""
    msg_text = state.get('msg_text', '')
    msg_style = {'fontWeight': 'bold', 'fontSize': '16px', 'color': state.get('msg_color', 'black'),
                 'marginLeft': '15px'}

    if view == 'country' and current_country:
        df_single = df_world[df_world['country'] == current_country].copy()
        if current_country == "România" and HAS_GEODATA:
            stats_bg, stats_border = '#d4b104', '2px solid #b39503'
            fig_country = px.choropleth(df_blank, geojson=geojson_nuts3, locations='NUTS_ID',
                                        featureidkey="properties.NUTS_ID", color='Valoare', hover_name='Nume',
                                        color_continuous_scale=[[0, "white"], [1, "white"]])
            fig_country.update_geos(fitbounds="locations", visible=False)
            fig_country.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, showlegend=False,
                                      coloraxis_showscale=False)
            fig_country.update_traces(marker_line_width=1, marker_line_color="black",
                                      hovertemplate="<b>%{hovertext}</b><extra></extra>",
                                      hoverlabel=dict(bgcolor="#ff7b00", bordercolor="#ffffff",
                                                      font=dict(color="white", size=16, family="Arial")))
            controls_style = {'display': 'block'}
            stats_title, stats_text = "Statistici Județ Selectat", "Selectați criteriile și apăsați 'Începe Evaluarea'."
            xpv_hint = f"Spațiu Maxim RO: {MAX_XPV_HA:,.0f} ha"
        else:
            df_single['status'] = 'Inactiv'
            fig_country = px.choropleth(df_single, locations="iso_alpha", color="status",
                                        color_discrete_map={'Inactiv': '#b0b0b0'}, hover_name="country")
            fig_country.update_geos(fitbounds="locations", visible=False, showcountries=True, countrycolor="black")
            fig_country.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, showlegend=False)
            fig_country.update_traces(marker_line_width=1, marker_opacity=0.5,
                                      hovertemplate="<b>%{hovertext}</b><extra></extra>",
                                      hoverlabel=dict(bgcolor="#ff7b00", bordercolor="#ffffff",
                                                      font=dict(color="white", size=16, family="Arial")))
            stats_bg, stats_border = '#fff5f5', '3px solid red'
            stats_title, stats_text = "Eroare de Date", "Datele necesare nu au fost introduse pentru această regiune."

    if view == 'world':
        return {'display': 'block'}, {'display': 'none'}, {'display': 'none'}, {
            'display': 'none'}, "", "", fig_world, fig_country, "", "", msg_text, msg_style
    else:
        stil_bara = {'display': 'block', 'position': 'fixed', 'bottom': 0, 'width': '100%', 'minHeight': '90px',
                     'backgroundColor': stats_bg, 'borderTop': stats_border, 'padding': '15px', 'zIndex': 1000}
        return {'display': 'none'}, {'display': 'block',
                                     'paddingBottom': '120px'}, controls_style, stil_bara, stats_title, stats_text, fig_world, fig_country, f"Vizualizare: {current_country}", xpv_hint, msg_text, msg_style


@app.callback(
    Output('country-specific-map', 'figure', allow_duplicate=True),
    Output('evaluation-results', 'data'),
    Output('stats-text', 'children', allow_duplicate=True),
    Input('btn-start-eval', 'n_clicks'),
    State('xpv-input', 'value'),
    State('extra-input', 'value'),
    State('model-selector', 'value'),
    State('prio-1', 'value'), State('prio-2', 'value'), State('prio-3', 'value'),
    State('app-state', 'data'),
    prevent_initial_call=True
)
def run_evaluation(n_clicks, xpv_value, extra_value, selected_model, p1, p2, p3, state):
    if n_clicks is None or state['current_country'] != "România":
        return dash.no_update, dash.no_update, dash.no_update

    if xpv_value is None or xpv_value <= 0:
        return dash.no_update, dash.no_update, html.Span("Eroare: Introduceți o suprafață validă > 0 ha.",
                                                         style={'color': 'red'})

    extra_nn = int(extra_value) if extra_value is not None else 6

    df_res = opt_service.run_evaluation(xpv_value, selected_model, p1, p2, p3)
    top_n = cfg["run"]["top_n"]

    has_eligible = df_res['eligible'].any()

    def get_strong_yellow_gradient(rank, total):
        if total <= 1: return "#FFD700"
        ratio = rank / (total - 1)
        r = 255
        g = int(215 + (240 - 215) * ratio)
        b = int(0 + (194 - 0) * ratio)
        return f"#{r:02x}{g:02x}{b:02x}"

    df_res['Culoare'] = '#ffffff'
    eligible_count = 0
    extra_count = 0

    actual_eligible_yellows = min(len(df_res[df_res['eligible']]), top_n) - 1
    if actual_eligible_yellows < 0: actual_eligible_yellows = 0

    for idx, row in df_res.iterrows():
        if row['eligible']:
            eligible_count += 1
            if eligible_count == 1:
                df_res.at[idx, 'Culoare'] = '#009e61'
            elif eligible_count <= top_n:
                df_res.at[idx, 'Culoare'] = get_strong_yellow_gradient(eligible_count - 2, actual_eligible_yellows)
        else:
            extra_count += 1
            if extra_count <= extra_nn:
                df_res.at[idx, 'Culoare'] = '#db0202'

    fig = px.choropleth(
        df_res, geojson=geojson_nuts3, locations='county_id', featureidkey="properties.NUTS_ID",
        color='Culoare', hover_name='county_name',
        color_discrete_map={c: c for c in df_res['Culoare'].unique()}
    )

    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, showlegend=False)
    fig.update_traces(marker_line_width=1, marker_line_color="black",
                      hovertemplate="<b>%{hovertext}</b><extra></extra>",
                      hoverlabel=dict(bgcolor="#ff7b00", bordercolor="#ffffff",
                                      font=dict(color="white", size=16, family="Arial")))

    if not has_eligible:
        msg = html.Span(
            f"Niciun județ nu dispune de {xpv_value} ha libere. Sunt afișate doar alternativele cele mai bune (Roșu).",
            style={'color': '#db0202', 'fontWeight': 'bold'})
    else:
        msg = html.Span("Evaluare completă! Criteriile au fost aplicate cu succes.",
                        style={'color': 'green', 'fontWeight': 'bold'})

    return fig, df_res.to_dict('records'), msg


@app.callback(
    Output('stats-title', 'children', allow_duplicate=True),
    Output('stats-text', 'children', allow_duplicate=True),
    Input('country-specific-map', 'clickData'),
    State('evaluation-results', 'data'),
    prevent_initial_call=True
)
def display_county_stats(clickData, eval_data):
    if not clickData or not eval_data:
        return dash.no_update, dash.no_update

    clicked_county_id = clickData['points'][0]['location']
    county_data = next((item for item in eval_data if item["county_id"] == clicked_county_id), None)

    if not county_data:
        return "Statistici Județ Selectat", "Acest județ nu este inclus în analiza curentă."

    title = f"Statistici NUTS3: {county_data['county_name']} ({county_data['county_id']})"

    warning_html = ""
    if not county_data['eligible']:
        motiv = []
        if not county_data['land_ok']:
            motiv.append(f"Spațiu insuficient (Lipsesc {county_data['missing_ha_to_fit']:,.1f} ha).")
        if not county_data['grid_ok']:
            motiv.append("Distanță rețea prea mare.")

        warning_html = html.Div(f"Ne-optimizat: {' '.join(motiv)}",
                                style={'color': '#db0202', 'fontWeight': 'bold', 'marginBottom': '10px'})

    stats_content = html.Div([
        warning_html,
        dbc.Row([
            dbc.Col([html.Strong("Energie Anuală: "), html.Br(), f"{county_data['annual_energy_kWh']:,.2f} kWh"]),
            dbc.Col([html.Strong("Randament: "), html.Br(), f"{county_data['Ey_used_kWh_per_kWp']:,.2f} kWh/kWp"]),
            dbc.Col([html.Strong("Distanță Rețea: "), html.Br(),
                     f"{county_data['nearest_substation_km']:.2f} km" if county_data[
                         'nearest_substation_km'] else "N/A"]),
            dbc.Col([html.Strong("Spațiu Liber: "), html.Br(), f"{county_data['available_ha']:,.1f} ha"])
        ])
    ])

    return title, stats_content


if __name__ == '__main__':
    app.run(debug=True)