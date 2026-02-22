# ui/layout_home.py
try:
    from dash import html, dcc
except Exception:
    import dash_html_components as html
    import dash_core_components as dcc
import dash_bootstrap_components as dbc
from pathlib import Path


def _logo_src(candidates):
    assets_dir = Path(__file__).resolve().parents[1] / "assets"
    for name in candidates:
        if (assets_dir / name).exists():
            return f"/assets/{name}"
    return None


def _partner_logo(candidates, label):
    src = _logo_src(candidates)
    if src:
        return html.Img(src=src, className="partner-logo", alt=label)
    return html.Div(label, className="partner-fallback")

def layout_home():
    return dbc.Container(

        fluid=True,
        className="simagri-page simagri-home vh-100 d-flex align-items-center",
        children=[

            dbc.Row(
                className="w-100 justify-content-center",
                children=[

                    dbc.Col(
                        md=8,
                        className="text-center",
                        children=[

                            dbc.Row(
                                className="justify-content-center g-3 mb-3",
                                children=[
                                    dbc.Col(
                                        _partner_logo(
                                            [
                                                "isra_logo_new.png",
                                                "isra_logo_50ans.png",
                                                "lsp_50ans.png",
                                                "isra_logo.png",
                                            ],
                                            "ISRA",
                                        ),
                                        width="auto",
                                    ),
                                    dbc.Col(
                                        _partner_logo(
                                            [
                                                "lpao_sp_logo.png",
                                                "lpao_sf_logo.png",
                                                "lpao_sp.png",
                                                "lpao_sf.png",
                                            ],
                                            "LPAO-SP",
                                        ),
                                        width="auto",
                                    ),
                                    dbc.Col(
                                        _partner_logo(["anacim_logo.png"], "ANACIM"),
                                        width="auto",
                                    ),
                                    dbc.Col(
                                        _partner_logo(["fao_logo.png"], "FAO"),
                                        width="auto",
                                    ),
                                ],
                            ),

                            # LOGO
                            html.Div("SIMAGRI", className="simagri-logo-fallback mb-4"),

                            html.H1(
                                "SIMAGRI",
                                className="fw-bold mb-2"
                            ),

                            html.H5(
                                "Outil d’aide à la décision agricole",
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
                            ),

                            html.Hr(className="my-4"),
                            dbc.Card(
                                className="text-start",
                                children=[
                                    dbc.CardHeader("Equipe de developpement"),
                                    dbc.CardBody(
                                        [
                                            html.P(
                                                [
                                                    html.Strong("Lead developpeur: "),
                                                    "Abdoulaye Diop (Bioinformaticien - Biomathematicien) ",
                                                    html.A(
                                                        "dioplayes@gmail.com",
                                                        href="mailto:dioplayes@gmail.com",
                                                    ),
                                                ],
                                                className="mb-2",
                                            ),
                                            html.P("Collegues:", className="mb-1"),
                                            html.Ul(
                                                [
                                                    html.Li("Dr Adama Faye"),
                                                    html.Li("Dr Mbaye Diop"),
                                                    html.Li("... reste de l'equipe a ajouter"),
                                                ],
                                                className="mb-0",
                                            ),
                                        ]
                                    ),
                                ],
                            ),
                        ]
                    )
                ]
            )
        ]
    )
