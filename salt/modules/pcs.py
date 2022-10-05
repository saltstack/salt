"""
Configure a Pacemaker/Corosync cluster with PCS
===============================================

Configure Pacemaker/Cororsync clusters with the
Pacemaker/Cororsync conifguration system (PCS)

:depends: pcs

.. versionadded:: 2016.3.0
"""


import logging

import salt.utils.path

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if pcs package is installed
    """
    if salt.utils.path.which("pcs"):
        return "pcs"
    return (False, "Missing dependency: pcs")


def __use_new_commands():
    """
    The command line arguments of pcs changed after version 0.10
    This will return True if the new arguments are needed and
    false if the old ones are needed
    """
    pcs_version = __salt__["pkg.version"]("pcs")
    log.debug("PCS package version %s", pcs_version)

    if __salt__["pkg.version_cmp"](pcs_version, "0.10") == 1:
        log.debug("New version, new command")
        return True
    else:
        log.debug("Old Version")
        return False


def item_show(
    item, item_id=None, item_type=None, show="show", extra_args=None, cibfile=None
):
    """
    Show an item via pcs command
    (mainly for use with the pcs state module)

    item
        config, property, resource, constraint etc.
    item_id
        id of the item
    item_type
        item type
    show
        show command (probably None, default: show or status for newer implementation)
    extra_args
        additional options for the pcs command
    cibfile
        use cibfile instead of the live CIB
    """

    new_commands = __use_new_commands()

    cmd = ["pcs"]

    if isinstance(cibfile, str):
        cmd += ["-f", cibfile]

    if isinstance(item, str):
        cmd += [item]
    elif isinstance(item, (list, tuple)):
        cmd += item

    # constraint command follows a different order
    if item in ["constraint"]:
        cmd += [item_type]

    # New implementions use config instead of show. This resolves that issue.
    if new_commands and (
        item != "config" and item != "constraint" and item != "property"
    ):
        if show == "show":
            show = "config"
        elif isinstance(show, (list, tuple)):
            for index, value in enumerate(show):
                if show[index] == "show":
                    show[index] = "config"

    if isinstance(show, str):
        cmd += [show]
    elif isinstance(show, (list, tuple)):
        cmd += show

    if isinstance(item_id, str):
        cmd += [item_id]

    if isinstance(extra_args, (list, tuple)):
        cmd += extra_args

    # constraint command only shows id, when using '--full'-parameter
    if item in ["constraint"]:
        if not isinstance(extra_args, (list, tuple)) or "--full" not in extra_args:
            cmd += ["--full"]
    log.debug("Running item show %s", cmd)
    return __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)


def item_create(
    item, item_id, item_type, create="create", extra_args=None, cibfile=None
):
    """
    Create an item via pcs command
    (mainly for use with the pcs state module)

    item
        config, property, resource, constraint etc.
    item_id
        id of the item
    item_type
        item type
    create
        create command (create or set f.e., default: create)
    extra_args
        additional options for the pcs command
    cibfile
        use cibfile instead of the live CIB
    """
    cmd = ["pcs"]
    if isinstance(cibfile, str):
        cmd += ["-f", cibfile]

    if isinstance(item, str):
        cmd += [item]
    elif isinstance(item, (list, tuple)):
        cmd += item

    # constraint command follows a different order
    if item in ["constraint"]:
        if isinstance(item_type, str):
            cmd += [item_type]

    if isinstance(create, str):
        cmd += [create]
    elif isinstance(create, (list, tuple)):
        cmd += create

    # constraint command needs item_id in format 'id=<id' after all params
    # constraint command follows a different order
    if item not in ["constraint"]:
        cmd += [item_id]
        if isinstance(item_type, str):
            cmd += [item_type]

    if isinstance(extra_args, (list, tuple)):
        # constraint command needs item_id in format 'id=<id' after all params
        if item in ["constraint"]:
            extra_args = extra_args + ["id={}".format(item_id)]
        cmd += extra_args

    return __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)


def auth(nodes, pcsuser="hacluster", pcspasswd="hacluster", extra_args=None):
    """
    Authorize nodes to the cluster

    nodes
        a list of nodes which should be authorized to the cluster
    pcsuser
        user for communitcation with PCS (default: hacluster)
    pcspasswd
        password for pcsuser (default: hacluster)
    extra_args
        list of extra option for the \'pcs cluster auth\' command. The newer cluster host command has no extra args and so will ignore it.

    CLI Example:

    .. code-block:: bash

        salt '*' pcs.auth nodes='[ node1.example.org, node2.example.org ]' pcsuser=hacluster pcspasswd=hoonetorg extra_args=[ '--force' ]
    """
    if __use_new_commands():
        cmd = ["pcs", "host", "auth"]
    else:
        cmd = ["pcs", "cluster", "auth"]

    cmd.extend(["-u", pcsuser, "-p", pcspasswd])

    if not __use_new_commands() and isinstance(extra_args, (list, tuple)):
        cmd += extra_args

    cmd += nodes

    return __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)


def is_auth(nodes, pcsuser="hacluster", pcspasswd="hacluster"):
    """
    Check if nodes are already authorized

    nodes
        a list of nodes to be checked for authorization to the cluster
    pcsuser
        user for communitcation with PCS (default: hacluster)
    pcspasswd
        password for pcsuser (default: hacluster)

    CLI Example:

    .. code-block:: bash

        salt '*' pcs.is_auth nodes='[node1.example.org, node2.example.org]' pcsuser=hacluster pcspasswd=hoonetorg
    """
    if __use_new_commands():
        cmd = ["pcs", "host", "auth", "-u", pcsuser, "-p", pcspasswd]
    else:
        cmd = ["pcs", "cluster", "auth"]

    cmd += nodes

    return __salt__["cmd.run_all"](
        cmd, stdin="\n\n", output_loglevel="trace", python_shell=False
    )


def cluster_setup(nodes, pcsclustername="pcscluster", extra_args=None):
    """
    Setup pacemaker cluster via pcs command

    nodes
        a list of nodes which should be set up
    pcsclustername
        Name of the Pacemaker cluster (default: pcscluster)
    extra_args
        list of extra option for the \'pcs cluster setup\' command

    CLI Example:

    .. code-block:: bash

        salt '*' pcs.cluster_setup nodes='[ node1.example.org, node2.example.org ]' pcsclustername=pcscluster
    """
    cmd = ["pcs", "cluster", "setup"]

    if __use_new_commands():
        cmd += [pcsclustername]
    else:
        cmd += ["--name", pcsclustername]

    cmd += nodes
    if isinstance(extra_args, (list, tuple)):
        cmd += extra_args

    log.debug("Running cluster setup: %s", cmd)

    return __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)


def cluster_destroy(extra_args=None):
    """
    Destroy corosync cluster using the pcs command

    extra_args
        list of extra option for the \'pcs cluster destroy\' command (only really --all)

    CLI Example:

    .. code-block:: bash

        salt '*' pcs.cluster_destroy extra_args=--all
    """
    cmd = ["pcs", "cluster", "destroy"]

    if isinstance(extra_args, (list, tuple)):
        cmd += extra_args

    log.debug("Running cluster destroy: %s", cmd)

    return __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)


def cluster_node_add(node, extra_args=None):
    """
    Add a node to the pacemaker cluster via pcs command

    node
        node that should be added
    extra_args
        list of extra option for the \'pcs cluster node add\' command

    CLI Example:

    .. code-block:: bash

        salt '*' pcs.cluster_node_add node=node2.example.org
    """
    cmd = ["pcs", "cluster", "node", "add"]

    cmd += [node]
    if isinstance(extra_args, (list, tuple)):
        cmd += extra_args

    return __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)


def cib_create(cibfile, scope="configuration", extra_args=None):
    """
    Create a CIB-file from the current CIB of the cluster

    cibfile
        name/path of the file containing the CIB
    scope
        specific section of the CIB (default: configuration)
    extra_args
        additional options for creating the CIB-file

    CLI Example:

    .. code-block:: bash

        salt '*' pcs.cib_create cibfile='/tmp/VIP_apache_1.cib' scope=False
    """
    cmd = ["pcs", "cluster", "cib", cibfile]
    if isinstance(scope, str):
        cmd += ["scope={}".format(scope)]
    if isinstance(extra_args, (list, tuple)):
        cmd += extra_args

    return __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)


def cib_push(cibfile, scope="configuration", extra_args=None):
    """
    Push a CIB-file as the new CIB to the cluster

    cibfile
        name/path of the file containing the CIB
    scope
        specific section of the CIB (default: configuration)
    extra_args
        additional options for creating the CIB-file

    CLI Example:

    .. code-block:: bash

        salt '*' pcs.cib_push cibfile='/tmp/VIP_apache_1.cib' scope=False
    """
    cmd = ["pcs", "cluster", "cib-push", cibfile]
    if isinstance(scope, str):
        cmd += ["scope={}".format(scope)]
    if isinstance(extra_args, (list, tuple)):
        cmd += extra_args

    return __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)


def config_show(cibfile=None):
    """
    Show config of cluster

    cibfile
        name/path of the file containing the CIB

    CLI Example:

    .. code-block:: bash

        salt '*' pcs.config_show cibfile='/tmp/cib_for_galera'
    """
    return item_show(item="config", item_id=None, extra_args=None, cibfile=cibfile)


def prop_show(prop, extra_args=None, cibfile=None):
    """
    Show the value of a cluster property

    prop
        name of the property
    extra_args
        additional options for the pcs property command
    cibfile
        use cibfile instead of the live CIB

    CLI Example:

    .. code-block:: bash

        salt '*' pcs.prop_show cibfile='/tmp/2_node_cluster.cib' prop='no-quorum-policy' cibfile='/tmp/2_node_cluster.cib'
    """
    return item_show(
        item="property", item_id=prop, extra_args=extra_args, cibfile=cibfile
    )


def prop_set(prop, value, extra_args=None, cibfile=None):
    """
    Set the value of a cluster property

    prop
        name of the property
    value
        value of the property prop
    extra_args
        additional options for the pcs property command
    cibfile
        use cibfile instead of the live CIB

    CLI Example:

    .. code-block:: bash

        salt '*' pcs.prop_set prop='no-quorum-policy' value='ignore' cibfile='/tmp/2_node_cluster.cib'
    """
    return item_create(
        item="property",
        item_id="{}={}".format(prop, value),
        item_type=None,
        create="set",
        extra_args=extra_args,
        cibfile=cibfile,
    )


def stonith_show(stonith_id, extra_args=None, cibfile=None):
    """
    Show the value of a cluster stonith

    stonith_id
        name for the stonith resource
    extra_args
        additional options for the pcs stonith command
    cibfile
        use cibfile instead of the live CIB

    CLI Example:

    .. code-block:: bash

        salt '*' pcs.stonith_show stonith_id='eps_fence' cibfile='/tmp/2_node_cluster.cib'
    """
    return item_show(
        item="stonith", item_id=stonith_id, extra_args=extra_args, cibfile=cibfile
    )


def stonith_create(
    stonith_id, stonith_device_type, stonith_device_options=None, cibfile=None
):
    """
    Create a stonith resource via pcs command

    stonith_id
        name for the stonith resource
    stonith_device_type
        name of the stonith agent fence_eps, fence_xvm f.e.
    stonith_device_options
        additional options for creating the stonith resource
    cibfile
        use cibfile instead of the live CIB for manipulation

    CLI Example:

    .. code-block:: bash

        salt '*' pcs.stonith_create stonith_id='eps_fence' stonith_device_type='fence_eps'
                                    stonith_device_options="['pcmk_host_map=node1.example.org:01;node2.example.org:02', 'ipaddr=myepsdevice.example.org', 'action=reboot', 'power_wait=5', 'verbose=1', 'debug=/var/log/pcsd/eps_fence.log', 'login=hidden', 'passwd=hoonetorg']" cibfile='/tmp/cib_for_stonith.cib'
    """
    return item_create(
        item="stonith",
        item_id=stonith_id,
        item_type=stonith_device_type,
        extra_args=stonith_device_options,
        cibfile=cibfile,
    )


def resource_show(resource_id, extra_args=None, cibfile=None):
    """
    Show a resource via pcs command

    resource_id
        name of the resource
    extra_args
        additional options for the pcs command
    cibfile
        use cibfile instead of the live CIB

    CLI Example:

    .. code-block:: bash

        salt '*' pcs.resource_show resource_id='galera' cibfile='/tmp/cib_for_galera.cib'
    """
    return item_show(
        item="resource", item_id=resource_id, extra_args=extra_args, cibfile=cibfile
    )


def resource_create(resource_id, resource_type, resource_options=None, cibfile=None):
    """
    Create a resource via pcs command

    resource_id
        name for the resource
    resource_type
        resource type (f.e. ocf:heartbeat:IPaddr2 or VirtualIP)
    resource_options
        additional options for creating the resource
    cibfile
        use cibfile instead of the live CIB for manipulation

    CLI Example:

    .. code-block:: bash

        salt '*' pcs.resource_create resource_id='galera' resource_type='ocf:heartbeat:galera' resource_options="['wsrep_cluster_address=gcomm://node1.example.org,node2.example.org,node3.example.org', '--master']" cibfile='/tmp/cib_for_galera.cib'
    """
    return item_create(
        item="resource",
        item_id=resource_id,
        item_type=resource_type,
        extra_args=resource_options,
        cibfile=cibfile,
    )
