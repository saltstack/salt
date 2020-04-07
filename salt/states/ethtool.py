# -*- coding: utf-8 -*-
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

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt libs
from salt.ext import six

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    """
    Provide ethtool state
    """
    return "ethtool" if "ethtool.show_driver" in __salt__ else False


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
        "comment": "Network device {0} coalescing settings are up to date.".format(
            name
        ),
    }
    apply_coalescing = False
    if "test" not in kwargs:
        kwargs["test"] = __opts__.get("test", False)

    # Build coalescing settings
    try:
        old = __salt__["ethtool.show_coalesce"](name)
        if not isinstance(old, dict):
            ret["result"] = False
            ret["comment"] = "Device {0} coalescing settings are not supported".format(
                name
            )
            return ret

        new = {}
        diff = []

        # Retreive changes to made
        for key, value in kwargs.items():
            if key in old and value != old[key]:
                new.update({key: value})
                diff.append("{0}: {1}".format(key, value))

        # Dry run
        if kwargs["test"]:
            if not new:
                return ret
            if new:
                ret["result"] = None
                ret["comment"] = (
                    "Device {0} coalescing settings are set to be "
                    "updated:\n{1}".format(name, "\n".join(diff))
                )
                return ret

        # Prepare return output
        if new:
            apply_coalescing = True
            ret["comment"] = "Device {0} coalescing settings updated.".format(name)
            ret["changes"]["ethtool_coalesce"] = "\n".join(diff)

    except AttributeError as error:
        ret["result"] = False
        ret["comment"] = six.text_type(error)
        return ret

    # Apply coalescing settings
    if apply_coalescing:
        try:
            __salt__["ethtool.set_coalesce"](name, **new)
        except AttributeError as error:
            ret["result"] = False
            ret["comment"] = six.text_type(error)
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
        "comment": "Network device {0} ring parameters are up to date.".format(name),
    }
    apply_ring = False
    if "test" not in kwargs:
        kwargs["test"] = __opts__.get("test", False)

    # Build ring parameters
    try:
        old = __salt__["ethtool.show_ring"](name)
        if not isinstance(old, dict):
            ret["result"] = False
            ret["comment"] = "Device {0} ring parameters are not supported".format(name)
            return ret

        new = {}
        diff = []

        # Retreive changes to made
        for key, value in kwargs.items():
            if key in old:
                if value == "max":
                    value = old["{0}_max".format(key)]

                if value != old[key]:
                    new.update({key: value})
                    diff.append("{0}: {1}".format(key, value))

        # Dry run
        if kwargs["test"]:
            if not new:
                return ret
            if new:
                ret["result"] = None
                ret["comment"] = (
                    "Device {0} ring parameters are set to be "
                    "updated:\n{1}".format(name, "\n".join(diff))
                )
                return ret

        # Prepare return output
        if new:
            apply_ring = True
            ret["comment"] = "Device {0} ring parameters updated.".format(name)
            ret["changes"]["ethtool_ring"] = "\n".join(diff)

    except AttributeError as error:
        ret["result"] = False
        ret["comment"] = six.text_type(error)
        return ret

    # Apply ring parameters
    if apply_ring:
        try:
            __salt__["ethtool.set_ring"](name, **new)
        except AttributeError as error:
            ret["result"] = False
            ret["comment"] = six.text_type(error)
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
        "comment": "Network device {0} offload settings are up to date.".format(name),
    }
    apply_offload = False
    if "test" not in kwargs:
        kwargs["test"] = __opts__.get("test", False)

    # Build offload settings
    try:
        old = __salt__["ethtool.show_offload"](name)
        if not isinstance(old, dict):
            ret["result"] = False
            ret["comment"] = "Device {0} offload settings are not supported".format(
                name
            )
            return ret

        new = {}
        diff = []

        # Retreive changes to made
        for key, value in kwargs.items():
            value = value and "on" or "off"
            if key in old and value != old[key]:
                new.update({key: value})
                diff.append("{0}: {1}".format(key, value))

        # Dry run
        if kwargs["test"]:
            if not new:
                return ret
            if new:
                ret["result"] = None
                ret["comment"] = (
                    "Device {0} offload settings are set to be "
                    "updated:\n{1}".format(name, "\n".join(diff))
                )
                return ret

        # Prepare return output
        if new:
            apply_offload = True
            ret["comment"] = "Device {0} offload settings updated.".format(name)
            ret["changes"]["ethtool_offload"] = "\n".join(diff)

    except AttributeError as error:
        ret["result"] = False
        ret["comment"] = six.text_type(error)
        return ret

    # Apply offload settings
    if apply_offload:
        try:
            __salt__["ethtool.set_offload"](name, **new)
        except AttributeError as error:
            ret["result"] = False
            ret["comment"] = six.text_type(error)
            return ret

    return ret
