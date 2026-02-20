from app import app
from ui.layout_historic import layout_historic
from ui.callbacks import register_callbacks

app.layout = layout_historic()
#register_callbacks(app)
