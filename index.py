from app import app
from ui.layout_main import layout_main
from ui.callbacks import register_callbacks

app.layout = layout_main()
#register_callbacks(app)
