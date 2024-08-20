"""
Manage provisioned apps
=======================

.. versionadded:: 3007.0

Provisioned apps are part of the image and are installed for every user the
first time the user logs on. Provisioned apps are also updated and sometimes
reinstalled when the system is updated.

Apps removed with this module will remove the app for all users and deprovision
the app. Deprovisioned apps will neither be installed for new users nor will
they be upgraded.

An app removed with this module can only be re-provisioned on the machine, but
it can't be re-installed for all users. Also, once a package has been
deprovisioned, the only way to reinstall it is to download the package. This is
difficult. The steps are outlined below:

1. Obtain the Microsoft Store URL for the app:
    - Open the page for the app in the Microsoft Store
    - Click the share button and copy the URL

2. Look up the packages on https://store.rg-adguard.net/:
    - Ensure ``URL (link)`` is selected in the first dropdown
    - Paste the URL in the search field
    - Ensure Retail is selected in the 2nd dropdown
    - Click the checkmark button

This should return a list of URLs for the package and all dependencies for all
architectures. Download the package and all dependencies for your system
architecture. These will usually have one of the following file extensions:

- ``.appx``
- ``.appxbundle``
- ``.msix``
- ``.msixbundle``

Dependencies will need to be installed first.

Not all packages can be found this way, but it seems like most of them can.

Use the ``appx.install`` function to provision the new app.
"""

import fnmatch
import logging

import salt.utils.platform
import salt.utils.win_pwsh
import salt.utils.win_reg
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

CURRENT_VERSION_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion"
DEPROVISIONED_KEY = rf"{CURRENT_VERSION_KEY}\Appx\AppxAllUserStore\Deprovisioned"

__virtualname__ = "appx"
__func_alias__ = {"list_": "list"}


def __virtual__():
    """
    Load only on Windows
    """
    if not salt.utils.platform.is_windows():
        return False, "Appx module: Only available on Windows systems"

    pwsh_info = __salt__["cmd.shell_info"](shell="powershell", list_modules=False)
    if not pwsh_info["installed"]:
        return False, "Appx module: PowerShell not available"

    return __virtualname__


def _pkg_list(raw, field="Name"):
    result = []
    if raw:
        if isinstance(raw, list):
            for pkg in raw:
                result.append(pkg[field])
        else:
            result.append(raw[field])
    else:
        result = None
    return result


def list_(
    query=None, field="Name", include_store=False, frameworks=False, bundles=True
):
    """
    Get a list of Microsoft Store packages installed on the system.

    Args:

        query (str):
            The query string to use to filter packages to be listed. The string
            can match multiple packages. ``None`` will return all packages. Here
            are some example strings:

            - ``*teams*`` - Returns Microsoft Teams
            - ``*zune*`` - Returns Windows Media Player and ZuneVideo
            - ``*zuneMusic*`` - Only returns Windows Media Player
            - ``*xbox*`` - Returns all xbox packages, there are 5 by default
            - ``*`` - Returns everything but the Microsoft Store, unless
              ``include_store=True``

        field (str):
            This function returns a list of packages on the system. It can
            display a short name or a full name. If ``None`` is passed, a
            dictionary will be returned with some common fields. The default is
            ``Name``. Valid options are any fields returned by the powershell
            command ``Get-AppxPackage``. Here are some useful fields:

            - Name
            - Version
            - PackageFullName
            - PackageFamilyName

        include_store (bool):
            Include the Microsoft Store in the results. Default is ``False``

        frameworks (bool):
            Include frameworks in the results. Default is ``False``

        bundles (bool):
            If ``True``, this will return application bundles only. If
            ``False``, this will return individual packages only, even if they
            are part of a bundle.

    Returns:
        list: A list of packages ordered by the string passed in field
        list: A list of dictionaries of package information if field is ``None``

    Raises:
        CommandExecutionError: If an error is encountered retrieving packages

    CLI Example:

    .. code-block:: bash

        # List installed apps that contain the word "candy"
        salt '*' appx.list *candy*

        # Return more information about the package
        salt '*' appx.list *candy* field=None

        # List all installed apps, including the Microsoft Store
        salt '*' appx.list include_store=True

        # List all installed apps, including frameworks
        salt '*' appx.list frameworks=True

        # List all installed apps that are bundles
        salt '*' appx.list bundles=True
    """
    cmd = []

    if bundles:
        cmd_str = "Get-AppxPackage -AllUsers -PackageTypeFilter Bundle"
    else:
        cmd_str = "Get-AppxPackage -AllUsers"

    if query:
        cmd.append(f"{cmd_str} -Name {query}")
    else:
        cmd.append(f"{cmd_str}")
    if not include_store:
        cmd.append('Where-Object {$_.name -notlike "Microsoft.WindowsStore*"}')
    if not frameworks:
        cmd.append("Where-Object -Property IsFramework -eq $false")
    cmd.append("Where-Object -Property NonRemovable -eq $false")
    if not field:
        cmd.append("Sort-Object Name")
        cmd.append(
            "Select Name, Version, PackageFullName, PackageFamilyName, IsBundle, IsFramework"
        )
        return salt.utils.win_pwsh.run_dict(" | ".join(cmd))
    else:
        cmd.append(f"Sort-Object {field}")
        return _pkg_list(salt.utils.win_pwsh.run_dict(" | ".join(cmd)), field)


