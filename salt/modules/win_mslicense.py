import logging
import salt.utils.platform

# Set up logging
log = logging.getLogger(__name__)
__virtualname__ = "mslicense"

def __virtual__():
    """
    Only work on Windows
    """
    if salt.utils.platform.is_windows():
        return __virtualname__
    return (False, "Only Windows OS supported")

def install(product_key:str):
    """
    Install the given product key

    CLI Example:
    .. code-block:: bash

        salt '*' license.install XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
    """

    cmd="Invoke-CimMethod -Query 'Select * From SoftwareLicensingService' -MethodName InstallProductKey -Arguments @{{ProductKey='{0}'}}".format(product_key)
    log.debug("prepare cmd: {0}".format(cmd))

    cmdout= __salt__["cmd.powershell_all"](cmd)
    if cmdout["retcode"]!=0:
        return (False,cmdout["stderr"])

    return True

def installed(product_key:str):
    """
    Check to see if the product key is already installed.

    Note: This is not 100% accurate as we can only see the last
     5 digits of the license.

    CLI Example:

    .. code-block:: bash
        salt '*' license.installed XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
    """

    cmd = "Get-CimInstance -Query 'SELECT PartialProductKey FROM SoftwareLicensingProduct WHERE PartialProductKey is not NULL'"
    log.debug("prepare cmd: {0}".format(cmd))
    cmdout = __salt__["cmd.powershell_all"](cmd)

    if cmdout["retcode"]!=0:
        return (False,cmdout["stderr"])

    if not "result" in cmdout:
        return False

    if isinstance(cmdout["result"], dict):
        cmdout["result"] = [cmdout["result"]]

    for prod in cmdout["result"]:
        if product_key[-5:] == prod["PartialProductKey"]:
            return True
    return (False)

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
    if len(key)==1:
        cmd="Invoke-CimMethod -Query \"SELECT * FROM SoftwareLicensingProduct WHERE PartialProductKey='{0}'\" -MethodName UninstallProductKey".format(key[0][-5:])
    elif len (key)==0:
        cmd="Invoke-CimMethod -Query \"SELECT * FROM SoftwareLicensingProduct WHERE PartialProductKey is not NULL\" -MethodName UninstallProductKey"
    else:
        return (False, "Only one key is required, or nothing")

    log.debug("prepare cmd: {0}".format(cmd))

    cmdout=__salt__["cmd.powershell_all"](cmd)

    if cmdout["retcode"]!=0:
        return (False,cmdout["stderr"])

    return True

def install_kms(host="", port=0, key=""):
    """
    Install the host and port for the specified product key
    (using SoftwareLicensingProduct.SetKeyManagementService[Machine|Port]).

    If the key is not specified, installs global parameters for the entire system
    (using SoftwareLicensingService.SetKeyManagementService[Machine|Port]).

    The last five digits of the key are used.

    key
        The product key for which you want to remove the kms server setting.
        If not specified, the KMS server setting will be deleted globally for
        the entire system (which does not exclude individual settings for a
        specific product)

    host
        kms server host name or ip address
    
    port
        kms server port
    """

    if host:
        cmd=""
        if key:
            cmd="Invoke-CimMethod -Query \"SELECT * FROM SoftwareLicensingProduct WHERE PartialProductKey='{0}'\" -MethodName SetKeyManagementServiceMachine -Arguments @{{MachineName='{1}'}}".format(key[-5:],host)

        else:
            cmd="Invoke-CimMethod -Query 'SELECT * FROM SoftwareLicensingService' -MethodName SetKeyManagementServiceMachine -Arguments @{{MachineName='{0}'}}".format(host)

        log.debug("prepare cmd: {0}".format(cmd))

        cmdout=__salt__["cmd.powershell_all"](cmd)

        if cmdout["retcode"]!=0:
            return (False,cmdout["stderr"])
    
    if port!=0:
        cmd=""
        if key:
            cmd="Invoke-CimMethod -Query \"SELECT * FROM SoftwareLicensingProduct WHERE PartialProductKey='{0}'\" -MethodName SetKeyManagementServicePort -Arguments @{{ PortNumber=[uint32]{1} }}".format(key[-5:],port)

        else:
            cmd="Invoke-CimMethod -Query 'SELECT * FROM SoftwareLicensingService' -MethodName SetKeyManagementServicePort -Arguments @{{ PortNumber=[uint32]{0} }}".format(port)

        log.debug("prepare cmd: {0}".format(cmd))

        cmdout=__salt__["cmd.powershell_all"](cmd)

        if cmdout["retcode"]!=0:
            return (False,cmdout["stderr"])

    return True

def uninstall_kms(host=False, port=False, key=""):
    """
    Uninstall the host and port for the specified product key
    (using SoftwareLicensingProduct.SetKeyManagementService[Machine|Port]).

    If the key is not specified, uninstalls global parameters for the entire system
    (using SoftwareLicensingService.SetKeyManagementService[Machine|Port]).

    The last five digits of the key are used.
    """

    if host:
        cmd=""
        if key:
            cmd="Invoke-CimMethod -Query \"SELECT * FROM SoftwareLicensingProduct WHERE PartialProductKey='{0}'\" -MethodName ClearKeyManagementServiceMachine".format(key[-5:])

        else:
            cmd="Invoke-CimMethod -Query 'SELECT * FROM SoftwareLicensingService' -MethodName ClearKeyManagementServiceMachine"

        log.debug("prepare cmd: {0}".format(cmd))

        cmdout=__salt__["cmd.powershell_all"](cmd)

        if cmdout["retcode"]!=0:
            return (False,cmdout["stderr"])
    
    if port:
        cmd=""
        if key:
            cmd="Invoke-CimMethod -Query \"SELECT * FROM SoftwareLicensingProduct WHERE PartialProductKey='{0}'\" -MethodName ClearKeyManagementServicePort".format(key[-5:])

        else:
            cmd="Invoke-CimMethod -Query 'SELECT * FROM SoftwareLicensingService' -MethodName ClearKeyManagementServicePort"

        log.debug("prepare cmd: {0}".format(cmd))

        cmdout=__salt__["cmd.powershell_all"](cmd)

        if cmdout["retcode"]!=0:
            return (False,cmdout["stderr"])

    return True

def installed_kms(host="",port=0,key=""):
    """
    """

    if host:
        cmd=""
        if key:
            cmd="Get-CimInstance -Query 'SELECT Name, PartialProductKey, KeyManagementServiceMachine FROM SoftwareLicensingProduct WHERE KeyManagementServiceMachine ='{0}' and PartialProductKey = '{1}'".format(host,key[-5:])
        else:
            cmd="Get-CimInstance -Query 'SELECT KeyManagementServiceMachine FROM SoftwareLicensingService WHERE KeyManagementServiceMachine ='{0}'".format(host)

    log.debug("prepare cmd: {0}".format(cmd))

    cmdout=__salt__["cmd.powershell_all"](cmd)

    if cmdout!=0:
        return (False,cmdout["stderr"])

    if not "result" in cmdout:
        return False