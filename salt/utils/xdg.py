"""
Create an XDG function to get the config dir
"""

import os


def xdg_config_dir():
    """
    Check xdg locations for config files
    """
    xdg_config = os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    xdg_config_directory = os.path.join(xdg_config, "salt")
    return xdg_config_directory
