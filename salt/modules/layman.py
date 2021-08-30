"""
Support for Layman
"""

import salt.exceptions
import salt.utils.path


def __virtual__():
    """
    Only work on Gentoo systems with layman installed
    """
    if __grains__["os"] == "Gentoo" and salt.utils.path.which("layman"):
        return "layman"
    return (
        False,
        "layman execution module cannot be loaded: only available on Gentoo with layman"
        " installed.",
    )


def _get_makeconf():
    """
    Find the correct make.conf. Gentoo recently moved the make.conf
    but still supports the old location, using the old location first
    """
    old_conf = "/etc/make.conf"
    new_conf = "/etc/portage/make.conf"
    if __salt__["file.file_exists"](old_conf):
        return old_conf
    elif __salt__["file.file_exists"](new_conf):
        return new_conf


def add(overlay):
    """
    Add the given overlay from the cached remote list to your locally
    installed overlays. Specify 'ALL' to add all overlays from the
    remote list.

    Return a list of the new overlay(s) added:

    CLI Example:

    .. code-block:: bash

        salt '*' layman.add <overlay name>
    """
    ret = list()
    old_overlays = list_local()
    cmd = "layman --quietness=0 --add {}".format(overlay)
    add_attempt = __salt__["cmd.run_all"](cmd, python_shell=False, stdin="y")
    if add_attempt["retcode"] != 0:
        raise salt.exceptions.CommandExecutionError(add_attempt["stdout"])
    new_overlays = list_local()

    # If we did not have any overlays before and we successfully added
    # a new one. We need to ensure the make.conf is sourcing layman's
    # make.conf so emerge can see the overlays
    if not old_overlays and new_overlays:
        srcline = "source /var/lib/layman/make.conf"
        makeconf = _get_makeconf()
        if not __salt__["file.contains"](makeconf, "layman"):
            __salt__["file.append"](makeconf, srcline)

    ret = [overlay for overlay in new_overlays if overlay not in old_overlays]
    return ret


def delete(overlay):
    """
    Remove the given overlay from the your locally installed overlays.
    Specify 'ALL' to remove all overlays.

    Return a list of the overlays(s) that were removed:

    CLI Example:

    .. code-block:: bash

        salt '*' layman.delete <overlay name>
    """
    ret = list()
    old_overlays = list_local()
    cmd = "layman --quietness=0 --delete {}".format(overlay)
    delete_attempt = __salt__["cmd.run_all"](cmd, python_shell=False)
    if delete_attempt["retcode"] != 0:
        raise salt.exceptions.CommandExecutionError(delete_attempt["stdout"])
    new_overlays = list_local()

    # If we now have no overlays added, We need to ensure that the make.conf
    # does not source layman's make.conf, as it will break emerge
    if not new_overlays:
        srcline = "source /var/lib/layman/make.conf"
        makeconf = _get_makeconf()
        if __salt__["file.contains"](makeconf, "layman"):
            __salt__["file.sed"](makeconf, srcline, "")

    ret = [overlay for overlay in old_overlays if overlay not in new_overlays]
    return ret


def sync(overlay="ALL"):
    """
    Update the specified overlay. Use 'ALL' to synchronize all overlays.
    This is the default if no overlay is specified.

    overlay
        Name of the overlay to sync. (Defaults to 'ALL')

    CLI Example:

    .. code-block:: bash

        salt '*' layman.sync
    """
    cmd = "layman --quietness=0 --sync {}".format(overlay)
    return __salt__["cmd.retcode"](cmd, python_shell=False) == 0


def list_local():
    """
    List the locally installed overlays.

    Return a list of installed overlays:

    CLI Example:

    .. code-block:: bash

        salt '*' layman.list_local
    """
    cmd = "layman --quietness=1 --list-local --nocolor"
    out = __salt__["cmd.run"](cmd, python_shell=False).split("\n")
    ret = [line.split()[1] for line in out if len(line.split()) > 2]
    return ret


def list_all():
    """
    List all overlays, including remote ones.

    Return a list of available overlays:

    CLI Example:

    .. code-block:: bash

        salt '*' layman.list_all
    """
    cmd = "layman --quietness=1 --list --nocolor"
    out = __salt__["cmd.run"](cmd, python_shell=False).split("\n")
    ret = [line.split()[1] for line in out if len(line.split()) > 2]
    return ret
