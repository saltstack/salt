"""
Configuration of network device

.. versionadded:: 2016.11.0

:codeauthor:    Krzysztof Pawlowski <msciciel@msciciel.eu>
:maturity:      new
:depends:       python-ethtool
:platform:      linux

.. code-block:: yaml

    eth0:
      ethtool.coalesce:
        - name: eth0
        - rx_usecs: 24
        - tx_usecs: 48

    eth0:
      ethtool.ring:
        - name: eth0
        - rx: 1024
        - tx: 1024

    eth0:
      ethtool.offload:
        - name: eth0
        - tcp_segmentation_offload: on

"""

import logging

from salt.exceptions import CommandExecutionError

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    """
    Provide ethtool state
    """
    if "ethtool.show_driver" in __salt__:
        return "ethtool"
    return (False, "ethtool module could not be loaded")


def coalesce(name, **kwargs):
    """
    Manage coalescing settings of network device

    name
        Interface name to apply coalescing settings

    .. code-block:: yaml

        eth0:
          ethtool.coalesce:
            - name: eth0
            - adaptive_rx: on
            - adaptive_tx: on
            - rx_usecs: 24
            - rx_frame: 0
            - rx_usecs_irq: 0
            - rx_frames_irq: 0
            - tx_usecs: 48
            - tx_frames: 0
            - tx_usecs_irq: 0
            - tx_frames_irq: 0
            - stats_block_usecs: 0
            - pkt_rate_low: 0
            - rx_usecs_low: 0
            - rx_frames_low: 0
            - tx_usecs_low: 0
            - tx_frames_low: 0
            - pkt_rate_high: 0
            - rx_usecs_high: 0
            - rx_frames_high: 0
            - tx_usecs_high: 0
            - tx_frames_high: 0
            - sample_interval: 0

    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"Network device {name} coalescing settings are up to date.",
    }
    apply_coalescing = False
    if "test" not in kwargs:
        kwargs["test"] = __opts__.get("test", False)

    # Build coalescing settings
    try:
        old = __salt__["ethtool.show_coalesce"](name)
        if not isinstance(old, dict):
            ret["result"] = False
            ret["comment"] = "Device {} coalescing settings are not supported".format(
                name
            )
            return ret

        new = {}
        diff = []

        # Retreive changes to made
        for key, value in kwargs.items():
            if key in old and value != old[key]:
                new.update({key: value})
                diff.append(f"{key}: {value}")

        # Dry run
        if kwargs["test"]:
            if not new:
                return ret
            if new:
                ret["result"] = None
                ret["comment"] = (
                    "Device {} coalescing settings are set to be updated:\n{}".format(
                        name, "\n".join(diff)
                    )
                )
                return ret

        # Prepare return output
        if new:
            apply_coalescing = True
            ret["comment"] = f"Device {name} coalescing settings updated."
            ret["changes"]["ethtool_coalesce"] = "\n".join(diff)

    except AttributeError as error:
        ret["result"] = False
        ret["comment"] = str(error)
        return ret

    # Apply coalescing settings
    if apply_coalescing:
        try:
            __salt__["ethtool.set_coalesce"](name, **new)
        except AttributeError as error:
            ret["result"] = False
            ret["comment"] = str(error)
            return ret

    return ret


def ring(name, **kwargs):
    """
    Manage rx/tx ring parameters of network device

    Use 'max' word to set with factory maximum

    name
        Interface name to apply ring parameters

    .. code-block:: yaml

        eth0:
          ethtool.ring:
            - name: eth0
            - rx: 1024
            - rx_mini: 0
            - rx_jumbo: 0
            - tx: max

    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"Network device {name} ring parameters are up to date.",
    }
    apply_ring = False
    if "test" not in kwargs:
        kwargs["test"] = __opts__.get("test", False)

    # Build ring parameters
    try:
        old = __salt__["ethtool.show_ring"](name)
        if not isinstance(old, dict):
            ret["result"] = False
            ret["comment"] = f"Device {name} ring parameters are not supported"
            return ret

        new = {}
        diff = []

        # Retreive changes to made
        for key, value in kwargs.items():
            if key in old:
                if value == "max":
                    value = old[f"{key}_max"]

                if value != old[key]:
                    new.update({key: value})
                    diff.append(f"{key}: {value}")

        # Dry run
        if kwargs["test"]:
            if not new:
                return ret
            if new:
                ret["result"] = None
                ret["comment"] = (
                    "Device {} ring parameters are set to be updated:\n{}".format(
                        name, "\n".join(diff)
                    )
                )
                return ret

        # Prepare return output
        if new:
            apply_ring = True
            ret["comment"] = f"Device {name} ring parameters updated."
            ret["changes"]["ethtool_ring"] = "\n".join(diff)

    except AttributeError as error:
        ret["result"] = False
        ret["comment"] = str(error)
        return ret

    # Apply ring parameters
    if apply_ring:
        try:
            __salt__["ethtool.set_ring"](name, **new)
        except AttributeError as error:
            ret["result"] = False
            ret["comment"] = str(error)
            return ret

    return ret


