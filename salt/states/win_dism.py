"""
Installing of Windows features using DISM
=========================================

Install Windows features, capabilities, and packages with DISM

.. code-block:: bash

    Language.Basic~~~en-US~0.0.1.0:
      dism.capability_installed

    NetFx3:
      dism.feature_installed
"""

import logging
import os

import salt.utils.data
import salt.utils.platform

log = logging.getLogger(__name__)
__virtualname__ = "dism"


def __virtual__():
    """
    Only work on Windows where the DISM module is available
    """
    if not salt.utils.platform.is_windows():
        return False, "Module only available on Windows"

    return __virtualname__


def capability_installed(
    name, source=None, limit_access=False, image=None, restart=False
):
    """
    Install a DISM capability

    Args:

        name (str):
            The capability to install

        source (str):
            The optional source of the capability

        limit_access (bool):
            Prevent DISM from contacting Windows Update for online images

        image (Optional[str]):
            The path to the root directory of an offline Windows image. If
            ``None`` is passed, the running operating system is targeted.
            Default is ``None``

        restart (Optional[bool]):
            Reboot the machine if required by the install

    Example:

        Run ``dism.available_capabilities`` to get a list of available
        capabilities. This will help you get the proper name to use

        .. code-block:: yaml

            install_dotnet35:
              dism.capability_installed:
                - name: NetFX3~~~~
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    old = __salt__["dism.installed_capabilities"]()

    if name in old:
        ret["comment"] = f"The capability {name} is already installed"
        return ret

    if __opts__["test"]:
        ret["changes"]["capability"] = f"{name} will be installed"
        ret["result"] = None
        return ret

    # Install the capability
    status = __salt__["dism.add_capability"](name, source, limit_access, image, restart)

    if status["retcode"] not in [0, 1641, 3010]:
        ret["comment"] = f'Failed to install {name}: {status["stdout"]}'
        ret["result"] = False

    new = __salt__["dism.installed_capabilities"]()
    changes = salt.utils.data.compare_lists(old, new)

    if changes:
        ret["comment"] = f"Installed {name}"
        ret["changes"] = status
        ret["changes"]["capability"] = changes

    return ret


def capability_removed(name, image=None, restart=False):
    """
    Uninstall a DISM capability

    Args:

        name (str):
            The capability to uninstall

        image (Optional[str]):
            The path to the root directory of an offline Windows image. If
            ``None`` is passed, the running operating system is targeted.
            Default is ``None``

        restart (Optional[bool]):
            Reboot the machine if required by the uninstall

    Example:

        Run ``dism.installed_capabilities`` to get a list of installed
        capabilities. This will help you get the proper name to use

        .. code-block:: yaml

            remove_dotnet35:
              dism.capability_removed:
                - name: NetFX3~~~~
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    old = __salt__["dism.installed_capabilities"]()

    if name not in old:
        ret["comment"] = f"The capability {name} is already removed"
        return ret

    if __opts__["test"]:
        ret["changes"]["capability"] = f"{name} will be removed"
        ret["result"] = None
        return ret

    # Remove the capability
    status = __salt__["dism.remove_capability"](name, image, restart)

    if status["retcode"] not in [0, 1641, 3010]:
        ret["comment"] = f'Failed to remove {name}: {status["stdout"]}'
        ret["result"] = False

    new = __salt__["dism.installed_capabilities"]()
    changes = salt.utils.data.compare_lists(old, new)

    if changes:
        ret["comment"] = f"Removed {name}"
        ret["changes"] = status
        ret["changes"]["capability"] = changes

    return ret


