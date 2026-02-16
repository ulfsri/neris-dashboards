"""Reusable component factories for Dash Design Kit components."""

from dash import html, dcc, Input, Output, State, no_update
from typing import Literal

import dash_design_kit as ddk
import dash_bootstrap_components as dbc
from .theme import (
    BUTTON_BASE_STYLE,
    BUTTON_VARIANT_STYLES,
    BASE_INFO_ICON_STYLE,
    CARD_HEADER_STYLE,
    DEFAULT_SPINNER_CHART,
    DEFAULT_SPINNER_METRIC,
)

# TODO make internal those not intended for externalization
__all__ = [
    "create_metric_card",
    "create_last_updated_badge",
    "create_action_button",
    "register_button_loading_state",
    "create_info_icon",
    "create_card_header",
    "create_graph_card",
]


def create_info_icon(
    icon_id, tooltip_text, type="metric", base_style=BASE_INFO_ICON_STYLE
):
    """Create an info icon with a tooltip.

    Types:
        - "metric": Styled for metric cards (relative positioning)
        - "card-header": Styled for chart cards (absolute positioning overlay)
    """

    if type == "card-header":
        # placed within a zero-height container to overlay the card title area
        container_style = {
            "display": "inline-block",
            "marginLeft": "8px",
            "verticalAlign": "middle",
        }
        icon_style = {**base_style, "marginLeft": "0"}
    else:
        container_style = {"display": "inline-block"}
        icon_style = {**base_style, "marginLeft": "5px"}

    # Handle multi-line tooltips
    if isinstance(tooltip_text, list):
        formatted_text = []
        for i, line in enumerate(tooltip_text):
            formatted_text.append(line)
            if i < len(tooltip_text) - 1:
                formatted_text.append(html.Br())
                formatted_text.append(html.Br())
        tooltip_content = html.Span(formatted_text)
    else:
        tooltip_content = tooltip_text

    return html.Span(
        [
            html.Span(
                "ⓘ",
                id=icon_id,
                style={**icon_style, "pointerEvents": "auto"},
            ),
            dbc.Tooltip(tooltip_content, target=icon_id),
        ],
        style=container_style,
    )


def create_card_header(title_text, tooltip_text, extra_controls=None):
    """Create a card header that sits next to the DDK title area."""
    safe_id = "".join(e for e in title_text if e.isalnum()).lower()
    tooltip_id = f"tt-header-{safe_id}"

    header_children = [
        html.Div(
            [
                html.Span(title_text),
                create_info_icon(tooltip_id, tooltip_text, type="card-header"),
            ],
            style={"display": "flex", "alignItems": "center"},
        )
    ]

    if extra_controls:
        header_children.append(
            html.Div(extra_controls, style={"marginLeft": "auto", "display": "flex"})
        )

    return html.Div(
        [
            html.H5(
                header_children,
                className="custom-card-header",
                style={
                    **CARD_HEADER_STYLE,
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "space-between",
                    "width": "100%",
                },
            ),
        ],
    )


def create_graph_card(
    title_text: str,
    tooltip_text: str,
    graph_component: any,
    spinner: dict | Literal[False] = DEFAULT_SPINNER_CHART,
    extra_header_controls: any = None,
    **card_kwargs,
):
    """Create a ddk.Card with a header (including info icon) and a graph component.

    Args:
        title_text: Text for the header
        tooltip_text: Text for the tooltip
        graph_component: The component (e.g. dcc.Graph or dl.Map) to place in the card
        spinner: Configuration for the loading spinner. False to disable.
        extra_header_controls: Optional component(s) to add to the right of the header title
        **card_kwargs: Any additional arguments to pass to ddk.Card (e.g. style, modal, fullscreen)
    """
    # Use our custom CSS class to ensure the header area exists
    class_name = card_kwargs.get("className", "")
    card_kwargs["className"] = f"{class_name} card-with-custom-header".strip()

    children = [
        create_card_header(
            title_text, tooltip_text, extra_controls=extra_header_controls
        )
    ]

    child = (
        html.Div(graph_component)
        if isinstance(graph_component, list)
        else graph_component
    )
    if spinner:
        child = dcc.Loading(child, **spinner)

    children.append(child)

    return ddk.Card(children, **card_kwargs)


