"""
Manage Windows features via the ServerManager powershell module. Can list
available and installed roles/features. Can install and remove roles/features.

:maintainer:    Shane Lee <slee@saltstack.com>
:platform:      Windows Server 2008R2 or greater
:depends:       PowerShell module ``ServerManager``
"""


import logging
import shlex

import salt.utils.json
import salt.utils.platform
import salt.utils.powershell
import salt.utils.versions
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

__virtualname__ = "win_servermanager"


def __virtual__():
    """
    Load only on windows with servermanager module
    """
    if not salt.utils.platform.is_windows():
        return (
            False,
            "Module win_servermanager: module only works on Windows systems.",
        )

    if salt.utils.versions.version_cmp(__grains__["osversion"], "6.1.7600") == -1:
        return (
            False,
            "Failed to load win_servermanager module: "
            "Requires Remote Server Administration Tools which "
            "is only available on Windows 2008 R2 and later.",
        )

    if not salt.utils.powershell.module_exists("ServerManager"):
        return (
            False,
            "Failed to load win_servermanager module: "
            "ServerManager module not available. "
            "May need to install Remote Server Administration Tools.",
        )

    return __virtualname__


def _pshell_json(cmd, cwd=None):
    """
    Execute the desired powershell command and ensure that it returns data
    in JSON format and load that into python
    """
    cmd = "Import-Module ServerManager; {}".format(cmd)
    if "convertto-json" not in cmd.lower():
        cmd = "{} | ConvertTo-Json".format(cmd)
    log.debug("PowerShell: %s", cmd)
    ret = __salt__["cmd.run_all"](cmd, shell="powershell", cwd=cwd)

    if "pid" in ret:
        del ret["pid"]

    if ret.get("stderr", ""):
        error = ret["stderr"].splitlines()[0]
        raise CommandExecutionError(error, info=ret)

    if "retcode" not in ret or ret["retcode"] != 0:
        # run_all logs an error to log.error, fail hard back to the user
        raise CommandExecutionError(
            "Issue executing PowerShell {}".format(cmd), info=ret
        )

    # Sometimes Powershell returns an empty string, which isn't valid JSON
    if ret["stdout"] == "":
        ret["stdout"] = "{}"

    try:
        ret = salt.utils.json.loads(ret["stdout"], strict=False)
    except ValueError:
        raise CommandExecutionError("No JSON results from PowerShell", info=ret)
    return ret


def list_available():
    """
    List available features to install

    Returns:
        str: A list of available features as returned by the
        ``Get-WindowsFeature`` PowerShell command

    CLI Example:

    .. code-block:: bash

        salt '*' win_servermanager.list_available
    """
    cmd = (
        "Import-Module ServerManager; "
        "Get-WindowsFeature "
        "-ErrorAction SilentlyContinue "
        "-WarningAction SilentlyContinue"
    )
    return __salt__["cmd.shell"](cmd, shell="powershell")


def list_installed():
    """
    List installed features. Supported on Windows Server 2008 and Windows 8 and
    newer.

    Returns:
        dict: A dictionary of installed features

    CLI Example:

    .. code-block:: bash

        salt '*' win_servermanager.list_installed
    """
    cmd = (
        "Get-WindowsFeature "
        "-ErrorAction SilentlyContinue "
        "-WarningAction SilentlyContinue "
        "| Select DisplayName,Name,Installed"
    )
    features = _pshell_json(cmd)

    ret = {}
    for entry in features:
        if entry["Installed"]:
            ret[entry["Name"]] = entry["DisplayName"]

    return ret


