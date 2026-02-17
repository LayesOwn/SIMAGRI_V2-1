# app.py
import dash
try:
    Output = dash.Output
    Input = dash.Input
except Exception:
    from dash.dependencies import Output, Input
try:
    from dash import html, dcc
except Exception:
    import dash_html_components as html
    import dash_core_components as dcc
import dash_bootstrap_components as dbc
import os

# Layouts
from ui.layout_home import layout_home
from ui.layout_main import layout_main
from ui.layout_forecast import layout_forecast

external_stylesheets = [
    dbc.themes.BOOTSTRAP,
    "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
]
from ui.callbacks import register_callbacks
from ui.callbacks_forecast import register_forecast_callbacks

app = dash.Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    suppress_callback_exceptions=True
)

register_callbacks(app)
register_forecast_callbacks(app)   # 🔥 OBLIGATOIRE

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
    Output("page-content", "children"),
    Input("url", "pathname")
)
def display_page(pathname):

    if pathname == "/historique":
        return layout_main()

    elif pathname == "/prevision":
        return layout_forecast()

    elif pathname == "/docs":
        return html.H3(
            "Documentation SIMAGRI",
            className="text-center mt-5"
        )

    # Page d'accueil par défaut
    return layout_home()


# ==================================================
# 🔑 LANCEMENT DE L'APPLICATION
# ==================================================
if __name__ == "__main__":
    # Configuration pour Docker et local
    host = os.getenv('SIMAGRI_HOST', '0.0.0.0')
    debug = os.getenv('SIMAGRI_DEBUG', 'False').lower() == 'true'
    
    app.run_server(
        debug=debug,
        host=host,
        port=8050
    )

# ========== IMPORTANT : Exécuter le serveur même sans if __name__ ==========
# Cela permet à Docker de lancer directement l'app
if __name__ != "__main__":
    # Depuis Docker/WSGI
    host = os.getenv('SIMAGRI_HOST', '0.0.0.0')
    debug = os.getenv('SIMAGRI_DEBUG', 'False').lower() == 'true'
    
    # Le serveur est exposé via app.server pour WSGI
    # Dash va le servir automatiquement
