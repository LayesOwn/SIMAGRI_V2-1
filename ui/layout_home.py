# ui/layout_home.py
try:
    from dash import html, dcc
except Exception:
    import dash_html_components as html
    import dash_core_components as dcc
import dash_bootstrap_components as dbc

def layout_home():
    return dbc.Container(

        fluid=True,
        className="vh-100 d-flex align-items-center",
        children=[

            dbc.Row(
                className="w-100 justify-content-center",
                children=[

                    dbc.Col(
                        md=8,
                        className="text-center",
                        children=[

                            # LOGO
                            html.Img(
                                src="/assets/simagri_logo.png",
                                style={"height": "120px"},
                                className="mb-4"
                            ),

                            html.H1(
                                "SIMAGRI",
                                className="fw-bold mb-2"
                            ),

                            html.H5(
                                "Outil d’aide à la décision agricole et climatique",
                                className="text-muted mb-5"
                            ),

                            # BOUTONS
                            dbc.Row(
                                className="g-4",
                                children=[

                                    dbc.Col(
                                        dbc.Button(
                                            "📊 Analyse historique",
                                            href="/historique",
                                            color="primary",
                                            size="lg",
                                            className="w-100 py-4"
                                        ),
                                        md=4
                                    ),

                                    dbc.Col(
                                        dbc.Button(
                                            "🌦️ Analyse prévisionnelle",
                                            href="/prevision",
                                            color="success",
                                            size="lg",
                                            className="w-100 py-4"
                                        ),
                                        md=4
                                    ),

                                    dbc.Col(
                                        dbc.Button(
                                            "📘 Documentation",
                                            href="/docs",
                                            color="secondary",
                                            size="lg",
                                            className="w-100 py-4"
                                        ),
                                        md=4
                                    ),

                                ]
                            )
                        ]
                    )
                ]
            )
        ]
    )