def install(feature, recurse=False, restart=False, source=None, exclude=None):
    r"""
    Install a feature

    .. note::
        Some features require reboot after un/installation, if so until the
        server is restarted other features can not be installed!

    .. note::
        Some features take a long time to complete un/installation, set -t with
        a long timeout

    Args:

        feature (str, list):
            The name of the feature(s) to install. This can be a single feature,
            a string of features in a comma delimited list (no spaces), or a
            list of features.

            .. versionadded:: 2018.3.0
                Added the ability to pass a list of features to be installed.

        recurse (Options[bool]):
            Install all sub-features. Default is False

        restart (Optional[bool]):
            Restarts the computer when installation is complete, if required by
            the role/feature installed. Will also trigger a reboot if an item
            in ``exclude`` requires a reboot to be properly removed. Default is
            False

        source (Optional[str]):
            Path to the source files if missing from the target system. None
            means that the system will use windows update services to find the
            required files. Default is None

        exclude (Optional[str]):
            The name of the feature to exclude when installing the named
            feature. This can be a single feature, a string of features in a
            comma-delimited list (no spaces), or a list of features.

            .. warning::
                As there is no exclude option for the ``Add-WindowsFeature``
                or ``Install-WindowsFeature`` PowerShell commands the features
                named in ``exclude`` will be installed with other sub-features
                and will then be removed. **If the feature named in ``exclude``
                is not a sub-feature of one of the installed items it will still
                be removed.**

    Returns:
        dict: A dictionary containing the results of the install

    CLI Example:

    .. code-block:: bash

        # Install the Telnet Client passing a single string
        salt '*' win_servermanager.install Telnet-Client

        # Install the TFTP Client and the SNMP Service passing a comma-delimited
        # string. Install all sub-features
        salt '*' win_servermanager.install TFTP-Client,SNMP-Service recurse=True

        # Install the TFTP Client from d:\side-by-side
        salt '*' win_servermanager.install TFTP-Client source=d:\\side-by-side

        # Install the XPS Viewer, SNMP Service, and Remote Access passing a
        # list. Install all sub-features, but exclude the Web Server
        salt '*' win_servermanager.install "['XPS-Viewer', 'SNMP-Service', 'RemoteAccess']" True recurse=True exclude="Web-Server"
    """
    # If it is a list of features, make it a comma delimited string
    if isinstance(feature, list):
        feature = ",".join(feature)

    # Use Install-WindowsFeature on Windows 2012 (osversion 6.2) and later
    # minions. Default to Add-WindowsFeature for earlier releases of Windows.
    # The newer command makes management tools optional so add them for parity
    # with old behavior.
    command = "Add-WindowsFeature"
    management_tools = ""
    if salt.utils.versions.version_cmp(__grains__["osversion"], "6.2") >= 0:
        command = "Install-WindowsFeature"
        management_tools = "-IncludeManagementTools"

    cmd = "{} -Name {} {} {} {} -WarningAction SilentlyContinue".format(
        command,
        shlex.quote(feature),
        management_tools,
        "-IncludeAllSubFeature" if recurse else "",
        "" if source is None else "-Source {}".format(source),
    )
    out = _pshell_json(cmd)

    # Uninstall items in the exclude list
    # The Install-WindowsFeature command doesn't have the concept of an exclude
    # list. So you install first, then remove
    if exclude is not None:
        removed = remove(exclude)

    # Results are stored in a list of dictionaries in `FeatureResult`
    if out["FeatureResult"]:
        ret = {
            "ExitCode": out["ExitCode"],
            "RestartNeeded": False,
            "Restarted": False,
            "Features": {},
            "Success": out["Success"],
        }

        # FeatureResult is a list of dicts, so each item is a dict
        for item in out["FeatureResult"]:
            ret["Features"][item["Name"]] = {
                "DisplayName": item["DisplayName"],
                "Message": item["Message"],
                "RestartNeeded": item["RestartNeeded"],
                "SkipReason": item["SkipReason"],
                "Success": item["Success"],
            }

            if item["RestartNeeded"]:
                ret["RestartNeeded"] = True

        # Only items that installed are in the list of dictionaries
        # Add 'Already installed' for features that aren't in the list of dicts
        for item in feature.split(","):
            if item not in ret["Features"]:
                ret["Features"][item] = {"Message": "Already installed"}

        # Some items in the exclude list were removed after installation
        # Show what was done, update the dict
        if exclude is not None:
            # Features is a dict, so it only iterates over the keys
            for item in removed["Features"]:
                if item in ret["Features"]:
                    ret["Features"][item] = {
                        "Message": "Removed after installation (exclude)",
                        "DisplayName": removed["Features"][item]["DisplayName"],
                        "RestartNeeded": removed["Features"][item]["RestartNeeded"],
                        "SkipReason": removed["Features"][item]["SkipReason"],
                        "Success": removed["Features"][item]["Success"],
                    }

                    # Exclude items might need a restart
                    if removed["Features"][item]["RestartNeeded"]:
                        ret["RestartNeeded"] = True

        # Restart here if needed
        if restart:
            if ret["RestartNeeded"]:
                if __salt__["system.reboot"](in_seconds=True):
                    ret["Restarted"] = True

        return ret

    else:

        # If we get here then all features were already installed
        ret = {
            "ExitCode": out["ExitCode"],
            "Features": {},
            "RestartNeeded": False,
            "Restarted": False,
            "Success": out["Success"],
        }

        for item in feature.split(","):
            ret["Features"][item] = {"Message": "Already installed"}

        return ret


