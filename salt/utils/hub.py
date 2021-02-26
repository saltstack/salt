"""
Pop Hub Support
===============

This util provides access to a pop hub

.. versionadded:: 3004
"""
import logging
import sys

try:
    import pop.hub

    HAS_POP = True
except ImportError:
    HAS_POP = False

log = logging.getLogger(__name__)

__virtualname__ = "hub"


def __virtual__():
    if sys.version_info < (3, 6):
        return False, "only works on python3.6 and later"
    if not HAS_POP:
        return False, "The hub util module could not be loaded. Pop module is required"
    return __virtualname__


def hub(project, subs=None, sub_dirs=None, confs=None):
    """
    Create a hub with specified pop project ready to go and completely loaded
    """
    if "{}.hub".format(project) not in __context__:
        log.debug("Creating the POP hub")
        hub = pop.hub.Hub()

        log.debug("Initializing the loop")
        hub.pop.loop.create()

        log.debug("Loading subs onto hub")
        hub.pop.sub.add(dyne_name=project)
        if subs:
            for sub in subs:
                hub.pop.sub.add(dyne_name=sub)

        if sub_dirs:
            for sub_dir in sub_dirs:
                hub.pop.sub.load_subdirs(getattr(hub, sub_dir), recurse=True)

        if confs:
            hub.pop.sub.add(dyne_name="config")
            hub.pop.config.load(confs, project, parse_cli=False, logs=False)

        __context__["{}.hub".format(project)] = hub

    return __context__["{}.hub".format(project)]
