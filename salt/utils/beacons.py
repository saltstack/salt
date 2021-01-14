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
