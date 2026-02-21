# ui/layout_home.py
try:
    from dash import html, dcc
except Exception:
    import dash_html_components as html
    import dash_core_components as dcc
import dash_bootstrap_components as dbc
from pathlib import Path


def _find_logo_filename(prefix):
    assets_dir = Path(__file__).resolve().parents[1] / "assets"
    tokens = [f"{prefix}.png", f"{prefix}.jpg", f"{prefix}.jpeg", f"{prefix}.webp", f"{prefix}.gif"]
    for token in tokens:
        p = assets_dir / token
        if p.exists():
            return token
    for p in assets_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            continue
        if p.stem.lower().startswith(prefix.lower()):
            return p.name
    return None


def _partner_logo(prefix, label):
    filename = _find_logo_filename(prefix)
    if filename:
        return html.Img(src=f"/assets/{filename}", className="partner-logo", alt=label)
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
                                    dbc.Col(_partner_logo("isra", "ISRA"), width="auto"),
                                    dbc.Col(_partner_logo("anacim", "ANACIM"), width="auto"),
                                    dbc.Col(_partner_logo("fao", "FAO"), width="auto"),
                                ],
                            ),

                            # LOGO
                            (
                                html.Img(
                                    src=f"/assets/{_find_logo_filename('simagri_logo') or _find_logo_filename('simagri')}",
                                    style={"height": "120px"},
                                    className="mb-4"
                                )
                                if (_find_logo_filename("simagri_logo") or _find_logo_filename("simagri"))
                                else html.Div("SIMAGRI", className="simagri-logo-fallback mb-4")
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
