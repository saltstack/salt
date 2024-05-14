"""
Manage Windows Packages using Chocolatey
.. versionadded:: 2016.3.0

.. note::
    Chocolatey pulls data from the Chocolatey internet database to determine
    current versions, find available versions, etc. This is normally a slow
    operation and may be optimized by specifying a local, smaller chocolatey
    repo.
"""

import salt.utils.data
import salt.utils.versions
from salt.exceptions import CommandExecutionError, SaltInvocationError


def __virtual__():
    """
    Load only if chocolatey is loaded
    """
    if "chocolatey.install" in __salt__:
        return "chocolatey"
    return False, "chocolatey module could not be loaded"


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
    execution_timeout=None,
):
    """
    Installs a package if not already installed

    Args:

        name (str):
            The name of the package to be installed. Required.

        version (str):
            Install a specific version of the package. Defaults to the latest
            version. If the version is different to the one installed, then the
            specified version will be installed. Default is ``None``.

        source (str):
            Chocolatey repository (directory, share or remote URL, feed).
            ``None`` defaults to the official Chocolatey feed. Default is
            ``None``.

        force (bool):
            Reinstall the current version of an existing package. Do not use
            with ``allow_multiple``. Default is ``False``.

        pre_versions (bool):
            Include pre-release packages. Default is ``False``.

        install_args (str):
            Install arguments you want to pass to the installation process, i.e.
            product key or feature list. Default is ``None``.

        override_args (bool):
            Set to ``True`` to override the original install arguments (for the
            native installer) in the package and use your own. When this is set
            to ``False``, install_args will be appended to the end of the
            default arguments. Default is ``False``.

        force_x86 (bool):
            Force x86 (32bit) installation on 64bit systems. Default is
            ``False``.

        package_args (str):
            Arguments you want to pass to the package. Default is ``None``.

        allow_multiple (bool):
            Allow multiple versions of the package to be installed. Do not use
            with ``force``. Does not work with all packages. Default is
            ``False``.

            .. versionadded:: 2017.7.0

        execution_timeout (str):
            Chocolatey execution timeout value you want to pass to the
            installation process. Default is ``None``.

    Example:

    .. code-block:: yaml

        install_some_package:
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
            ret["comment"] = f"{name} {version} will be installed"
        else:
            ret["comment"] = f"Latest version of {name} will be installed"

    # Package installed
    else:
        version_info = __salt__["chocolatey.version"](
            name=name, check_remote=True, source=source
        )

        full_name = name
        for pkg in version_info:
            if name.lower() == pkg.lower():
                full_name = pkg

        installed_version = version_info[full_name].get("installed")[0]

        if version:
            if salt.utils.versions.compare(
                ver1=installed_version, oper="==", ver2=version
            ):
                if force:
                    ret["comment"] = f"{name} {version} will be reinstalled"
                else:
                    ret["comment"] = f"{name} {version} is already installed"
            else:
                if allow_multiple:
                    ret["comment"] = (
                        f"{name} {version} will be installed side by side with {name} {installed_version} if supported"
                    )
                else:
                    ret["comment"] = (
                        f"{name} {version} will be installed over {name} {installed_version}"
                    )
                    force = True
        else:
            version = installed_version
            if force:
                ret["comment"] = f"{name} {version} will be reinstalled"
            else:
                ret["comment"] = f"{name} {version} is already installed"
                return ret

    if __opts__["test"]:
        ret["result"] = None
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
        execution_timeout=execution_timeout,
    )

    if "Running chocolatey failed" not in result:
        ret["comment"] = f"{name} installed successfully"
        ret["result"] = True
    else:
        ret["comment"] = f"Failed to install {name}"
        ret["result"] = False

    # Get list of installed packages after 'chocolatey.install'
    post_install = __salt__["chocolatey.list"](local_only=True)

    ret["changes"] = salt.utils.data.compare_dicts(pre_install, post_install)

    return ret


def uninstalled(name, version=None, uninstall_args=None, override_args=False):
    """
    Uninstalls a chocolatey package

    Args:

        name (str):
            The name of the package to be uninstalled. Required.

        version (str):
            Uninstalls a specific version of the package. Defaults to the latest
            version installed.

        uninstall_args (str):
            A list of uninstall arguments you want to pass to the uninstallation
            process, i.e. product key or feature list

        override_args (str):
            Set to ``True`` if you want to override the original uninstall
            arguments (for the native uninstaller) in the package and use your
            own. When this is set to ``False``, uninstall_args will be appended
            to the end of the default arguments

    Example:

    .. code-block:: yaml

      remove_my_package:
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
            ret["comment"] = f"{name} {pre_uninstall[name][0]} will be removed"
        except KeyError:
            ret["comment"] = f"{name} will be removed"
    else:
        ret["comment"] = f"The package {name} is not installed"
        return ret

    if __opts__["test"]:
        ret["result"] = None
        return ret

    # Uninstall the package
    result = __salt__["chocolatey.uninstall"](
        name, version, uninstall_args, override_args
    )

    if "Running chocolatey failed" not in result:
        ret["comment"] = f"{name} uninstalled successfully"
        ret["result"] = True
    else:
        ret["comment"] = f"Failed to uninstall {name}"
        ret["result"] = False

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
    Upgrades a chocolatey package. Will install the package if not installed.

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
            ``True`` will include pre-release packages. Default is ``False``.

        install_args (str):
            Install arguments you want to pass to the installation process, i.e
            product key or feature list. Default is ``None``.

        override_args (bool):
            ``True`` will override the original install arguments (for the
            native installer) in the package and use those specified in
            ``install_args``. ``False`` will append install_args to the end of
            the default arguments. Default is ``False``.

        force_x86 (bool):
            ``True`` forces 32bit installation on 64bit systems. Default is
            ``False``.

        package_args (str):
            Arguments you want to pass to the package. Default is ``None``.

    Example:

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
            ret["comment"] = f"{name} {version} will be installed"
        else:
            ret["comment"] = f"Latest version of {name} will be installed"

    # Package installed
    else:
        version_info = __salt__["chocolatey.version"](
            name=name, check_remote=True, source=source
        )

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
                    ret["comment"] = f"{name} {version} will be reinstalled"
                else:
                    ret["comment"] = f"{name} {version} is already installed"
                    return ret
            else:
                # If installed version is older than new version
                if salt.utils.versions.compare(
                    ver1=installed_version, oper="<", ver2=version
                ):
                    ret["comment"] = (
                        f"{name} {installed_version} will be upgraded to version {version}"
                    )
                # If installed version is newer than new version
                else:
                    ret["comment"] = (
                        f"{name} {installed_version} (newer) is already installed"
                    )
                    return ret
        # Catch all for a condition where version is not passed and there is no
        # available version
        else:
            ret["comment"] = "No version found to install"
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
        ret["comment"] = f"{name} upgraded successfully"
        ret["result"] = True
    else:
        ret["comment"] = f"Failed to upgrade {name}"
        ret["result"] = False

    # Get list of installed packages after 'chocolatey.install'
    post_install = __salt__["chocolatey.list"](local_only=True)

    # Prior to this, ret['changes'] would have contained expected changes,
    # replace them with the actual changes now that we have completed the
    # installation.
    ret["changes"] = salt.utils.data.compare_dicts(pre_install, post_install)

    return ret


