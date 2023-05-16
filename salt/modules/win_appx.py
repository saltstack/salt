import fnmatch
import logging

import salt.utils.platform
import salt.utils.win_reg

log = logging.getLogger(__name__)

CURRENTVERSION_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion"
DEPROVISIONED_KEY = fr"{CURRENTVERSION_KEY}\Appx\AppxAllUserStore\Deprovisioned"
__virtualname__ = "appx"


def __virtual__():
    """
    Load only on Windows
    """
    if not salt.utils.platform.is_windows():
        return False, "Module appx: module only works on Windows systems."

    return __virtualname__


def _pkg_list(raw, field="PackageFullName"):
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


def get(query=None, field="Name", include_store=False, frameworks=False, bundles=True):
    """
    Get a list of Microsoft Store packages installed on the system.

    Args:

        query (str):
            The query string to use to filter packages to be list. The string
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
        cmd.append("Select Name, Version, PackageFullName, PackageFamilyName, IsBundle, IsFramework")
        return __utils__["win_pwsh.run_dict"](" | ".join(cmd))
    else:
        cmd.append(f"Sort-Object {field}")
        return _pkg_list(__utils__["win_pwsh.run_dict"](" | ".join(cmd)), field)


def remove(query=None, include_store=False, frameworks=False, deprovision_only=False):
    """
    Removes Microsoft Store packages from the system. If the package is part of
    a bundle, the entire bundle will be removed.

    By default, this function will remove the package for all users on the
    system. It will also deprovision the packages so that it isn't re-installed
    by later system updates. To only deprovision a package, set
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
                Use the ``appx.get`` function to make sure your query is
                returning what you expect

        include_store (bool):
            Include the Microsoft Store in the results of the query to be
            removed. Use this with caution. It difficult to reinstall the
            Microsoft Store once it has been removed with this function. Default
            is ``False``

        frameworks (bool):
            Include frameworks in the results of the query to be removed.
            Default is ``False``

        deprovision_only (bool):
            Deprovision the package. The package will be removed from the
            current user and added to the list of deprovisioned packages. The
            package will not be re-installed in future system updates. New users
            of the system will not have the package installed. However, the
            package will still be installed for existing users. Default is
            ``False``

    Returns:
        bool: ``True`` if successful, ``None`` if no packages found

    Raises:
        CommandExecutionError: On errors encountered removing the package

    """
    packages = get(
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
            bundle = get(
                query=f'{package["Name"]}*',
                field=None,
                include_store=include_store,
                frameworks=frameworks,
                bundles=True,
            )
            if bundle and bundle["IsBundle"]:
                log.debug(f'Found bundle: {bundle["PackageFullName"]}')
                remove_name = bundle["PackageFullName"]

        if deprovision_only:
            log.debug("Deprovisioning package: %s", remove_name)
            remove_cmd = f"Remove-AppxProvisionedPackage -Online -PackageName {remove_name}"
        else:
            log.debug("Removing package: %s", remove_name)
            remove_cmd = f"Remove-AppxPackage -AllUsers -Package {remove_name}"
        __utils__["win_pwsh.run_dict"](remove_cmd)

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


def get_deprovisioned(query=None):
    ret = salt.utils.win_reg.list_keys(hive="HKLM", key=f"{DEPROVISIONED_KEY}")
    if query is None:
        return ret
    return fnmatch.filter(ret, query)



def reprovision(package_name):
    key = f"{DEPROVISIONED_KEY}\\{package_name}"
    if salt.utils.win_reg.key_exists(hive="HKLM", key=key):
        log.debug(f"Deprovisioned app found: {package_name}")
        ret = salt.utils.win_reg.delete_key_recursive(hive="HKLM", key=key)
        return not ret["Failed"]
    log.debug(f"Deprovisioned app not found: {package_name}")
    return None
