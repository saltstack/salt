"""
Device-Mapper module
"""

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
        return f"{device} does not exist"

    cmd = f"multipath -f {device}"
    return __salt__["cmd.run"](cmd).splitlines()
