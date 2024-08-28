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
    Only work on Windows
    """
    if salt.utils.platform.is_windows():
        return __virtualname__
    return (False, "Only Windows OS supported")


def present(name: str, kms_host="", kms_port=0, activate=False):
    """
    Ensure that the product key is present and optionally activate it.

    name
        Product key for OS or software
    kms_host
        Host for KMS activation
    kms_port
        Port for KMS activation
    activate
        Whether to activate the product
    """

    name = name.upper()
    kms_host = kms_host.lower()

    ret = {"name": name[-5:], "result": None, "comment": "", "changes": {}}

    info = __salt__["mslicense.info"](name)
    if info[0] == False:
        log.error("error occurred while collecting data", info[1])

        ret["result"] = False
        ret["comment"] = "error occurred while collecting data"
        return ret

    def infoIsNone(t: tuple, k: str): return None if (
        t[0] == None) else t[1][0][k]

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "{0} would be present".format(name[-5:])

        if (info[0] == None) or (name[-5:] != info[1][0]["PartialProductKey"]):
            ret["changes"]["product key"] = {
                "old": infoIsNone(info, "PartialProductKey"),
                "new": "XXXXX-XXXXX-XXXXX-XXXXX-{0}".format(name[-5:]),
            }

        if (kms_host != "") and ((info[0] == None) or (kms_host != info[1][0]["KeyManagementServiceMachine"])):
            ret["changes"]["kms host"] = {
                "old": infoIsNone(info, "KeyManagementServiceMachine"),
                "new": kms_host,
            }

        if (kms_port != 0) and ((info[0] == None) or (kms_port != info[1][0]["KeyManagementServicePort"])):
            ret["changes"]["kms port"] = {
                "old": infoIsNone(info, "KeyManagementServicePort"),
                "new": kms_port,
            }

        if activate and ((info[0] == None) or (info[1][0]["LicenseStatus"] != 1)):
            ret["changes"]["activate"] = {
                "old": infoIsNone(info, "LicenseStatus"),
                "new": 1
            }
        return ret

    if (info[0] == None) or (name[-5:] != info[1][0]["PartialProductKey"]):

        install = __salt__["mslicense.install"](name)
        if install[0] == False:
            log.error("error installing product key", install[1])

            ret["result"] = False
            ret["comment"] = "error installing product key"
            ret["changes"]["product key"] = {
                "old": infoIsNone(info, "PartialProductKey"),
                "new": "error: {0}".format(install[1])
            }
            return ret

        test_install = __salt__["mslicense.installed"](name)

        match test_install[0]:
            case False:
                log.error("product key check error", test_install[1])

                ret["result"] = False
                ret["comment"] = "product key check error"
                ret["changes"]["product key"] = {
                    "old": infoIsNone(info, "PartialProductKey"),
                    "new": "error: {0}".format(test_install[1])
                }
                return ret

            case None:
                log.error("product key was not installed, result: None")

                ret["result"] = False
                ret["comment"] = "product key was not installed"
                ret["changes"]["product key"] = {
                    "old": infoIsNone(info, "PartialProductKey"),
                    "new": "check failed, product key not found"
                }
                return ret

            case True:
                ret["comment"] = "{0} be present".format(name[-5:])
                ret["changes"]["product key"] = {
                    "old":  infoIsNone(info, "PartialProductKey"),
                    "new": "XXXXX-XXXXX-XXXXX-XXXXX-{0}".format(name[-5:]),
                }

    # If installation of kms host, port or activation is required,
    # update the license information

    if kms_host != "" or kms_port != 0 or activate:
        info = __salt__["mslicense.info"](name)
        if info[0] == False:
            log.error(
                "an error occurred during secondary data collection", info[1])

            ret["result"] = False
            ret["comment"] = "an error occurred during secondary data collection"

            return ret

    if kms_host != "" and kms_host != info[1][0]["KeyManagementServiceMachine"]:

        install = __salt__["mslicense.set_kms_host"](name)
        if install[0] != True:
            log.error("error when installing the kms-host: ", install[1])

            ret["result"] = False
            ret["comment"] = "error when installing the kms host"
            ret["changes"]["kms host"] = {
                "old": info[1][0]["KeyManagementServiceMachine"],
                "new": "error: {0}".format(install[1])
            }
            return ret

        test_install = __salt__["mslicense.get_kms_host"](name)
        match test_install[0]:
            case False:
                log.error("kms-host check error", test_install[1])

                ret["result"] = False
                ret["comment"] = "kms-host check error"
                ret["changes"]["kms host"] = {
                    "old": info[1][0]["KeyManagementServiceMachine"],
                    "new": "error: {0}".format(test_install[1])
                }
                return ret

            case None:
                log.error("kms host not be checked, result: None")

                ret["result"] = False
                ret["comment"] = "kms host not be checked"
                ret["changes"]["kms host"] = {
                    "old": info[1][0]["KeyManagementServiceMachine"],
                    "new": "check failed, product not found"
                }
                return ret

            case True:
                if test_install[1] == kms_host:
                    ret["changes"]["kms host"] = {
                        "old": info[1][0]["KeyManagementServiceMachine"],
                        "new": test_install[1]
                    }
                else:
                    ret["result"] = False
                    ret["comment"] = "kms host was not changed"
                    ret["changes"]["kms host"] = {
                        "old": info[1][0]["KeyManagementServiceMachine"],
                        "checked": test_install[1]
                    }
                    return ret

    if kms_port != 0 and kms_port != info[1][0]["KeyManagementServicePort"]:

        install = __salt__["mslicense.set_kms_port"](name)
        if install[0] != True:
            log.error("error when installing the kms-port", install[1])

            ret["result"] = False
            ret["comment"] = "error when installing the kms-port"
            ret["changes"]["kms port"] = {
                "old": info[1][0]["KeyManagementServiceMachine"],
                "new": "error: {0}".format(install[1])
            }
            return ret

        test_install = __salt__["mslicense.get_kms_port"](name)
        match test_install[0]:
            case False:
                log.error("kms-port check error: {0}".format(test_install[1]))

                ret["result"] = False
                ret["comment"] = "kms port check error"
                ret["changes"]["kms port"] = {
                    "old":  info[1][0]["KeyManagementServicePort"],
                    "new": "error: {0}".format(test_install[1])
                }
                return ret

            case None:
                log.error("kms port not be installed, result: None")

                ret["result"] = False
                ret["comment"] = "kms port not be installed"
                ret["changes"]["kms port"] = {
                    "old": info[1][0]["KeyManagementServicePort"],
                    "new": "check failed, kms port not found"
                }
                return ret

            case True:
                if test_install[1] == kms_port:
                    ret["changes"]["kms port"] = {
                        "old": info[1][0]["KeyManagementServicePort"],
                        "new": test_install[1]
                    }
                else:
                    ret["result"] = False
                    ret["comment"] = "kms port was not changed"
                    ret["changes"]["kms port"] = {
                        "old": info[1][0]["KeyManagementServiceMachine"],
                        "checked": test_install[1]
                    }
                    return ret

    if activate and info[1][0]["LicenseStatus"] != 1:
        install = __salt__["mslicense.activate"](name)
        if install[0] != True:
            log.error("error when product activate", install[1])

            ret["result"] = False
            ret["comment"] = "error when product activate"
            ret["changes"]["activate"] = {
                "old": info[1][0]["LicenseStatus"],
                "new": "error: {0}".format(install[1])
            }
            return ret

        test_install = __salt__["mslicense.license"](name)
        match test_install[0]:
            case False:
                log.error("error when check product activate", test_install[1])

                ret["result"] = False
                ret["comment"] = "error when check product activate"
                ret["changes"]["activate"] = {
                    "old": info[1][0]["LicenseStatus"],
                    "new": "error: {0}".format(test_install[1])
                }
                return ret

            case None:
                log.error("license status was not checked, result: None")

                ret["result"] = False
                ret["comment"] = "license status was not checked"
                ret["changes"]["activate"] = {
                    "old": info[1][0]["LicenseStatus"],
                    "new": "check failed, product not found"
                }
                return ret

            case True:
                if test_install[1] == 1:
                    ret["changes"]["activate"] = {
                        "old": info[1][0]["LicenseStatus"],
                        "new": test_install[1]
                    }
                else:
                    ret["result"] = False
                    ret["comment"] = "license status was not changed"
                    ret["changes"]["activate"] = {
                        "old": info[1][0]["LicenseStatus"],
                        "checked": test_install[1]
                    }
                    return ret

    ret["result"] = True
    return ret


def absent(name: str, all=False):
    """
    Ensure that the product key is absent.

    name
        Product key for OS or software to be removed.
        If left blank (name :""), it is equivalent to using the all=True key
    all
        If specified, removes all product keys
    """

    ret = {"name": name[-5:], "result": None, "comment": "", "changes": {}}

    if all:
        name = ""

    info = __salt__["mslicense.info"](name)
    if info[0] == False:
        log.error("error occurred while collecting data", info[1])

        ret["result"] = False
        ret["comment"] = "error occurred while collecting data"
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "{0} would be absent".format(name[-5:])

        if info[0] == None:
            ret["changes"]["uninstall product key"] = {
                "old": "",
                "new": ""
            }
        else:
            ret["changes"]["uninstall product key"] = {
                "old": info[1][0]["PartialProductKey"],
                "new": ""
            }
        return ret

    if info[0] != None:
        remove = __salt__["mslicense.uninstall"](name)
        if remove[0] != True:
            log.error(
                "error when removing product key: {0}".format(remove[1]))

            ret["result"] = False
            ret["comment"] = "error when removing product key"

            ret["changes"]["absent key"] = {
                "old": info[1],
                "new": ""
            }
            return ret

        test_remove = __salt__["mslicense.info"](name)
        if test_remove[0] != False:
            log.error("error occurred while collecting data", info[1])

            ret["result"] = False
            ret["comment"] = "error occurred while collecting data"
            return ret

        if test_remove[0] != None:
            log.error("product keys was not removed")

            ret["result"] = False
            ret["comment"] = "product kes(-s) not removed"
            ret["changes"]["absent key"] = {
                "old": info[1],
                "checked": "check failed, keys found"
            }
            return ret

    ret["changes"]["absent key"] = {
        "old": info[1],
        "new": ""
    }
    ret["comment"] = "keys has been removed"
    ret["result"] = True
    return ret


def present_kms(name: str, kms_port=0, key=""):
    """
    Ensure that the KMS host and port are correctly configured.

    name
        The host for KMS activation.
    kms_port
        The port for KMS activation.
    key
        The product key to which the KMS server is assigned.
    """

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    info = __salt__["mslicense.get_kms_host"](key)
    if info[0] == False:
        log.error("error occurred while collecting kms-host info", info[1])

        ret["result"] = False
        ret["comment"] = "error occurred while collecting kms-host info"
        return ret

    # If the KMS port is specified, query information about the current port
    info_port = (None, 0)

    if kms_port != 0:
        info_port = __salt__["mslicense.get_kms_port"](key)
        if info_port[0] == False:
            log.error("error occurred while collecting kms-port info",
                      info_port[1])

            ret["result"] = False
            ret["comment"] = "error occurred while collecting kms-port info"
            return ret

    if __opts__["test"]:
        ret["result"] = None

        if key != "":
            ret["comment"] = "{0} would be present for product: XXXXX-XXXXX-XXXXX-XXXXX-{1}".format(
                name, key[-5:])
        else:
            ret["comment"] = "{0} would be present".format(name)

        if info[0] == None:
            ret["changes"]["host"] = {
                "old": "kms installed: {0}".format(info[1]),
                "new": "kms will be install: {0}".format(info[1])
            }

        if kms_port != 0:
            if info_port[0] == None:
                ret["changes"]["port"] = {
                    "old": "kms installed: {0}".format(info_port[1]),
                    "new": "kms will be installed: {0}".format(kms_port)
                }
        return ret

    # Если kms-сервер не установлен, выполняю его установку
    if name != info[1]:
        install = __salt__["mslicense.set_kms_host"](name, key)
        if install[0] != True:
            log.error("error when installing the kms-host: ", install[1])
            ret["result"] = False
            ret["comment"] = "error when installing the kms-host"
            return ret

        test_install = __salt__["mslicense.get_kms_host"](key)
        if test_install[0] != True:
            log.error("error when check the kms-host", install[1])
            ret["result"] = False
            ret["comment"] = "error when check the kms-host"
            return ret

        ret["changes"]["host"] = {
            "old": info[1],
            "new": test_install[1],
        }

    if kms_port != 0 and kms_port != info_port[1]:

        install = __salt__["mslicense.set_kms_port"](kms_port, key)
        if install[0] != True:
            log.error("error when installing the kms-port", install[1])
            ret["result"] = False
            ret["comment"] = "error when installing the kms-port"
            return ret

        test_install = __salt__["mslicense.get_kms_port"](key)
        if test_install[0] != True:
            log.error("error when installing the kms-port", install[1])
            ret["result"] = False
            ret["comment"] = "error when check the kms-port"
            return ret

        ret["changes"]["port"] = {
            "old": info_port[1],
            "new": test_install[1],
        }

    ret["result"] = True
    return ret


def absent_kms(name="", host=False, port=False):
    """
    kms_host

    kms_port
        порт  удаляемого KMS-хоста
    """
    if not host and not port:
        log.error("требуется указать хоть одну цель для очистки - хост или порт")
        return (False, "требуется указать хоть одну цель для очистки - хост или порт")

    ret = {"name": name, "result": None, "comment": "", "changes": {}}
    info_kms = (None, "")
    info_port = (None, "")

    if host:
        info_kms = __salt__["mslicense.get_kms_host"](name)
        if info_kms[0] == False:
            log.error("error occurred while collecting data", info_kms[1])
            return (False, info_kms[1])
    if port:
        info_port = __salt__["mslicense.get_kms_port"](name)
        if info_port[0] == False:
            log.error("error occurred while collecting data", info_port[1])
            return (False, info_port[1])

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = 'would be absent'

        if info_kms[0] == True:
            ret["changes"]["removed kms-host"] = {
                "old": info_kms[1],
                "new": ""
            }

        if info_port[0] == True:
            ret["changes"]["removed kms-port"] = {
                "old": info_port[1],
                "new": ""
            }
        return ret

    if host:
        absent = __salt__["mslicense.clear_kms_host"](name)
        if absent[0] != True:
            log.error("error when clear kms-host: ", absent[1])
            ret["result"] = False
            ret["comment"] = "error when clear kms-host"
            return ret

        ret["changes"]["kms-host"] = {
            "old": info_kms[1],
            "new": ""
        }
    if port:
        absent = __salt__["mslicense.clear_kms_port"](name)
        if absent[0] != True:
            log.error("error when clear kms-port: ", absent[1])
            ret["result"] = False
            ret["comment"] = "error when clear kms-port"
            return ret
        ret["changes"]["kms-port"] = {
            "old": info_port[1],
            "new": ""
        }

    ret["result"] = True
    return ret
