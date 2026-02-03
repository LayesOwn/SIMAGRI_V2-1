from app import app
from index import app as _  # force le chargement du layout et callbacks

if __name__ == "__main__":
    app.run_server(
        debug=True,
        host="127.0.0.1",
        port=8050
    )
