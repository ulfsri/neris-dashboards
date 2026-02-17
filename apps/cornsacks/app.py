"""
Main application file for the cornsacks dashboard.
"""

import os

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

    # for signing Flask's built-in session cookie
    app.server.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

    # Redis as cache unless there's no REDIS_URL in the env
    cache = Cache(app.server, config=get_cache_config(CACHE_TIMEOUT_SECONDS))

    # Callable layout so create_app_layout runs per initial page load, triggering
    # auth initialization each time a new session is created
    app.layout = lambda: ddk.App(create_app_layout())

    register_all_callbacks(app, cache)

    return app


app = create_app()
server = app.server


if __name__ == "__main__":
    print("Starting Dash app...")
    run_params = {
        "debug": True,
        "port": 8081,
    }
    if os.environ.get("DASHBOARD_CONTEXT") == "local":
        run_params["dev_tools_hot_reload"] = True
        run_params["use_reloader"] = True
    app.run(**run_params)
