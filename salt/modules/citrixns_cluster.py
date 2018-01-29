# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the cluster key.

:codeauthor: :email:`Spencer Ervin <spencer_ervin@hotmail.com>`
:maturity:   new
:depends:    none
:platform:   unix


Configuration
=============
This module accepts connection configuration details either as
parameters, or as configuration settings in pillar as a Salt proxy.
Options passed into opts will be ignored if options are passed into pillar.

.. seealso::
    :prox:`Citrix Netscaler Proxy Module <salt.proxy.citrixns>`

About
=====
This execution module was designed to handle connections to a Citrix Netscaler. This module adds support to send
connections directly to the device through the rest API.

'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
import salt.utils.platform
import salt.proxy.citrixns

log = logging.getLogger(__name__)

__virtualname__ = 'cluster'


def __virtual__():
    '''
    Will load for the citrixns proxy minions.
    '''
    try:
        if salt.utils.platform.is_proxy() and \
           __opts__['proxy']['proxytype'] == 'citrixns':
            return __virtualname__
    except KeyError:
        pass

    return False, 'The cluster execution module can only be loaded for citrixns proxy minions.'


def add_clusterinstance(clid=None, deadinterval=None, hellointerval=None, preemption=None, quorumtype=None, inc=None,
                        processlocal=None, retainconnectionsoncluster=None, nodegroup=None, save=False):
    '''
    Add a new clusterinstance to the running configuration.

    clid(int): Unique number that identifies the cluster. Minimum value = 1 Maximum value = 16

    deadinterval(int): Amount of time, in seconds, after which nodes that do not respond to the heartbeats are assumed to be
        down.If the value is less than 3 sec, set the helloInterval parameter to 200 msec. Default value: 3 Minimum value
        = 1 Maximum value = 60

    hellointerval(int): Interval, in milliseconds, at which heartbeats are sent to each cluster node to check the health
        status.Set the value to 200 msec, if the deadInterval parameter is less than 3 sec. Default value: 200 Minimum
        value = 200 Maximum value = 1000

    preemption(str): Preempt a cluster node that is configured as a SPARE if an ACTIVE node becomes available. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    quorumtype(str): Quorum Configuration Choices - "Majority" (recommended) requires majority of nodes to be online for the
        cluster to be UP. "None" relaxes this requirement. Default value: MAJORITY Possible values = MAJORITY, NONE

    inc(str): This option is required if the cluster nodes reside on different networks. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    processlocal(str): By turning on this option packets destined to a service in a cluster will not under go any steering.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    retainconnectionsoncluster(str): This option enables you to retain existing connections on a node joining a Cluster
        system or when a node is being configured for passive timeout. By default, this option is disabled. Default
        value: NO Possible values = YES, NO

    nodegroup(str): The node group in a Cluster system used for transition from L2 to L3.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.add_clusterinstance <args>

    '''

    result = {}

    payload = {'clusterinstance': {}}

    if clid:
        payload['clusterinstance']['clid'] = clid

    if deadinterval:
        payload['clusterinstance']['deadinterval'] = deadinterval

    if hellointerval:
        payload['clusterinstance']['hellointerval'] = hellointerval

    if preemption:
        payload['clusterinstance']['preemption'] = preemption

    if quorumtype:
        payload['clusterinstance']['quorumtype'] = quorumtype

    if inc:
        payload['clusterinstance']['inc'] = inc

    if processlocal:
        payload['clusterinstance']['processlocal'] = processlocal

    if retainconnectionsoncluster:
        payload['clusterinstance']['retainconnectionsoncluster'] = retainconnectionsoncluster

    if nodegroup:
        payload['clusterinstance']['nodegroup'] = nodegroup

    execution = __proxy__['citrixns.post']('config/clusterinstance', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_clusternode(nodeid=None, ipaddress=None, state=None, backplane=None, priority=None, nodegroup=None, delay=None,
                    clearnodegroupconfig=None, save=False):
    '''
    Add a new clusternode to the running configuration.

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    ipaddress(str): NetScaler IP (NSIP) address of the appliance to add to the cluster. Must be an IPv4 address. Minimum
        length = 1

    state(str): Admin state of the cluster node. The available settings function as follows: ACTIVE - The node serves
        traffic. SPARE - The node does not serve traffic unless an ACTIVE node goes down. PASSIVE - The node does not
        serve traffic, unless you change its state. PASSIVE state is useful during temporary maintenance activities in
        which you want the node to take part in the consensus protocol but not to serve traffic. Default value: PASSIVE
        Possible values = ACTIVE, SPARE, PASSIVE

    backplane(str): Interface through which the node communicates with the other nodes in the cluster. Must be specified in
        the three-tuple form n/c/u, where n represents the node ID and c/u refers to the interface on the appliance.
        Minimum length = 1

    priority(int): Preference for selecting a node as the configuration coordinator. The node with the lowest priority value
        is selected as the configuration coordinator. When the current configuration coordinator goes down, the node with
        the next lowest priority is made the new configuration coordinator. When the original node comes back up, it will
        preempt the new configuration coordinator and take over as the configuration coordinator. Note: When priority is
        not configured for any of the nodes or if multiple nodes have the same priority, the cluster elects one of the
        nodes as the configuration coordinator. Default value: 31 Minimum value = 0 Maximum value = 31

    nodegroup(str): The default node group in a Cluster system. Default value: DEFAULT_NG Minimum length = 1

    delay(int): Applicable for Passive node and node becomes passive after this timeout. Default value: 0 Minimum value = 0
        Maximum value = 1440

    clearnodegroupconfig(str): Option to remove nodegroup config. Default value: YES Possible values = YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.add_clusternode <args>

    '''

    result = {}

    payload = {'clusternode': {}}

    if nodeid:
        payload['clusternode']['nodeid'] = nodeid

    if ipaddress:
        payload['clusternode']['ipaddress'] = ipaddress

    if state:
        payload['clusternode']['state'] = state

    if backplane:
        payload['clusternode']['backplane'] = backplane

    if priority:
        payload['clusternode']['priority'] = priority

    if nodegroup:
        payload['clusternode']['nodegroup'] = nodegroup

    if delay:
        payload['clusternode']['delay'] = delay

    if clearnodegroupconfig:
        payload['clusternode']['clearnodegroupconfig'] = clearnodegroupconfig

    execution = __proxy__['citrixns.post']('config/clusternode', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_clusternode_routemonitor_binding(nodeid=None, routemonitor=None, netmask=None, save=False):
    '''
    Add a new clusternode_routemonitor_binding to the running configuration.

    nodeid(int): A number that uniquely identifies the cluster node. . Minimum value = 0 Maximum value = 31

    routemonitor(str): The IP address (IPv4 or IPv6).

    netmask(str): The netmask.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.add_clusternode_routemonitor_binding <args>

    '''

    result = {}

    payload = {'clusternode_routemonitor_binding': {}}

    if nodeid:
        payload['clusternode_routemonitor_binding']['nodeid'] = nodeid

    if routemonitor:
        payload['clusternode_routemonitor_binding']['routemonitor'] = routemonitor

    if netmask:
        payload['clusternode_routemonitor_binding']['netmask'] = netmask

    execution = __proxy__['citrixns.post']('config/clusternode_routemonitor_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_clusternodegroup(name=None, strict=None, sticky=None, state=None, priority=None, save=False):
    '''
    Add a new clusternodegroup to the running configuration.

    name(str): Name of the nodegroup. The name uniquely identifies the nodegroup on the cluster. Minimum length = 1

    strict(str): Specifies whether cluster nodes, that are not part of the nodegroup, will be used as backup for the
        nodegroup.  * Enabled - When one of the nodes goes down, no other cluster node is picked up to replace it. When
        the node comes up, it will continue being part of the nodegroup.  * Disabled - When one of the nodes goes down, a
        non-nodegroup cluster node is picked up and acts as part of the nodegroup. When the original node of the
        nodegroup comes up, the backup node will be replaced. Default value: NO Possible values = YES, NO

    sticky(str): Only one node can be bound to nodegroup with this option enabled. It specifies whether to prempt the traffic
        for the entities bound to nodegroup when owner node goes down and rejoins the cluster.  * Enabled - When owner
        node goes down, backup node will become the owner node and takes the traffic for the entities bound to the
        nodegroup. When bound node rejoins the cluster, traffic for the entities bound to nodegroup will not be steered
        back to this bound node. Current owner will have the ownership till it goes down.  * Disabled - When one of the
        nodes goes down, a non-nodegroup cluster node is picked up and acts as part of the nodegroup. When the original
        node of the nodegroup comes up, the backup node will be replaced. Default value: NO Possible values = YES, NO

    state(str): State of the nodegroup. All the nodes binding to this nodegroup must have the same state.
        ACTIVE/SPARE/PASSIVE. Possible values = ACTIVE, SPARE, PASSIVE

    priority(int): Priority of Nodegroup. This priority is used for all the nodes bound to the nodegroup for Nodegroup
        selection. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.add_clusternodegroup <args>

    '''

    result = {}

    payload = {'clusternodegroup': {}}

    if name:
        payload['clusternodegroup']['name'] = name

    if strict:
        payload['clusternodegroup']['strict'] = strict

    if sticky:
        payload['clusternodegroup']['sticky'] = sticky

    if state:
        payload['clusternodegroup']['state'] = state

    if priority:
        payload['clusternodegroup']['priority'] = priority

    execution = __proxy__['citrixns.post']('config/clusternodegroup', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_clusternodegroup_authenticationvserver_binding(vserver=None, name=None, save=False):
    '''
    Add a new clusternodegroup_authenticationvserver_binding to the running configuration.

    vserver(str): vserver that need to be bound to this nodegroup.

    name(str): Name of the nodegroup. The name uniquely identifies the nodegroup on the cluster. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.add_clusternodegroup_authenticationvserver_binding <args>

    '''

    result = {}

    payload = {'clusternodegroup_authenticationvserver_binding': {}}

    if vserver:
        payload['clusternodegroup_authenticationvserver_binding']['vserver'] = vserver

    if name:
        payload['clusternodegroup_authenticationvserver_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/clusternodegroup_authenticationvserver_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_clusternodegroup_clusternode_binding(name=None, node=None, save=False):
    '''
    Add a new clusternodegroup_clusternode_binding to the running configuration.

    name(str): Name of the nodegroup. The name uniquely identifies the nodegroup on the cluster. Minimum length = 1

    node(int): Nodes in the nodegroup. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.add_clusternodegroup_clusternode_binding <args>

    '''

    result = {}

    payload = {'clusternodegroup_clusternode_binding': {}}

    if name:
        payload['clusternodegroup_clusternode_binding']['name'] = name

    if node:
        payload['clusternodegroup_clusternode_binding']['node'] = node

    execution = __proxy__['citrixns.post']('config/clusternodegroup_clusternode_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_clusternodegroup_crvserver_binding(vserver=None, name=None, save=False):
    '''
    Add a new clusternodegroup_crvserver_binding to the running configuration.

    vserver(str): vserver that need to be bound to this nodegroup.

    name(str): Name of the nodegroup. The name uniquely identifies the nodegroup on the cluster. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.add_clusternodegroup_crvserver_binding <args>

    '''

    result = {}

    payload = {'clusternodegroup_crvserver_binding': {}}

    if vserver:
        payload['clusternodegroup_crvserver_binding']['vserver'] = vserver

    if name:
        payload['clusternodegroup_crvserver_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/clusternodegroup_crvserver_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_clusternodegroup_csvserver_binding(vserver=None, name=None, save=False):
    '''
    Add a new clusternodegroup_csvserver_binding to the running configuration.

    vserver(str): vserver that need to be bound to this nodegroup.

    name(str): Name of the nodegroup. The name uniquely identifies the nodegroup on the cluster. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.add_clusternodegroup_csvserver_binding <args>

    '''

    result = {}

    payload = {'clusternodegroup_csvserver_binding': {}}

    if vserver:
        payload['clusternodegroup_csvserver_binding']['vserver'] = vserver

    if name:
        payload['clusternodegroup_csvserver_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/clusternodegroup_csvserver_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_clusternodegroup_gslbsite_binding(gslbsite=None, name=None, save=False):
    '''
    Add a new clusternodegroup_gslbsite_binding to the running configuration.

    gslbsite(str): vserver that need to be bound to this nodegroup.

    name(str): Name of the nodegroup. The name uniquely identifies the nodegroup on the cluster. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.add_clusternodegroup_gslbsite_binding <args>

    '''

    result = {}

    payload = {'clusternodegroup_gslbsite_binding': {}}

    if gslbsite:
        payload['clusternodegroup_gslbsite_binding']['gslbsite'] = gslbsite

    if name:
        payload['clusternodegroup_gslbsite_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/clusternodegroup_gslbsite_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_clusternodegroup_gslbvserver_binding(vserver=None, name=None, save=False):
    '''
    Add a new clusternodegroup_gslbvserver_binding to the running configuration.

    vserver(str): vserver that need to be bound to this nodegroup.

    name(str): Name of the nodegroup. The name uniquely identifies the nodegroup on the cluster. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.add_clusternodegroup_gslbvserver_binding <args>

    '''

    result = {}

    payload = {'clusternodegroup_gslbvserver_binding': {}}

    if vserver:
        payload['clusternodegroup_gslbvserver_binding']['vserver'] = vserver

    if name:
        payload['clusternodegroup_gslbvserver_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/clusternodegroup_gslbvserver_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_clusternodegroup_lbvserver_binding(vserver=None, name=None, save=False):
    '''
    Add a new clusternodegroup_lbvserver_binding to the running configuration.

    vserver(str): vserver that need to be bound to this nodegroup.

    name(str): Name of the nodegroup. The name uniquely identifies the nodegroup on the cluster. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.add_clusternodegroup_lbvserver_binding <args>

    '''

    result = {}

    payload = {'clusternodegroup_lbvserver_binding': {}}

    if vserver:
        payload['clusternodegroup_lbvserver_binding']['vserver'] = vserver

    if name:
        payload['clusternodegroup_lbvserver_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/clusternodegroup_lbvserver_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_clusternodegroup_nslimitidentifier_binding(name=None, identifiername=None, save=False):
    '''
    Add a new clusternodegroup_nslimitidentifier_binding to the running configuration.

    name(str): Name of the nodegroup to which you want to bind a cluster node or an entity. Minimum length = 1

    identifiername(str): stream identifier and rate limit identifier that need to be bound to this nodegroup.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.add_clusternodegroup_nslimitidentifier_binding <args>

    '''

    result = {}

    payload = {'clusternodegroup_nslimitidentifier_binding': {}}

    if name:
        payload['clusternodegroup_nslimitidentifier_binding']['name'] = name

    if identifiername:
        payload['clusternodegroup_nslimitidentifier_binding']['identifiername'] = identifiername

    execution = __proxy__['citrixns.post']('config/clusternodegroup_nslimitidentifier_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_clusternodegroup_service_binding(name=None, service=None, save=False):
    '''
    Add a new clusternodegroup_service_binding to the running configuration.

    name(str): Name of the nodegroup. The name uniquely identifies the nodegroup on the cluster. Minimum length = 1

    service(str): name of the service bound to this nodegroup.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.add_clusternodegroup_service_binding <args>

    '''

    result = {}

    payload = {'clusternodegroup_service_binding': {}}

    if name:
        payload['clusternodegroup_service_binding']['name'] = name

    if service:
        payload['clusternodegroup_service_binding']['service'] = service

    execution = __proxy__['citrixns.post']('config/clusternodegroup_service_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_clusternodegroup_streamidentifier_binding(name=None, identifiername=None, save=False):
    '''
    Add a new clusternodegroup_streamidentifier_binding to the running configuration.

    name(str): Name of the nodegroup to which you want to bind a cluster node or an entity. Minimum length = 1

    identifiername(str): stream identifier and rate limit identifier that need to be bound to this nodegroup.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.add_clusternodegroup_streamidentifier_binding <args>

    '''

    result = {}

    payload = {'clusternodegroup_streamidentifier_binding': {}}

    if name:
        payload['clusternodegroup_streamidentifier_binding']['name'] = name

    if identifiername:
        payload['clusternodegroup_streamidentifier_binding']['identifiername'] = identifiername

    execution = __proxy__['citrixns.post']('config/clusternodegroup_streamidentifier_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_clusternodegroup_vpnvserver_binding(vserver=None, name=None, save=False):
    '''
    Add a new clusternodegroup_vpnvserver_binding to the running configuration.

    vserver(str): vserver that need to be bound to this nodegroup.

    name(str): Name of the nodegroup. The name uniquely identifies the nodegroup on the cluster. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.add_clusternodegroup_vpnvserver_binding <args>

    '''

    result = {}

    payload = {'clusternodegroup_vpnvserver_binding': {}}

    if vserver:
        payload['clusternodegroup_vpnvserver_binding']['vserver'] = vserver

    if name:
        payload['clusternodegroup_vpnvserver_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/clusternodegroup_vpnvserver_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def disable_clusterinstance(clid=None, save=False):
    '''
    Disables a clusterinstance matching the specified filter.

    clid(int): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.disable_clusterinstance clid=foo

    '''

    result = {}

    payload = {'clusterinstance': {}}

    if clid:
        payload['clusterinstance']['clid'] = clid
    else:
        result['result'] = 'False'
        result['error'] = 'clid value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/clusterinstance?action=disable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_clusterinstance(clid=None, save=False):
    '''
    Enables a clusterinstance matching the specified filter.

    clid(int): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.enable_clusterinstance clid=foo

    '''

    result = {}

    payload = {'clusterinstance': {}}

    if clid:
        payload['clusterinstance']['clid'] = clid
    else:
        result['result'] = 'False'
        result['error'] = 'clid value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/clusterinstance?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def get_clusterinstance(clid=None, deadinterval=None, hellointerval=None, preemption=None, quorumtype=None, inc=None,
                        processlocal=None, retainconnectionsoncluster=None, nodegroup=None):
    '''
    Show the running configuration for the clusterinstance config key.

    clid(int): Filters results that only match the clid field.

    deadinterval(int): Filters results that only match the deadinterval field.

    hellointerval(int): Filters results that only match the hellointerval field.

    preemption(str): Filters results that only match the preemption field.

    quorumtype(str): Filters results that only match the quorumtype field.

    inc(str): Filters results that only match the inc field.

    processlocal(str): Filters results that only match the processlocal field.

    retainconnectionsoncluster(str): Filters results that only match the retainconnectionsoncluster field.

    nodegroup(str): Filters results that only match the nodegroup field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusterinstance

    '''

    search_filter = []

    if clid:
        search_filter.append(['clid', clid])

    if deadinterval:
        search_filter.append(['deadinterval', deadinterval])

    if hellointerval:
        search_filter.append(['hellointerval', hellointerval])

    if preemption:
        search_filter.append(['preemption', preemption])

    if quorumtype:
        search_filter.append(['quorumtype', quorumtype])

    if inc:
        search_filter.append(['inc', inc])

    if processlocal:
        search_filter.append(['processlocal', processlocal])

    if retainconnectionsoncluster:
        search_filter.append(['retainconnectionsoncluster', retainconnectionsoncluster])

    if nodegroup:
        search_filter.append(['nodegroup', nodegroup])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusterinstance{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusterinstance')

    return response


def get_clusterinstance_binding():
    '''
    Show the running configuration for the clusterinstance_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusterinstance_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusterinstance_binding'), 'clusterinstance_binding')

    return response


def get_clusterinstance_clusternode_binding(nodeid=None, clid=None):
    '''
    Show the running configuration for the clusterinstance_clusternode_binding config key.

    nodeid(int): Filters results that only match the nodeid field.

    clid(int): Filters results that only match the clid field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusterinstance_clusternode_binding

    '''

    search_filter = []

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    if clid:
        search_filter.append(['clid', clid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusterinstance_clusternode_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusterinstance_clusternode_binding')

    return response


def get_clusternode(nodeid=None, ipaddress=None, state=None, backplane=None, priority=None, nodegroup=None, delay=None,
                    clearnodegroupconfig=None):
    '''
    Show the running configuration for the clusternode config key.

    nodeid(int): Filters results that only match the nodeid field.

    ipaddress(str): Filters results that only match the ipaddress field.

    state(str): Filters results that only match the state field.

    backplane(str): Filters results that only match the backplane field.

    priority(int): Filters results that only match the priority field.

    nodegroup(str): Filters results that only match the nodegroup field.

    delay(int): Filters results that only match the delay field.

    clearnodegroupconfig(str): Filters results that only match the clearnodegroupconfig field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusternode

    '''

    search_filter = []

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if state:
        search_filter.append(['state', state])

    if backplane:
        search_filter.append(['backplane', backplane])

    if priority:
        search_filter.append(['priority', priority])

    if nodegroup:
        search_filter.append(['nodegroup', nodegroup])

    if delay:
        search_filter.append(['delay', delay])

    if clearnodegroupconfig:
        search_filter.append(['clearnodegroupconfig', clearnodegroupconfig])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusternode{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusternode')

    return response


def get_clusternode_binding():
    '''
    Show the running configuration for the clusternode_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusternode_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusternode_binding'), 'clusternode_binding')

    return response


def get_clusternode_routemonitor_binding(nodeid=None, routemonitor=None, netmask=None):
    '''
    Show the running configuration for the clusternode_routemonitor_binding config key.

    nodeid(int): Filters results that only match the nodeid field.

    routemonitor(str): Filters results that only match the routemonitor field.

    netmask(str): Filters results that only match the netmask field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusternode_routemonitor_binding

    '''

    search_filter = []

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    if routemonitor:
        search_filter.append(['routemonitor', routemonitor])

    if netmask:
        search_filter.append(['netmask', netmask])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusternode_routemonitor_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusternode_routemonitor_binding')

    return response


def get_clusternodegroup(name=None, strict=None, sticky=None, state=None, priority=None):
    '''
    Show the running configuration for the clusternodegroup config key.

    name(str): Filters results that only match the name field.

    strict(str): Filters results that only match the strict field.

    sticky(str): Filters results that only match the sticky field.

    state(str): Filters results that only match the state field.

    priority(int): Filters results that only match the priority field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusternodegroup

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if strict:
        search_filter.append(['strict', strict])

    if sticky:
        search_filter.append(['sticky', sticky])

    if state:
        search_filter.append(['state', state])

    if priority:
        search_filter.append(['priority', priority])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusternodegroup{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusternodegroup')

    return response


def get_clusternodegroup_authenticationvserver_binding(vserver=None, name=None):
    '''
    Show the running configuration for the clusternodegroup_authenticationvserver_binding config key.

    vserver(str): Filters results that only match the vserver field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusternodegroup_authenticationvserver_binding

    '''

    search_filter = []

    if vserver:
        search_filter.append(['vserver', vserver])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusternodegroup_authenticationvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusternodegroup_authenticationvserver_binding')

    return response


def get_clusternodegroup_binding():
    '''
    Show the running configuration for the clusternodegroup_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusternodegroup_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusternodegroup_binding'), 'clusternodegroup_binding')

    return response


def get_clusternodegroup_clusternode_binding(name=None, node=None):
    '''
    Show the running configuration for the clusternodegroup_clusternode_binding config key.

    name(str): Filters results that only match the name field.

    node(int): Filters results that only match the node field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusternodegroup_clusternode_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if node:
        search_filter.append(['node', node])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusternodegroup_clusternode_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusternodegroup_clusternode_binding')

    return response


def get_clusternodegroup_crvserver_binding(vserver=None, name=None):
    '''
    Show the running configuration for the clusternodegroup_crvserver_binding config key.

    vserver(str): Filters results that only match the vserver field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusternodegroup_crvserver_binding

    '''

    search_filter = []

    if vserver:
        search_filter.append(['vserver', vserver])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusternodegroup_crvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusternodegroup_crvserver_binding')

    return response


def get_clusternodegroup_csvserver_binding(vserver=None, name=None):
    '''
    Show the running configuration for the clusternodegroup_csvserver_binding config key.

    vserver(str): Filters results that only match the vserver field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusternodegroup_csvserver_binding

    '''

    search_filter = []

    if vserver:
        search_filter.append(['vserver', vserver])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusternodegroup_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusternodegroup_csvserver_binding')

    return response


def get_clusternodegroup_gslbsite_binding(gslbsite=None, name=None):
    '''
    Show the running configuration for the clusternodegroup_gslbsite_binding config key.

    gslbsite(str): Filters results that only match the gslbsite field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusternodegroup_gslbsite_binding

    '''

    search_filter = []

    if gslbsite:
        search_filter.append(['gslbsite', gslbsite])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusternodegroup_gslbsite_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusternodegroup_gslbsite_binding')

    return response


def get_clusternodegroup_gslbvserver_binding(vserver=None, name=None):
    '''
    Show the running configuration for the clusternodegroup_gslbvserver_binding config key.

    vserver(str): Filters results that only match the vserver field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusternodegroup_gslbvserver_binding

    '''

    search_filter = []

    if vserver:
        search_filter.append(['vserver', vserver])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusternodegroup_gslbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusternodegroup_gslbvserver_binding')

    return response


def get_clusternodegroup_lbvserver_binding(vserver=None, name=None):
    '''
    Show the running configuration for the clusternodegroup_lbvserver_binding config key.

    vserver(str): Filters results that only match the vserver field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusternodegroup_lbvserver_binding

    '''

    search_filter = []

    if vserver:
        search_filter.append(['vserver', vserver])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusternodegroup_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusternodegroup_lbvserver_binding')

    return response


def get_clusternodegroup_nslimitidentifier_binding(name=None, identifiername=None):
    '''
    Show the running configuration for the clusternodegroup_nslimitidentifier_binding config key.

    name(str): Filters results that only match the name field.

    identifiername(str): Filters results that only match the identifiername field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusternodegroup_nslimitidentifier_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if identifiername:
        search_filter.append(['identifiername', identifiername])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusternodegroup_nslimitidentifier_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusternodegroup_nslimitidentifier_binding')

    return response


def get_clusternodegroup_service_binding(name=None, service=None):
    '''
    Show the running configuration for the clusternodegroup_service_binding config key.

    name(str): Filters results that only match the name field.

    service(str): Filters results that only match the service field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusternodegroup_service_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if service:
        search_filter.append(['service', service])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusternodegroup_service_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusternodegroup_service_binding')

    return response


def get_clusternodegroup_streamidentifier_binding(name=None, identifiername=None):
    '''
    Show the running configuration for the clusternodegroup_streamidentifier_binding config key.

    name(str): Filters results that only match the name field.

    identifiername(str): Filters results that only match the identifiername field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusternodegroup_streamidentifier_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if identifiername:
        search_filter.append(['identifiername', identifiername])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusternodegroup_streamidentifier_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusternodegroup_streamidentifier_binding')

    return response


def get_clusternodegroup_vpnvserver_binding(vserver=None, name=None):
    '''
    Show the running configuration for the clusternodegroup_vpnvserver_binding config key.

    vserver(str): Filters results that only match the vserver field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusternodegroup_vpnvserver_binding

    '''

    search_filter = []

    if vserver:
        search_filter.append(['vserver', vserver])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusternodegroup_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusternodegroup_vpnvserver_binding')

    return response


def get_clusterpropstatus(nodeid=None):
    '''
    Show the running configuration for the clusterpropstatus config key.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.get_clusterpropstatus

    '''

    search_filter = []

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/clusterpropstatus{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'clusterpropstatus')

    return response


def unset_clusterinstance(clid=None, deadinterval=None, hellointerval=None, preemption=None, quorumtype=None, inc=None,
                          processlocal=None, retainconnectionsoncluster=None, nodegroup=None, save=False):
    '''
    Unsets values from the clusterinstance configuration key.

    clid(bool): Unsets the clid value.

    deadinterval(bool): Unsets the deadinterval value.

    hellointerval(bool): Unsets the hellointerval value.

    preemption(bool): Unsets the preemption value.

    quorumtype(bool): Unsets the quorumtype value.

    inc(bool): Unsets the inc value.

    processlocal(bool): Unsets the processlocal value.

    retainconnectionsoncluster(bool): Unsets the retainconnectionsoncluster value.

    nodegroup(bool): Unsets the nodegroup value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.unset_clusterinstance <args>

    '''

    result = {}

    payload = {'clusterinstance': {}}

    if clid:
        payload['clusterinstance']['clid'] = True

    if deadinterval:
        payload['clusterinstance']['deadinterval'] = True

    if hellointerval:
        payload['clusterinstance']['hellointerval'] = True

    if preemption:
        payload['clusterinstance']['preemption'] = True

    if quorumtype:
        payload['clusterinstance']['quorumtype'] = True

    if inc:
        payload['clusterinstance']['inc'] = True

    if processlocal:
        payload['clusterinstance']['processlocal'] = True

    if retainconnectionsoncluster:
        payload['clusterinstance']['retainconnectionsoncluster'] = True

    if nodegroup:
        payload['clusterinstance']['nodegroup'] = True

    execution = __proxy__['citrixns.post']('config/clusterinstance?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_clusternode(nodeid=None, ipaddress=None, state=None, backplane=None, priority=None, nodegroup=None, delay=None,
                      clearnodegroupconfig=None, save=False):
    '''
    Unsets values from the clusternode configuration key.

    nodeid(bool): Unsets the nodeid value.

    ipaddress(bool): Unsets the ipaddress value.

    state(bool): Unsets the state value.

    backplane(bool): Unsets the backplane value.

    priority(bool): Unsets the priority value.

    nodegroup(bool): Unsets the nodegroup value.

    delay(bool): Unsets the delay value.

    clearnodegroupconfig(bool): Unsets the clearnodegroupconfig value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.unset_clusternode <args>

    '''

    result = {}

    payload = {'clusternode': {}}

    if nodeid:
        payload['clusternode']['nodeid'] = True

    if ipaddress:
        payload['clusternode']['ipaddress'] = True

    if state:
        payload['clusternode']['state'] = True

    if backplane:
        payload['clusternode']['backplane'] = True

    if priority:
        payload['clusternode']['priority'] = True

    if nodegroup:
        payload['clusternode']['nodegroup'] = True

    if delay:
        payload['clusternode']['delay'] = True

    if clearnodegroupconfig:
        payload['clusternode']['clearnodegroupconfig'] = True

    execution = __proxy__['citrixns.post']('config/clusternode?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_clusternodegroup(name=None, strict=None, sticky=None, state=None, priority=None, save=False):
    '''
    Unsets values from the clusternodegroup configuration key.

    name(bool): Unsets the name value.

    strict(bool): Unsets the strict value.

    sticky(bool): Unsets the sticky value.

    state(bool): Unsets the state value.

    priority(bool): Unsets the priority value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.unset_clusternodegroup <args>

    '''

    result = {}

    payload = {'clusternodegroup': {}}

    if name:
        payload['clusternodegroup']['name'] = True

    if strict:
        payload['clusternodegroup']['strict'] = True

    if sticky:
        payload['clusternodegroup']['sticky'] = True

    if state:
        payload['clusternodegroup']['state'] = True

    if priority:
        payload['clusternodegroup']['priority'] = True

    execution = __proxy__['citrixns.post']('config/clusternodegroup?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_clusterinstance(clid=None, deadinterval=None, hellointerval=None, preemption=None, quorumtype=None, inc=None,
                           processlocal=None, retainconnectionsoncluster=None, nodegroup=None, save=False):
    '''
    Update the running configuration for the clusterinstance config key.

    clid(int): Unique number that identifies the cluster. Minimum value = 1 Maximum value = 16

    deadinterval(int): Amount of time, in seconds, after which nodes that do not respond to the heartbeats are assumed to be
        down.If the value is less than 3 sec, set the helloInterval parameter to 200 msec. Default value: 3 Minimum value
        = 1 Maximum value = 60

    hellointerval(int): Interval, in milliseconds, at which heartbeats are sent to each cluster node to check the health
        status.Set the value to 200 msec, if the deadInterval parameter is less than 3 sec. Default value: 200 Minimum
        value = 200 Maximum value = 1000

    preemption(str): Preempt a cluster node that is configured as a SPARE if an ACTIVE node becomes available. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    quorumtype(str): Quorum Configuration Choices - "Majority" (recommended) requires majority of nodes to be online for the
        cluster to be UP. "None" relaxes this requirement. Default value: MAJORITY Possible values = MAJORITY, NONE

    inc(str): This option is required if the cluster nodes reside on different networks. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    processlocal(str): By turning on this option packets destined to a service in a cluster will not under go any steering.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    retainconnectionsoncluster(str): This option enables you to retain existing connections on a node joining a Cluster
        system or when a node is being configured for passive timeout. By default, this option is disabled. Default
        value: NO Possible values = YES, NO

    nodegroup(str): The node group in a Cluster system used for transition from L2 to L3.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.update_clusterinstance <args>

    '''

    result = {}

    payload = {'clusterinstance': {}}

    if clid:
        payload['clusterinstance']['clid'] = clid

    if deadinterval:
        payload['clusterinstance']['deadinterval'] = deadinterval

    if hellointerval:
        payload['clusterinstance']['hellointerval'] = hellointerval

    if preemption:
        payload['clusterinstance']['preemption'] = preemption

    if quorumtype:
        payload['clusterinstance']['quorumtype'] = quorumtype

    if inc:
        payload['clusterinstance']['inc'] = inc

    if processlocal:
        payload['clusterinstance']['processlocal'] = processlocal

    if retainconnectionsoncluster:
        payload['clusterinstance']['retainconnectionsoncluster'] = retainconnectionsoncluster

    if nodegroup:
        payload['clusterinstance']['nodegroup'] = nodegroup

    execution = __proxy__['citrixns.put']('config/clusterinstance', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_clusternode(nodeid=None, ipaddress=None, state=None, backplane=None, priority=None, nodegroup=None,
                       delay=None, clearnodegroupconfig=None, save=False):
    '''
    Update the running configuration for the clusternode config key.

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    ipaddress(str): NetScaler IP (NSIP) address of the appliance to add to the cluster. Must be an IPv4 address. Minimum
        length = 1

    state(str): Admin state of the cluster node. The available settings function as follows: ACTIVE - The node serves
        traffic. SPARE - The node does not serve traffic unless an ACTIVE node goes down. PASSIVE - The node does not
        serve traffic, unless you change its state. PASSIVE state is useful during temporary maintenance activities in
        which you want the node to take part in the consensus protocol but not to serve traffic. Default value: PASSIVE
        Possible values = ACTIVE, SPARE, PASSIVE

    backplane(str): Interface through which the node communicates with the other nodes in the cluster. Must be specified in
        the three-tuple form n/c/u, where n represents the node ID and c/u refers to the interface on the appliance.
        Minimum length = 1

    priority(int): Preference for selecting a node as the configuration coordinator. The node with the lowest priority value
        is selected as the configuration coordinator. When the current configuration coordinator goes down, the node with
        the next lowest priority is made the new configuration coordinator. When the original node comes back up, it will
        preempt the new configuration coordinator and take over as the configuration coordinator. Note: When priority is
        not configured for any of the nodes or if multiple nodes have the same priority, the cluster elects one of the
        nodes as the configuration coordinator. Default value: 31 Minimum value = 0 Maximum value = 31

    nodegroup(str): The default node group in a Cluster system. Default value: DEFAULT_NG Minimum length = 1

    delay(int): Applicable for Passive node and node becomes passive after this timeout. Default value: 0 Minimum value = 0
        Maximum value = 1440

    clearnodegroupconfig(str): Option to remove nodegroup config. Default value: YES Possible values = YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.update_clusternode <args>

    '''

    result = {}

    payload = {'clusternode': {}}

    if nodeid:
        payload['clusternode']['nodeid'] = nodeid

    if ipaddress:
        payload['clusternode']['ipaddress'] = ipaddress

    if state:
        payload['clusternode']['state'] = state

    if backplane:
        payload['clusternode']['backplane'] = backplane

    if priority:
        payload['clusternode']['priority'] = priority

    if nodegroup:
        payload['clusternode']['nodegroup'] = nodegroup

    if delay:
        payload['clusternode']['delay'] = delay

    if clearnodegroupconfig:
        payload['clusternode']['clearnodegroupconfig'] = clearnodegroupconfig

    execution = __proxy__['citrixns.put']('config/clusternode', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_clusternodegroup(name=None, strict=None, sticky=None, state=None, priority=None, save=False):
    '''
    Update the running configuration for the clusternodegroup config key.

    name(str): Name of the nodegroup. The name uniquely identifies the nodegroup on the cluster. Minimum length = 1

    strict(str): Specifies whether cluster nodes, that are not part of the nodegroup, will be used as backup for the
        nodegroup.  * Enabled - When one of the nodes goes down, no other cluster node is picked up to replace it. When
        the node comes up, it will continue being part of the nodegroup.  * Disabled - When one of the nodes goes down, a
        non-nodegroup cluster node is picked up and acts as part of the nodegroup. When the original node of the
        nodegroup comes up, the backup node will be replaced. Default value: NO Possible values = YES, NO

    sticky(str): Only one node can be bound to nodegroup with this option enabled. It specifies whether to prempt the traffic
        for the entities bound to nodegroup when owner node goes down and rejoins the cluster.  * Enabled - When owner
        node goes down, backup node will become the owner node and takes the traffic for the entities bound to the
        nodegroup. When bound node rejoins the cluster, traffic for the entities bound to nodegroup will not be steered
        back to this bound node. Current owner will have the ownership till it goes down.  * Disabled - When one of the
        nodes goes down, a non-nodegroup cluster node is picked up and acts as part of the nodegroup. When the original
        node of the nodegroup comes up, the backup node will be replaced. Default value: NO Possible values = YES, NO

    state(str): State of the nodegroup. All the nodes binding to this nodegroup must have the same state.
        ACTIVE/SPARE/PASSIVE. Possible values = ACTIVE, SPARE, PASSIVE

    priority(int): Priority of Nodegroup. This priority is used for all the nodes bound to the nodegroup for Nodegroup
        selection. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cluster.update_clusternodegroup <args>

    '''

    result = {}

    payload = {'clusternodegroup': {}}

    if name:
        payload['clusternodegroup']['name'] = name

    if strict:
        payload['clusternodegroup']['strict'] = strict

    if sticky:
        payload['clusternodegroup']['sticky'] = sticky

    if state:
        payload['clusternodegroup']['state'] = state

    if priority:
        payload['clusternodegroup']['priority'] = priority

    execution = __proxy__['citrixns.put']('config/clusternodegroup', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result
