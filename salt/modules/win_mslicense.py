import logging
import salt.utils.platform

log = logging.getLogger(__name__)
__virtualname__ = "mslicense"

def __virtual__():
    """
    Only work on Windows
    """
    if salt.utils.platform.is_windows():
        return __virtualname__
    return (False, "Only Windows OS supported")


def installed(product_key: str):
    """
    Check to see if the product key is already installed.

    Note: This is not 100% accurate as we can only see the last 5 digits of the license.

    CLI Example:

    .. code-block:: bash
        salt '*' license.installed XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' license.installed ZZZZZ
    """

    cmd = "Get-CimInstance -Query 'SELECT PartialProductKey FROM SoftwareLicensingProduct WHERE PartialProductKey = \"{0}\"'".format(
        product_key[-5:]
    )
    log.debug("prepare cmd: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    if not "result" in out:
        return (None, "empty out")

    if product_key[-5:] == out["result"]["PartialProductKey"]:
        return (True,)

    return (None,)


def install(product_key: str):
    """
    Install the given product key.

    CLI Example:
    .. code-block:: bash

        salt '*' license.install XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
    """

    cmd = "Invoke-CimMethod -Query 'Select * From SoftwareLicensingService' -MethodName InstallProductKey -Arguments @{{ProductKey='{0}'}}".format(
        product_key
    )
    log.debug("prepare cmd: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)
    if out["retcode"] != 0:
        return (False, out["stderr"])

    return (True,)


def uninstall(key=""):
    """

    Uninstall the specified product key.
    The last five digits of the key are used.

    CAUTION: If you intend to uninstall the product key for Office, for example,
    and forget to enter the Activation ID, all installed product keys are
    uninstalled. This includes the product key for Windows.

    https://learn.microsoft.com/en-us/deployoffice/vlactivation/tools-to-manage-volume-activation-of-office#slmgrvbs-command-options

    CLI Example:

    .. code-block:: bash
        salt '*' license.uninstall
        salt '*' license.uninstall XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' license.uninstall ZZZZZ
    """

    cmd=""
    if len(key) != 0:
        cmd = "Invoke-CimMethod -Query \"SELECT ID FROM SoftwareLicensingProduct WHERE PartialProductKey='{0}'\" -MethodName UninstallProductKey".format(
            key[-5:]
        )
    elif len (key)==0:
        cmd = 'Invoke-CimMethod -Query "SELECT ID FROM SoftwareLicensingProduct WHERE PartialProductKey is not NULL" -MethodName UninstallProductKey'
    else:
        return (False, "Only one key is required, or nothing")

    log.debug("prepare cmd: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    return (True,)


def install_kms_host(host: str, key=""):
    """
    Install the kms-host for the specified product key
    (using SoftwareLicensingProduct.SetKeyManagementServiceMachine).

    If the key is not specified, installs global parameters for the entire system
    (using SoftwareLicensingService.SetKeyManagementServiceMachine).

    The last five digits of the key are used.

    key
        The product key for which you want to install the kms server setting.
        If not specified, the KMS server setting will be install globally for
        the entire system (which does not exclude individual settings for a
        specific product)

    host
        kms server host name or ip address

    CLI Example:

    .. code-block:: bash
        salt '*' license.install_kms_host kms.example.com
        salt '*' license.install_kms_host kms.example.com XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' license.install_kms_host kms.example.com ZZZZZ
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

    log.debug("prepare cmd: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    return (True,)


def install_kms_port(port: int, key=""):
    """
    Install the kms-port for the specified product key
    (using SoftwareLicensingProduct.SetKeyManagementServicePort).

    If the key is not specified, installs global parameters for the entire system
    (using SoftwareLicensingService.SetKeyManagementServicePort).

    The last five digits of the key are used.

    key
        The product key for which you want to install the kms server setting.
        If not specified, the KMS server setting will be install globally for
        the entire system (which does not exclude individual settings for a
        specific product)
    port
        kms server port

    CLI Example:

    .. code-block:: bash
        salt '*' license.install_kms_port 1688
        salt '*' license.install_kms_port 1688 XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' license.install_kms_port 1688 ZZZZZ
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


def uninstall_kms_host(key=""):
    """
    Uninstall the kms-host for the specified product key
    (using SoftwareLicensingProduct.ClearKeyManagementServiceMachine).

    If the key is not specified, uninstalls global parameters for the entire system
    (using SoftwareLicensingService.ClearKeyManagementServiceMachine).

    The last five digits of the key are used.

    CLI Example:

    .. code-block:: bash
        salt '*' license.uninstall_kms_host
        salt '*' license.uninstall_kms_host XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' license.uninstall_kms_host ZZZZZ
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


def uninstall_kms_port(key=""):
    """
    Uninstall the kms-port for the specified product key
    (using SoftwareLicensingProduct.ClearKeyManagementServicePort).

    If the key is not specified, uninstalls global parameters for the entire system
    (using SoftwareLicensingService.ClearKeyManagementServicePort).

    The last five digits of the key are used.

    CLI Example:

    .. code-block:: bash
        salt '*' license.uninstall_kms_port
        salt '*' license.uninstall_kms_port XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' license.uninstall_kms_port ZZZZZ
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


def installed_kms_host(host: str, key=""):
    """
    Checking that the specified kms-host matches the installed.

    If the key is not specified, the global parameter is checked.
    If a key is specified, the parameter for the specified product key is checked.

    CLI Example:

    .. code-block:: bash
        salt '*' license.installed_kms_host kms.example.com
        salt '*' license.installed_kms_host kms.example.com XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' license.installed_kms_host kms.example.com ZZZZZ
    """

    cmd = ""
    if key:
        cmd = "Get-CimInstance -Query \"SELECT KeyManagementServiceMachine FROM SoftwareLicensingProduct WHERE KeyManagementServiceMachine ='{0}' and PartialProductKey = '{1}'\"".format(
            host, key[-5:]
        )
    else:
        cmd = "Get-CimInstance -Query \"SELECT KeyManagementServiceMachine FROM SoftwareLicensingService WHERE KeyManagementServiceMachine ='{0}'\"".format(
            host
        )

    log.debug("prepare cmd: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    if not "result" in out:
        return (None, "empty out")

    if host == out["result"]["KeyManagementServiceMachine"]:
        return (True,)

    return (None,)


def installed_kms_port(port: int, key=""):
    """
    Checking that the specified kms-port matches the installed.

    If the key is not specified, the global parameter is checked.
    If a key is specified, the parameter for the specified product key is checked.

    CLI Example:

    .. code-block:: bash
        salt '*' license.installed_kms_port 1688
        salt '*' license.installed_kms_port 1688 XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' license.installed_kms_port 1688 ZZZZZ
    """

    cmd = ""
    if key:
        cmd = "Get-CimInstance -Query \"SELECT KeyManagementServicePort FROM SoftwareLicensingProduct WHERE KeyManagementServicePort = {0} and PartialProductKey = '{1}'\"".format(
            port, key[-5:]
        )
    else:
        cmd = 'Get-CimInstance -Query "SELECT KeyManagementServicePort FROM SoftwareLicensingService WHERE KeyManagementServicePort ={0}"'.format(
            port
        )

    log.debug("prepare cmd: {0}".format(cmd))

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    if not "result" in out:
        return (None, "empty out")

    if port == out["result"]["KeyManagementServicePort"]:
        return (True,)

    return (None,)


def licensed(key: str):
    """
    Checking that the specified product is in the "Licensed" state (code 1)
    https://learn.microsoft.com/en-us/previous-versions/windows/desktop/sppwmi/softwarelicensingproduct#LicenseStatus

    CLI Example:

    .. code-block:: bash
        salt '*' license.licensed XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' license.licensed ZZZZZ
    """

    cmd = "Get-CimInstance -Query 'SELECT LicenseStatus FROM SoftwareLicensingProduct WHERE PartialProductKey = '{0}'".format(
        key[-5:]
    )

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    if not "result" in out:
        return (None, "empty out")

    if out["result"]["LicenseStatus"] != 1:
        return (False, "LicenseStatus: {0}".format(out["result"]["LicenseStatus"]))

    else:
        return (True,)


def activate(key: str):
    """
    Activates the specified product key.

    https://learn.microsoft.com/en-us/previous-versions/windows/desktop/sppwmi/activate-softwarelicensingproduct

    CLI Example:

    .. code-block:: bash
        salt '*' license.activate XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' license.activate ZZZZZ
    """

    cmd = "Invoke-CimMethod -Query \"SELECT ID FROM SoftwareLicensingProduct WHERE PartialProductKey = '{0}' -MethodName Activate".format(
        key[-5:]
    )

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    return (True,)


def info(key=""):
    """
    Returns a summary of the licenses.
    If a key is specified, returns a summary for the specified product only.

    If the product is not found, returns an object with empty values.
    .. code-block:: bash
        return [{
                "Name": None,
                "Description": None,
                "PartialProductKey": None,
                "LicenseStatus": None,
                "KeyManagementServiceMachine": None,
                "KeyManagementServicePort": None,
            }]

    CLI Example:

    .. code-block:: bash
        salt '*' license.info
        salt '*' license.info XXXXX-XXXXX-XXXXX-XXXXX-ZZZZZ
        salt '*' license.info ZZZZZ
    """

    cmd = ""
    if key == "":
        cmd = "Get-CimInstance -Query 'SELECT Name, Description, PartialProductKey, LicenseStatus, KeyManagementServiceMachine, KeyManagementServicePort FROM SoftwareLicensingProduct WHERE PartialProductKey is not NULL'"
    else:
        cmd = "Get-CimInstance -Query \"SELECT Name, Description, PartialProductKey, LicenseStatus, KeyManagementServiceMachine, KeyManagementServicePort FROM SoftwareLicensingProduct WHERE PartialProductKey = '{0}' \"".format(
            key[-5:]
        )

    out = __salt__["cmd.powershell_all"](cmd)

    if out["retcode"] != 0:
        return (False, out["stderr"])

    if not "result" in out:
        out["result"] = {
            "Name": None,
            "Description": None,
            "PartialProductKey": None,
            "LicenseStatus": None,
            "KeyManagementServiceMachine": None,
            "KeyManagementServicePort": None,
        }

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
