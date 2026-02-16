"""
Main application file for the cornsacks dashboard.
"""

import dash_design_kit as ddk
from flask_caching import Cache

from dash import Dash
from layout import create_app_layout
from callbacks import register_all_callbacks
from config import CACHE_TIMEOUT_SECONDS

from neris_dash_common import get_cache_config, initialize_data_sources


def create_app():
    """Create and configure the app."""
    initialize_data_sources(source_type="s3")

    app = Dash(
        __name__,
        suppress_callback_exceptions=True,
    )

    cache = Cache(app.server, config=get_cache_config(CACHE_TIMEOUT_SECONDS))

    app.layout = ddk.App(create_app_layout())

    register_all_callbacks(app, cache)

    return app


app = create_app()
server = app.server


if __name__ == "__main__":
    print("Starting Dash app...")
    app.run(debug=True, port=8081, dev_tools_hot_reload=True, use_reloader=True)
    # app.run(debug=False, port=8081)
