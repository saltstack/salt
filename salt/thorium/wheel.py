# -*- coding: utf-8 -*-
"""
React by calling asynchronous runners
"""
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# import salt libs
import salt.wheel


def cmd(name, fun=None, arg=(), **kwargs):
    """
    Execute a runner asynchronous:

    USAGE:

    .. code-block:: yaml

        run_cloud:
          wheel.cmd:
            - fun: key.delete
            - match: minion_id
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": True}
    if fun is None:
        fun = name
    client = salt.wheel.WheelClient(__opts__)
    low = {"fun": fun, "arg": arg, "kwargs": kwargs}
    client.cmd_async(low)
    return ret
