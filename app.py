# app.py
import dash
from dash import html, dcc
import dash_bootstrap_components as dbc

# Layouts
from ui.layout_home import layout_home
from ui.layout_main import layout_main

external_stylesheets = [
    dbc.themes.BOOTSTRAP,
    "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
]
from ui.callbacks import register_callbacks

app = dash.Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    suppress_callback_exceptions=True
)

register_callbacks(app)   # 🔥 OBLIGATOIRE

server = app.server

# ==================================================
# LAYOUT PRINCIPAL (ROUTER)
# ==================================================
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    html.Div(id="page-content")
])

# ==================================================
# ROUTAGE DES PAGES
# ==================================================
@app.callback(
    dash.Output("page-content", "children"),
    dash.Input("url", "pathname")
)
def display_page(pathname):

    if pathname == "/historique":
        return layout_main()

    elif pathname == "/prevision":
        return html.H3(
            "Analyse prévisionnelle (en cours de développement)",
            className="text-center mt-5"
        )

    elif pathname == "/docs":
        return html.H3(
            "Documentation SIMAGRI",
            className="text-center mt-5"
        )

    # Page d'accueil par défaut
    return layout_home()


# ==================================================
# 🔑 LANCEMENT DE L’APPLICATION
# ==================================================
if __name__ == "__main__":
    app.run_server(debug=True)