def create_metric_card(
    card_id,
    title_id=None,
    title_text=None,
    *,
    value_style=None,
    title_style=None,
    card_style=None,
    class_name="metric-card",
    hover=True,
    tooltip_text=None,
    spinner: dict | None = DEFAULT_SPINNER_METRIC,
):
    """Create a metric card component using DDK Card."""
    if title_id is None:
        title_id = f"{card_id}-title"

    # TODO Move these defaults out to theme, and allow for Config override in app
    default_value_style = {
        "fontSize": "2rem",
        "fontWeight": "bold",
        "margin": "0 0 8px 0",
        "textAlign": "center",
    }
    default_title_style = {
        "fontSize": "0.9rem",
        "color": "#6c757d",
        "margin": "0",
        "textAlign": "center",
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "center",
    }
    default_card_style = {"textAlign": "center", "height": "100%", "padding": "15px"}

    value_style = {**default_value_style, **(value_style or {})}
    title_style = {**default_title_style, **(title_style or {})}
    card_style = {**default_card_style, **(card_style or {})}

    title_children = [html.Span(title_text, id=title_id)]
    if tooltip_text:
        title_children.append(create_info_icon(f"{card_id}-info-icon", tooltip_text))

    card_content = [
        html.H4(id=card_id, style=value_style),
        html.P(title_children, style=title_style),
    ]

    return ddk.Card(
        dcc.Loading(card_content, **spinner) if spinner else card_content,
        style=card_style,
        className=class_name,
        card_hover=hover,
    )


def create_last_updated_badge(
    element_id="data-last-updated",
    label_text="Data last updated: ",
    *,
    label_style=None,
    value_style=None,
    container_style=None,
    bottom_offset="5px",
    right_offset="5px",
):
    """Create a last updated timestamp badge component for headers."""
    default_label_style = {
        "fontSize": "0.65rem",
        "color": "#666",
        "fontWeight": "normal",
    }
    default_value_style = {
        "fontSize": "0.65rem",
        "color": "#666",
        "fontWeight": "normal",
    }
    default_container_style = {
        "position": "absolute",
        "bottom": bottom_offset,
        "right": right_offset,
    }

    label_style = {**default_label_style, **(label_style or {})}
    value_style = {**default_value_style, **(value_style or {})}
    container_style = {**default_container_style, **(container_style or {})}

    return html.Div(
        [
            html.Span(label_text, style=label_style),
            html.Span("", id=element_id, style=value_style),
        ],
        style=container_style,
    )


def create_action_button(
    button_text: str,
    button_id: str,
    *,
    style: dict | None = None,
    variant: str = "default",
) -> html.Button:
    """Create an action button component.

    Args:
        button_text: Text to display on the button
        button_id: ID for the button component
        style: Optional custom style dictionary (merged with theme defaults).
               Individual style properties can override theme defaults.
        variant: Button style variant. Options: "default", "primary", "secondary"

    Returns:
        html.Button component

    """
    base_style = BUTTON_BASE_STYLE.copy()
    variant_style = BUTTON_VARIANT_STYLES.get(variant, {}).copy()
    final_style = {**base_style, **variant_style, **(style or {})}

    return html.Button(
        button_text,
        id=button_id,
        n_clicks=0,
        disabled=False,
        style=final_style,
    )


def register_button_loading_state(
    app,
    button_id: str,
    loading_text: str,
    reset_trigger_id: str,
    reset_trigger_prop: str = "data",
    initial_text: str | None = None,
):
    """Register callbacks to automatically manage button loading state.

    When a button is clicked, it is disabled and shows loading_text.
    When reset_trigger_id changes, the button is re-enabled and reset to initial_text.

    Args:
        app: Dash app instance
        button_id: ID of the button component
        loading_text: Text to show while button action is processing
        reset_trigger_id: ID of component that triggers button reset (e.g., "filters", "download-data")
        reset_trigger_prop: Property of reset_trigger_id to watch (default: "data")
        initial_text: Text to show when button is reset. If None, uses button's original children.
    """
    # # Store initial text if not provided - we'll get it from the button's current state
    # if initial_text is None:
    #     # We can't get it at registration time, so we'll use a default pattern
    #     # Apps should provide initial_text for clarity
    #     initial_text = "Button"  # Fallback, but apps should provide this

    # Set loading state when button is clicked
    @app.callback(
        Output(button_id, "disabled"),
        Output(button_id, "children"),
        Input(button_id, "n_clicks"),
        prevent_initial_call=True,
    )
    def set_loading_state(n_clicks):
        """Set button to loading state when clicked."""
        if n_clicks == 0:
            return False, initial_text
        return True, loading_text

    # Reset button when trigger changes
    @app.callback(
        Output(button_id, "disabled", allow_duplicate=True),
        Output(button_id, "children", allow_duplicate=True),
        Input(reset_trigger_id, reset_trigger_prop),
        State(button_id, "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_button_state(trigger_value, n_clicks):
        """Reset button after action completes."""
        if n_clicks == 0:
            return no_update, no_update
        return False, initial_text
