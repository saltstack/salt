"""
This thorium state is used to track the status beacon events and keep track of
the active status of minions

.. versionadded:: 2016.11.0
"""

import fnmatch
import time


def reg(name):
    """
    Activate this register to turn on a minion status tracking register, this
    register keeps the current status beacon data and the time that each beacon
    was last checked in.
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": True}
    now = time.time()
    if "status" not in __reg__:
        __reg__["status"] = {}
        __reg__["status"]["val"] = {}
    for event in __events__:
        if fnmatch.fnmatch(event["tag"], "salt/beacon/*/status/*"):
            # Got one!
            idata = {"recv_time": now}
            for key in event["data"]["data"]:
                if key in ("id", "recv_time"):
                    continue
                idata[key] = event["data"]["data"][key]
            __reg__["status"]["val"][event["data"]["id"]] = idata
            ret["changes"][event["data"]["id"]] = True
    return ret
