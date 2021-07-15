"""
    salt._logging
    ~~~~~~~~~~~~~

    This is salt's new logging setup.
    As the name suggests, this is considered an internal API which can change without notice,
    although, as best effort, we'll try not to break code relying on it.

    The ``salt._logging`` package should be imported as soon as possible since salt tweaks
    the python's logging system.
"""


from salt._logging.impl import *  # pylint: disable=wildcard-import
