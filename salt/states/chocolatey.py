# -*- coding: utf-8 -*-

"""
Manage Chocolatey package installs
.. versionadded:: 2016.3.0

.. note::
    Chocolatey pulls data from the Chocolatey internet database to determine
    current versions, find available versions, etc. This is normally a slow
    operation and may be optimized by specifying a local, smaller chocolatey
    repo.
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.data
import salt.utils.versions
from salt.exceptions import SaltInvocationError


def __virtual__():
    """
    Load only if chocolatey is loaded
    """
    return "chocolatey" if "chocolatey.install" in __salt__ else False


def installed(
    name,
    version=None,
    source=None,
    force=False,
    pre_versions=False,
    install_args=None,
    override_args=False,
    force_x86=False,
    package_args=None,
    allow_multiple=False,
):
    """
    Installs a package if not already installed

    Args:

        name (str):
            The name of the package to be installed. Required.

        version (str):
            Install a specific version of the package. Defaults to latest
            version. If the version is different to the one installed then the
            specified version will be installed. Default is None.

        source (str):
            Chocolatey repository (directory, share or remote URL, feed).
            Defaults to the official Chocolatey feed. Default is None.

        force (bool):
            Reinstall the current version of an existing package. Do not use
            with ``allow_multiple``. Default is False.

        pre_versions (bool):
            Include pre-release packages. Default is False.

        install_args (str):
            Install arguments you want to pass to the installation process, i.e
            product key or feature list. Default is None.

        override_args (bool):
            Set to True if you want to override the original install arguments
            (for the native installer) in the package and use your own. When
            this is set to False install_args will be appended to the end of the
            default arguments. Default is False.

        force_x86 (bool):
            Force x86 (32bit) installation on 64 bit systems. Default is False.

        package_args (str):
            Arguments you want to pass to the package. Default is None.

        allow_multiple (bool):
            Allow mulitiple versions of the package to be installed. Do not use
            with ``force``. Does not work with all packages. Default is False.

            .. versionadded:: 2017.7.0

    .. code-block:: yaml

        Installsomepackage:
          chocolatey.installed:
            - name: packagename
            - version: '12.04'
            - source: 'mychocolatey/source'
            - force: True
    """
    if force and allow_multiple:
        raise SaltInvocationError(
            "Cannot use 'force' in conjunction with 'allow_multiple'"
        )

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    # Get list of currently installed packages
    pre_install = __salt__["chocolatey.list"](local_only=True)

    # Determine action
    # Package not installed
    if name.lower() not in [package.lower() for package in pre_install.keys()]:
        if version:
            ret["changes"] = {name: "Version {0} will be installed".format(version)}
        else:
            ret["changes"] = {name: "Latest version will be installed"}

    # Package installed
    else:
        version_info = __salt__["chocolatey.version"](
            name=name, check_remote=True, source=source
        )

        full_name = name
        for pkg in version_info:
            if name.lower() == pkg.lower():
                full_name = pkg

        installed_version = version_info[full_name]["installed"][0]

        if version:
            if salt.utils.versions.compare(
                ver1=installed_version, oper="==", ver2=version
            ):
                if force:
                    ret["changes"] = {
                        name: "Version {0} will be reinstalled".format(version)
                    }
                    ret["comment"] = "Reinstall {0} {1}".format(full_name, version)
                else:
                    ret["comment"] = "{0} {1} is already installed".format(
                        name, version
                    )
                    if __opts__["test"]:
                        ret["result"] = None
                    return ret
            else:
                if allow_multiple:
                    ret["changes"] = {
                        name: "Version {0} will be installed side by side with "
                        "Version {1} if supported".format(version, installed_version)
                    }
                    ret["comment"] = "Install {0} {1} side-by-side with {0} {2}".format(
                        full_name, version, installed_version
                    )
                else:
                    ret["changes"] = {
                        name: "Version {0} will be installed over Version {1}".format(
                            version, installed_version
                        )
                    }
                    ret["comment"] = "Install {0} {1} over {0} {2}".format(
                        full_name, version, installed_version
                    )
                    force = True
        else:
            version = installed_version
            if force:
                ret["changes"] = {
                    name: "Version {0} will be reinstalled".format(version)
                }
                ret["comment"] = "Reinstall {0} {1}".format(full_name, version)
            else:
                ret["comment"] = "{0} {1} is already installed".format(name, version)
                if __opts__["test"]:
                    ret["result"] = None
                return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "The installation was tested"
        return ret

    # Install the package
    result = __salt__["chocolatey.install"](
        name=name,
        version=version,
        source=source,
        force=force,
        pre_versions=pre_versions,
        install_args=install_args,
        override_args=override_args,
        force_x86=force_x86,
        package_args=package_args,
        allow_multiple=allow_multiple,
    )

    if "Running chocolatey failed" not in result:
        ret["result"] = True
    else:
        ret["result"] = False

    if not ret["result"]:
        ret["comment"] = "Failed to install the package {0}".format(name)

    # Get list of installed packages after 'chocolatey.install'
    post_install = __salt__["chocolatey.list"](local_only=True)

    ret["changes"] = salt.utils.data.compare_dicts(pre_install, post_install)

    return ret


def uninstalled(name, version=None, uninstall_args=None, override_args=False):
    """
    Uninstalls a package

    name
      The name of the package to be uninstalled

    version
      Uninstalls a specific version of the package. Defaults to latest
      version installed.

    uninstall_args
      A list of uninstall arguments you want to pass to the uninstallation
      process i.e product key or feature list

    override_args
      Set to true if you want to override the original uninstall arguments (
      for the native uninstaller)in the package and use your own.
      When this is set to False uninstall_args will be appended to the end of
      the default arguments

    .. code-block:: yaml

      Removemypackage:
        chocolatey.uninstalled:
          - name: mypackage
          - version: '21.5'

    """

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    # Get list of currently installed packages
    pre_uninstall = __salt__["chocolatey.list"](local_only=True)

    # Determine if package is installed
    if name.lower() in [package.lower() for package in pre_uninstall.keys()]:
        try:
            ret["changes"] = {
                name: "{0} version {1} will be removed".format(
                    name, pre_uninstall[name][0]
                )
            }
        except KeyError:
            ret["changes"] = {name: "{0} will be removed".format(name)}
    else:
        ret["comment"] = "The package {0} is not installed".format(name)
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "The uninstall was tested"
        return ret

    # Uninstall the package
    result = __salt__["chocolatey.uninstall"](
        name, version, uninstall_args, override_args
    )

    if "Running chocolatey failed" not in result:
        ret["result"] = True
    else:
        ret["result"] = False

    if not ret["result"]:
        ret["comment"] = "Failed to uninstall the package {0}".format(name)

    # Get list of installed packages after 'chocolatey.uninstall'
    post_uninstall = __salt__["chocolatey.list"](local_only=True)

    ret["changes"] = salt.utils.data.compare_dicts(pre_uninstall, post_uninstall)

    return ret


def upgraded(
    name,
    version=None,
    source=None,
    force=False,
    pre_versions=False,
    install_args=None,
    override_args=False,
    force_x86=False,
    package_args=None,
):
    """
    Upgrades a package. Will install the package if not installed.

    .. versionadded:: 2018.3.0

    Args:

        name (str):
            The name of the package to be installed. Required.

        version (str):
            Install a specific version of the package. Defaults to latest
            version. If the version is greater than the one installed then the
            specified version will be installed. Default is ``None``.

        source (str):
            Chocolatey repository (directory, share or remote URL, feed).
            Defaults to the official Chocolatey feed. Default is ``None``.

        force (bool):
            ``True`` will reinstall an existing package with the same version.
            Default is ``False``.

        pre_versions (bool):
            ``True`` will nclude pre-release packages. Default is ``False``.

        install_args (str):
            Install arguments you want to pass to the installation process, i.e
            product key or feature list. Default is ``None``.

        override_args (bool):
            ``True`` will override the original install arguments (for the
            native installer) in the package and use those specified in
            ``install_args``. ``False`` will append install_args to the end of
            the default arguments. Default is ``False``.

        force_x86 (bool):
            ``True`` forces 32bit installation on 64 bit systems. Default is
            ``False``.

        package_args (str):
            Arguments you want to pass to the package. Default is ``None``.

    .. code-block:: yaml

        upgrade_some_package:
          chocolatey.upgraded:
            - name: packagename
            - version: '12.04'
            - source: 'mychocolatey/source'
    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    # Get list of currently installed packages
    pre_install = __salt__["chocolatey.list"](local_only=True)

    # Determine if there are changes
    # Package not installed
    if name.lower() not in [package.lower() for package in pre_install.keys()]:
        if version:
            ret["changes"][name] = "Version {0} will be installed".format(version)
            ret["comment"] = "Install version {0}".format(version)
        else:
            ret["changes"][name] = "Latest version will be installed"
            ret["comment"] = "Install latest version"

    # Package installed
    else:
        version_info = __salt__["chocolatey.version"](name, check_remote=True)

        # Get the actual full name out of version_info
        full_name = name
        for pkg in version_info:
            if name.lower() == pkg.lower():
                full_name = pkg

        installed_version = version_info[full_name]["installed"][0]

        # If version is not passed, use available... if available is available
        if not version:
            if "available" in version_info[full_name]:
                version = version_info[full_name]["available"][0]

        if version:
            # If installed version and new version are the same
            if salt.utils.versions.compare(
                ver1=installed_version, oper="==", ver2=version
            ):
                if force:
                    ret["changes"][name] = "Version {0} will be reinstalled".format(
                        version
                    )
                    ret["comment"] = "Reinstall {0} {1}".format(full_name, version)
                else:
                    ret["comment"] = "{0} {1} is already installed".format(
                        name, installed_version
                    )
            else:
                # If installed version is older than new version
                if salt.utils.versions.compare(
                    ver1=installed_version, oper="<", ver2=version
                ):
                    ret["changes"][
                        name
                    ] = "Version {0} will be upgraded to Version {1}".format(
                        installed_version, version
                    )
                    ret["comment"] = "Upgrade {0} {1} to {2}".format(
                        full_name, installed_version, version
                    )
                # If installed version is newer than new version
                else:
                    ret["comment"] = "{0} {1} (newer) is already installed".format(
                        name, installed_version
                    )
        # Catch all for a condition where version is not passed and there is no
        # available version
        else:
            ret["comment"] = "No version found to install"

    # Return if there are no changes to be made
    if not ret["changes"]:
        return ret

    # Return if running in test mode
    if __opts__["test"]:
        ret["result"] = None
        return ret

    # Install the package
    result = __salt__["chocolatey.upgrade"](
        name=name,
        version=version,
        source=source,
        force=force,
        pre_versions=pre_versions,
        install_args=install_args,
        override_args=override_args,
        force_x86=force_x86,
        package_args=package_args,
    )

    if "Running chocolatey failed" not in result:
        ret["comment"] = "Package {0} upgraded successfully".format(name)
        ret["result"] = True
    else:
        ret["comment"] = "Failed to upgrade the package {0}".format(name)
        ret["result"] = False

    # Get list of installed packages after 'chocolatey.install'
    post_install = __salt__["chocolatey.list"](local_only=True)

    # Prior to this, ret['changes'] would have contained expected changes,
    # replace them with the actual changes now that we have completed the
    # installation.
    ret["changes"] = salt.utils.data.compare_dicts(pre_install, post_install)

    return ret
