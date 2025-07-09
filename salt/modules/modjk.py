"""
Control Modjk via the Apache Tomcat "Status" worker
(http://tomcat.apache.org/connectors-doc/reference/status.html)

Below is an example of the configuration needed for this module. This
configuration data can be placed either in :ref:`grains
<targeting-grains>` or :ref:`pillar <salt-pillars>`.

If using grains, this can be accomplished :ref:`statically
<static-custom-grains>` or via a :ref:`grain module <writing-grains>`.

If using pillar, the yaml configuration can be placed directly into a pillar
SLS file, making this both the easier and more dynamic method of configuring
this module.

.. code-block:: yaml

    modjk:
      default:
        url: http://localhost/jkstatus
        user: modjk
        pass: secret
        realm: authentication realm for digest passwords
        timeout: 5
      otherVhost:
        url: http://otherVhost/jkstatus
        user: modjk
        pass: secret2
        realm: authentication realm2 for digest passwords
        timeout: 600
"""

import urllib.parse
import urllib.request


def __virtual__():
    """
    Always load
    """
    return True


def _auth(url, user, passwd, realm):
    """
    returns a authentication handler.
    """

    basic = urllib.request.HTTPBasicAuthHandler()
    basic.add_password(realm=realm, uri=url, user=user, passwd=passwd)
    digest = urllib.request.HTTPDigestAuthHandler()
    digest.add_password(realm=realm, uri=url, user=user, passwd=passwd)
    return urllib.request.build_opener(basic, digest)


def _do_http(opts, profile="default"):
    """
    Make the http request and return the data
    """

    ret = {}

    url = __salt__["config.get"](f"modjk:{profile}:url", "")
    user = __salt__["config.get"](f"modjk:{profile}:user", "")
    passwd = __salt__["config.get"](f"modjk:{profile}:pass", "")
    realm = __salt__["config.get"](f"modjk:{profile}:realm", "")
    timeout = __salt__["config.get"](f"modjk:{profile}:timeout", "")

    if not url:
        raise Exception(f"missing url in profile {profile}")

    if user and passwd:
        auth = _auth(url=url, realm=realm, user=user, passwd=passwd)
        urllib.request.install_opener(auth)

    url += f"?{urllib.parse.urlencode(opts)}"

    for line in urllib.request.urlopen(url, timeout=timeout).read().splitlines():
        splt = line.split("=", 1)
        if splt[0] in ret:
            ret[splt[0]] += f",{splt[1]}"
        else:
            ret[splt[0]] = splt[1]

    return ret


def _worker_ctl(worker, lbn, vwa, profile="default"):
    """
    enable/disable/stop a worker
    """

    cmd = {
        "cmd": "update",
        "mime": "prop",
        "w": lbn,
        "sw": worker,
        "vwa": vwa,
    }
    return _do_http(cmd, profile)["worker.result.type"] == "OK"


def version(profile="default"):
    """
    Return the modjk version

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.version
        salt '*' modjk.version other-profile
    """

    cmd = {
        "cmd": "version",
        "mime": "prop",
    }
    return _do_http(cmd, profile)["worker.jk_version"].split("/")[-1]


def get_running(profile="default"):
    """
    Get the current running config (not from disk)

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.get_running
        salt '*' modjk.get_running other-profile
    """

    cmd = {
        "cmd": "list",
        "mime": "prop",
    }
    return _do_http(cmd, profile)


def dump_config(profile="default"):
    """
    Dump the original configuration that was loaded from disk

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.dump_config
        salt '*' modjk.dump_config other-profile
    """

    cmd = {
        "cmd": "dump",
        "mime": "prop",
    }
    return _do_http(cmd, profile)


def list_configured_members(lbn, profile="default"):
    """
    Return a list of member workers from the configuration files

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.list_configured_members loadbalancer1
        salt '*' modjk.list_configured_members loadbalancer1 other-profile
    """

    config = dump_config(profile)

    try:
        ret = config[f"worker.{lbn}.balance_workers"]
    except KeyError:
        return []

    return [_f for _f in ret.strip().split(",") if _f]


