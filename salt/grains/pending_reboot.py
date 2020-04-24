# -*- coding: utf-8 -*-
"""
Grain that indicates the system is pending a reboot
See functions in salt.utils.win_system to see what conditions would indicate
a reboot is pending
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

# Import salt libs
import salt.utils.platform
import salt.utils.win_system

log = logging.getLogger(__name__)

__virtualname__ = "pending_reboot"


def __virtual__():
    if not salt.utils.platform.is_windows():
        return False, "'pending_reboot' grain only available on Windows"
    return __virtualname__


def pending_reboot():
    """
    A grain that indicates that the system is pending a reboot.
    """
    return {"pending_reboot": salt.utils.win_system.get_pending_reboot()}
