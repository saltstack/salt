"""
Manage and query udev info

.. versionadded:: 2015.8.0

"""

import logging

import salt.modules.cmdmod
import salt.utils.path
from salt.exceptions import CommandExecutionError

__salt__ = {
    "cmd.run_all": salt.modules.cmdmod.run_all,
}

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only work when udevadm is installed.
    """
    return salt.utils.path.which_bin(["udevadm"]) is not None


def _parse_udevadm_info(udev_info):
    """
    Parse the info returned by udevadm command.
    """
    devices = []
    dev = {}

    for line in (line.strip() for line in udev_info.splitlines()):
        if line:
            line = line.split(":", 1)
            if len(line) != 2:
                continue
            query, data = line
            if query == "E":
                if query not in dev:
                    dev[query] = {}
                key, val = data.strip().split("=", 1)

                try:
                    val = int(val)
                except ValueError:
                    try:
                        val = float(val)
                    except ValueError:
                        pass  # Quiet, this is not a number.

                dev[query][key] = val
            else:
                if query not in dev:
                    dev[query] = []
                dev[query].append(data.strip())
        else:
            if dev:
                devices.append(_normalize_info(dev))
                dev = {}
    if dev:
        _normalize_info(dev)
        devices.append(_normalize_info(dev))

    return devices


def _normalize_info(dev):
    """
    Replace list with only one element to the value of the element.

    :param dev:
    :return:
    """
    for sect, val in dev.items():
        if len(val) == 1:
            dev[sect] = val[0]

    return dev


def info(dev):
    """
    Extract all info delivered by udevadm

    CLI Example:

    .. code-block:: bash

        salt '*' udev.info /dev/sda
        salt '*' udev.info /sys/class/net/eth0
    """
    if "sys" in dev:
        qtype = "path"
    else:
        qtype = "name"

    cmd = "udevadm info --export --query=all --{}={}".format(qtype, dev)
    udev_result = __salt__["cmd.run_all"](cmd, output_loglevel="quiet")

    if udev_result["retcode"] != 0:
        raise CommandExecutionError(udev_result["stderr"])

    return _parse_udevadm_info(udev_result["stdout"])[0]


def env(dev):
    """
    Return all environment variables udev has for dev

    CLI Example:

    .. code-block:: bash

        salt '*' udev.env /dev/sda
        salt '*' udev.env /sys/class/net/eth0
    """
    return info(dev).get("E", None)


def name(dev):
    """
    Return the actual dev name(s?) according to udev for dev

    CLI Example:

    .. code-block:: bash

        salt '*' udev.dev /dev/sda
        salt '*' udev.dev /sys/class/net/eth0
    """
    return info(dev).get("N", None)


def path(dev):
    """
    Return the physical device path(s?) according to udev for dev

    CLI Example:

    .. code-block:: bash

        salt '*' udev.path /dev/sda
        salt '*' udev.path /sys/class/net/eth0
    """
    return info(dev).get("P", None)


def links(dev):
    """
    Return all udev-created device symlinks

    CLI Example:

    .. code-block:: bash

        salt '*' udev.links /dev/sda
        salt '*' udev.links /sys/class/net/eth0
    """
    return info(dev).get("S", None)


def exportdb():
    """
    Return all the udev database

    CLI Example:

    .. code-block:: bash

        salt '*' udev.exportdb
    """

    cmd = "udevadm info --export-db"
    udev_result = __salt__["cmd.run_all"](cmd, output_loglevel="quiet")

    if udev_result["retcode"]:
        raise CommandExecutionError(udev_result["stderr"])

    return _parse_udevadm_info(udev_result["stdout"])
