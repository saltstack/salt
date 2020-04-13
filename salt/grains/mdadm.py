# -*- coding: utf-8 -*-
"""
Detect MDADM RAIDs
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

# Import salt libs
import salt.utils.files

log = logging.getLogger(__name__)


def mdadm():
    """
    Return list of mdadm devices
    """
    devices = set()
    try:
        with salt.utils.files.fopen("/proc/mdstat", "r") as mdstat:
            for line in mdstat:
                line = salt.utils.stringutils.to_unicode(line)
                if line.startswith("Personalities : "):
                    continue
                if line.startswith("unused devices:"):
                    continue
                if " : " in line:
                    devices.add(line.split(" : ")[0])
    except IOError:
        return {}

    devices = sorted(devices)
    if devices:
        log.trace("mdadm devices detected: %s", ", ".join(devices))

    return {"mdadm": devices}
