"""
Module for running ethtool command

.. versionadded:: 2016.3.0

:codeauthor:    Krzysztof Pawlowski <msciciel@msciciel.eu>
:maturity:      new
:depends:       python-ethtool
:platform:      linux
"""

import logging
import os

import salt.utils.path
from salt.exceptions import CommandExecutionError

try:
    import ethtool

    HAS_ETHTOOL = True
except ImportError:
    HAS_ETHTOOL = False

log = logging.getLogger(__name__)

ethtool_coalesce_map = {
    "pkt_rate_high": "pkt_rate_high",
    "pkt_rate_low": "pkt_rate_low",
    "sample_interval": "rate_sample_interval",
    "rx_usecs": "rx_coalesce_usecs",
    "rx_usecs_high": "rx_coalesce_usecs_high",
    "rx_usecs_irq": "rx_coalesce_usecs_irq",
    "rx_usecs_low": "rx_coalesce_usecs_low",
    "rx_frames": "rx_max_coalesced_frames",
    "rx_frames_high": "rx_max_coalesced_frames_high",
    "rx_frames_irg": "rx_max_coalesced_frames_irq",
    "rx_frames_low": "rx_max_coalesced_frames_low",
    "stats_block_usecs": "stats_block_coalesce_usecs",
    "tx_usecs": "tx_coalesce_usecs",
    "tx_usecs_high": "tx_coalesce_usecs_high",
    "tx_usecs_irq": "tx_coalesce_usecs_irq",
    "tx_usecs_low": "tx_coalesce_usecs_low",
    "tx_frames": "tx_max_coalesced_frames",
    "tx_frames_high": "tx_max_coalesced_frames_high",
    "tx_frames_irq": "tx_max_coalesced_frames_irq",
    "tx_frames_low": "tx_max_coalesced_frames_low",
    "adaptive_rx": "use_adaptive_rx_coalesce",
    "adaptive_tx": "use_adaptive_tx_coalesce",
}

ethtool_coalesce_remap = {}
for k, v in ethtool_coalesce_map.items():
    ethtool_coalesce_remap[v] = k

ethtool_ring_map = {
    "rx": "rx_pending",
    "rx_max": "rx_max_pending",
    "rx_mini": "rx_mini_pending",
    "rx_mini_max": "rx_mini_max_pending",
    "rx_jumbo": "rx_jumbo_pending",
    "rx_jumbo_max": "rx_jumbo_max_pending",
    "tx": "tx_pending",
    "tx_max": "tx_max_pending",
}

ethtool_ring_remap = {}
for k, v in ethtool_ring_map.items():
    ethtool_ring_remap[v] = k

# Define the module's virtual name
__virtualname__ = "ethtool"


def __virtual__():
    """
    Only load this module if python-ethtool is installed
    """
    if HAS_ETHTOOL:
        return __virtualname__
    else:
        return (
            False,
            "The ethtool module could not be loaded: ethtool "
            "python libraries not found.",
        )


def show_ring(devname):
    """
    Queries the specified network device for rx/tx ring parameter information

    CLI Example:

    .. code-block:: bash

        salt '*' ethtool.show_ring <devname>
    """

    try:
        ring = ethtool.get_ringparam(devname)
    except OSError:
        log.error("Ring parameters not supported on %s", devname)
        return "Not supported"

    ret = {}
    for key, value in ring.items():
        ret[ethtool_ring_remap[key]] = ring[key]

    return ret


def show_coalesce(devname):
    """
    Queries the specified network device for coalescing information

    CLI Example:

    .. code-block:: bash

        salt '*' ethtool.show_coalesce <devname>
    """

    try:
        coalesce = ethtool.get_coalesce(devname)
    except OSError:
        log.error("Interrupt coalescing not supported on %s", devname)
        return "Not supported"

    ret = {}
    for key, value in coalesce.items():
        ret[ethtool_coalesce_remap[key]] = coalesce[key]

    return ret


