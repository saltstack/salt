"""
Simple grain to merge the opts into the grains directly if the grain_opts
configuration value is set.
"""


def opts():
    """
    Return the minion configuration settings
    """
    if __opts__.get("grain_opts", False) or (
        isinstance(__pillar__, dict) and __pillar__.get("grain_opts", False)
    ):
        return __opts__
    return {}