def feature_installed(
    name,
    package=None,
    source=None,
    limit_access=False,
    enable_parent=False,
    image=None,
    restart=False,
):
    """
    Install a DISM feature

    Args:

        name (str):
            The feature in which to install

        package (Optional[str]):
            The parent package for the feature. You do not have to specify the
            package if it is the Windows Foundation Package. Otherwise, use
            package to specify the parent package of the feature

        source (str):
            The optional source of the feature

        limit_access (bool):
            Prevent DISM from contacting Windows Update for online images

        enable_parent (Optional[bool]):
            ``True`` will enable all parent features of the specified feature

        image (Optional[str]):
            The path to the root directory of an offline Windows image. If
            ``None`` is passed, the running operating system is targeted.
            Default is ``None``

        restart (Optional[bool]):
            Reboot the machine if required by the install

    Example:

        Run ``dism.available_features`` to get a list of available features.
        This will help you get the proper name to use

        .. code-block:: yaml

            install_telnet_client:
              dism.feature_installed:
                - name: TelnetClient
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    old = __salt__["dism.installed_features"]()

    if name in old:
        ret["comment"] = f"The feature {name} is already installed"
        return ret

    if __opts__["test"]:
        ret["changes"]["feature"] = f"{name} will be installed"
        ret["result"] = None
        return ret

    # Install the feature
    status = __salt__["dism.add_feature"](
        name, package, source, limit_access, enable_parent, image, restart
    )

    if status["retcode"] not in [0, 1641, 3010]:
        ret["comment"] = f'Failed to install {name}: {status["stdout"]}'
        ret["result"] = False

    new = __salt__["dism.installed_features"]()
    changes = salt.utils.data.compare_lists(old, new)

    if changes:
        ret["comment"] = f"Installed {name}"
        ret["changes"] = status
        ret["changes"]["feature"] = changes

    return ret


def feature_removed(name, remove_payload=False, image=None, restart=False):
    """
    Disables a feature.

    Args:

        name (str):
            The feature to disable

        remove_payload (Optional[bool]):
            Remove the feature's payload. Must supply source when enabling in
            the future.

        image (Optional[str]):
            The path to the root directory of an offline Windows image. If
            ``None`` is passed, the running operating system is targeted.
            Default is ``None``

        restart (Optional[bool]):
            Reboot the machine if required by the uninstall

    Example:

        Run ``dism.installed_features`` to get a list of installed features.
        This will help you get the proper name to use

        .. code-block:: yaml

            remove_telnet_client:
              dism.feature_removed:
                - name: TelnetClient
                - remove_payload: True
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    old = __salt__["dism.installed_features"]()

    if name not in old:
        ret["comment"] = f"The feature {name} is already removed"
        return ret

    if __opts__["test"]:
        ret["changes"]["feature"] = f"{name} will be removed"
        ret["result"] = None
        return ret

    # Remove the feature
    status = __salt__["dism.remove_feature"](name, remove_payload, image, restart)

    if status["retcode"] not in [0, 1641, 3010]:
        ret["comment"] = f'Failed to remove {name}: {status["stdout"]}'
        ret["result"] = False

    new = __salt__["dism.installed_features"]()
    changes = salt.utils.data.compare_lists(old, new)

    if changes:
        ret["comment"] = f"Removed {name}"
        ret["changes"] = status
        ret["changes"]["feature"] = changes

    return ret


def package_installed(
    name, ignore_check=False, prevent_pending=False, image=None, restart=False
):
    """
    Install a package.

    Args:

        name (str):
            The package to install. Can be a .cab file, a .msu file, or a folder

        ignore_check (Optional[bool]):
            Skip installation of the package if the applicability checks fail

        prevent_pending (Optional[bool]):
            Skip the installation of the package if there are pending online
            actions

        image (Optional[str]):
            The path to the root directory of an offline Windows image. If
            ``None`` is passed, the running operating system is targeted.
            Default is ``None``

        restart (Optional[bool]):
            Reboot the machine if required by the install

    Example:

        .. code-block:: yaml

            install_KB123123123:
              dism.package_installed:
                - name: C:\\Packages\\KB123123123.cab
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    # Fail if using a non-existent package path
    if "~" not in name and not os.path.exists(name):
        if __opts__["test"]:
            ret["result"] = None
        else:
            ret["result"] = False
        ret["comment"] = f"Package path {name} does not exist"
        return ret

    old = __salt__["dism.installed_packages"]()

    # Get package info so we can see if it's already installed
    package_info = __salt__["dism.package_info"](name)

    if package_info["Package Identity"] in old:
        ret["comment"] = (
            f"The package {name} is already installed: "
            f'{package_info["Package Identity"]}'
        )
        return ret

    if __opts__["test"]:
        ret["changes"]["package"] = f"{name} will be installed"
        ret["result"] = None
        return ret

    # Install the package
    status = __salt__["dism.add_package"](
        name, ignore_check, prevent_pending, image, restart
    )

    if status["retcode"] not in [0, 1641, 3010]:
        ret["comment"] = f'Failed to install {name}: {status["stdout"]}'
        ret["result"] = False

    new = __salt__["dism.installed_packages"]()
    changes = salt.utils.data.compare_lists(old, new)

    if changes:
        ret["comment"] = f"Installed {name}"
        ret["changes"] = status
        ret["changes"]["package"] = changes

    return ret


def provisioned_package_installed(name, image=None, restart=False):
    """
    Provision a package on a Windows image.

    .. versionadded:: 3007.0

    Args:

        name (str):
            The package to install. Can be one of the following:

            - ``.appx`` or ``.appxbundle``
            - ``.msix`` or ``.msixbundle``
            - ``.ppkg``

            The name of the file before the file extension must match the name
            of the package after it is installed. This name can be found by
            running ``dism.provisioned_packages``

        image (Optional[str]):
            The path to the root directory of an offline Windows image. If
            ``None`` is passed, the running operating system is targeted.
            Default is ``None``

        restart (Optional[bool]):
            Reboot the machine if required by the installation. Default is
            ``False``

    Example:

        .. code-block:: yaml

            install_windows_media_player:
              dism.provisioned_package_installed:
                - name: C:\\Packages\\Microsoft.ZuneVideo_2019.22091.10036.0_neutral_~_8wekyb3d8bbwe.Msixbundle
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    # Fail if using a non-existent package path
    if not os.path.exists(name):
        if __opts__["test"]:
            ret["result"] = None
        else:
            ret["result"] = False
        ret["comment"] = f"Package path {name} does not exist"
        return ret

    old = __salt__["dism.provisioned_packages"]()

    # Get package name so we can see if it's already installed
    package_name = os.path.splitext(os.path.basename(name))

    if package_name in old:
        ret["comment"] = f"The package {name} is already installed: {package_name}"
        return ret

    if __opts__["test"]:
        ret["changes"]["package"] = f"{name} will be installed"
        ret["result"] = None
        return ret

    # Install the package
    status = __salt__["dism.add_provisioned_package"](name, image, restart)

    if status["retcode"] not in [0, 1641, 3010]:
        ret["comment"] = f'Failed to install {name}: {status["stdout"]}'
        ret["result"] = False

    new = __salt__["dism.provisioned_packages"]()
    changes = salt.utils.data.compare_lists(old, new)

    if changes:
        ret["comment"] = f"Installed {name}"
        ret["changes"] = status
        ret["changes"]["package"] = changes

    return ret