def show_driver(devname):
    """
    Queries the specified network device for associated driver information

    CLI Example:

    .. code-block:: bash

        salt '*' ethtool.show_driver <devname>
    """

    try:
        module = ethtool.get_module(devname)
    except OSError:
        log.error("Driver information not implemented on %s", devname)
        return "Not implemented"

    try:
        businfo = ethtool.get_businfo(devname)
    except OSError:
        log.error("Bus information no available on %s", devname)
        return "Not available"

    ret = {
        "driver": module,
        "bus_info": businfo,
    }

    return ret


def set_ring(devname, **kwargs):
    """
    Changes the rx/tx ring parameters of the specified network device

    CLI Example:

    .. code-block:: bash

        salt '*' ethtool.set_ring <devname> [rx=N] [rx_mini=N] [rx_jumbo=N] [tx=N]
    """

    try:
        ring = ethtool.get_ringparam(devname)
    except OSError:
        log.error("Ring parameters not supported on %s", devname)
        return "Not supported"

    changed = False
    for param, value in kwargs.items():
        if param in ethtool_ring_map:
            param = ethtool_ring_map[param]
            if param in ring:
                if ring[param] != value:
                    ring[param] = value
                    changed = True

    try:
        if changed:
            ethtool.set_ringparam(devname, ring)
        return show_ring(devname)
    except OSError:
        log.error("Invalid ring arguments on %s: %s", devname, ring)
        return "Invalid arguments"


def set_coalesce(devname, **kwargs):
    """
    Changes the coalescing settings of the specified network device

    CLI Example:

    .. code-block:: bash

        salt '*' ethtool.set_coalesce <devname> [adaptive_rx=on|off] [adaptive_tx=on|off] [rx_usecs=N] [rx_frames=N]
            [rx_usecs_irq=N] [rx_frames_irq=N] [tx_usecs=N] [tx_frames=N] [tx_usecs_irq=N] [tx_frames_irq=N]
            [stats_block_usecs=N] [pkt_rate_low=N] [rx_usecs_low=N] [rx_frames_low=N] [tx_usecs_low=N] [tx_frames_low=N]
            [pkt_rate_high=N] [rx_usecs_high=N] [rx_frames_high=N] [tx_usecs_high=N] [tx_frames_high=N]
            [sample_interval=N]
    """

    try:
        coalesce = ethtool.get_coalesce(devname)
    except OSError:
        log.error("Interrupt coalescing not supported on %s", devname)
        return "Not supported"

    changed = False
    for param, value in kwargs.items():
        if param in ethtool_coalesce_map:
            param = ethtool_coalesce_map[param]
            if param in coalesce:
                if coalesce[param] != value:
                    coalesce[param] = value
                    changed = True

    try:
        if changed:
            # pylint: disable=too-many-function-args
            ethtool.set_coalesce(devname, coalesce)
            # pylint: enable=too-many-function-args
        return show_coalesce(devname)
    except OSError:
        log.error("Invalid coalesce arguments on %s: %s", devname, coalesce)
        return "Invalid arguments"


def show_offload(devname):
    """
    Queries the specified network device for the state of protocol offload and other features

    CLI Example:

    .. code-block:: bash

        salt '*' ethtool.show_offload <devname>
    """

    try:
        sg = ethtool.get_sg(devname) and "on" or "off"
    except OSError:
        sg = "not supported"

    try:
        tso = ethtool.get_tso(devname) and "on" or "off"
    except OSError:
        tso = "not supported"

    try:
        ufo = ethtool.get_ufo(devname) and "on" or "off"
    except OSError:
        ufo = "not supported"

    try:
        gso = ethtool.get_gso(devname) and "on" or "off"
    except OSError:
        gso = "not supported"

    offload = {
        "scatter_gather": sg,
        "tcp_segmentation_offload": tso,
        "udp_fragmentation_offload": ufo,
        "generic_segmentation_offload": gso,
    }

    return offload


