"""
Manage flatpak packages via Salt

.. versionadded:: Sodium

:depends: flatpak for distribution
"""

import logging
import re

import salt.utils.path

__virtualname__ = "flatpak"

FLATPAK_BINARY_NAME = "flatpak"


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def __virtual__():
    if salt.utils.path.which("flatpak"):
        return __virtualname__

    return (
        False,
        'The flatpak execution module cannot be loaded: the "flatpak" binary is not in the path.',
    )


def _cmd_run_all(command):
    """
    Run the `command` via `cmd.run_all` and return a result dict that is
    suitable for being returned from one of this execution module's functions.
    """
    # `cmd_output` is a dict looking like this:
    # `{"pid": 123, "retcode": 0, "stdout": "abc", "stderr": "abc"}`
    cmd_output = __salt__["cmd.run_all"](command)

    if cmd_output["retcode"] != 0 and cmd_output["stderr"]:
        # The command failed with a non-zero return code and some text on stderr.
        return {
            "result": False,
            "stderr": cmd_output["stderr"].strip(),
        }

    # Either the command has a return code of 0, or stderr is empty.
    return {
        "result": True,
        "stdout": cmd_output["stdout"].strip(),
    }


def install(name, location):
    """
    Install the specified flatpak package or runtime from the specified location.

    Args:
        name (str): The name of the package or runtime.
        location (str): The location or remote to install from.

    Returns:
        dict: The ``result`` and ``stderr``/``stdout``.

    CLI Example:

    .. code-block:: bash

        salt '*' flatpak.install org.gimp.GIMP flathub
    """
    cmd = f"{FLATPAK_BINARY_NAME} install --noninteractive {location} {name}"
    return _cmd_run_all(cmd)


def is_installed(name):
    """
    Determine if a package or runtime is installed.

    Args:
        name (str): The name of the package or the runtime.

    Returns:
        bool: True if the specified package or runtime is installed, False otherwise.

    CLI Example:

    .. code-block:: bash

        salt '*' flatpak.is_installed org.gimp.GIMP
    """
    cmd = f"{FLATPAK_BINARY_NAME} info {name}"
    # `ignore_retcode` is needed to suppress Salt's error log in case of a
    # non-zero return code. Here the return code is just a status info, and a
    # non-zero return code doesn't mean "error".
    returncode = __salt__["cmd.retcode"](cmd, ignore_retcode=True)
    return returncode == 0


def uninstall(pkg):
    """
    Uninstall the specified package.

    Args:
        pkg (str): The package name.

    Returns:
        dict: The ``result`` and ``stderr``/``stdout``.

    CLI Example:

    .. code-block:: bash

        salt '*' flatpak.uninstall org.gimp.GIMP
    """
    cmd = f"{FLATPAK_BINARY_NAME} uninstall --noninteractive {pkg}"
    return _cmd_run_all(cmd)


def add_remote(name, location):
    """
    Add a new location to install flatpak packages from.

    Args:
        name (str): The repository's name.
        location (str): The location of the repository.

    Returns:
        dict: The ``result`` and ``stderr``/``stdout``.

    CLI Example:

    .. code-block:: bash

        salt '*' flatpak.add_remote flathub https://flathub.org/repo/flathub.flatpakrepo
    """
    cmd = f"{FLATPAK_BINARY_NAME} remote-add {name} {location}"
    return _cmd_run_all(cmd)


def modify_remote(name, **kwargs):
    """
    Modify options for an existing remote repository in the flatpak repository
    configuration.

    Args:
        name (str): The repository's name.
        kwargs: Options and their values; see flatpak-remote-modify(1) man page.

    Returns:
        dict: The ``result`` and ``stderr``/``stdout``.

    CLI Example:

    .. code-block:: bash

        salt '*' flatpak.modify_remote flathub title="The Hub" url=https://flathub.org/repo/flathub.flatpakrepo
    """
    # Format each option as '--key="value"'; separate multiple options with spaces.
    # Apparently Salt adds some dict items to `kwargs` on its own, e.g.
    # "__pub_fun"="flatpak.modify_remote" or "__pub_pid"=5170. We must skip those.
    # We can skip all items in `kwargs` that have a leading underscore because
    # there are no CLI options valid for "flatpak remote-modify" that have a
    # leading underscore.
    options = " ".join(
        f'--{k}="{v}"' for k, v in kwargs.items() if not k.startswith("_")
    )
    cmd = f"{FLATPAK_BINARY_NAME} remote-modify {name} {options}"
    log.debug(cmd)
    return _cmd_run_all(cmd)


def delete_remote(name):
    """
    Remove a remote repository from the flatpak repository configuration.

    The remote is forcibly removed, even if it is still in use by installed apps
    or runtimes.

    Args:
        name (str): The repository's name.

    Returns:
        dict: The ``result`` and ``stderr``/``stdout``.

    CLI Example:

    .. code-block:: bash

        salt '*' flatpak.delete_remote flathub
    """
    cmd = f"{FLATPAK_BINARY_NAME} remote-delete --force {name}"
    return _cmd_run_all(cmd)


def remotes_info():
    """
    Fetch information about all remote repositories.

    Returns:
        list: Attributes (``title``, ``url``, etc.) of all remotes; one dict for each remote.

    CLI Example:

    .. code-block:: bash

        salt '*' flatpak.remotes_info
    """
    columns = [
        "name",
        "title",
        "url",
        "filter",
        "collection",
        "priority",
        "options",
        "comment",
        "description",
        "homepage",
        "icon",
    ]

    # The command looks like this: "flatpak remotes --columns=name:f,title:f,...",
    # so we must add ':f' to each column name.
    # See: flatpak-remotes(1) man page.
    columns_option = ",".join(c + ":f" for c in columns)

    # List all remotes and their attributes. `cmd_output` is a dict looking like this:
    # `{"pid": 123, "retcode": 0, "stdout": "abc", "stderr": "abc"}`
    cmd = f"{FLATPAK_BINARY_NAME} remotes --columns={columns_option}"
    log.debug(cmd)
    cmd_output = __salt__["cmd.run_all"](cmd)

    log.debug(cmd_output)
    if cmd_output["retcode"] != 0 or cmd_output["stderr"]:
        return []

    lines = cmd_output["stdout"].splitlines()
    # `lines` is a list of strings, with each attribute separated by a tab, e.g.:
    # "foobar-flatpak-mirror\tFoobar Flatpak Mirror\t1"

    remotes = []
    # Iterate over each line (i.e. each remote) and add a dict with its attributes
    # to the list `remotes`. The keys of this dict are always the same: always
    # the `columns`.
    for line in lines:
        log.debug(line)
        # And the line contains all the values, separated by tabs.
        values = line.split("\t")
        remotes.append(dict(zip(columns, values)))

    return remotes


def remote_info(remote):
    """
    Fetch information about one remote repository.

    Args:
        remote (str): The remote's name.

    Returns:
        dict: Attributes (``title``, ``url``, etc.) of the remote.
        The dict is empty if the remote doesn't exist.

    CLI Example:

    .. code-block:: bash

        salt '*' flatpak.remote_info flathub
    """
    for r in remotes_info():
        if r["name"] == remote:
            return r
    return {}


def is_remote_added(remote):
    """
    Determine if a remote repository exists.

    Args:
        remote (str): The remote's name.

    Returns:
        bool: True if the remote has already been added.

    CLI Example:

    .. code-block:: bash

        salt '*' flatpak.is_remote_added flathub
    """
    return any(remote == r["name"] for r in remotes_info())
