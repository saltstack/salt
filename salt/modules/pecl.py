# -*- coding: utf-8 -*-
"""
Manage PHP pecl extensions.
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import python libs
import re

# Import salt libs
import salt.utils.data
import salt.utils.path

# Import 3rd-party libs
from salt.ext import six

try:
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _cmd_quote


__func_alias__ = {"list_": "list"}

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "pecl"


def __virtual__():
    if salt.utils.path.which("pecl"):
        return __virtualname__
    return (
        False,
        "The pecl execution module not loaded: pecl binary is not in the path.",
    )


def _pecl(command, defaults=False):
    """
    Execute the command passed with pecl
    """
    cmdline = "pecl {0}".format(command)
    if salt.utils.data.is_true(defaults):
        cmdline = "yes " "''" + " | " + cmdline

    ret = __salt__["cmd.run_all"](cmdline, python_shell=True)

    if ret["retcode"] == 0:
        return ret["stdout"]
    else:
        log.error("Problem running pecl. Is php-pear installed?")
        return ""


def install(pecls, defaults=False, force=False, preferred_state="stable"):
    """
    .. versionadded:: 0.17.0

    Installs one or several pecl extensions.

    pecls
        The pecl extensions to install.

    defaults
        Use default answers for extensions such as pecl_http which ask
        questions before installation. Without this option, the pecl.installed
        state will hang indefinitely when trying to install these extensions.

    force
        Whether to force the installed version or not

    CLI Example:

    .. code-block:: bash

        salt '*' pecl.install fuse
    """
    if isinstance(pecls, six.string_types):
        pecls = [pecls]
    preferred_state = "-d preferred_state={0}".format(_cmd_quote(preferred_state))
    if force:
        return _pecl(
            "{0} install -f {1}".format(preferred_state, _cmd_quote(" ".join(pecls))),
            defaults=defaults,
        )
    else:
        _pecl(
            "{0} install {1}".format(preferred_state, _cmd_quote(" ".join(pecls))),
            defaults=defaults,
        )
        if not isinstance(pecls, list):
            pecls = [pecls]
        for pecl in pecls:
            found = False
            if "/" in pecl:
                channel, pecl = pecl.split("/")
            else:
                channel = None
            installed_pecls = list_(channel)
            for pecl in installed_pecls:
                installed_pecl_with_version = "{0}-{1}".format(
                    pecl, installed_pecls.get(pecl)[0]
                )
                if pecl in installed_pecl_with_version:
                    found = True
            if not found:
                return False
        return True


def uninstall(pecls):
    """
    Uninstall one or several pecl extensions.

    pecls
        The pecl extensions to uninstall.

    CLI Example:

    .. code-block:: bash

        salt '*' pecl.uninstall fuse
    """
    if isinstance(pecls, six.string_types):
        pecls = [pecls]
    return _pecl("uninstall {0}".format(_cmd_quote(" ".join(pecls))))


def update(pecls):
    """
    Update one or several pecl extensions.

    pecls
        The pecl extensions to update.

    CLI Example:

    .. code-block:: bash

        salt '*' pecl.update fuse
    """
    if isinstance(pecls, six.string_types):
        pecls = [pecls]
    return _pecl("install -U {0}".format(_cmd_quote(" ".join(pecls))))


def list_(channel=None):
    """
    List installed pecl extensions.

    CLI Example:

    .. code-block:: bash

        salt '*' pecl.list
    """
    pecl_channel_pat = re.compile("^([^ ]+)[ ]+([^ ]+)[ ]+([^ ]+)")
    pecls = {}
    command = "list"
    if channel:
        command = "{0} -c {1}".format(command, _cmd_quote(channel))
    lines = _pecl(command).splitlines()
    lines = (l for l in lines if pecl_channel_pat.match(l))

    for line in lines:
        match = pecl_channel_pat.match(line)
        if match:
            pecls[match.group(1)] = [match.group(2), match.group(3)]

    return pecls
