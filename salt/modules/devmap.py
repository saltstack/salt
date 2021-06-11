# -*- coding: utf-8 -*-
"""
Device-Mapper module
"""
from __future__ import absolute_import, print_function, unicode_literals

import os.path


def multipath_list():
    """
    Device-Mapper Multipath list

    CLI Example:

    .. code-block:: bash

        salt '*' devmap.multipath_list
    """
    cmd = "multipath -l"
    return __salt__["cmd.run"](cmd).splitlines()


def multipath_flush(device):
    """
    Device-Mapper Multipath flush

    CLI Example:

    .. code-block:: bash

        salt '*' devmap.multipath_flush mpath1
    """
    if not os.path.exists(device):
        return "{0} does not exist".format(device)

    cmd = "multipath -f {0}".format(device)
    return __salt__["cmd.run"](cmd).splitlines()