def workers(profile="default"):
    """
    Return a list of member workers and their status

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.workers
        salt '*' modjk.workers other-profile
    """

    config = get_running(profile)
    lbn = config["worker.list"].split(",")
    worker_list = []
    ret = {}

    for lb in lbn:
        try:
            worker_list.extend(config[f"worker.{lb}.balance_workers"].split(","))
        except KeyError:
            pass

    worker_list = list(set(worker_list))

    for worker in worker_list:
        ret[worker] = {
            "activation": config[f"worker.{worker}.activation"],
            "state": config[f"worker.{worker}.state"],
        }

    return ret


def recover_all(lbn, profile="default"):
    """
    Set the all the workers in lbn to recover and activate them if they are not

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.recover_all loadbalancer1
        salt '*' modjk.recover_all loadbalancer1 other-profile
    """

    ret = {}
    config = get_running(profile)
    try:
        workers_ = config[f"worker.{lbn}.balance_workers"].split(",")
    except KeyError:
        return ret

    for worker in workers_:
        curr_state = worker_status(worker, profile)
        if curr_state["activation"] != "ACT":
            worker_activate(worker, lbn, profile)
        if not curr_state["state"].startswith("OK"):
            worker_recover(worker, lbn, profile)
        ret[worker] = worker_status(worker, profile)

    return ret


def reset_stats(lbn, profile="default"):
    """
    Reset all runtime statistics for the load balancer

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.reset_stats loadbalancer1
        salt '*' modjk.reset_stats loadbalancer1 other-profile
    """

    cmd = {
        "cmd": "reset",
        "mime": "prop",
        "w": lbn,
    }
    return _do_http(cmd, profile)["worker.result.type"] == "OK"


def lb_edit(lbn, settings, profile="default"):
    """
    Edit the loadbalancer settings

    Note: http://tomcat.apache.org/connectors-doc/reference/status.html
    Data Parameters for the standard Update Action

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.lb_edit loadbalancer1 "{'vlr': 1, 'vlt': 60}"
        salt '*' modjk.lb_edit loadbalancer1 "{'vlr': 1, 'vlt': 60}" other-profile
    """

    settings["cmd"] = "update"
    settings["mime"] = "prop"
    settings["w"] = lbn

    return _do_http(settings, profile)["worker.result.type"] == "OK"


def bulk_stop(workers, lbn, profile="default"):
    """
    Stop all the given workers in the specific load balancer

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.bulk_stop node1,node2,node3 loadbalancer1
        salt '*' modjk.bulk_stop node1,node2,node3 loadbalancer1 other-profile

        salt '*' modjk.bulk_stop ["node1","node2","node3"] loadbalancer1
        salt '*' modjk.bulk_stop ["node1","node2","node3"] loadbalancer1 other-profile
    """

    ret = {}

    if isinstance(workers, str):
        workers = workers.split(",")

    for worker in workers:
        try:
            ret[worker] = worker_stop(worker, lbn, profile)
        except Exception:  # pylint: disable=broad-except
            ret[worker] = False

    return ret


def bulk_activate(workers, lbn, profile="default"):
    """
    Activate all the given workers in the specific load balancer

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.bulk_activate node1,node2,node3 loadbalancer1
        salt '*' modjk.bulk_activate node1,node2,node3 loadbalancer1 other-profile

        salt '*' modjk.bulk_activate ["node1","node2","node3"] loadbalancer1
        salt '*' modjk.bulk_activate ["node1","node2","node3"] loadbalancer1 other-profile
    """

    ret = {}

    if isinstance(workers, str):
        workers = workers.split(",")

    for worker in workers:
        try:
            ret[worker] = worker_activate(worker, lbn, profile)
        except Exception:  # pylint: disable=broad-except
            ret[worker] = False

    return ret


