"""
Utilies for beacons
"""

import copy


def remove_hidden_options(config, whitelist):
    """
    Remove any hidden options not whitelisted
    """
    for entry in copy.copy(config):
        for func in entry:
            if func.startswith("_") and func not in whitelist:
                config.remove(entry)
    return config


def list_to_dict(config):
    """
    Convert list based beacon configuration
    into a dictionary.
    """
    _config = {}
    list(map(_config.update, config))
    return _config
