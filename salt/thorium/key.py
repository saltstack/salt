"""
Apply Thorium decisions to accepted, rejected, and pending minion keys.

This module is intended for workflows where Thorium tracks minion health and
then removes or rejects keys for minions that have stopped reporting.

.. versionadded:: 2016.11.0
"""

import time

import salt.key


def _get_key_api():
    """
    Return the key api hook
    """
    if "keyapi" not in __context__:
        __context__["keyapi"] = salt.key.Key(__opts__)
    return __context__["keyapi"]


def timeout(name, delete=0, reject=0):
    """
    If any minion's status is older than the timeout value then apply the
    given action to the timed out key. This example will remove keys to
    minions that have not checked in for 300 seconds (5 minutes).

    This state depends on the ``status`` register created by ``status.reg``.
    ``delete`` removes keys entirely, while ``reject`` leaves them visible in a
    rejected state.

    USAGE:

    .. code-block:: yaml

        statreg:
          status.reg

        clean_keys:
          key.timeout:
            - require:
              - status: statreg
            - delete: 300

        reject_keys:
          key.timeout:
            - require:
              - status: statreg
            - reject: 300
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": True}
    now = time.time()
    ktr = "key_start_tracker"
    if ktr not in __context__:
        __context__[ktr] = {}
    remove = set()
    reject_set = set()
    keyapi = _get_key_api()
    current = keyapi.list_status("acc")
    for id_ in current.get("minions", []):
        if id_ in __reg__["status"]["val"]:
            # minion is reporting, check timeout and mark for removal
            if delete and (now - __reg__["status"]["val"][id_]["recv_time"]) > delete:
                remove.add(id_)
            if reject and (now - __reg__["status"]["val"][id_]["recv_time"]) > reject:
                reject_set.add(id_)
        else:
            # No report from minion recorded, mark for change if thorium has
            # been running for longer than the timeout
            if id_ not in __context__[ktr]:
                __context__[ktr][id_] = now
            else:
                if delete and (now - __context__[ktr][id_]) > delete:
                    remove.add(id_)
                if reject and (now - __context__[ktr][id_]) > reject:
                    reject_set.add(id_)
    for id_ in remove:
        keyapi.delete_key(id_)
        __reg__["status"]["val"].pop(id_, None)
        __context__[ktr].pop(id_, None)
    for id_ in reject_set:
        keyapi.reject(id_)
        __reg__["status"]["val"].pop(id_, None)
        __context__[ktr].pop(id_, None)
    return ret
