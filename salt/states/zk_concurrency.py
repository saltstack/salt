"""
Control concurrency of steps within state execution using zookeeper
===================================================================

:depends: kazoo
:configuration: See :py:mod:`salt.modules.zookeeper` for setup instructions.


This module allows you to "wrap" a state's execution with concurrency control.
This is useful to protect against all hosts executing highstate simultaneously
if your services don't all HUP restart. The common way of protecting against this
is to run in batch mode, but that doesn't protect from another person running
the same batch command (and thereby having 2x the number of nodes deploying at once).

This module will bock while acquiring a slot, meaning that however the command gets
called it will coordinate with zookeeper to ensure that no more than max_concurrency
steps are executing with a single path.

.. code-block:: yaml

    acquire_lock:
      zk_concurrency.lock:
        - name: /trafficeserver
        - zk_hosts: 'zookeeper:2181'
        - max_concurrency: 4
        - prereq:
            - service: trafficserver

    trafficserver:
      service.running:
        - watch:
          - file: /etc/trafficserver/records.config

    /etc/trafficserver/records.config:
      file.managed:
        - source: salt://records.config

    release_lock:
      zk_concurrency.unlock:
        - name: /trafficserver
        - require:
            - service: trafficserver

This example would allow the file state to change, but would limit the
concurrency of the trafficserver service restart to 4.
"""


# TODO: use depends decorator to make these per function deps, instead of all or nothing
REQUIRED_FUNCS = (
    "zk_concurrency.lock",
    "zk_concurrency.unlock",
    "zk_concurrency.party_members",
)

__virtualname__ = "zk_concurrency"


def __virtual__():
    if not all(func in __salt__ for func in REQUIRED_FUNCS):
        return (False, "zk_concurrency module could not be loaded")
    return __virtualname__


def lock(
    name,
    zk_hosts=None,
    identifier=None,
    max_concurrency=1,
    timeout=None,
    ephemeral_lease=False,
    profile=None,
    scheme=None,
    username=None,
    password=None,
    default_acl=None,
):
    """
    Block state execution until you are able to get the lock (or hit the timeout)

    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    conn_kwargs = {
        "profile": profile,
        "scheme": scheme,
        "username": username,
        "password": password,
        "default_acl": default_acl,
    }

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Attempt to acquire lock"
        return ret

    if identifier is None:
        identifier = __grains__["id"]

    locked = __salt__["zk_concurrency.lock"](
        name,
        zk_hosts,
        identifier=identifier,
        max_concurrency=max_concurrency,
        timeout=timeout,
        ephemeral_lease=ephemeral_lease,
        **conn_kwargs
    )
    if locked:
        ret["result"] = True
        ret["comment"] = "lock acquired"
    else:
        ret["comment"] = "Unable to acquire lock"

    return ret


def unlock(
    name,
    zk_hosts=None,  # in case you need to unlock without having run lock (failed execution for example)
    identifier=None,
    max_concurrency=1,
    ephemeral_lease=False,
    profile=None,
    scheme=None,
    username=None,
    password=None,
    default_acl=None,
):
    """
    Remove lease from semaphore.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    conn_kwargs = {
        "profile": profile,
        "scheme": scheme,
        "username": username,
        "password": password,
        "default_acl": default_acl,
    }

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Released lock if it is here"
        return ret

    if identifier is None:
        identifier = __grains__["id"]

    unlocked = __salt__["zk_concurrency.unlock"](
        name,
        zk_hosts=zk_hosts,
        identifier=identifier,
        max_concurrency=max_concurrency,
        ephemeral_lease=ephemeral_lease,
        **conn_kwargs
    )

    if unlocked:
        ret["result"] = True
    else:
        ret["comment"] = "Unable to find lease for path {}".format(name)

    return ret


def min_party(
    name,
    zk_hosts,
    min_nodes,
    blocking=False,
    profile=None,
    scheme=None,
    username=None,
    password=None,
    default_acl=None,
):
    """
    Ensure that there are `min_nodes` in the party at `name`, optionally blocking if not available.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    conn_kwargs = {
        "profile": profile,
        "scheme": scheme,
        "username": username,
        "password": password,
        "default_acl": default_acl,
    }

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Attempt to ensure min_party"
        return ret

    nodes = __salt__["zk_concurrency.party_members"](
        name, zk_hosts, min_nodes, blocking=blocking, **conn_kwargs
    )
    if not isinstance(nodes, list):
        raise Exception(
            "Error from zk_concurrency.party_members, return was not a list: {}".format(
                nodes
            )
        )

    num_nodes = len(nodes)

    if num_nodes >= min_nodes or blocking:
        ret["result"] = None if __opts__["test"] else True
        if not blocking:
            ret["comment"] = "Currently {} nodes, which is >= {}".format(
                num_nodes, min_nodes
            )
        else:
            ret["comment"] = (
                "Blocked until {} nodes were available. Unblocked after {} nodes became"
                " available".format(min_nodes, num_nodes)
            )
    else:
        ret["result"] = False
        ret["comment"] = "Currently {} nodes, which is < {}".format(
            num_nodes, min_nodes
        )

    return ret
