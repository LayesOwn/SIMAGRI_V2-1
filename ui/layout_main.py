# ==========================================================
# layout_main.py
# Interface principale SIMAGRI v2
# ==========================================================

#import dash_html_components as html
from dash import html
from dash import dcc
#import dash_core_components as dcc
import dash_bootstrap_components as dbc
from dash import dash_table
from datetime import date
import dash_leaflet as dl
from domain.crop import get_crop_options
from domain.geography import get_department_options
import datetime
current_year = datetime.datetime.now().year
from domain.socio_eco import compute_labor_cost, compute_post_harvest_cost, compute_soil_preparation_cost, compute_total_socio_cost
from domain.socio_eco import (SOIL_PREPARATION, LABOR, POST_HARVEST, SEEDS)




def layout_main():

    return dbc.Container([

        # ==================================================
        # MÉMOIRE DES SCÉNARIOS
        # ==================================================
        dcc.Store(id="scenario-store", data=[]),
        dcc.Store(id="fertilization-store", data=[]),
        dcc.Store(id="irrigation-store", data=[]),


        # ==================================================
        # TITRE
        # ==================================================
        html.H3(
            "SIMAGRI - Analyse Historique des cultures",
            className="text-center my-4"
        ),

        # ==================================================
        # ZONE PRINCIPALE : 2 COLONNES
        # ==================================================
        dbc.Row([

            # ==================================================
            # COLONNE GAUCHE — FORMULAIRE
            # ==================================================
            dbc.Col([

                dbc.Card([
                    dbc.CardHeader("Paramètres de simulation"),
                    dbc.CardBody([

                        # --- Localisation & culture ---
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Département"),
                                dcc.Dropdown(
                                    id="department",
                                    options=get_department_options(),
                                    value="Kaolack",
                                    clearable=False
                                )
                            ], md=4),
                            dbc.Col([
                                    dbc.Label("Type de sol (chargé automatiquement)"),
                                    dcc.Dropdown(
                                        id="soil_type",
                                        options=[
                                            {"label": "Sandy (Sableux)", "value": "S"},
                                            {"label": "Sandy loam (Sablo-limoneux)", "value": "SL"},
                                            {"label": "Loamy sand (Limon sableux)", "value": "LS"},
                                        ],
                                        value=None,
                                        disabled=True   # 🔒 verrouillé
                                    ),
                                ], md=4),
                            


                            dbc.Col([
                                dbc.Label("Culture"),
                                dcc.Dropdown(
                                    id="crop",
                                    options=get_crop_options(),
                                    value="ML",   # valeur par défaut
                                    clearable=False
                                )
                            ], md=4),

                            dbc.Col([
                                dbc.Label("Cycle variétal"),
                                dcc.Dropdown(
                                    id="cycle",
                                    options=[
                                        {"label": "Court", "value": "court"},
                                        {"label": "Intermédiaire", "value": "intermediaire"},
                                        {"label": "Long", "value": "long"},
                                    ],
                                    value="court",
                                    clearable=False
                                )
                            ],
                                    
                                    md=4),
                            dbc.Row([
                            ]),
                            ### Analyse historique début de saison ###
                           dbc.Card([
                                dbc.CardHeader("Plage de dates simulees"),
                                dbc.CardBody([

                                    dbc.Row([
                                        dbc.Col([
                                            dbc.Label("Année de début"),
                                            dbc.Input(
                                                id="hist_start_year",
                                                type="number",
                                                value=current_year - 30,  # 🔑 20 ans par défaut
                                                min=1991,
                                                max=current_year
                                            )
                                        ], md=3),

                                        dbc.Col([
                                            dbc.Label("Année de fin"),
                                            dbc.Input(
                                                id="hist_end_year",
                                                type="number",
                                                value=current_year-1,  # 🔑 année actuelle
                                                min=1991,
                                                max=current_year
                                            )
                                        ], md=3),

                                        
                                    ]),

                                    html.Br(),

                                    dbc.Alert(
                                        id="hist_info",
                                        color="info",
                                        is_open=False
                                    )
                                ])
                            ]),
   
                          dbc.Row([  
                            dbc.Col([
                                dbc.Label("Date de semis"),
                                dcc.DatePickerSingle(
                                    id="planting_date",
                                    date=date(2026, 6, 15),
                                    display_format="DD/MM/YYYY"
                                )
                            ], md=4),
                            dbc.Col([
                                dbc.Label("📅 Date de semis conseillée (ENACTS)"),
                                dbc.Input(
                                    id="recommended_sowing_date",
                                    type="text",
                                    disabled=True,
                                    placeholder="Calculée automatiquement à partir des pluies"
                                ),
                                dbc.FormText(
                                    "Basée sur l’analyse des pluies ENACTS (début de saison agricole)"
                                )
                            ], md=6),
                        ]),
                        
                            
                        ]),

                           html.Hr(),

                        # --- Pratiques culturales ---
                        dbc.Row([
                            

                        dbc.Row([
                        dbc.Col([
                            dbc.Label("Fertilisation"),
                            dbc.RadioItems(
                                id="fertilization",
                                options=[
                                    {"label": "Non", "value": False},
                                    {"label": "Oui", "value": True},
                                ],
                                value=False,  # 🔑 par défaut
                                inline=True
                            )
                               ]),
                        html.Div(
                                id="fertilization-block",
                                style={"display": "none"},
                                children=[

                                    dbc.Button(
                                        "➕ Ajouter une fertilisation",
                                        id="add-fertilization",
                                        color="secondary",
                                        size="sm",
                                        className="mb-2"
                                    ),

                                    # 🔹 En-tête
                                    dbc.Row([
                                        dbc.Col(html.Strong("Type"), md=4),
                                        dbc.Col(html.Strong("Quantité (Kg/ha)"), md=3),
                                        dbc.Col(html.Strong("Prix (FCFA)"), md=3,style={"textAlign": "right"}),
                                    ], className="mb-1"),
                               
                                    # 🔹 Lignes dynamiques
                                    html.Div(id="fertilization-lines"),
                                
                                # --- Résumé fertilisation ---
                                    dbc.Alert(
                                        id="fert_npk_summary",
                                        color="info",
                                        is_open=True,
                                        children="Aucun apport calculé",
                                    ),
                                #    html.Hr(),

                                    dbc.Row([
                                        dbc.Col([
                                            dbc.Label("Coût total fertilisation (FCFA/ha)"),
                                            dbc.Input(id="fert_total_cost", type="number", disabled=True)
                                        ], md=4)
                                    ])
                                ]
                            ),
                        
                             ]),
                            html.Hr(),

                            dbc.Row([
                                dbc.Col([
                                    dbc.Label("Irrigation"),
                                    dbc.RadioItems(
                                        id="irrigation",
                                        options=[
                                            {"label": "Non", "value": False},
                                            {"label": "Oui", "value": True},
                                        ],
                                        value=False,
                                        inline=True
                                    )
                                ]),
                                html.Div(
                                    id="irrigation-block",
                                    style={"display": "none"},
                                    children=[

                                        dbc.Button(
                                            "➕ Ajouter une irrigation",
                                            id="add-irrigation",
                                            color="secondary",
                                            size="sm",
                                            className="mb-2"
                                        ),

                                        dbc.Row([
                                            dbc.Col(html.Strong("Jour (JAS)"), md=3),
                                            dbc.Col(html.Strong("Quantité (mm)"), md=3),
                                            dbc.Col(html.Strong("Prix (FCFA/mm)"), md=3),
                                        
                                        ], className="mb-1"),

                                        html.Div(id="irrigation-lines"),

                                        dbc.Alert(
                                            id="irrig_summary",
                                            color="info",
                                            children="Aucune irrigation définie",
                                        ),

                                        dbc.Row([
                                            dbc.Col([
                                                dbc.Label("Coût total irrigation (FCFA/ha)"),
                                                dbc.Input(id="irrig_cost", type="number", disabled=True)
                                            ], md=4)
                                        ])
                                    ]
                                )


                            ]),
                            html.Hr(),
                            dbc.Row([
                              dbc.Col([
                                  dbc.Button(
                                "Section socio-économique",
                                id="toggle_socio",
                                color="secondary",
                                className="my-3"
                            ),

                              ])   
                                
                            ]),
                            html.Div(
                            id="socio-block",
                            style={"display": "none"},
                            children=[

                                html.H5("Compte d’exploitation agricole"),
                                # La superficie est gérée dans le bloc principal
                             dbc.Row([
                                    dbc.Col([
                                        dbc.Label("Superficie cultivée (ha)"),
                                        dbc.Input(
                                            id="area_ha",
                                            type="number",
                                            min=0.1,
                                            step=0.1,
                                            value=1
                                        ),
                                    ], md=4),
                                ]),
                             #   html.Hr(),   
                                

                                # Préparation du sol
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Label("Préparation du sol"),
                                        dcc.Dropdown(
                                            id="prep_sol",
                                            options=[
                                                {"label": k, "value": k}
                                                for k in ["Labour", "Hersage", "Billonnage"]
                                            ],
                                            value=["Labour"],   # valeur par défaut
                                            multi=True
                                        ),
                                        dbc.FormText("Plusieurs opérations possibles")
                                    ], md=6),

                                    dbc.Col([
                                        dbc.Label("Coût préparation du sol (FCFA/ha)"),
                                        dbc.Input(id="prep_sol_cost", type="number", disabled=True)
                                    ], md=6),
                                ])
                                ,

                                html.Hr(),

                                # Semences
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Label("Type de semence"),
                                        dcc.Dropdown(
                                            id="seed_type",
                                            options=[
                                                {"label": k, "value": k}
                                                for k in SEEDS.keys()
                                            ],
                                            value="Semence locale"
                                        )
                                    ], md=3),

                                    dbc.Col([
                                        dbc.Label("Quantité (kg/ha)"),
                                        dbc.Input(id="seed_qty", type="number")
                                    ], md=3),

                                    dbc.Col([
                                        dbc.Label("Prix unitaire (FCFA/kg)"),
                                        dbc.Input(id="seed_price", type="number")
                                    ], md=3),

                                    dbc.Col([
                                        dbc.Label("Coût semences"),
                                        dbc.Input(id="seed_cost", type="number", disabled=False)
                                    ], md=3),
                                ]),

                                html.Hr(),
                                
                                dbc.Row([
                                        dbc.Col([
                                            dbc.Label("Post-récolte"),
                                            dcc.Dropdown(
                                                id="post_harvest",
                                                options=[{"label": k, "value": k} for k in POST_HARVEST.keys()],
                                                multi=True
                                            ),
                                        ], md=6),

                                        dbc.Col([
                                            dbc.Label("Coût post-récolte (FCFA)"),
                                            dbc.Input(id="post_harvest_cost", type="number", disabled=True),
                                        ], md=6),
                                    ]),
                                      html.Hr(),
                                # Main d'œuvre
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Label("Main-d’œuvre"),
                                        dcc.Dropdown(
                                            id="labor_type",
                                            options=[
                                                {"label": k, "value": k}
                                                for k in ["Semis", "Sarclage", "Récolte"]
                                            ],
                                            value=["Semis"],
                                            multi=True
                                        ),
                                        dbc.FormText("Sélectionnez toutes les opérations réalisées")
                                    ], md=6),

                                    dbc.Col([
                                        dbc.Label("Coût main-d’œuvre (FCFA/ha)"),
                                        dbc.Input(id="labor_cost", type="number", disabled=True)
                                    ], md=6),
                                ])
                                ,

                                html.Hr(),

                                # Total
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Label("Coût total de production (FCFA/ha)"),
                                        dbc.Input(id="total_cost", type="number", disabled=True)
                                    ], md=6),
                                ]),
                            ]
                        )


                        ]),

                        html.Hr(),

                        # --- Mode de simulation ---
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Type de simulation"),
                                dbc.RadioItems(
                                    id="simulation_mode",
                                    options=[
                                        {"label": "Simuler un seul scénario", "value": "single"},
                                
                                    ],
                                    value="single",
                                    inline=True
                                )
                            ])
                        ]),

                        html.Br(),

                        # --- Boutons ---
                        dbc.Row([
                            dbc.Col(
                                dbc.Button(
                                    "Ajouter le scénario",
                                    id="add_scenario",
                                    color="primary",
                                    className="w-100"
                                ),
                                md=6
                            ),
                            dbc.Col(
                                dbc.Button(
                                    "Simuler",
                                    id="run_simulation",
                                    color="success",
                                    className="w-100"
                                ),
                                md=6
                            ),
                        ]),

                    ])
                ]),

            ], md=6),

            # ==================================================
            # COLONNE DROITE — CARTE INTERACTIVE
            # ==================================================
 
  dbc.Col([

    dbc.Card([
        dbc.CardHeader("Localisation du département"),
        dbc.CardBody(
                dl.Map(
                    id="map",
                    center=[14.15, -16.07],
                    zoom=7,
                    style={"width": "100%", "height": "500px"},
                    children=[
                        dl.TileLayer(
                            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        ),

                        # 🔹 Contour département (chargé dynamiquement)
                        dl.GeoJSON(
                            id="dept-geojson",
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

                        # 🔹 Marqueur département
                        dl.Marker(
                            id="dept-marker",
                            position=[14.15, -16.07],
                            children=dl.Tooltip(id="dept-tooltip")
                        ),
                    ],
                )

        )
    ]),

], md=6),

        ]),

        html.Hr(),

        # ==================================================
        # TABLE DES SCÉNARIOS
        # ==================================================
        dbc.Card([
            dbc.CardHeader("Scénarios simulés"),
            dbc.CardBody([
                dash_table.DataTable(
                    id="scenario-table",
                    data=[],
                    columns=[],
                    page_size=6,
                    row_selectable="multi",
                    style_table={"overflowX": "auto"},
                    style_cell={
                        "minWidth": "120px",
                        "width": "120px",
                        "maxWidth": "200px",
                        "overflow": "hidden",
                        "textOverflow": "ellipsis",
                        "textAlign": "center",
                    },
                )
            ])
        ]),

        html.Br(),

        # ==================================================
        # RÉSULTATS DE SIMULATION / COMPARAISON
        # ==================================================
        dbc.Card([
            dbc.CardHeader("Résultats de la simulation"),
            dbc.CardBody(
                html.Div(
                    id="comparison-output",
                    children="Ajoutez un ou plusieurs scénarios puis cliquez sur « Simuler »."
                )
            )
        ]),

    ], fluid=True)
