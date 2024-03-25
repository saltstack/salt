"""
Idem Support
============

This util provides access to an idem-ready hub

.. versionadded:: 3002
"""

import logging
import sys

try:
    import pop.hub

    HAS_POP = True, None
except ImportError as e:
    HAS_POP = False, str(e)

log = logging.getLogger(__name__)

__virtualname__ = "idem"


def __virtual__():
    if sys.version_info < (3, 6):
        return False, "idem only works on python3.6 and later"
    if not HAS_POP[0]:
        return HAS_POP
    return __virtualname__


def hub():
    """
    Create a hub with idem ready to go and completely loaded
    """
    if "idem.hub" not in __context__:
        log.debug("Creating the POP hub")
        hub = pop.hub.Hub()

        log.debug("Initializing the loop")
        hub.pop.loop.create()

        log.debug("Loading subs onto hub")
        hub.pop.sub.add(dyne_name="config")
        # We aren't collecting grains at all but some exec modules depend on the sub being on the hub
        hub.pop.sub.add(dyne_name="grains")
        hub.pop.sub.add(dyne_name="idem")

        log.debug("Reading idem config options")
        hub.config.integrate.load(["acct", "idem"], "idem", parse_cli=False, logs=False)

        __context__["idem.hub"] = hub

    return __context__["idem.hub"]
