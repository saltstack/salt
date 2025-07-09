"""
Manage RabbitMQ Clusters
========================

Example:

.. code-block:: yaml

    rabbit@rabbit.example.com:
      rabbitmq_cluster.join:
        - user: rabbit
        - host: rabbit.example.com
"""

import logging

import salt.utils.functools
import salt.utils.path

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if RabbitMQ is installed.
    """
    if salt.utils.path.which("rabbitmqctl"):
        return True
    return (False, "Command not found: rabbitmqctl")


def joined(name, host, user="rabbit", ram_node=None, runas="root"):
    """
    Ensure the current node joined to a cluster with node user@host

    name
        Irrelevant, not used (recommended: user@host)
    user
        The user of node to join to (default: rabbit)
    host
        The host of node to join to
    ram_node
        Join node as a RAM node
    runas
        The user to run the rabbitmq command as
    """

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    status = __salt__["rabbitmq.cluster_status"]()
    if f"{user}@{host}" in status:
        ret["comment"] = "Already in cluster"
        return ret

    if not __opts__["test"]:
        result = __salt__["rabbitmq.join_cluster"](host, user, ram_node, runas=runas)
        if "Error" in result:
            ret["result"] = False
            ret["comment"] = result["Error"]
            return ret
        elif "Join" in result:
            ret["comment"] = result["Join"]

    # If we've reached this far before returning, we have changes.
    ret["changes"] = {"old": "", "new": f"{user}@{host}"}

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Node is set to join cluster {user}@{host}"

    return ret


# Alias join to preserve backward compat
join = salt.utils.functools.alias_function(joined, "join")
