# ==========================================================
# layout_forecast.py
# Interface analyse previsionnelle SIMAGRI v2
# ==========================================================

try:
    from dash import html, dcc, dash_table
except Exception:
    import dash_html_components as html
    import dash_core_components as dcc
    import dash_table

import dash_bootstrap_components as dbc
import dash_leaflet as dl
from datetime import date
import datetime

from domain.crop import get_crop_options
from domain.geography import get_department_options
from domain.socio_eco import POST_HARVEST, SEEDS


current_year = datetime.datetime.now().year


def layout_forecast():
    return dbc.Container(
        fluid=True,
        className="simagri-page simagri-forecast",
        children=[
            dcc.Store(id="forecast-scenario-store", data=[]),
            dcc.Store(id="forecast-fertilization-store", data=[]),
            dcc.Store(id="forecast-irrigation-store", data=[]),
            dcc.Store(id="forecast-results-store", data={}),

            html.H3("SIMAGRI - Analyse previsionnelle des cultures", className="text-center my-4"),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button(
                            "Retour vers Accueil",
                            href="/",
                            color="secondary",
                            size="sm",
                        ),
                        width="auto",
                    )
                ],
                className="mb-2",
            ),

            dbc.Row(
                [
                    dbc.Col(
                        md=6,
                        children=[
                            dbc.Card(
                                [
                                    dbc.CardHeader("Parametres de simulation previsionnelle"),
                                    dbc.CardBody(
                                        [
                                            dbc.Row(
                                                [
                                                    dbc.Col(
                                                        [
                                                            dbc.Label("Departement"),
                                                            dcc.Dropdown(
                                                                id="forecast-department",
                                                                options=get_department_options(),
                                                                value="Kaolack",
                                                                clearable=False,
                                                            ),
                                                        ],
                                                        md=4,
                                                    ),
                                                    dbc.Col(
                                                        [
                                                            dbc.Label("Type de sol (charge automatiquement)"),
                                                            dcc.Dropdown(
                                                                id="forecast-soil-type",
                                                                options=[],
                                                                value=None,
                                                                disabled=True,
                                                            ),
                                                        ],
                                                        md=4,
                                                    ),
                                                    dbc.Col(
                                                        [
                                                            dbc.Label("Culture"),
                                                            dcc.Dropdown(
                                                                id="forecast-crop",
                                                                options=get_crop_options(),
                                                                value="ML",
                                                                clearable=False,
                                                            ),
                                                        ],
                                                        md=4,
                                                    ),
                                                ],
                                                className="g-2",
                                            ),
                                            html.Hr(),

                                            dbc.Row(
                                                [
                                                    dbc.Col(
                                                        [
                                                            dbc.Label("Cycle varietal"),
                                                            dcc.Dropdown(
                                                                id="forecast-cycle",
                                                                options=[
                                                                    {"label": "Court", "value": "court"},
                                                                    {"label": "Intermediaire", "value": "intermediaire"},
                                                                    {"label": "Long", "value": "long"},
                                                                ],
                                                                value="court",
                                                                clearable=False,
                                                            ),
                                                        ],
                                                        md=4,
                                                    ),
                                                    dbc.Col(
                                                        [
                                                            dbc.Label("Annee cible"),
                                                            dbc.Input(
                                                                id="forecast-target-year",
                                                                type="number",
                                                                value=current_year,
                                                                min=current_year,
                                                                max=current_year,
                                                                disabled=True,
                                                            ),
                                                        ],
                                                        md=4,
                                                    ),
                                                    dbc.Col(
                                                        [
                                                            dbc.Label("Date de semis"),
                                                            dcc.DatePickerSingle(
                                                                id="forecast-planting-date",
                                                                date=date(current_year, 6, 15),
                                                                display_format="DD/MM/YYYY",
                                                                clearable=False,
                                                            ),
                                                            dbc.FormText(
                                                                id="forecast-recommended-sowing",
                                                                children="Date conseillee: en attente du forecast",
                                                            ),
                                                        ],
                                                        md=4,
                                                    ),
                                                ],
                                                className="g-2",
                                            ),
                                            dbc.Row(
                                                [
                                                    dbc.Col(
                                                        [
                                                            dbc.Label("Methode downscaling"),
                                                            dcc.Dropdown(
                                                                id="forecast-downscaling-method",
                                                                options=[
                                                                    {"label": "Prevision probabiliste (re-echantillonnage BN/NN/AN)", "value": "FRESAMPLER1"},
                                                                ],
                                                                value="FRESAMPLER1",
                                                                clearable=False,
                                                            ),
                                                        ],
                                                        md=8,
                                                    ),
                                                    dbc.Col(
                                                        [
                                                            dbc.Label("Nombre de realisations"),
                                                            dbc.Input(
                                                                id="forecast-realizations",
                                                                type="number",
                                                                value=20,
                                                                min=1,
                                                                max=200,
                                                                step=1,
                                                            ),
                                                        ],
                                                        md=4,
                                                    ),
                                                ],
                                                className="g-2 mt-1",
                                            ),

                                            html.Hr(),

                                            dbc.Row(
                                                [
                                                    dbc.Col(
                                                        [
                                                            dbc.Label("Fertilisation"),
                                                            dbc.RadioItems(
                                                                id="forecast-fertilization",
                                                                options=[
                                                                    {"label": "Non", "value": False},
                                                                    {"label": "Oui", "value": True},
                                                                ],
                                                                value=False,
                                                                inline=True,
                                                            ),
                                                            dbc.FormText(
                                                                "Non = aucune fertilisation, Oui = saisie manuelle des apports."
                                                            ),
                                                        ],
                                                        md=12,
                                                    ),
                                                ],
                                                className="g-2",
                                            ),

                                            html.Div(
                                                id="forecast-fertilization-block",
                                                style={"display": "none"},
                                                children=[
                                                    dbc.Button(
                                                        "Ajouter une fertilisation",
                                                        id="forecast-add-fertilization",
                                                        color="secondary",
                                                        size="sm",
                                                        className="mb-2",
                                                    ),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(html.Strong("Type"), md=4),
                                                            dbc.Col(html.Strong("Quantite (kg/ha)"), md=4),
                                                            dbc.Col(html.Strong("Cout (FCFA)"), md=4),
                                                        ],
                                                        className="mb-1",
                                                    ),
                                                    html.Div(id="forecast-fertilization-lines"),
                                                    dbc.Alert(
                                                        id="forecast-fert-npk-summary",
                                                        color="info",
                                                        is_open=True,
                                                        children="Aucun apport calcule",
                                                        className="mt-2",
                                                    ),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Cout total fertilisation (FCFA/ha)"),
                                                                    dbc.Input(
                                                                        id="forecast-fert-total-cost",
                                                                        type="number",
                                                                        disabled=True,
                                                                    ),
                                                                ],
                                                                md=4,
                                                            )
                                                        ]
                                                    ),
                                                ],
                                            ),

                                            html.Hr(),

                                            dbc.Row(
                                                [
                                                    dbc.Col(
                                                        [
                                                            dbc.Label("Irrigation"),
                                                            dbc.RadioItems(
                                                                id="forecast-irrigation",
                                                                options=[
                                                                    {"label": "Non", "value": "NONE"},
                                                                    {"label": "Oui", "value": "MANUAL"},
                                                                    {"label": "Auto", "value": "AUTO"},
                                                                ],
                                                                value="NONE",
                                                                inline=True,
                                                            ),
                                                            dbc.FormText(
                                                                "Non = aucune irrigation, Oui = saisie manuelle, Auto = irrigation automatique DSSAT."
                                                            ),
                                                        ],
                                                        md=12,
                                                    ),
                                                ],
                                                className="g-2",
                                            ),

                                            html.Div(
                                                id="forecast-irrigation-block",
                                                style={"display": "none"},
                                                children=[
                                                    dbc.Button(
                                                        "Ajouter une irrigation",
                                                        id="forecast-add-irrigation",
                                                        color="secondary",
                                                        size="sm",
                                                        className="mb-2",
                                                    ),
                                                    dbc.Button(
                                                        "Auto-irrigation",
                                                        id="forecast-auto-irrigation",
                                                        color="info",
                                                        size="sm",
                                                        className="mb-2 ms-2",
                                                    ),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(html.Strong("Nom"), md=3),
                                                            dbc.Col(html.Strong("Jour (JAS)"), md=3),
                                                            dbc.Col(html.Strong("Quantite (mm)"), md=2),
                                                            dbc.Col(html.Strong("Prix (FCFA/mm)"), md=2),
                                                            dbc.Col(html.Strong("Cout (FCFA)"), md=2),
                                                        ],
                                                        className="mb-1",
                                                    ),
                                                    html.Div(id="forecast-irrigation-lines"),
                                                    dbc.Alert(
                                                        id="forecast-irrig-summary",
                                                        color="info",
                                                        children="Aucune irrigation definie",
                                                    ),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Cout total irrigation (FCFA/ha)"),
                                                                    dbc.Input(
                                                                        id="forecast-irrig-cost",
                                                                        type="number",
                                                                        disabled=True,
                                                                    ),
                                                                ],
                                                                md=4,
                                                            )
                                                        ]
                                                    ),
                                                ],
                                            ),

                                            html.Hr(),

                                            dbc.Row(
                                                [
                                                    dbc.Col(
                                                        [
                                                            dbc.Button(
                                                                "Section socio-economique",
                                                                id="forecast-toggle-socio",
                                                                color="secondary",
                                                                className="my-2",
                                                            )
                                                        ],
                                                        md=12,
                                                    )
                                                ]
                                            ),

                                            html.Div(
                                                id="forecast-socio-block",
                                                style={"display": "none"},
                                                children=[
                                                    html.H5("Compte d'exploitation agricole"),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Superficie cultivee (ha)"),
                                                                    dbc.Input(
                                                                        id="forecast-area-ha",
                                                                        type="number",
                                                                        value=1,
                                                                        min=0.1,
                                                                        step=0.1,
                                                                    ),
                                                                ],
                                                                md=4,
                                                            )
                                                        ]
                                                    ),
                                                    html.Hr(),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Preparation du sol"),
                                                                    dcc.Dropdown(
                                                                        id="forecast-prep-sol",
                                                                        options=[
                                                                            {"label": "Labour", "value": "Labour"},
                                                                            {"label": "Offsetage", "value": "Offsetage"},
                                                                            {"label": "Billonnage", "value": "Billonnage"},
                                                                        ],
                                                                        value=["Labour"],
                                                                        multi=True,
                                                                    ),
                                                                ],
                                                                md=6,
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Cout preparation du sol (FCFA/ha)"),
                                                                    dbc.Input(
                                                                        id="forecast-prep-sol-cost",
                                                                        type="number",
                                                                        disabled=True,
                                                                    ),
                                                                ],
                                                                md=6,
                                                            ),
                                                        ],
                                                        className="g-2",
                                                    ),
                                                    html.Hr(),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Type de semence"),
                                                                    dcc.Dropdown(
                                                                        id="forecast-seed-type",
                                                                        options=[{"label": k, "value": k} for k in SEEDS.keys()],
                                                                        value="Semence locale",
                                                                    ),
                                                                ],
                                                                md=3,
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Quantite (kg/ha)"),
                                                                    dbc.Input(id="forecast-seed-qty", type="number"),
                                                                ],
                                                                md=3,
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Prix unitaire (FCFA/kg)"),
                                                                    dbc.Input(id="forecast-seed-price", type="number"),
                                                                ],
                                                                md=3,
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Cout semences (FCFA)"),
                                                                    dbc.Input(
                                                                        id="forecast-seed-cost",
                                                                        type="number",
                                                                        disabled=True,
                                                                    ),
                                                                ],
                                                                md=3,
                                                            ),
                                                        ],
                                                        className="g-2",
                                                    ),
                                                    html.Hr(),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Post-recolte"),
                                                                    dcc.Dropdown(
                                                                        id="forecast-post-harvest",
                                                                        options=[{"label": k, "value": k} for k in POST_HARVEST.keys()],
                                                                        multi=True,
                                                                    ),
                                                                ],
                                                                md=6,
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Cout post-recolte (FCFA)"),
                                                                    dbc.Input(
                                                                        id="forecast-post-harvest-cost",
                                                                        type="number",
                                                                        disabled=True,
                                                                    ),
                                                                ],
                                                                md=6,
                                                            ),
                                                        ],
                                                        className="g-2",
                                                    ),
                                                    html.Hr(),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Main-d'oeuvre"),
                                                                    dcc.Dropdown(
                                                                        id="forecast-labor-type",
                                                                        options=[
                                                                            {"label": "Semis", "value": "Semis"},
                                                                            {"label": "Sarclage", "value": "Sarclage"},
                                                                            {"label": "Recolte", "value": "Recolte"},
                                                                            {"label": "Autres", "value": "Autres"},
                                                                        ],
                                                                        value=["Semis"],
                                                                        multi=True,
                                                                    ),
                                                                ],
                                                                md=6,
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Cout main-d'oeuvre (FCFA/ha)"),
                                                                    dbc.Input(
                                                                        id="forecast-labor-cost",
                                                                        type="number",
                                                                        disabled=True,
                                                                    ),
                                                                ],
                                                                md=6,
                                                            ),
                                                        ],
                                                        className="g-2",
                                                    ),
                                                    html.Hr(),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Cout total production (FCFA/ha)"),
                                                                    dbc.Input(id="forecast-total-cost", type="number", disabled=True),
                                                                ],
                                                                md=6,
                                                            ),
                                                        ],
                                                        className="g-2",
                                                    ),
                                                ],
                                            ),

                                            html.Hr(),

                                            dbc.Row(
                                                [
                                                    dbc.Col(
                                                        [
                                                            dbc.Label("Type de scenario"),
                                                            dbc.RadioItems(
                                                                id="forecast-simulation-mode",
                                                                options=[
                                                                    {"label": "1 Scenario", "value": 1},
                                                                    {"label": "2 Scenarios", "value": 2},
                                                                    {"label": "3 Scenarios", "value": 3},
                                                                ],
                                                                value=1,
                                                                inline=True,
                                                            ),
                                                        ],
                                                        md=12,
                                                    ),
                                                ],
                                                className="g-2",
                                            ),

                                            dbc.Row(
                                                [
                                                    dbc.Col(
                                                        dbc.Button(
                                                            "Ajouter le scenario",
                                                            id="forecast-add-scenario",
                                                            color="primary",
                                                            className="w-100",
                                                        ),
                                                        md=4,
                                                    ),
                                                    dbc.Col(
                                                        dbc.Button(
                                                            "Simuler",
                                                            id="forecast-run-simulation",
                                                            color="success",
                                                            className="w-100",
                                                        ),
                                                        md=4,
                                                    ),
                                                    dbc.Col(
                                                        dbc.Button(
                                                            "Reinitialiser",
                                                            id="forecast-reset-scenarios",
                                                            color="danger",
                                                            className="w-100",
                                                        ),
                                                        md=4,
                                                    ),
                                                ],
                                                className="g-2",
                                            ),
                                        ]
                                    ),
                                ]
                            )
                        ],
                    ),

                    dbc.Col(
                        md=6,
                        children=[
                            dbc.Card(
                                [
                                    dbc.CardHeader("Localisation du departement"),
                                    dbc.CardBody(
                                        dl.Map(
                                            id="forecast-map",
                                            center=[14.15, -16.07],
                                            zoom=6,
                                            style={"width": "100%", "height": "500px"},
                                            children=[
                                                dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"),
                                                dl.GeoJSON(
                                                    id="forecast-dept-geojson",
                                                    options={
                                                        "style": {
                                                            "color": "#2c7fb8",
                                                            "weight": 3,
                                                            "fillColor": "#7fcdbb",
                                                            "fillOpacity": 0.4,
                                                        }
                                                    },
                                                    zoomToBounds=True,
                                                    hoverStyle={"weight": 5, "color": "#081d58"},
                                                ),
                                                dl.Marker(
                                                    id="forecast-dept-marker",
                                                    position=[14.15, -16.07],
                                                    children=dl.Tooltip(id="forecast-dept-tooltip"),
                                                ),
                                            ],
                                        )
                                    ),
                                ]
                            )
                        ],
                    ),
                ],
                className="g-3",
            ),

            html.Hr(),

            dbc.Card(
                [
                    dbc.CardHeader("Scenarios previsionnels"),
                    dbc.CardBody(
                        dash_table.DataTable(
                            id="forecast-scenario-table",
                            data=[],
                            columns=[],
                            page_size=6,
                            style_table={"overflowX": "auto"},
                            style_data_conditional=[
                                {
                                    "if": {
                                        "filter_query": "{DSSAT:Status} = 'ERREUR'",
                                        "column_id": "DSSAT:Status",
                                    },
                                    "backgroundColor": "#dc3545",
                                    "color": "white",
                                    "fontWeight": "bold",
                                },
                                {
                                    "if": {
                                        "filter_query": "{DSSAT:Status} = 'VIDE'",
                                        "column_id": "DSSAT:Status",
                                    },
                                    "backgroundColor": "#ffc107",
                                    "color": "#212529",
                                    "fontWeight": "bold",
                                },
                                {
                                    "if": {
                                        "filter_query": "{DSSAT:Status} = 'SUCCES'",
                                        "column_id": "DSSAT:Status",
                                    },
                                    "backgroundColor": "#198754",
                                    "color": "white",
                                    "fontWeight": "bold",
                                },
                            ],
                            style_cell={
                                "minWidth": "120px",
                                "width": "120px",
                                "maxWidth": "220px",
                                "overflow": "hidden",
                                "textOverflow": "ellipsis",
                                "textAlign": "center",
                            },
                        )
                    ),
                ]
            ),

            html.Br(),

            dbc.Card(
                [
                    dbc.CardHeader("Resultats previsionnels"),
                    dbc.CardBody(
                        html.Div(
                            id="forecast-comparison-output",
                            children="Ajoutez un ou plusieurs scenarios previsionnels puis cliquez sur Simuler.",
                        )
                    ),
                ]
            ),
        ],
    )
