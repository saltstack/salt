"""
Support for Alternatives system

:codeauthor: Radek Rada <radek.rada@gmail.com>
"""

import logging
import os

import salt.utils.files
import salt.utils.path

__outputter__ = {
    "display": "txt",
    "install": "txt",
    "remove": "txt",
}

log = logging.getLogger(__name__)

# Don't shadow built-in's.
__func_alias__ = {"set_": "set"}


def __virtual__():
    """
    Only if alternatives dir is available
    """
    if os.path.isdir("/etc/alternatives"):
        return True
    return (False, "Cannot load alternatives module: /etc/alternatives dir not found")


def _get_cmd():
    """
    Alteratives commands and differ across distributions
    """
    if __grains__["os_family"] == "RedHat":
        return "alternatives"
    return "update-alternatives"


def display(name):
    """
    Display alternatives settings for defined command name

    CLI Example:

    .. code-block:: bash

        salt '*' alternatives.display editor
    """
    cmd = [_get_cmd(), "--display", name]
    out = __salt__["cmd.run_all"](cmd, python_shell=False, ignore_retcode=True)
    if out["retcode"] > 0 and out["stderr"] != "":
        return out["stderr"]
    return out["stdout"]


def show_link(name):
    """
    Display master link for the alternative

    .. versionadded:: 2015.8.13,2016.3.4,2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' alternatives.show_link editor
    """

    if __grains__["os_family"] == "RedHat":
        path = "/var/lib/"
    elif __grains__["os_family"] == "Suse":
        path = "/var/lib/rpm/"
    else:
        path = "/var/lib/dpkg/"

    path += "alternatives/{}".format(name)

    try:
        with salt.utils.files.fopen(path, "rb") as r_file:
            contents = salt.utils.stringutils.to_unicode(r_file.read())
            return contents.splitlines(True)[1].rstrip("\n")
    except OSError:
        log.error("alternatives: %s does not exist", name)
    except (OSError, IndexError) as exc:  # pylint: disable=duplicate-except
        log.error(
            "alternatives: unable to get master link for %s. Exception: %s",
            name,
            exc,
        )

    return False


def show_current(name):
    """
    Display the current highest-priority alternative for a given alternatives
    link

    CLI Example:

    .. code-block:: bash

        salt '*' alternatives.show_current editor
    """
    try:
        return _read_link(name)
    except OSError:
        log.error("alternative: %s does not exist", name)
    return False


def check_exists(name, path):
    """
    Check if the given path is an alternative for a name.

    .. versionadded:: 2015.8.4

    CLI Example:

    .. code-block:: bash

        salt '*' alternatives.check_exists name path
    """
    cmd = [_get_cmd(), "--display", name]
    out = __salt__["cmd.run_all"](cmd, python_shell=False, ignore_retcode=True)

    if out["retcode"] > 0 and out["stderr"] != "":
        return False

    return any(line.startswith(path) for line in out["stdout"].splitlines())


def check_installed(name, path):
    """
    Check if the current highest-priority match for a given alternatives link
    is set to the desired path

    CLI Example:

    .. code-block:: bash

        salt '*' alternatives.check_installed name path
    """
    try:
        return _read_link(name) == path
    except OSError:
        return False


def install(name, link, path, priority):
    """
    Install symbolic links determining default commands

    CLI Example:

    .. code-block:: bash

        salt '*' alternatives.install editor /usr/bin/editor /usr/bin/emacs23 50
    """
    cmd = [_get_cmd(), "--install", link, name, path, str(priority)]
    out = __salt__["cmd.run_all"](cmd, python_shell=False)
    if out["retcode"] > 0 and out["stderr"] != "":
        return out["stderr"]
    return out["stdout"]


def remove(name, path):
    """
    Remove symbolic links determining the default commands.

    CLI Example:

    .. code-block:: bash

        salt '*' alternatives.remove name path
    """
    cmd = [_get_cmd(), "--remove", name, path]
    out = __salt__["cmd.run_all"](cmd, python_shell=False)
    if out["retcode"] > 0:
        return out["stderr"]
    return out["stdout"]


def auto(name):
    """
    Trigger alternatives to set the path for <name> as
    specified by priority.

    CLI Example:

    .. code-block:: bash

        salt '*' alternatives.auto name
    """
    cmd = [_get_cmd(), "--auto", name]
    out = __salt__["cmd.run_all"](cmd, python_shell=False)
    if out["retcode"] > 0:
        return out["stderr"]
    return out["stdout"]


def set_(name, path):
    """
    Manually set the alternative <path> for <name>.

    CLI Example:

    .. code-block:: bash

        salt '*' alternatives.set name path
    """
    cmd = [_get_cmd(), "--set", name, path]
    out = __salt__["cmd.run_all"](cmd, python_shell=False)
    if out["retcode"] > 0:
        return out["stderr"]
    return out["stdout"]


def _read_link(name):
    """
    Read the link from /etc/alternatives

    Throws an OSError if the link does not exist
    """
    alt_link_path = "/etc/alternatives/{}".format(name)
    return salt.utils.path.readlink(alt_link_path)
