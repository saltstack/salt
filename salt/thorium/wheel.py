"""
React by calling asynchronous runners
"""

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
