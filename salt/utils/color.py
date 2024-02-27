"""
Functions used for CLI color themes.
"""

import logging
import os

from salt.utils.textformat import TextFormat

log = logging.getLogger(__name__)


def get_color_theme(theme):
    """
    Return the color theme to use
    """
    # Keep the heavy lifting out of the module space
    import salt.utils.data
    import salt.utils.files
    import salt.utils.yaml

    if not os.path.isfile(theme):
        log.warning("The named theme %s if not available", theme)

    try:
        with salt.utils.files.fopen(theme, "rb") as fp_:
            colors = salt.utils.data.decode(salt.utils.yaml.safe_load(fp_))
            ret = {}
            for color in colors:
                ret[color] = f"\033[{colors[color]}m"
            if not isinstance(colors, dict):
                log.warning("The theme file %s is not a dict", theme)
                return {}
            return ret
    except Exception:  # pylint: disable=broad-except
        log.warning("Failed to read the color theme %s", theme)
        return {}


def get_colors(use=True, theme=None):
    """
    Return the colors as an easy to use dict. Pass `False` to deactivate all
    colors by setting them to empty strings. Pass a string containing only the
    name of a single color to be used in place of all colors. Examples:

    .. code-block:: python

        colors = get_colors()  # enable all colors
        no_colors = get_colors(False)  # disable all colors
        red_colors = get_colors('RED')  # set all colors to red

    """

    colors = {
        "BLACK": TextFormat("black"),
        "DARK_GRAY": TextFormat("bold", "black"),
        "RED": TextFormat("red"),
        "LIGHT_RED": TextFormat("bold", "red"),
        "GREEN": TextFormat("green"),
        "LIGHT_GREEN": TextFormat("bold", "green"),
        "YELLOW": TextFormat("yellow"),
        "LIGHT_YELLOW": TextFormat("bold", "yellow"),
        "BLUE": TextFormat("blue"),
        "LIGHT_BLUE": TextFormat("bold", "blue"),
        "MAGENTA": TextFormat("magenta"),
        "LIGHT_MAGENTA": TextFormat("bold", "magenta"),
        "CYAN": TextFormat("cyan"),
        "LIGHT_CYAN": TextFormat("bold", "cyan"),
        "LIGHT_GRAY": TextFormat("white"),
        "WHITE": TextFormat("bold", "white"),
        "DEFAULT_COLOR": TextFormat("default"),
        "ENDC": TextFormat("reset"),
    }
    if theme:
        colors.update(get_color_theme(theme))

    if not use:
        for color in colors:
            colors[color] = ""
    if isinstance(use, str):
        # Try to set all of the colors to the passed color
        if use in colors:
            for color in colors:
                # except for color reset
                if color == "ENDC":
                    continue
                colors[color] = colors[use]

    return colors
