"""
Process Management
==================

Ensure a process matching a given pattern is absent.

.. code-block:: yaml

    httpd-absent:
      process.absent:
        - name: apache2
"""


def __virtual__():
    if "ps.pkill" in __salt__:
        return True
    return (False, "ps module could not be loaded")


def absent(name, user=None, signal=None):
    """
    Ensures that the named command is not running.

    name
        The pattern to match.

    user
        The user to which the process belongs

    signal
        Signal to send to the process(es).
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if __opts__["test"]:
        running = __salt__["ps.pgrep"](name, user=user)
        ret["result"] = None
        if running:
            ret["comment"] = "{} processes will be killed".format(len(running))
        else:
            ret["comment"] = "No matching processes running"
        return ret

    if signal:
        status = __salt__["ps.pkill"](name, user=user, signal=signal, full=True)
    else:
        status = __salt__["ps.pkill"](name, user=user, full=True)

    ret["result"] = True
    if status:
        ret["comment"] = "Killed {} processes".format(len(status["killed"]))
        ret["changes"] = status
    else:
        ret["comment"] = "No matching processes running"
    return ret