def set_offload(devname, **kwargs):
    """
    Changes the offload parameters and other features of the specified network device

    CLI Example:

    .. code-block:: bash

        salt '*' ethtool.set_offload <devname> tcp_segmentation_offload=on
    """

    for param, value in kwargs.items():
        if param == "tcp_segmentation_offload":
            value = value == "on" and 1 or 0
            try:
                ethtool.set_tso(devname, value)
            except OSError:
                return "Not supported"

    return show_offload(devname)


def _ethtool_command(devname, *args, **kwargs):
    """
    Helper function to build an ethtool command
    """
    ethtool = salt.utils.path.which("ethtool")
    if not ethtool:
        raise CommandExecutionError("Command 'ethtool' cannot be found")
    switches = " ".join(arg for arg in args)
    params = " ".join("{} {}".format(key, val) for key, val in kwargs.items())
    cmd = "{} {} {} {}".format(ethtool, switches, devname, params).strip()
    ret = __salt__["cmd.run"](cmd, ignore_retcode=True).splitlines()
    if ret and ret[0].startswith("Cannot"):
        raise CommandExecutionError(ret[0])
    return ret


def _validate_params(valid_params, kwargs):
    """
    Helper function to validate parameters to ethtool commands. Boolean values
    will be transformed into ``on`` and ``off`` to match expected syntax.
    """
    validated = {}
    for key, val in kwargs.items():
        key = key.lower()
        if key in valid_params:
            if val is True:
                val = "on"
            elif val is False:
                val = "off"
            validated[key] = val
    if not validated:
        raise CommandExecutionError(
            "None of the valid parameters were provided: {}".format(valid_params)
        )
    return validated


def show_pause(devname):
    """
    .. versionadded:: 3006.0

    Queries the specified network device for associated pause information

    CLI Example:

    .. code-block:: bash

        salt '*' ethtool.show_pause <devname>
    """
    data = {}

    content = _ethtool_command(devname, "-a")

    for line in content[1:]:
        if line.strip():
            (key, value) = (s.strip() for s in line.split(":", 1))
            data[key] = value == "on"

    return data


def set_pause(devname, **kwargs):
    """
    .. versionadded:: 3006.0

    Changes the pause parameters of the specified network device

    CLI Example:

    .. code-block:: bash

        salt '*' ethtool.set_pause <devname> autoneg=off rx=off tx=off
    """
    valid_params = ["autoneg", "rx", "tx"]
    params = _validate_params(valid_params, kwargs)
    ret = _ethtool_command(devname, "-A", **params)
    if not ret:
        return True
    return ret


def show_features(devname):
    """
    .. versionadded:: 3006.0

    Queries the specified network device for associated feature information

    CLI Example:

    .. code-block:: bash

        salt '*' ethtool.show_features <devname>
    """
    data = {}

    content = _ethtool_command(devname, "-k")

    for line in content[1:]:
        if ":" in line:
            key, value = (s.strip() for s in line.strip().split(":", 1))
            fixed = "fixed" in value
            if fixed:
                value = value.split()[0].strip()
            data[key.strip()] = {"on": value == "on", "fixed": fixed}

    return data


def set_feature(devname, **kwargs):
    """
    .. versionadded:: 3006.0

    Changes the feature parameters of the specified network device

    CLI Example:

    .. code-block:: bash

        salt '*' ethtool.set_feature <devname> sg=off
    """
    valid_params = [
        "rx",
        "tx",
        "sg",
        "tso",
        "ufo",
        "gso",
        "gro",
        "lro",
        "rxvlan",
        "txvlan",
        "ntuple",
        "rxhash",
    ]
    params = _validate_params(valid_params, kwargs)
    ret = _ethtool_command(devname, "-K", **params)
    if not ret:
        return True
    return os.linesep.join(ret)
