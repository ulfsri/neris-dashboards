"""Color utility functions for NERIS dashboards."""

import colorsys


def hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """Convert hex color (#RRGGBB) to RGB tuple (0.0-1.0)."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    """Convert RGB tuple (0.0-1.0) to hex color (#RRGGBB)."""
    return "#" + "".join(f"{int(round(c * 255)):02x}" for c in rgb)


def lighten_color(hex_color: str, amount: float = 0.2) -> str:
    """
    Lighten a hex color by a specified amount (0.0 to 1.0).
    Uses HLS color space to increase lightness.
    """
    red, green, blue = hex_to_rgb(hex_color)
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    # Increase lightness, capping at 1.0
    new_lightness = min(1.0, lightness + (amount * (1.0 - lightness)))
    return rgb_to_hex(colorsys.hls_to_rgb(hue, new_lightness, saturation))


def generate_hierarchical_colors(
    ids: list[str],
    base_color_map: dict[str, str],
    default_color: str = "#D3D3D3",
    lighten_increment: float = 0.15,
) -> dict[str, str]:
    """
    Generate colors for a list of hierarchical IDs based on top-level base colors.

    IDs are expected to be separated by '||'.
    """
    color_map = {}

    for node_id in ids:
        if not node_id or node_id == "all":
            color_map[node_id] = default_color
            continue

        tiers = node_id.split("||")
        top_level = tiers[0]

        base_color = base_color_map.get(top_level, default_color)

        if len(tiers) == 1:
            color_map[node_id] = base_color
        else:
            # Lighten based on depth
            lighten_amount = (len(tiers) - 1) * lighten_increment
            color_map[node_id] = lighten_color(base_color, lighten_amount)

    return color_map
