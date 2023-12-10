"""
This is the "master" deltaproxy minion, known better as the `control proxy` because
it controls all the deltaproxies underneath it.
"""

import logging

# This must be present or the Salt loader won"t load this module
__proxyenabled__ = ["deltaproxy"]


# Variables are scoped to this module so we can have persistent data
# across calls to fns in here.
DETAILS = {}

log = logging.getLogger(__file__)


# This does nothing, it"s here just as an example and to provide a log
# entry when the module is loaded.
def __virtual__():
    """
    Only return if all the modules are available
    """
    return True


def init(opts):
    """
    init
    """
    DETAILS["initialized"] = True


def initialized():
    """
    Since grains are loaded in many different places and some of those ws
    places occur before the proxy can be initialized, return whether
    our init() function has been called
    """
    return DETAILS.get("initialized", False)


def grains():
    """
    Make up some grains
    """
    if "grains_cache" not in DETAILS:
        DETAILS["grains_cache"] = {
            "dummy_grain_1": "one",
            "dummy_grain_2": "two",
            "dummy_grain_3": "three",
        }

    return DETAILS["grains_cache"]


def grains_refresh():
    """
    Refresh the grains
    """
    DETAILS["grains_cache"] = None
    return grains()


def ping():
    """
    Degenerate ping
    """
    log.debug("deltaproxy returning ping")
    return True


def shutdown(opts):
    """
    For this proxy shutdown is a no-op
    """
    # TODO call shutdown on all the sub-proxies?
    log.debug("deltaproxy shutdown() called...")
