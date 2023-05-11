import logging

import salt.utils.platform
import salt.utils.win_reg

log = logging.getLogger(__name__)

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
    cmd.append("Sort-Object PackageFullName")
    if not field:
        cmd.append("Select Name, Version, PackageFullName, IsBundle, IsFramework")
        return __utils__["win_pwsh.run_dict"](" | ".join(cmd))
    else:
        return _pkg_list(__utils__["win_pwsh.run_dict"](" | ".join(cmd)), field)


def remove(query=None, include_store=False, frameworks=False, bundles=True):
    packages = get(
        query=query,
        field=None,
        include_store=include_store,
        frameworks=frameworks,
        bundles=bundles,
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
                remove_name = bundle["PackageFullName"]

        log.debug("Removing package: %s", remove_name)
        __utils__["win_pwsh.run_dict"](
            f"Remove-AppxPackage -AllUsers -Package {remove_name}"
        )

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