def remove(feature, remove_payload=False, restart=False):
    r"""
    Remove an installed feature

    .. note::
        Some features require a reboot after installation/uninstallation. If
        one of these features are modified, then other features cannot be
        installed until the server is restarted. Additionally, some features
        take a while to complete installation/uninstallation, so it is a good
        idea to use the ``-t`` option to set a longer timeout.

    Args:

        feature (str, list):
            The name of the feature(s) to remove. This can be a single feature,
            a string of features in a comma delimited list (no spaces), or a
            list of features.

            .. versionadded:: 2018.3.0
                Added the ability to pass a list of features to be removed.

        remove_payload (Optional[bool]):
            True will cause the feature to be removed from the side-by-side
            store (``%SystemDrive%:\Windows\WinSxS``). Default is False

        restart (Optional[bool]):
            Restarts the computer when uninstall is complete, if required by the
            role/feature removed. Default is False

    Returns:
        dict: A dictionary containing the results of the uninstall

    CLI Example:

    .. code-block:: bash

        salt -t 600 '*' win_servermanager.remove Telnet-Client
    """
    # If it is a list of features, make it a comma delimited string
    if isinstance(feature, list):
        feature = ",".join(feature)

    # Use Uninstall-WindowsFeature on Windows 2012 (osversion 6.2) and later
    # minions. Default to Remove-WindowsFeature for earlier releases of Windows.
    # The newer command makes management tools optional so add them for parity
    # with old behavior.
    command = "Remove-WindowsFeature"
    management_tools = ""
    _remove_payload = ""
    if salt.utils.versions.version_cmp(__grains__["osversion"], "6.2") >= 0:
        command = "Uninstall-WindowsFeature"
        management_tools = "-IncludeManagementTools"

        # Only available with the `Uninstall-WindowsFeature` command
        if remove_payload:
            _remove_payload = "-Remove"

    cmd = "{} -Name {} {} {} {} -WarningAction SilentlyContinue".format(
        command,
        shlex.quote(feature),
        management_tools,
        _remove_payload,
        "-Restart" if restart else "",
    )
    try:
        out = _pshell_json(cmd)
    except CommandExecutionError as exc:
        if "ArgumentNotValid" in exc.message:
            raise CommandExecutionError("Invalid Feature Name", info=exc.info)
        raise

    # Results are stored in a list of dictionaries in `FeatureResult`
    if out["FeatureResult"]:
        ret = {
            "ExitCode": out["ExitCode"],
            "RestartNeeded": False,
            "Restarted": False,
            "Features": {},
            "Success": out["Success"],
        }

        for item in out["FeatureResult"]:
            ret["Features"][item["Name"]] = {
                "DisplayName": item["DisplayName"],
                "Message": item["Message"],
                "RestartNeeded": item["RestartNeeded"],
                "SkipReason": item["SkipReason"],
                "Success": item["Success"],
            }

        # Only items that installed are in the list of dictionaries
        # Add 'Not installed' for features that aren't in the list of dicts
        for item in feature.split(","):
            if item not in ret["Features"]:
                ret["Features"][item] = {"Message": "Not installed"}

        return ret

    else:

        # If we get here then none of the features were installed
        ret = {
            "ExitCode": out["ExitCode"],
            "Features": {},
            "RestartNeeded": False,
            "Restarted": False,
            "Success": out["Success"],
        }

        for item in feature.split(","):
            ret["Features"][item] = {"Message": "Not installed"}

        return ret
