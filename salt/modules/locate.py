"""
Module for using the locate utilities
"""

import logging

import salt.utils.platform

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only work on POSIX-like systems
    """
    if salt.utils.platform.is_windows():
        return (
            False,
            "The locate execution module cannot be loaded: only available on "
            "non-Windows systems.",
        )
    return True


def version():
    """
    Returns the version of locate

    CLI Example:

    .. code-block:: bash

        salt '*' locate.version
    """
    cmd = "locate -V"
    out = __salt__["cmd.run"](cmd).splitlines()
    return out


def stats():
    """
    Returns statistics about the locate database

    CLI Example:

    .. code-block:: bash

        salt '*' locate.stats
    """
    ret = {}
    cmd = "locate -S"
    out = __salt__["cmd.run"](cmd).splitlines()
    for line in out:
        comps = line.strip().split()
        if line.startswith("Database"):
            ret["database"] = comps[1].replace(":", "")
            continue
        ret[" ".join(comps[1:])] = comps[0]
    return ret


def updatedb():
    """
    Updates the locate database

    CLI Example:

    .. code-block:: bash

        salt '*' locate.updatedb
    """
    cmd = "updatedb"
    out = __salt__["cmd.run"](cmd).splitlines()
    return out


def locate(pattern, database="", limit=0, **kwargs):
    """
    Performs a file lookup. Valid options (and their defaults) are::

        basename=False
        count=False
        existing=False
        follow=True
        ignore=False
        nofollow=False
        wholename=True
        regex=False
        database=<locate's default database>
        limit=<integer, not set by default>

    See the manpage for ``locate(1)`` for further explanation of these options.

    CLI Example:

    .. code-block:: bash

        salt '*' locate.locate
    """
    options = ""
    toggles = {
        "basename": "b",
        "count": "c",
        "existing": "e",
        "follow": "L",
        "ignore": "i",
        "nofollow": "P",
        "wholename": "w",
    }
    for option in kwargs:
        if bool(kwargs[option]) is True and option in toggles:
            options += toggles[option]
    if options:
        options = "-{}".format(options)
    if database:
        options += " -d {}".format(database)
    if limit > 0:
        options += " -l {}".format(limit)
    if "regex" in kwargs and bool(kwargs["regex"]) is True:
        options += " --regex"
    cmd = "locate {} {}".format(options, pattern)
    out = __salt__["cmd.run"](cmd, python_shell=False).splitlines()
    return out
