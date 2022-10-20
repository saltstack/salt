"""
Dot NET functions

.. versionadded:: 3001
"""

import salt.utils.platform
import salt.utils.win_reg as win_reg
from salt.utils.versions import LooseVersion

__virtualname__ = "dotnet"


# Although utils are often directly imported, it is also possible to use the
# loader.
def __virtual__():
    """
    Only load if platform is Windows
    """
    if not salt.utils.platform.is_windows():
        return False, "This utility only works on Windows"

    return __virtualname__


def versions():
    """
    Figure out what versions of .NET are installed on the system

    Returns:
        dict: A dictionary containing two keys:
            - versions: A list of versions installed on the system
            - details: A dictionary with details about the versions installed on
              the system
    """
    hive = "HKLM"
    key = "SOFTWARE\\Microsoft\\NET Framework Setup\\NDP"
    ver_keys = win_reg.list_keys(hive=hive, key=key)

    def dotnet_45_plus_versions(release):
        if release >= 528040:
            return "4.8"
        if release >= 461808:
            return "4.7.2"
        if release >= 461308:
            return "4.7.1"
        if release >= 460798:
            return "4.7"
        if release >= 394802:
            return "4.6.2"
        if release >= 394254:
            return "4.6.1"
        if release >= 393295:
            return "4.6"
        if release >= 379893:
            return "4.5.2"
        if release >= 378675:
            return "4.5.1"
        if release >= 378389:
            return "4.5"

    return_dict = {"versions": [], "details": {}}
    for ver_key in ver_keys:

        if ver_key.startswith("v"):
            if win_reg.value_exists(
                hive=hive, key="\\".join([key, ver_key]), vname="Version"
            ):
                # https://docs.microsoft.com/en-us/dotnet/framework/migration-guide/how-to-determine-which-versions-are-installed#find-net-framework-versions-1-4-with-codep
                install = win_reg.read_value(
                    hive=hive, key="\\".join([key, ver_key]), vname="Install"
                )["vdata"]
                if not install:
                    continue
                version = win_reg.read_value(
                    hive=hive, key="\\".join([key, ver_key]), vname="Version"
                )["vdata"]
                sp = win_reg.read_value(
                    hive=hive, key="\\".join([key, ver_key]), vname="SP"
                )["vdata"]
            elif win_reg.value_exists(
                hive=hive, key="\\".join([key, ver_key, "Full"]), vname="Release"
            ):
                # https://docs.microsoft.com/en-us/dotnet/framework/migration-guide/how-to-determine-which-versions-are-installed#find-net-framework-versions-45-and-later-with-code
                install = win_reg.read_value(
                    hive=hive, key="\\".join([key, ver_key, "Full"]), vname="Install"
                )["vdata"]
                if not install:
                    continue
                version = dotnet_45_plus_versions(
                    win_reg.read_value(
                        hive=hive,
                        key="\\".join([key, ver_key, "Full"]),
                        vname="Release",
                    )["vdata"]
                )
                sp = "N/A"
            else:
                continue

            service_pack = " SP{}".format(sp) if sp != "N/A" else ""
            return_dict["versions"].append(version)
            return_dict["details"][ver_key] = {
                "version": version,
                "service_pack": sp,
                "full": "{}{}".format(version, service_pack),
            }

    return return_dict


def versions_list():
    """
    Get a sorted list of .NET versions installed on the system

    Returns:
        list: A sorted list of versions installed on the system
    """
    return sorted(versions()["versions"])


def versions_details():
    """
    Get the details for all versions of .NET installed on a system

    Returns:
        dict: A dictionary of details for each version on the system. Contains
        the following keys:
            - version: The version installed
            - service_pack: The service pack for the version installed
            - full: The full version name including the service pack
    """
    return versions()["details"]


def version_at_least(version):
    """
    Check that the system contains a version of .NET that is at least the
    passed version.

    Args:

        version (str): The version to check for

    Returns:
        bool: ``True`` if the system contains a version of .NET that is at least
        the passed version, otherwise ``False``
    """
    for dotnet_version in versions_list():
        if LooseVersion(dotnet_version) >= LooseVersion(str(version)):
            return True
    return False
