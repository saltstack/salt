"""
:maintainer:    Alberto Planas <aplanas@suse.com>
:maturity:      new
:depends:       None
:platform:      Linux
"""

import logging

log = logging.getLogger(__name__)

__func_alias__ = {
    "filter_": "filter",
}


def _udev(udev_info, key):
    """
    Return the value for a udev key.

    The `key` parameter is a lower case text joined by dots. For
    example, 'e.id_bus' will represent the key for
    `udev_info['E']['ID_BUS']`.

    """
    k, _, r = key.partition(".")
    if not k:
        return udev_info
    if not isinstance(udev_info, dict):
        return "n/a"
    if not r:
        return udev_info.get(k.upper(), "n/a")
    return _udev(udev_info.get(k.upper(), {}), r)


def _match(udev_info, match_info):
    """
    Check if `udev_info` match the information from `match_info`.
    """
    res = True
    for key, value in match_info.items():
        udev_value = _udev(udev_info, key)
        if isinstance(udev_value, dict):
            # If is a dict we probably make a mistake in key from
            # match_info, as is not accessing a final value
            log.warning(
                "The key %s for the udev information dictionary is not a leaf element",
                key,
            )
            continue

        # Converting both values to sets make easy to see if there is
        # a coincidence between both values
        value = set(value) if isinstance(value, list) else {value}
        udev_value = set(udev_value) if isinstance(udev_value, list) else {udev_value}
        res = res and (value & udev_value)
    return res


def filter_(udev_in=None, udev_ex=None):
    """
    Returns a list of devices, filtered under udev keys.

    udev_in
        A dictionary of key:values that are expected in the device
        udev information

    udev_ex
        A dictionary of key:values that are not expected in the device
        udev information (excluded)

    The key is a lower case string, joined by dots, that represent a
    path in the udev information dictionary. For example, 'e.id_bus'
    will represent the udev entry `udev['E']['ID_BUS']`

    If the udev entry is a list, the algorithm will check that at
    least one item match one item of the value of the parameters.

    Returns list of devices that match `udev_in` and do not match
    `udev_ex`.

    CLI Example:

    .. code-block:: bash

       salt '*' devinfo.filter udev_in='{"e.id_bus": "ata"}'

    """

    udev_in = udev_in if udev_in else {}
    udev_ex = udev_ex if udev_ex else {}

    all_devices = __grains__["disks"]

    # Get the udev information only one time
    udev_info = {d: __salt__["udev.info"](d) for d in all_devices}

    devices_udev_key_in = {d for d in all_devices if _match(udev_info[d], udev_in)}
    devices_udev_key_ex = {
        d for d in all_devices if _match(udev_info[d], udev_ex) if udev_ex
    }

    return sorted(devices_udev_key_in - devices_udev_key_ex)


def _hwinfo_parse_short(report):
    """Parse the output of hwinfo and return a dictionary"""
    result = {}
    current_result = {}
    key_counter = 0
    for line in report.strip().splitlines():
        if line.startswith("    "):
            key = key_counter
            key_counter += 1
            current_result[key] = line.strip()
        elif line.startswith("  "):
            key, value = line.strip().split(" ", 1)
            current_result[key] = value.strip()
        elif line.endswith(":"):
            key = line[:-1]
            value = {}
            result[key] = value
            current_result = value
            key_counter = 0
        else:
            log.error("Error parsing hwinfo short output: %s", line)

    return result


