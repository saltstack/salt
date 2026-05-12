"""
Minion status monitoring

Maps to the `status` execution module.
"""

__monitor__ = [
    "loadavg",
    "process",
]


def loadavg(name, maximum=None, minimum=None):
    """
    Return the current load average for the specified minion. Available values
    for name are `1-min`, `5-min` and `15-min`. `minimum` and `maximum` values
    should be passed in as strings.
    """
    # Monitoring state, no changes will be made so no test interface needed
    ret = {
        "name": name,
        "result": False,
        "comment": "",
        "changes": {},
        "data": {},
    }  # Data field for monitoring state

    data = __salt__["status.loadavg"]()
    if name not in data:
        ret["result"] = False
        ret["comment"] += f"Requested load average {name} not available "
        return ret
    if minimum and maximum and minimum >= maximum:
        ret["comment"] += "Min must be less than max"
    if ret["comment"]:
        return ret
    cap = float(data[name])
    ret["data"] = data[name]
    if minimum:
        if cap < float(minimum):
            ret["comment"] = "Load avg is below minimum of {} at {}".format(
                minimum, cap
            )
            return ret
    if maximum:
        if cap > float(maximum):
            ret["comment"] = f"Load avg above maximum of {maximum} at {cap}"
            return ret
    ret["comment"] = "Load avg in acceptable range"
    ret["result"] = True
    return ret


def process(name):
    """
    Return whether the specified signature is found in the process tree. This
    differs slightly from the services states, in that it may refer to a
    process that is not managed via the init system.
    """
    # Monitoring state, no changes will be made so no test interface needed
    ret = {
        "name": name,
        "result": False,
        "comment": "",
        "changes": {},
        "data": {},
    }  # Data field for monitoring state

    data = __salt__["status.pid"](name)
    if not data:
        ret["result"] = False
        ret["comment"] += f'Process signature "{name}" not found '
        return ret
    ret["data"] = data
    ret["comment"] += f'Process signature "{name}" was found '
    ret["result"] = True
    return ret
