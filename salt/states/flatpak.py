"""
Management of flatpak packages
==============================
Allows the installation and uninstallation of flatpak packages.

.. versionadded:: Sodium
"""

import salt.utils.data
import salt.utils.path

__virtualname__ = "flatpak"


def __virtual__():
    if salt.utils.path.which("flatpak"):
        return __virtualname__

    return (
        False,
        'The flatpak state module cannot be loaded: the "flatpak" binary is not in the path.',
    )


def installed(name, location=""):
    """
    Ensure that the named package is installed.

    Args:
        name (str): The name of the package or runtime.
        location (str): The location or remote to install the flatpak from.

    Returns:
        dict: The ``result``, ``comment``, and ``changes``.

    Example:

    .. code-block:: yaml

        install_package:
          flatpack.installed:
            - name: gimp
            - location: flathub
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    old = __salt__["flatpak.is_installed"](name)
    if old:
        ret["comment"] = f'Flatpak package "{name}" is already installed'
        if not __opts__["test"]:
            ret["result"] = True
        return ret

    # The flatpak package is not installed yet.
    if __opts__["test"]:
        ret["comment"] = f'Flatpak package "{name}" would have been installed'
        ret["changes"]["new"] = name
        ret["changes"]["old"] = ""
        return ret

    # Install the flatpak package.
    install_ret = __salt__["flatpak.install"](name, location)
    # Verify that the flatpak package was installed.
    if __salt__["flatpak.is_installed"](name):
        ret["comment"] = f'Flatpak package "{name}" was installed'
        ret["changes"]["new"] = name
        ret["changes"]["old"] = ""
        ret["result"] = True
    else:
        # Installing the flatpak package failed.
        ret["comment"] = f'Flatpak package "{name}" failed to install'
        ret["comment"] += "\noutput:\n" + install_ret["stderr"]
        ret["result"] = False

    return ret


def uninstalled(name):
    """
    Ensure that the named package is not installed.

    Args:
        name (str): The flatpak package.

    Returns:
        dict: The ``result``, ``comment``, and ``changes``.

    Example:

    .. code-block:: yaml

        uninstall_package:
          flatpack.uninstalled:
            - name: gimp
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    old = __salt__["flatpak.is_installed"](name)
    if not old:
        ret["comment"] = f'Flatpak package "{name}" is not installed'
        if not __opts__["test"]:
            ret["result"] = True
        return ret

    # The flatpak package is still installed.
    if __opts__["test"]:
        ret["comment"] = f'Flatpak package "{name}" would have been uninstalled'
        return ret

    # Uninstall the flatpak package.
    uninstall_ret = __salt__["flatpak.uninstall"](name)
    # Verify that the flatpak package was uninstalled.
    if not __salt__["flatpak.is_installed"](name):
        ret["comment"] = f'Flatpak package "{name}" uninstalled'
        ret["result"] = True
    else:
        # Uninstalling the flatpak package failed.
        ret["comment"] = f'Flatpak package "{name}" failed to uninstall'
        ret["comment"] += "\noutput:\n" + uninstall_ret["stderr"]
        ret["result"] = False

    return ret


def add_remote(name, location, expected_homepage):
    """
    Adds a new location to install flatpak packages from.

    This state only checks whether the remote repository is configured in
    flatpak and adds it if necessary. It does not manage the remote's attributes
    like description, comment, etc.
    You may want to check these yourself using `flatpak.remote_info` and then
    delete and re-add the remote if necessary.

    Args:
        name (str): The repository's name.
        location (str): The location of the repository (URL of either a flatpak
            repository or a .flatpakrepo file which describes a repository).

    Returns:
        dict: The ``result``, ``comment``, and ``changes``.

    Example:

    .. code-block:: yaml

        add_flathub:
          flatpack.add_remote:
            - name: flathub
            - location: https://flathub.org/repo/flathub.flatpakrepo
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    current_remote = __salt__["flatpak.remote_info"](name)
    if current_remote:
        ret["comment"] = f'Remote "{name}" already exists'
        if not __opts__["test"]:
            ret["result"] = True
        return ret

    # The remote doesn't exist yet.
    if __opts__["test"]:
        ret["comment"] = f'Remote "{name}" would have been added'
        ret["changes"]["new"] = name
        ret["changes"]["old"] = ""
        return ret

    # Add the remote.
    add_ret = __salt__["flatpak.add_remote"](name, location)
    # Verify that the remote was added.
    if __salt__["flatpak.is_remote_added"](name):
        ret["comment"] = f'Remote "{name}" was added'
        ret["changes"]["new"] = name
        ret["changes"]["old"] = ""
        ret["result"] = True
    else:
        # Adding the remote failed.
        ret["comment"] = f'Failed to add remote "{name}"'
        ret["comment"] += "\noutput:\n" + add_ret["stderr"]
        ret["result"] = False

    return ret
