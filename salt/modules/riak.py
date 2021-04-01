"""
Riak Salt Module
"""

import salt.utils.path


def __virtual__():
    """
    Only available on systems with Riak installed.
    """
    if salt.utils.path.which("riak"):
        return True
    return (
        False,
        "The riak execution module failed to load: the riak binary is not in the path.",
    )


def __execute_cmd(name, cmd):
    """
    Execute Riak commands
    """
    return __salt__["cmd.run_all"]("{} {}".format(salt.utils.path.which(name), cmd))


def start():
    """
    Start Riak

    CLI Example:

    .. code-block:: bash

        salt '*' riak.start
    """
    ret = {"comment": "", "success": False}

    cmd = __execute_cmd("riak", "start")

    if cmd["retcode"] != 0:
        ret["comment"] = cmd["stderr"]
    else:
        ret["comment"] = cmd["stdout"]
        ret["success"] = True

    return ret


def stop():
    """
    Stop Riak

    .. versionchanged:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' riak.stop
    """
    ret = {"comment": "", "success": False}

    cmd = __execute_cmd("riak", "stop")

    if cmd["retcode"] != 0:
        ret["comment"] = cmd["stderr"]
    else:
        ret["comment"] = cmd["stdout"]
        ret["success"] = True

    return ret


def cluster_join(username, hostname):
    """
    Join a Riak cluster

    .. versionchanged:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' riak.cluster_join <user> <host>

    username - The riak username to join the cluster
    hostname - The riak hostname you are connecting to
    """
    ret = {"comment": "", "success": False}

    cmd = __execute_cmd("riak-admin", "cluster join {}@{}".format(username, hostname))

    if cmd["retcode"] != 0:
        ret["comment"] = cmd["stdout"]
    else:
        ret["comment"] = cmd["stdout"]
        ret["success"] = True

    return ret


def cluster_leave(username, hostname):
    """
    Leave a Riak cluster

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' riak.cluster_leave <username> <host>

    username - The riak username to join the cluster
    hostname - The riak hostname you are connecting to
    """
    ret = {"comment": "", "success": False}

    cmd = __execute_cmd("riak-admin", "cluster leave {}@{}".format(username, hostname))

    if cmd["retcode"] != 0:
        ret["comment"] = cmd["stdout"]
    else:
        ret["comment"] = cmd["stdout"]
        ret["success"] = True

    return ret


def cluster_plan():
    """
    Review Cluster Plan

    .. versionchanged:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' riak.cluster_plan
    """
    cmd = __execute_cmd("riak-admin", "cluster plan")

    if cmd["retcode"] != 0:
        return False

    return True


def cluster_commit():
    """
    Commit Cluster Changes

    .. versionchanged:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' riak.cluster_commit
    """
    ret = {"comment": "", "success": False}

    cmd = __execute_cmd("riak-admin", "cluster commit")

    if cmd["retcode"] != 0:
        ret["comment"] = cmd["stdout"]
    else:
        ret["comment"] = cmd["stdout"]
        ret["success"] = True

    return ret


def member_status():
    """
    Get cluster member status

    .. versionchanged:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' riak.member_status
    """
    ret = {
        "membership": {},
        "summary": {"Valid": 0, "Leaving": 0, "Exiting": 0, "Joining": 0, "Down": 0},
    }

    out = __execute_cmd("riak-admin", "member-status")["stdout"].splitlines()

    for line in out:
        if line.startswith(("=", "-", "Status")):
            continue
        if "/" in line:
            # We're in the summary line
            for item in line.split("/"):
                key, val = item.split(":")
                ret["summary"][key.strip()] = val.strip()

        if len(line.split()) == 4:
            # We're on a node status line
            (status, ring, pending, node) = line.split()

            ret["membership"][node] = {
                "Status": status,
                "Ring": ring,
                "Pending": pending,
            }

    return ret


def status():
    """
    Current node status

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' riak.status
    """
    ret = {}

    cmd = __execute_cmd("riak-admin", "status")

    for i in cmd["stdout"].splitlines():
        if ":" in i:
            (name, val) = i.split(":", 1)
            ret[name.strip()] = val.strip()

    return ret


def test():
    """
    Runs a test of a few standard Riak operations

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' riak.test
    """
    ret = {"comment": "", "success": False}

    cmd = __execute_cmd("riak-admin", "test")

    if cmd["retcode"] != 0:
        ret["comment"] = cmd["stdout"]
    else:
        ret["comment"] = cmd["stdout"]
        ret["success"] = True

    return ret


def services():
    """
    List available services on a node

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' riak.services
    """
    cmd = __execute_cmd("riak-admin", "services")

    return cmd["stdout"][1:-1].split(",")
