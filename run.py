from app import app
from index import app as _  # force le chargement du layout et callbacks
import os

if __name__ == "__main__":
    # Déterminer le host selon l'environnement
    host = os.getenv('SIMAGRI_HOST', '127.0.0.1')
    debug = os.getenv('SIMAGRI_DEBUG', 'True').lower() == 'true'
    
    app.run_server(
        debug=debug,
        host=host,
        port=8050
    )