def bulk_disable(workers, lbn, profile="default"):
    """
    Disable all the given workers in the specific load balancer

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.bulk_disable node1,node2,node3 loadbalancer1
        salt '*' modjk.bulk_disable node1,node2,node3 loadbalancer1 other-profile

        salt '*' modjk.bulk_disable ["node1","node2","node3"] loadbalancer1
        salt '*' modjk.bulk_disable ["node1","node2","node3"] loadbalancer1 other-profile
    """

    ret = {}

    if isinstance(workers, str):
        workers = workers.split(",")

    for worker in workers:
        try:
            ret[worker] = worker_disable(worker, lbn, profile)
        except Exception:  # pylint: disable=broad-except
            ret[worker] = False

    return ret


def bulk_recover(workers, lbn, profile="default"):
    """
    Recover all the given workers in the specific load balancer

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.bulk_recover node1,node2,node3 loadbalancer1
        salt '*' modjk.bulk_recover node1,node2,node3 loadbalancer1 other-profile

        salt '*' modjk.bulk_recover ["node1","node2","node3"] loadbalancer1
        salt '*' modjk.bulk_recover ["node1","node2","node3"] loadbalancer1 other-profile
    """

    ret = {}

    if isinstance(workers, str):
        workers = workers.split(",")

    for worker in workers:
        try:
            ret[worker] = worker_recover(worker, lbn, profile)
        except Exception:  # pylint: disable=broad-except
            ret[worker] = False

    return ret


def worker_status(worker, profile="default"):
    """
    Return the state of the worker

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.worker_status node1
        salt '*' modjk.worker_status node1 other-profile
    """

    config = get_running(profile)
    try:
        return {
            "activation": config[f"worker.{worker}.activation"],
            "state": config[f"worker.{worker}.state"],
        }
    except KeyError:
        return False


def worker_recover(worker, lbn, profile="default"):
    """
    Set the worker to recover
    this module will fail if it is in OK state

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.worker_recover node1 loadbalancer1
        salt '*' modjk.worker_recover node1 loadbalancer1 other-profile
    """

    cmd = {
        "cmd": "recover",
        "mime": "prop",
        "w": lbn,
        "sw": worker,
    }
    return _do_http(cmd, profile)


def worker_disable(worker, lbn, profile="default"):
    """
    Set the worker to disable state in the lbn load balancer

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.worker_disable node1 loadbalancer1
        salt '*' modjk.worker_disable node1 loadbalancer1 other-profile
    """

    return _worker_ctl(worker, lbn, "d", profile)


def worker_activate(worker, lbn, profile="default"):
    """
    Set the worker to activate state in the lbn load balancer

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.worker_activate node1 loadbalancer1
        salt '*' modjk.worker_activate node1 loadbalancer1 other-profile
    """

    return _worker_ctl(worker, lbn, "a", profile)


def worker_stop(worker, lbn, profile="default"):
    """
    Set the worker to stopped state in the lbn load balancer

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.worker_activate node1 loadbalancer1
        salt '*' modjk.worker_activate node1 loadbalancer1 other-profile
    """

    return _worker_ctl(worker, lbn, "s", profile)


def worker_edit(worker, lbn, settings, profile="default"):
    """
    Edit the worker settings

    Note: http://tomcat.apache.org/connectors-doc/reference/status.html
    Data Parameters for the standard Update Action

    CLI Examples:

    .. code-block:: bash

        salt '*' modjk.worker_edit node1 loadbalancer1 "{'vwf': 500, 'vwd': 60}"
        salt '*' modjk.worker_edit node1 loadbalancer1 "{'vwf': 500, 'vwd': 60}" other-profile
    """

    settings["cmd"] = "update"
    settings["mime"] = "prop"
    settings["w"] = lbn
    settings["sw"] = worker

    return _do_http(settings, profile)["worker.result.type"] == "OK"