def source_present(
    name, source_location, username=None, password=None, force=False, priority=None
):
    """
    Adds a Chocolatey source if not already present.

    Args:

        name (str):
            The name of the source to be added as a chocolatey repository.

        source (str):
            Location of the source you want to work with.

        username (str):
            The username for a chocolatey source that needs authentication
            credentials.

        password (str):
            The password for a chocolatey source that needx authentication
            credentials.

        force (bool):
            Salt will not modify an existing repository with the same name. Set
            this option to ``True`` to update an existing repository.

        priority (int):
            The priority order of this source as compared to other sources.
            Lower is better. Defaults to 0 (no priority). All priorities
            above 0 will be evaluated first, then zero-based values will be
            evaluated in config file order.

    Example:

    .. code-block:: yaml

        add_some_source:
          chocolatey.source_present:
            - name: reponame
            - source: https://repo.exemple.com
            - username: myuser
            - password: mypassword
            - priority: 100
    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    # Get list of currently present sources
    pre_install = __salt__["chocolatey.list_sources"]()

    # Determine action
    # Source with same name not present
    if name.lower() not in [present.lower() for present in pre_install.keys()]:
        ret["comment"] = f"{name} will be added"

    # Source with same name already present
    else:
        if force:
            ret["comment"] = f"{name} will be updated"
        else:
            ret["comment"] = f"{name} is already present"
            return ret

    if __opts__["test"]:
        ret["result"] = None
        return ret

    # Add the source
    result = __salt__["chocolatey.add_source"](
        name=name,
        source_location=source_location,
        username=username,
        password=password,
        priority=priority,
    )

    if "Running chocolatey failed" not in result:
        ret["result"] = True
        ret["comment"] = f"Source {name} added successfully"
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to add the source {name}"

    # Get list of present sources after 'chocolatey.add_source'
    post_install = __salt__["chocolatey.list_sources"]()

    ret["changes"] = salt.utils.data.compare_dicts(pre_install, post_install)

    return ret


def bootstrapped(name, force=False, source=None, version=None):
    """
    .. versionadded:: 3007.1

    Ensure chocolatey is installed on the system.

    You can't upgrade an existing installation with this state. You must use
    chocolatey to upgrade chocolatey.

    For example:

    .. code-block:: bash

        choco upgrade chocolatey --version 2.2.0

    Args:

        name (str):
            The name of the state that installs chocolatey. Required for all
            states. This is ignored.

        force (bool):
            Run the bootstrap process even if Chocolatey is found in the path.

            .. note::
                If chocolatey is already installed this will just re-run the
                install script over the existing version. The ``version``
                parameter is ignored.

        source (str):
            The location of the ``.nupkg`` file or ``.ps1`` file to run from an
            alternate location. This can be one of the following types of URLs:

            - salt://
            - http(s)://
            - ftp://
            - file:// - A local file on the system

        version (str):
            The version of chocolatey to install. The latest version is
            installed if this value is ``None``. Default is ``None``

    Example:

    .. code-block:: yaml

        # Bootstrap the latest version of chocolatey
        bootstrap_chocolatey:
          chocolatey.bootstrapped

        # Bootstrap the latest version of chocolatey
        # If chocolatey is already present, re-run the install script
        bootstrap_chocolatey:
          chocolatey.bootstrapped:
            - force: True

        # Bootstrap Chocolatey version 1.4.0
        bootstrap_chocolatey:
          chocolatey.bootstrapped:
            - version: 1.4.0

        # Bootstrap Chocolatey from a local file
        bootstrap_chocolatey:
          chocolatey.bootstrapped:
            - source: C:\\Temp\\chocolatey.nupkg

        # Bootstrap Chocolatey from a file on the salt master
        bootstrap_chocolatey:
          chocolatey.bootstrapped:
            - source: salt://Temp/chocolatey.nupkg
    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    try:
        old = __salt__["chocolatey.chocolatey_version"]()
    except CommandExecutionError:
        old = None

    # Try to predict what will happen
    if old:
        if force:
            ret["comment"] = (
                f"Chocolatey {old} will be reinstalled\n"
                'Use "choco upgrade chocolatey --version 2.1.0" to change the version'
            )
        else:
            # You can't upgrade chocolatey using the install script, you have to use
            # chocolatey itself
            ret["comment"] = (
                f"Chocolatey {old} is already installed.\n"
                'Use "choco upgrade chocolatey --version 2.1.0" to change the version'
            )
            return ret

    else:
        if version is None:
            ret["comment"] = "The latest version of Chocolatey will be installed"
        else:
            ret["comment"] = f"Chocolatey {version} will be installed"

    if __opts__["test"]:
        ret["result"] = None
        return ret

    __salt__["chocolatey.bootstrap"](force=force, source=source, version=version)

    try:
        new = __salt__["chocolatey.chocolatey_version"](refresh=True)
    except CommandExecutionError:
        new = None

    if new is None:
        ret["comment"] = f"Failed to install chocolatey {new}"
        ret["result"] = False
    else:
        if salt.utils.versions.version_cmp(old, new) == 0:
            ret["comment"] = f"Re-installed chocolatey {new}"
        else:
            ret["comment"] = f"Installed chocolatey {new}"
            ret["changes"] = {"old": old, "new": new}

    return ret


def unbootstrapped(name):
    """
    .. versionadded:: 3007.1

    Ensure chocolatey is removed from the system.

    Args:

        name (str):
            The name of the state that uninstalls chocolatey. Required for all
            states. This is ignored.

    Example:

    .. code-block:: yaml

        # Uninstall chocolatey
        uninstall_chocolatey:
          chocolatey.unbootstrapped

    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    try:
        old = __salt__["chocolatey.chocolatey_version"]()
    except CommandExecutionError:
        old = None

    if old is None:
        ret["comment"] = "Chocolatey not found on this system"
        return ret

    ret["comment"] = f"Chocolatey {old} will be removed"

    if __opts__["test"]:
        ret["result"] = None
        return ret

    __salt__["chocolatey.unbootstrap"]()

    try:
        new = __salt__["chocolatey.chocolatey_version"](refresh=True)
    except CommandExecutionError:
        new = None

    if new is None:
        ret["comment"] = f"Uninstalled chocolatey {old}"
        ret["changes"] = {"new": new, "old": old}
    else:
        ret["comment"] = f"Failed to uninstall chocolatey {old}\nFound version {new}"
        ret["result"] = False

    return ret