def _hwinfo_parse_full(report):
    """Parse the output of hwinfo and return a dictionary"""
    result = {}
    result_stack = []
    level = 0
    for line in report.strip().splitlines():
        current_level = line.count("  ")
        if level != current_level or len(result_stack) != result_stack:
            result_stack = result_stack[:current_level]
            level = current_level
        line = line.strip()

        # Ignore empty lines
        if not line:
            continue

        # Initial line of a segment
        if level == 0:
            key, value = line.split(":", 1)
            sub_result = {}
            result[key] = sub_result
            # The first line contains also a sub-element
            key, value = value.strip().split(": ", 1)
            sub_result[key] = value
            result_stack.append(sub_result)
            level += 1
            continue

        # Line is a note
        if line.startswith("[") or ":" not in line:
            sub_result = result_stack[-1]
            sub_result["Note"] = line if not line.startswith("[") else line[1:-1]
            continue

        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        sub_result = result_stack[-1]
        # If there is a value and it not starts with hash, this is a
        # (key, value) entry. But there are exception on the rule,
        # like when is about 'El Torito info', that is the begining of
        # a new dictorionart.
        if value and not value.startswith("#") and key != "El Torito info":
            if key == "I/O Port":
                key = "I/O Ports"
            elif key == "Config Status":
                value = dict(item.split("=") for item in value.split(", "))
            elif key in ("Driver", "Driver Modules"):
                value = value.replace('"', "").split(", ")
            elif key in ("Tags", "Device Files", "Features"):
                # We cannot split by ', ', as using spaces in
                # inconsisten in some fields
                value = [v.strip() for v in value.split(",")]
            else:
                if value.startswith('"'):
                    value = value[1:-1]

            # If there is a collision, we store it as a list
            if key in sub_result:
                current_value = sub_result[key]
                if type(current_value) is not list:
                    current_value = [current_value]
                if value not in current_value:
                    current_value.append(value)
                if len(current_value) == 1:
                    value = current_value[0]
                else:
                    value = current_value
            sub_result[key] = value
        else:
            if value.startswith("#"):
                value = {"Handle": value}
            elif key == "El Torito info":
                value = value.split(", ")
                value = {
                    "platform": value[0].split()[-1],
                    "bootable": "no" if "not" in value[1] else "yes",
                }
            else:
                value = {}

            sub_result[key] = value
            result_stack.append(value)
            level += 1

    return result


def _hwinfo_parse(report, short):
    """Parse the output of hwinfo and return a dictionary"""
    if short:
        return _hwinfo_parse_short(report)
    else:
        return _hwinfo_parse_full(report)


def _hwinfo_efi():
    """Return information about EFI"""
    return {
        "efi": __grains__["efi"],
        "efi-secure-boot": __grains__["efi-secure-boot"],
    }


def _hwinfo_memory():
    """Return information about the memory"""
    return {
        "mem_total": __grains__["mem_total"],
    }


def _hwinfo_network(short):
    """Return network information"""
    info = {
        "fqdn": __grains__["fqdn"],
        "ip_interfaces": __grains__["ip_interfaces"],
    }

    if not short:
        info["dns"] = __grains__["dns"]

    return info


def hwinfo(items=None, short=True, listmd=False, devices=None):
    """
    Probe for hardware

    items
        List of hardware items to inspect. Default ['bios', 'cpu', 'disk',
        'memory', 'network', 'partition']

    short
        Show only a summary. Default True.

    listmd
        Report RAID devices. Default False.

    devices
        List of devices to show information from. Default None.

    CLI Example:

    .. code-block:: bash

       salt '*' devinfo.hwinfo
       salt '*' devinfo.hwinfo items='["disk"]' short=no
       salt '*' devinfo.hwinfo items='["disk"]' short=no devices='["/dev/sda"]'
       salt '*' devinfo.hwinfo devices=/dev/sda

    """
    result = {}

    if not items:
        items = ["bios", "cpu", "disk", "memory", "network", "partition"]
    if not isinstance(items, (list, tuple)):
        items = [items]

    if not devices:
        devices = []
    if devices and not isinstance(devices, (list, tuple)):
        devices = [devices]

    cmd = ["hwinfo"]
    for item in items:
        cmd.append("--{}".format(item))

    if short:
        cmd.append("--short")

    if listmd:
        cmd.append("--listmd")

    for device in devices:
        cmd.append("--only {}".format(device))

    out = __salt__["cmd.run_stdout"](cmd)
    result["hwinfo"] = _hwinfo_parse(out, short)

    if "bios" in items:
        result["bios grains"] = _hwinfo_efi()

    if "memory" in items:
        result["memory grains"] = _hwinfo_memory()

    if "network" in items:
        result["network grains"] = _hwinfo_network(short)

    return result
