"""
Manage the Thorium complex event reaction system
"""

import salt.thorium


def start(grains=False, grain_keys=None, pillar=False, pillar_keys=None):
    """
    Execute the Thorium runtime
    """
    state = salt.thorium.ThorState(__opts__, grains, grain_keys, pillar, pillar_keys)
    state.start_runtime()
