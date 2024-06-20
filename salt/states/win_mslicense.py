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


def present(name: str, kms_host="", kms_port=0, activate=False):
    """ """

    ret = {"name": name[-5:], "result": None, "comment": "", "changes": {}}

    info = __salt__["mslicense.info"](name)
    if info[0] == False:
        log.error("error occurred while collecting data", info[1])
        return (False, info[1])

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "{0} would be present".format(name[-5:])

        if name[-5:] != info[1][0]["PartialProductKey"]:
            ret["changes"][name[-5:]] = {
                "old": "",
                "new": "XXXXX-XXXXX-XXXXX-XXXXX-{0}".format(name[-5:]),
            }

        if kms_host != "" and kms_host != info[1][0]["KeyManagementServiceMachine"]:
            ret["changes"]["kms_host"] = {
                "old": info[1][0]["KeyManagementServiceMachine"],
                "new": kms_host,
            }

        if kms_port != 0 and kms_port != info[1][0]["KeyManagementServicePort"]:
            ret["changes"]["kms_port"] = {
                "old": info[1][0]["KeyManagementServicePort"],
                "new": kms_port,
            }

        if activate and info[1][0]["LicenseStatus"] != 1:
            ret["changes"]["activate"] = {"old": info[1][0]["LicenseStatus"], "new": 1}
        return ret

    if name[-5:] != info[1][0]["PartialProductKey"]:
        install = __salt__["mslicense.install"](name)
        if install[0] != True:
            log.error("error when installing the key", install[1])
            ret["result"] = False
            ret["comment"] = "error when installing the key"
            return ret

        test_install = __salt__["mslicense.installed"](name)
        if test_install[0] != True:
            log.error("error when check the key", test_install[1])
            ret["result"] = False
            ret["comment"] = "error when check the key"
            return ret

        ret["comment"] = "{0} be present".format(name[-5:])
        ret["changes"][name[-5:]] = {
            "old": info[1][0]["PartialProductKey"],
            "new": "XXXXX-XXXXX-XXXXX-XXXXX-{0}".format(name[-5:]),
        }

    if kms_host != "" and kms_host != info[1][0]["KeyManagementServiceMachine"]:

        install = __salt__["mslicense.install_kms_host"](kms_host, name)
        if install[0] != True:
            log.error("error when installing the kms-host", install[1])
            ret["result"] = False
            ret["comment"] = "error when installing the kms-host"
            return ret

        test_install = __salt__["mslicense.installed_kms_host"](kms_host, name)
        if test_install[0] != True:
            log.error("error when check the kms-host", install[1])
            ret["result"] = False
            ret["comment"] = "error when check the kms-host"
            return ret

        ret["changes"]["kms_host"] = {
            "old": info[1][0]["KeyManagementServiceMachine"],
            "new": kms_host,
        }

    if kms_port != 0 and kms_port != info[1][0]["KeyManagementServicePort"]:

        install = __salt__["mslicense.install_kms_port"](kms_port, name)
        if install[0] != True:
            log.error("error when installing the kms-port", install[1])
            ret["result"] = False
            ret["comment"] = "error when installing the kms-port"
            return ret

        test_install = __salt__["mslicense.installed_kms_port"](kms_port, name)
        if test_install[0] != True:
            log.error("error when installing the kms-port", install[1])
            ret["result"] = False
            ret["comment"] = "error when check the kms-port"
            return ret
        ret["changes"]["kms_port"] = {
            "old": info[1][0]["KeyManagementServicePort"],
            "new": kms_port,
        }

    if activate and info[0][1]["LicenseStatus"] != 1:
        install = __salt__["mslicense.activate"](name)
        if install[0] != True:
            log.error("error when product activate", install[1])
            ret["result"] = False
            ret["comment"] = "error when product activate"
            return ret

        test_install = __salt__["mslicense.licensed"](name)
        if test_install[0] != True:
            log.error("error when check product activate", install[1])
            ret["result"] = False
            ret["comment"] = "error when check product activate"
            return ret
        ret["changes"]["activate"] = {"old": info[1][0]["LicenseStatus"], "new": 1}
    
    ret["result"]=True
    return ret