def package_removed(name, image=None, restart=False):
    """
    Uninstall a package

    Args:

        name (str):
            The full path to the package. Can be either a .cab file or a folder.
            Should point to the original source of the package, not to where the
            file is installed. This can also be the name of a package as listed
            in ``dism.installed_packages``

        image (Optional[str]):
            The path to the root directory of an offline Windows image. If
            ``None`` is passed, the running operating system is targeted.
            Default is ``None``

        restart (Optional[bool]):
            Reboot the machine if required by the uninstall

    Example:

        .. code-block:: yaml

            # Example using source
            remove_KB1231231:
              dism.package_installed:
                - name: C:\\Packages\\KB1231231.cab

            # Example using name from ``dism.installed_packages``
            remove_KB1231231:
              dism.package_installed:
                - name: Package_for_KB1231231~31bf3856ad364e35~amd64~~10.0.1.3
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    # Fail if using a non-existent package path
    if "~" not in name and not os.path.exists(name):
        if __opts__["test"]:
            ret["result"] = None
        else:
            ret["result"] = False
        ret["comment"] = f"Package path {name} does not exist"
        return ret

    old = __salt__["dism.installed_packages"]()

    # Get package info so we can see if it's already removed
    package_info = __salt__["dism.package_info"](name)

    # If `Package Identity` isn't returned or if they passed a cab file, if
    # `Package Identity` isn't in the list of installed packages
    if (
        "Package Identity" not in package_info
        or package_info["Package Identity"] not in old
    ):
        ret["comment"] = f"The package {name} is already removed"
        return ret

    if __opts__["test"]:
        ret["changes"]["package"] = f"{name} will be removed"
        ret["result"] = None
        return ret

    # Remove the package
    status = __salt__["dism.remove_package"](name, image, restart)

    if status["retcode"] not in [0, 1641, 3010]:
        ret["comment"] = f'Failed to remove {name}: {status["stdout"]}'
        ret["result"] = False

    new = __salt__["dism.installed_packages"]()
    changes = salt.utils.data.compare_lists(old, new)

    if changes:
        ret["comment"] = f"Removed {name}"
        ret["changes"] = status
        ret["changes"]["package"] = changes

    return ret


def kb_removed(name, image=None, restart=False):
    """
    Uninstall a KB package

    .. versionadded:: 3006.0

    Args:

        name (str):
            The name of the KB. Can be with or without the KB at the beginning

        image (Optional[str]):
            The path to the root directory of an offline Windows image. If
            ``None`` is passed, the running operating system is targeted.
            Default is ``None``

        restart (Optional[bool]):
            Reboot the machine if required by the uninstall

    Example:

        .. code-block:: yaml

            # Example using full KB name
            remove_KB1231231:
              dism.package_installed:
                - name: KB1231231

            # Example using just he KB number
            remove_KB1231231:
              dism.package_installed:
                - name: 1231231
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    pkg_name = __salt__["dism.get_kb_package_name"](kb=name, image=image)

    # If pkg_name is None, the package is not installed
    if pkg_name is None:
        ret["comment"] = f"{name} is not installed"
        return ret

    if __opts__["test"]:
        ret["changes"]["package"] = f"{name} will be removed"
        ret["result"] = None
        return ret

    # Fail if using a non-existent package path
    old = __salt__["dism.installed_packages"]()

    # Remove the package
    status = __salt__["dism.remove_kb"](kb=name, image=image, restart=restart)

    if status["retcode"] not in [0, 1641, 3010]:
        ret["comment"] = f'Failed to remove {name}: {status["stdout"]}'
        ret["result"] = False
        return ret

    new = __salt__["dism.installed_packages"]()
    changes = salt.utils.data.compare_lists(old, new)

    if changes:
        ret["comment"] = f"Removed {name}"
        ret["changes"] = status
        ret["changes"]["package"] = changes

    return ret
