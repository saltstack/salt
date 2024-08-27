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
    name
        ключ для установки продукта (ПО или ОС)
    kms_host
        хост для kms активации
    kms_port
        порт для kms активации
    activate
        нужно ли выполнять активацию продукта
    """

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
            ret["changes"]["activate"] = {
                "old": info[1][0]["LicenseStatus"], "new": 1}
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
        ret["changes"]["product"] = {
            "old": "",
            "new": "XXXXX-XXXXX-XXXXX-XXXXX-{0}".format(name[-5:]),
        }

    # Если указаны дополнительные аргументы, обновляю информацию по продукту
    if kms_host != "" or kms_port != 0 or activate:
        info = __salt__["mslicense.info"](name)
        if info[0] == False:
            log.error("error occurred while collecting data", info[1])
            return (False, info[1])

    if kms_host != "" and kms_host != info[1][0]["KeyManagementServiceMachine"]:

        install = __salt__["mslicense.set_kms_host"](name)
        if install[0] != True:
            log.error("error when installing the kms-host: ", install[1])
            ret["result"] = False
            ret["comment"] = "error when installing the kms-host"
            return ret

        test_install = __salt__["mslicense.get_kms_host"](name)
        if test_install[0] != True:
            log.error("error when check the kms-host", install[1])
            ret["result"] = False
            ret["comment"] = "error when check the kms-host"
            return ret

        ret["changes"]["kms_host"] = {
            "old": info[1][0]["KeyManagementServiceMachine"],
            "new": test_install[1],
        }

    if kms_port != 0 and kms_port != info[1][0]["KeyManagementServicePort"]:

        install = __salt__["mslicense.set_kms_port"](name)
        if install[0] != True:
            log.error("error when installing the kms-port", install[1])
            ret["result"] = False
            ret["comment"] = "error when installing the kms-port"
            return ret

        test_install = __salt__["mslicense.get_kms_port"](name)
        if test_install[0] != True:
            log.error("error when installing the kms-port", install[1])
            ret["result"] = False
            ret["comment"] = "error when check the kms-port"
            return ret

        ret["changes"]["kms_port"] = {
            "old": info[1][0]["KeyManagementServicePort"],
            "new": test_install[1],
        }

    if activate and info[1][0]["LicenseStatus"] != 1:
        install = __salt__["mslicense.activate"](name)
        if install[0] != True:
            log.error("error when product activate", install[1])
            ret["result"] = False
            ret["comment"] = "error when product activate"
            return ret

        test_install = __salt__["mslicense.licensed"](name)
        if test_install[0] != True:
            log.error("error when check product activate", test_install[1])
            ret["result"] = False
            ret["comment"] = "error when check product activate"
            return ret
        ret["changes"]["activate"] = {
            "old": info[1][0]["LicenseStatus"], "new": 1}

    ret["result"] = True
    return ret


def absent(name: str, all=False):
    """
    name
        ключ продукта (ПО или ОС) для удаления.
    all
        Если указан, удаляет все ключи
    """

    ret = {"name": name[-5:], "result": None, "comment": "", "changes": {}}

    info = __salt__["mslicense.info"](name)
    if info[0] == False:
        log.error("error occurred while collecting data", info[1])
        return (False, info[1])

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = 'would be absent'

        if not all and name[-5:] == info[1][0]["PartialProductKey"]:
            ret["changes"]["uninstall product key"] = {
                "old": "XXXXX-XXXXX-XXXXX-XXXXX-{0}".format(name[-5:]),
                "new": ""
            }
        else:
            ret["changes"]["uninstall product key"] = {
                "old": info[1],
                "new": ""
            }
        return ret

    if all:
        name = ""

    absent_ret = __salt__["mslicense.uninstall"](name)
    if absent_ret[0] != True:
        log.error("error when removing product key: ", absent_ret[1])
        ret["result"] = False
        ret["comment"] = "error when removing product key"
        return ret

    ret["changes"]["uninstall product key"] = {
        "old": info[1],
        "new": ""
    }
    ret["result"] = True
    return ret


def present_kms(name: str, kms_port=0, key=""):
    """
    name
        хост для kms активации
    kms_port
        порт для kms активации
    key
        ключ на который назначется KMS-сервер
    """

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    # Запрос данных о kms-сервере
    info_kms = __salt__["mslicense.get_kms_host"](key)
    if info_kms[0] == False:
        log.error("error occurred while collecting kms-host info", info_kms[1])
        return (False, info_kms[1])

    # Если будет работа с портом - запрос данных по порту
    info_port = (None, 0)
    if kms_port != 0:
        info_port = __salt__["mslicense.get_kms_port"](key)
        if info_port[0] == False:
            log.error("ошибка запроса информации о kms-портах",
                      info_port[1])
            return (False, info_port[1])

    if __opts__["test"]:
        ret["result"] = None

        if key != "":
            ret["comment"] = "{0} would be present for product: XXXXX-XXXXX-XXXXX-XXXXX-{1}".format(
                name, key[-5:])
        else:
            ret["comment"] = "{0} would be present".format(name)

        if info_kms[0] == None:
            ret["changes"]["host"] = {
                "old": "kms installed: {0}".format(info_kms[1]),
                "new": "kms will be install: {0}".format(info_kms[1])
            }

        if kms_port != 0:
            if info_port[0] == None:
                ret["changes"]["port"] = {
                    "old": "kms installed: {0}".format(info_port[1]),
                    "new": "kms will be installed: {0}".format(kms_port)
                }
        return ret

    # Если kms-сервер не установлен, выполняю его установку
    if name != info_kms[1]:
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
            "old": info_kms[1],
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