def remove(query=None, include_store=False, frameworks=False, deprovision_only=False):
    """
    Removes Microsoft Store packages from the system. If the package is part of
    a bundle, the entire bundle will be removed.

    This function removes the package for all users on the system. It also
    deprovisions the package so that it isn't re-installed by later system
    updates. To only deprovision a package and not remove it for all users, set
    ``deprovision_only=True``.

    Args:

        query (str):
            The query string to use to select the packages to be removed. If the
            string matches multiple packages, they will all be removed. Here are
            some example strings:

            - ``*teams*`` - Remove Microsoft Teams
            - ``*zune*`` - Remove Windows Media Player and ZuneVideo
            - ``*zuneMusic*`` - Only remove Windows Media Player
            - ``*xbox*`` - Remove all xbox packages, there are 5 by default
            - ``*`` - Remove everything but the Microsoft Store, unless
              ``include_store=True``

            .. note::
                Use the ``appx.list`` function to make sure your query is
                returning what you expect. Then use the same query to remove
                those packages

        include_store (bool):
            Include the Microsoft Store in the results of the query to be
            removed. Use this with caution. It is difficult to reinstall the
            Microsoft Store once it has been removed with this function. Default
            is ``False``

        frameworks (bool):
            Include frameworks in the results of the query to be removed.
            Default is ``False``

        deprovision_only (bool):
            Only deprovision the package. The package will be removed from the
            current user and added to the list of deprovisioned packages. The
            package will not be re-installed in future system updates. New users
            of the system will not have the package installed. However, the
            package will still be installed for existing users. Default is
            ``False``

    Returns:
        bool: ``True`` if successful, ``None`` if no packages found

    Raises:
        CommandExecutionError: On errors encountered removing the package

    CLI Example:

    .. code-block:: bash

        salt "*" appx.remove *candy*
    """
    packages = list_(
        query=query,
        field=None,
        include_store=include_store,
        frameworks=frameworks,
        bundles=False,
    )

    def remove_package(package):
        remove_name = package["PackageFullName"]
        # If the package is part of a bundle with the same name, removal will
        # fail. Let's make sure it's a bundle
        if not package["IsBundle"]:
            # If it's not a bundle, let's see if we can find the bundle
            bundle = list_(
                query=f'{package["Name"]}*',
                field=None,
                include_store=include_store,
                frameworks=frameworks,
                bundles=True,
            )
            if isinstance(bundle, list):
                # There may be multiple packages that match the query
                # Let's remove each one individually
                for item in bundle:
                    remove_package(item)
            else:
                if bundle and bundle["IsBundle"]:
                    log.debug("Found bundle: %s", bundle["PackageFullName"])
                    remove_name = bundle["PackageFullName"]
        if deprovision_only:
            log.debug("Deprovisioning package: %s", remove_name)
            remove_cmd = (
                f"Remove-AppxProvisionedPackage -Online -PackageName {remove_name}"
            )
        else:
            log.debug("Removing package: %s", remove_name)
            remove_cmd = f"Remove-AppxPackage -AllUsers -Package {remove_name}"
        try:
            salt.utils.win_pwsh.run_dict(remove_cmd)
        except CommandExecutionError as exc:
            # Some packages may be in a partially updated state
            # In that case, there will be 2 entries with the same name
            # The old one will not have an installer and will throw an error
            # We should be safe just logging the message
            # This is really hard to replicate
            log.debug("There was an error removing package: %s", remove_name)
            log.debug(exc)

    if isinstance(packages, list):
        log.debug("Removing %s packages", len(packages))
        for pkg in packages:
            remove_package(package=pkg)
    elif packages:
        log.debug("Removing a single package")
        remove_package(package=packages)
    else:
        log.debug("Package not found: %s", query)
        return None

    return True


def list_deprovisioned(query=None):
    """
    When an app is deprovisioned, a registry key is created that will keep it
    from being reinstalled during a major system update. This function returns a
    list of keys for apps that have been deprovisioned.

    Args:

        query (str):
            The query string to use to filter packages to be listed. The string
            can match multiple packages. ``None`` will return all packages. Here
            are some example strings:

            - ``*teams*`` - Returns Microsoft Teams
            - ``*zune*`` - Returns Windows Media Player and ZuneVideo
            - ``*zuneMusic*`` - Only returns Windows Media Player
            - ``*xbox*`` - Returns all xbox packages, there are 5 by default
            - ``*`` - Returns everything but the Microsoft Store, unless
              ``include_store=True``

    Returns:
        list: A list of packages matching the query criteria

    CLI Example:

    .. code-block:: bash

        salt "*" appx.list_deprovisioned *zune*
    """
    ret = salt.utils.win_reg.list_keys(hive="HKLM", key=f"{DEPROVISIONED_KEY}")
    if query is None:
        return ret
    return fnmatch.filter(ret, query)


def install(package):
    """
    This function uses ``dism`` to provision a package. This means that it will
    be made a part of the online image and added to new users on the system. If
    a package has dependencies, those must be installed first.

    If a package installed using this function has been deprovisioned
    previously, the registry entry marking it as deprovisioned will be removed.

    .. NOTE::
        There is no ``appx.present`` state. Instead, use the
        ``dism.provisioned_package_installed`` state.

    Args:

        package (str):
            The full path to the package to install. Can be one of the
            following:

            - ``.appx`` or ``.appxbundle``
            - ``.msix`` or ``.msixbundle``
            - ``.ppkg``

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt "*" appx.install "C:\\Temp\\Microsoft.ZuneMusic.msixbundle"
    """
    # I don't see a way to make the app installed for existing users on
    # the system. The best we can do is provision the package for new
    # users
    ret = __salt__["dism.add_provisioned_package"](package)
    return ret["retcode"] == 0
