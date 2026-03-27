"""
Track status beacon events and maintain a register of active minions.

This module is the foundation for health-oriented Thorium formulas. It records
the latest status beacon payload and the receive time for each minion so later
states can reason about stale or missing check-ins.

.. versionadded:: 2016.11.0
"""

import fnmatch
import time


def reg(name):
    """
    Activate this register to turn on a minion status tracking register, this
    register keeps the current status beacon data and the time that each beacon
    was last checked in.

    This state watches events whose tag matches ``salt/beacon/*/status/*``.
    It is commonly paired with ``key.timeout`` to reject or delete keys for
    minions that stop reporting.

    USAGE:

    .. code-block:: yaml

        status_register:
          status.reg

        reject_stale_keys:
          key.timeout:
            - reject: 300
            - require:
              - status: status_register
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
