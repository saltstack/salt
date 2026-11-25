"""
Utilies for beacons
"""

import contextlib
import contextvars
import copy

_RUNNING_BEACON = contextvars.ContextVar("salt_running_beacon", default=False)


@contextlib.contextmanager
def running_beacon():
    """
    Mark the current context as running a beacon.

    Beacons run on a short interval (every second by default), so anything
    they trigger that is normally logged at ``info`` level, such as the
    ``Executing command`` message of ``cmd.run``, fills the minion log. Code
    can use :py:func:`is_running_beacon` to log at a lower level instead.
    """
    token = _RUNNING_BEACON.set(True)
    try:
        yield
    finally:
        _RUNNING_BEACON.reset(token)


def is_running_beacon():
    """
    Return ``True`` when called while a beacon is being run
    """
    return _RUNNING_BEACON.get()


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
