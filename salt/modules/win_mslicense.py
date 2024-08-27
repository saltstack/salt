"""
Module for managing OS and software licenses on Windows,
utilizing PowerShell and CIM methods.

Invoke-CimMethod is supported in PowerShell 3.0, so
the module can potentially work starting from Windows 7.

Guaranteed tests were conducted on Windows 10.
"""

import logging
import salt.utils.platform

log = logging.getLogger(__name__)
__virtualname__ = "mslicense"


def __virtual__():
    """
    Only works on Windows
    """
    if salt.utils.platform.is_windows():
        return __virtualname__
    return (False, "Only Windows OS supported")


def install(key: str):
    """
    Install the given product key.

    https://learn.microsoft.com/en-us/previous-versions/windows/desktop/sppwmi/installproductkey-softwarelicensingservice

    Returns:
        tuple: tuple as operation status and payload

    .. code-block:: cfg

        (False, "error message")
        (True,)

    CLI Example:

    .. code-block:: powershell

        salt '*' mslicense.install XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
    """

    cmd = "Invoke-CimMethod -Query 'Select * From SoftwareLicensingService' -MethodName InstallProductKey -Arguments @{{ProductKey='{0}'}}".format(
        key)

    log.debug("product key installation command: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)
    if out["retcode"] != 0:
        return (False, out["stderr"])

    return (True,)


def installed(key: str):
    """
    Check to see if the product key is already installed.

    .. note::
        This is not 100% accurate as we can only see the last 5 digits of the license.

    Returns:
        tuple: tuple as operation status and payload

    .. code-block:: cfg

        (False, "error message")
        (None, "empty out")
        (True,)

    CLI Example:

    .. code-block:: powershell
        salt '*' mslicense.installed XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' mslicense.installed ZZZZZ
    """

    cmd = "Get-CimInstance -Query 'SELECT PartialProductKey FROM SoftwareLicensingProduct WHERE PartialProductKey = \"{0}\"'".format(
        key[-5:]
    )
    log.debug("product key check command: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    if not "result" in out:
        return (None, "empty out")

    if key[-5:] == out["result"]["PartialProductKey"]:
        return (True,)

    return (None,)


def uninstall(key=""):
    """

    Uninstall the specified product key.
    The last five digits of the key are used.

    CAUTION: If you intend to uninstall the product key for Office, for example,
    and forget to enter the Activation ID, all installed product keys are
    uninstalled. This includes the product key for Windows.

    https://learn.microsoft.com/en-us/deployoffice/vlactivation/tools-to-manage-volume-activation-of-office#slmgrvbs-command-options

    Returns:
        tuple: tuple as operation status and payload

    .. code-block:: cfg
        (False, "error message")
        (True,)

    CLI Example:

    .. code-block:: powershell
        salt '*' mslicense.uninstall_key
        salt '*' mslicense.uninstall_key XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' mslicense.uninstall_key ZZZZZ
    """

    cmd = ""
    if key != "":
        cmd = "Invoke-CimMethod -Query \"SELECT ID FROM SoftwareLicensingProduct WHERE PartialProductKey='{0}'\" -MethodName UninstallProductKey".format(
            key[-5:])

    else:
        cmd = 'Invoke-CimMethod -Query "SELECT ID FROM SoftwareLicensingProduct WHERE PartialProductKey is not NULL" -MethodName UninstallProductKey'

    log.debug("product key uninstall command: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    return (True,)


def licensed(key: str):
    """
    Returns the license status of a product key


    Table of license status:
    0       Unlicensed
    1       Licensed
    2       OOBGrace
    3       OOTGrace
    4       NonGenuineGrace
    5       Notification
    6       ExtendedGrace

    https://learn.microsoft.com/en-us/previous-versions/windows/desktop/sppwmi/softwarelicensingproduct#LicenseStatus

    Returns:
        tuple: tuple as operation status and payload

    .. code-block:: cfg

        (False, "error message")
        (None, "empty out")
        (True,)

    CLI Example:

    .. code-block:: powershell
        salt '*' mslicense.licensed XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' mslicense.licensed ZZZZZ
    """

    cmd = "Get-CimInstance -Query 'SELECT LicenseStatus FROM SoftwareLicensingProduct WHERE PartialProductKey = '{0}'".format(
        key[-5:]
    )
    log.debug("license status check command: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    if not "result" in out:
        return (None, "empty out")

    return (True, out["result"]["LicenseStatus"])


def activate(key: str):
    """
    Activates the specified product key.

    https://learn.microsoft.com/en-us/previous-versions/windows/desktop/sppwmi/activate-softwarelicensingproduct

    Returns:
        tuple: tuple as operation status and payload

    .. code-block:: cfg
        (False, "error message")
        (True,)

    CLI Example:

    .. code-block:: powershell
        salt '*' mslicense.activate XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' mslicense.activate ZZZZZ
    """

    cmd = "Invoke-CimMethod -Query \"SELECT ID FROM SoftwareLicensingProduct WHERE PartialProductKey = '{0}' -MethodName Activate".format(
        key[-5:]
    )
    log.debug("product key activation command: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    return (True,)


def info(key=""):
    """
    Returns a summary of the licenses.
    If a key is specified, returns a summary for the specified product only.

    Returns:
        tuple: tuple as operation status and payload

    .. code-block:: cfg

        (False, "error message")
        (None,)
        (True,[obj...])

    CLI Example:

    .. code-block:: powershell
        salt '*' mslicense.info
        salt '*' mslicense.info XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' mslicense.info ZZZZZ

        [{
            "Name": AAAA,
            "Description": BBBB,
            "PartialProductKey": CCCC,
            "LicenseStatus": 1,
            "KeyManagementServiceMachine": DDDD,
            "KeyManagementServicePort": 1688,
        }]
    """

    cmd = ""
    if key == "":
        cmd = "Get-CimInstance -Query 'SELECT Name, Description, PartialProductKey, LicenseStatus, KeyManagementServiceMachine, KeyManagementServicePort FROM SoftwareLicensingProduct WHERE PartialProductKey is not NULL'"
    else:
        cmd = "Get-CimInstance -Query \"SELECT Name, Description, PartialProductKey, LicenseStatus, KeyManagementServiceMachine, KeyManagementServicePort FROM SoftwareLicensingProduct WHERE PartialProductKey = '{0}' \"".format(
            key[-5:]
        )
    log.debug("license information query command: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    if not "result" in out:
        return (None,)

    if isinstance(out["result"], dict):
        out["result"] = [out["result"]]

    ret = []
    for lic in out["result"]:
        ret.append(
            {
                "Name": lic["Name"],
                "Description": lic["Description"],
                "PartialProductKey": lic["PartialProductKey"],
                "LicenseStatus": lic["LicenseStatus"],
                "KeyManagementServiceMachine": lic["KeyManagementServiceMachine"],
                "KeyManagementServicePort": lic["KeyManagementServicePort"],
            }
        )

    return (True, ret)


def set_kms_host(host: str, key=""):
    """
    Install the kms-host for the specified product key
    https://learn.microsoft.com/en-us/previous-versions/windows/desktop/sppwmi/setkeymanagementservicemachine-softwarelicensingproduct

    If the key is not specified, installs global parameters for the entire system
    https://learn.microsoft.com/en-us/previous-versions/windows/desktop/sppwmi/setkeymanagementservicemachine-softwarelicensingservice

    The last five digits of the key are used.

    key
        The product key for which you want to install the kms server setting.
        If not specified, the KMS server setting will be install globally for
        the entire system (which does not exclude individual settings for a
        specific product)

    host
        kms server host name or ip address

    Returns:
        tuple: tuple as operation status and payload

    .. code-block:: cfg
        (False, "error message")

    CLI Example:

    .. code-block:: powershell
        salt '*' mslicense.set_kms_host kms.example.com
        salt '*' mslicense.set_kms_host kms.example.com XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' mslicense.set_kms_host kms.example.com ZZZZZ
    """

    cmd = ""
    if key:
        cmd = "Invoke-CimMethod -Query \"SELECT ID FROM SoftwareLicensingProduct WHERE PartialProductKey='{0}'\" -MethodName SetKeyManagementServiceMachine -Arguments @{{MachineName='{1}'}}".format(
            key[-5:], host
        )

    else:
        cmd = "Invoke-CimMethod -Query 'SELECT * FROM SoftwareLicensingService' -MethodName SetKeyManagementServiceMachine -Arguments @{{MachineName='{0}'}}".format(
            host
        )
    log.debug("kms-host installation command: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    return (True,)


def set_kms_port(port: int, key=""):
    """
    Install the kms-port for the specified product key
    https://learn.microsoft.com/en-us/previous-versions/windows/desktop/sppwmi/setkeymanagementserviceport-softwarelicensingproduct

    If the key is not specified, installs global parameters for the entire system
    https://learn.microsoft.com/en-us/previous-versions/windows/desktop/sppwmi/setkeymanagementserviceport-softwarelicensingservice

    The last five digits of the key are used.

    key
        The product key for which you want to install the kms server setting.
        If not specified, the KMS server setting will be install globally for
        the entire system (which does not exclude individual settings for a
        specific product)
    port
        kms server port

    Returns:
        tuple: tuple as operation status and payload

    .. code-block:: cfg

        (False, "error message")
        (True,)

    CLI Example:

    .. code-block:: powershell
        salt '*' mslicense.set_kms_port 1688
        salt '*' mslicense.set_kms_port 1688 XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' mslicense.set_kms_port 1688 ZZZZZ
    """

    cmd = ""
    if key:
        cmd = "Invoke-CimMethod -Query \"SELECT ID FROM SoftwareLicensingProduct WHERE PartialProductKey='{0}'\" -MethodName SetKeyManagementServicePort -Arguments @{{ PortNumber=[uint32]{1} }}".format(
            key[-5:], port
        )

    else:
        cmd = "Invoke-CimMethod -Query 'SELECT * FROM SoftwareLicensingService' -MethodName SetKeyManagementServicePort -Arguments @{{ PortNumber=[uint32]{0} }}".format(
            port
        )

    log.debug("prepare cmd: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    return (True,)


def clear_kms_host(key=""):
    """
    Uninstall the kms-host for the specified product key
    https://learn.microsoft.com/en-us/previous-versions/windows/desktop/sppwmi/clearkeymanagementservicemachine-softwarelicensingproduct

    If the key is not specified, uninstalls global parameters for the entire system
    https://learn.microsoft.com/en-us/previous-versions/windows/desktop/sppwmi/clearkeymanagementservicemachine-softwarelicensingservice

    The last five digits of the key are used.

    Returns:
        tuple: tuple as operation status and payload

    .. code-block:: cfg

        (False, "error message")
        (True,)

    CLI Example:

    .. code-block:: bash
        salt '*' mslicense.clear_kms_host
        salt '*' mslicense.clear_kms_host XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' mslicense.clear_kms_host ZZZZZ
    """

    cmd = ""
    if key:
        cmd = "Invoke-CimMethod -Query \"SELECT ID FROM SoftwareLicensingProduct WHERE PartialProductKey='{0}'\" -MethodName ClearKeyManagementServiceMachine".format(
            key[-5:]
        )

    else:
        cmd = "Invoke-CimMethod -Query 'SELECT * FROM SoftwareLicensingService' -MethodName ClearKeyManagementServiceMachine"

    log.debug("prepare cmd: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    return (True,)


def clear_kms_port(key=""):
    """
    Uninstall the kms-port for the specified product key
    https://learn.microsoft.com/en-us/previous-versions/windows/desktop/sppwmi/clearkeymanagementserviceport-softwarelicensingproduct

    If the key is not specified, uninstalls global parameters for the entire system
    https://learn.microsoft.com/en-us/previous-versions/windows/desktop/sppwmi/clearkeymanagementserviceport-softwarelicensingservice

    The last five digits of the key are used.

    Returns:
        tuple: tuple as operation status and payload

    .. code-block:: cfg

        (False, "error message")
        (True,)

    CLI Example:

    .. code-block:: bash
        salt '*' mslicense.clear_kms_port
        salt '*' mslicense.clear_kms_port XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' mslicense.clear_kms_port ZZZZZ
    """

    cmd = ""
    if key:
        cmd = "Invoke-CimMethod -Query \"SELECT ID FROM SoftwareLicensingProduct WHERE PartialProductKey='{0}'\" -MethodName ClearKeyManagementServicePort".format(
            key[-5:]
        )

    else:
        cmd = "Invoke-CimMethod -Query 'SELECT * FROM SoftwareLicensingService' -MethodName ClearKeyManagementServicePort"

    log.debug("prepare cmd: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    return (True,)


def get_kms_host(key=""):
    """
    TODO
    Checking that the specified kms-host matches the installed.

    If the key is not specified, the global parameter is checked.
    If a key is specified, the parameter for the specified product key is checked.

    CLI Example:

    .. code-block:: bash
        salt '*' mslicense.get_kms_host kms.example.com
        salt '*' mslicense.get_kms_host kms.example.com XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' mslicense.get_kms_host kms.example.com ZZZZZ
    """

    cmd = ""
    if key:
        # Если указан ключ продукта - ищу порт в перечне продуктов
        cmd = "Get-CimInstance -Query \"SELECT KeyManagementServiceMachine FROM SoftwareLicensingProduct WHERE PartialProductKey = '{0}'\"".format(
            key[-5:])
    else:
        # Если ключ продукта не указан - возвращаю глобальный параметр
        cmd = "Get-CimInstance -Query 'SELECT KeyManagementServiceMachine FROM SoftwareLicensingService'"

    log.debug("prepare cmd: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    if not "result" in out:
        return (None, "empty out")
    if out["result"]["KeyManagementServiceMachine"] == "":
        return (None, "empty out")

    return (True, out["result"]["KeyManagementServiceMachine"])


def get_kms_port(key=""):
    """
    TODO
    Checking that the specified kms-port matches the installed.

    If the key is not specified, the global parameter is checked.
    If a key is specified, the parameter for the specified product key is checked.

    CLI Example:

    .. code-block:: bash
        salt '*' mslicense.get_kms_port 1688
        salt '*' mslicense.get_kms_port 1688 XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' mslicense.get_kms_port 1688 ZZZZZ
    """

    cmd = ""
    if key:
        # Если указан ключ продукта - ищу порт в перечне продуктов
        cmd = "Get-CimInstance -Query \"SELECT KeyManagementServicePort FROM SoftwareLicensingProduct WHERE PartialProductKey = '{0}'\"".format(
            key[-5:])
    else:
        # Если ключ продукта не указан - возвращаю глобальный параметр
        cmd = 'Get-CimInstance -Query "SELECT KeyManagementServicePort FROM SoftwareLicensingService"'

    log.debug("prepare cmd: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    if not "result" in out:
        return (None, "empty out")

    return (True, out["result"]["KeyManagementServicePort"])