def offload(name, **kwargs):
    """
    Manage protocol offload and other features of network device

    name
        Interface name to apply coalescing settings

    .. code-block:: yaml

        eth0:
          ethtool.offload:
            - name: eth0
            - tcp_segmentation_offload: on

    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"Network device {name} offload settings are up to date.",
    }
    apply_offload = False
    if "test" not in kwargs:
        kwargs["test"] = __opts__.get("test", False)

    # Build offload settings
    try:
        old = __salt__["ethtool.show_offload"](name)
        if not isinstance(old, dict):
            ret["result"] = False
            ret["comment"] = f"Device {name} offload settings are not supported"
            return ret

        new = {}
        diff = []

        # Retreive changes to made
        for key, value in kwargs.items():
            value = value and "on" or "off"
            if key in old and value != old[key]:
                new.update({key: value})
                diff.append(f"{key}: {value}")

        # Dry run
        if kwargs["test"]:
            if not new:
                return ret
            if new:
                ret["result"] = None
                ret["comment"] = (
                    "Device {} offload settings are set to be updated:\n{}".format(
                        name, "\n".join(diff)
                    )
                )
                return ret

        # Prepare return output
        if new:
            apply_offload = True
            ret["comment"] = f"Device {name} offload settings updated."
            ret["changes"]["ethtool_offload"] = "\n".join(diff)

    except AttributeError as error:
        ret["result"] = False
        ret["comment"] = str(error)
        return ret

    # Apply offload settings
    if apply_offload:
        try:
            __salt__["ethtool.set_offload"](name, **new)
        except AttributeError as error:
            ret["result"] = False
            ret["comment"] = str(error)
            return ret

    return ret


def pause(name, **kwargs):
    """
    .. versionadded:: 3006.0

    Manage pause parameters of network device

    name
        Interface name to apply pause parameters

    .. code-block:: yaml

        eth0:
          ethtool.pause:
            - name: eth0
            - autoneg: off
            - rx: off
            - tx: off

    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"Network device {name} pause parameters are up to date.",
    }
    apply_pause = False

    # Get current pause parameters
    try:
        old = __salt__["ethtool.show_pause"](name)
    except CommandExecutionError:
        ret["result"] = False
        ret["comment"] = f"Device {name} pause parameters are not supported"
        return ret

    # map ethtool command input to output text
    pause_map = {
        "autoneg": "Autonegotiate",
        "rx": "RX",
        "tx": "RX",
    }

    # Process changes
    new = {}
    diff = []

    for key, value in kwargs.items():
        key = key.lower()
        if key in pause_map:
            if value != old[pause_map[key]]:
                new.update({key: value})
                if value is True:
                    value = "on"
                elif value is False:
                    value = "off"
                diff.append(f"{key}: {value}")

    if not new:
        return ret

    # Dry run
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Device {} pause parameters are set to be updated:\n{}".format(
            name, "\n".join(diff)
        )
        return ret

    # Apply pause parameters
    try:
        __salt__["ethtool.set_pause"](name, **new)
        # Prepare return output
        ret["comment"] = f"Device {name} pause parameters updated."
        ret["changes"]["ethtool_pause"] = "\n".join(diff)
    except CommandExecutionError as exc:
        ret["result"] = False
        ret["comment"] = str(exc)
        return ret

    return ret
