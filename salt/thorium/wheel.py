"""
React by calling asynchronous wheel functions from Thorium.

This is useful for master-side maintenance operations such as key management or
other wheel actions that should only happen after Thorium has observed and
evaluated a stream of events.
"""

import salt.wheel


def cmd(name, fun=None, arg=(), **kwargs):
    """
    Execute a wheel function asynchronously.

    Any additional keyword arguments passed to this Thorium state are forwarded
    to the wheel function.

    USAGE:

    .. code-block:: yaml

        run_cloud:
          wheel.cmd:
            - fun: key.delete
            - match: minion_id

        reject_stale_key:
          wheel.cmd:
            - fun: key.reject
            - match: old-minion
            - require:
              - check: important_event
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": True}
    if fun is None:
        fun = name
    client = salt.wheel.WheelClient(__opts__)
    low = {"fun": fun, "arg": arg, "kwargs": kwargs}
    client.cmd_async(low)
    return ret
