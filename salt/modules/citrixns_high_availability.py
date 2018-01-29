# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the high-availability key.

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

__virtualname__ = 'high_availability'


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

    return False, 'The high_availability execution module can only be loaded for citrixns proxy minions.'


def add_hanode(id=None, ipaddress=None, inc=None, hastatus=None, hasync=None, haprop=None, hellointerval=None,
               deadinterval=None, failsafe=None, maxflips=None, maxfliptime=None, syncvlan=None, save=False):
    '''
    Add a new hanode to the running configuration.

    id(int): Number that uniquely identifies the node. For self node, it will always be 0. Peer node values can range from
        1-64. Minimum value = 1 Maximum value = 64

    ipaddress(str): The NSIP or NSIP6 address of the node to be added for an HA configuration. This setting is neither
        propagated nor synchronized. Minimum length = 1

    inc(str): This option is required if the HA nodes reside on different networks. When this mode is enabled, the following
        independent network entities and configurations are neither propagated nor synced to the other node: MIPs, SNIPs,
        VLANs, routes (except LLB routes), route monitors, RNAT rules (except any RNAT rule with a VIP as the NAT IP),
        and dynamic routing configurations. They are maintained independently on each node. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    hastatus(str): The HA status of the node. The HA status STAYSECONDARY is used to force the secondary device stay as
        secondary independent of the state of the Primary device. For example, in an existing HA setup, the Primary node
        has to be upgraded and this process would take few seconds. During the upgradation, it is possible that the
        Primary node may suffer from a downtime for a few seconds. However, the Secondary should not take over as the
        Primary node. Thus, the Secondary node should remain as Secondary even if there is a failure in the Primary node.
         STAYPRIMARY configuration keeps the node in primary state in case if it is healthy, even if the peer node was
        the primary node initially. If the node with STAYPRIMARY setting (and no peer node) is added to a primary node
        (which has this node as the peer) then this node takes over as the new primary and the older node becomes
        secondary. ENABLED state means normal HA operation without any constraints/preferences. DISABLED state disables
        the normal HA operation of the node. Possible values = ENABLED, STAYSECONDARY, DISABLED, STAYPRIMARY

    hasync(str): Automatically maintain synchronization by duplicating the configuration of the primary node on the secondary
        node. This setting is not propagated. Automatic synchronization requires that this setting be enabled (the
        default) on the current secondary node. Synchronization uses TCP port 3010. Default value: ENABLED Possible
        values = ENABLED, DISABLED

    haprop(str): Automatically propagate all commands from the primary to the secondary node, except the following: * All HA
        configuration related commands. For example, add ha node, set ha node, and bind ha node.  * All Interface related
        commands. For example, set interface and unset interface. * All channels related commands. For example, add
        channel, set channel, and bind channel. The propagated command is executed on the secondary node before it is
        executed on the primary. If command propagation fails, or if command execution fails on the secondary, the
        primary node executes the command and logs an error. Command propagation uses port 3010. Note: After enabling
        propagation, run force synchronization on either node. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    hellointerval(int): Interval, in milliseconds, between heartbeat messages sent to the peer node. The heartbeat messages
        are UDP packets sent to port 3003 of the peer node. Default value: 200 Minimum value = 200 Maximum value = 1000

    deadinterval(int): Number of seconds after which a peer node is marked DOWN if heartbeat messages are not received from
        the peer node. Default value: 3 Minimum value = 3 Maximum value = 60

    failsafe(str): Keep one node primary if both nodes fail the health check, so that a partially available node can back up
        data and handle traffic. This mode is set independently on each node. Default value: OFF Possible values = ON,
        OFF

    maxflips(int): Max number of flips allowed before becoming sticky primary. Default value: 0

    maxfliptime(int): Interval after which flipping of node states can again start. Default value: 0

    syncvlan(int): Vlan on which HA related communication is sent. This include sync, propagation , connection mirroring , LB
        persistency config sync, persistent session sync and session state sync. However HA heartbeats can go all
        interfaces. Minimum value = 1 Maximum value = 4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' high_availability.add_hanode <args>

    '''

    result = {}

    payload = {'hanode': {}}

    if id:
        payload['hanode']['id'] = id

    if ipaddress:
        payload['hanode']['ipaddress'] = ipaddress

    if inc:
        payload['hanode']['inc'] = inc

    if hastatus:
        payload['hanode']['hastatus'] = hastatus

    if hasync:
        payload['hanode']['hasync'] = hasync

    if haprop:
        payload['hanode']['haprop'] = haprop

    if hellointerval:
        payload['hanode']['hellointerval'] = hellointerval

    if deadinterval:
        payload['hanode']['deadinterval'] = deadinterval

    if failsafe:
        payload['hanode']['failsafe'] = failsafe

    if maxflips:
        payload['hanode']['maxflips'] = maxflips

    if maxfliptime:
        payload['hanode']['maxfliptime'] = maxfliptime

    if syncvlan:
        payload['hanode']['syncvlan'] = syncvlan

    execution = __proxy__['citrixns.post']('config/hanode', payload)

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


def add_hanode_routemonitor6_binding(routemonitor=None, id=None, netmask=None, save=False):
    '''
    Add a new hanode_routemonitor6_binding to the running configuration.

    routemonitor(str): The IP address (IPv4 or IPv6).

    id(int): Number that uniquely identifies the local node. The ID of the local node is always 0. Minimum value = 0 Maximum
        value = 64

    netmask(str): The netmask.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' high_availability.add_hanode_routemonitor6_binding <args>

    '''

    result = {}

    payload = {'hanode_routemonitor6_binding': {}}

    if routemonitor:
        payload['hanode_routemonitor6_binding']['routemonitor'] = routemonitor

    if id:
        payload['hanode_routemonitor6_binding']['id'] = id

    if netmask:
        payload['hanode_routemonitor6_binding']['netmask'] = netmask

    execution = __proxy__['citrixns.post']('config/hanode_routemonitor6_binding', payload)

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


def add_hanode_routemonitor_binding(routemonitor=None, id=None, netmask=None, save=False):
    '''
    Add a new hanode_routemonitor_binding to the running configuration.

    routemonitor(str): The IP address (IPv4 or IPv6).

    id(int): Number that uniquely identifies the local node. The ID of the local node is always 0. Minimum value = 0 Maximum
        value = 64

    netmask(str): The netmask.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' high_availability.add_hanode_routemonitor_binding <args>

    '''

    result = {}

    payload = {'hanode_routemonitor_binding': {}}

    if routemonitor:
        payload['hanode_routemonitor_binding']['routemonitor'] = routemonitor

    if id:
        payload['hanode_routemonitor_binding']['id'] = id

    if netmask:
        payload['hanode_routemonitor_binding']['netmask'] = netmask

    execution = __proxy__['citrixns.post']('config/hanode_routemonitor_binding', payload)

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


def get_hanode(id=None, ipaddress=None, inc=None, hastatus=None, hasync=None, haprop=None, hellointerval=None,
               deadinterval=None, failsafe=None, maxflips=None, maxfliptime=None, syncvlan=None):
    '''
    Show the running configuration for the hanode config key.

    id(int): Filters results that only match the id field.

    ipaddress(str): Filters results that only match the ipaddress field.

    inc(str): Filters results that only match the inc field.

    hastatus(str): Filters results that only match the hastatus field.

    hasync(str): Filters results that only match the hasync field.

    haprop(str): Filters results that only match the haprop field.

    hellointerval(int): Filters results that only match the hellointerval field.

    deadinterval(int): Filters results that only match the deadinterval field.

    failsafe(str): Filters results that only match the failsafe field.

    maxflips(int): Filters results that only match the maxflips field.

    maxfliptime(int): Filters results that only match the maxfliptime field.

    syncvlan(int): Filters results that only match the syncvlan field.

    CLI Example:

    .. code-block:: bash

    salt '*' high_availability.get_hanode

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if inc:
        search_filter.append(['inc', inc])

    if hastatus:
        search_filter.append(['hastatus', hastatus])

    if hasync:
        search_filter.append(['hasync', hasync])

    if haprop:
        search_filter.append(['haprop', haprop])

    if hellointerval:
        search_filter.append(['hellointerval', hellointerval])

    if deadinterval:
        search_filter.append(['deadinterval', deadinterval])

    if failsafe:
        search_filter.append(['failsafe', failsafe])

    if maxflips:
        search_filter.append(['maxflips', maxflips])

    if maxfliptime:
        search_filter.append(['maxfliptime', maxfliptime])

    if syncvlan:
        search_filter.append(['syncvlan', syncvlan])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/hanode{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'hanode')

    return response


def get_hanode_binding():
    '''
    Show the running configuration for the hanode_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' high_availability.get_hanode_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/hanode_binding'), 'hanode_binding')

    return response


def get_hanode_ci_binding(enaifaces=None, routemonitor=None, id=None):
    '''
    Show the running configuration for the hanode_ci_binding config key.

    enaifaces(str): Filters results that only match the enaifaces field.

    routemonitor(str): Filters results that only match the routemonitor field.

    id(int): Filters results that only match the id field.

    CLI Example:

    .. code-block:: bash

    salt '*' high_availability.get_hanode_ci_binding

    '''

    search_filter = []

    if enaifaces:
        search_filter.append(['enaifaces', enaifaces])

    if routemonitor:
        search_filter.append(['routemonitor', routemonitor])

    if id:
        search_filter.append(['id', id])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/hanode_ci_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'hanode_ci_binding')

    return response


def get_hanode_fis_binding(name=None, routemonitor=None, id=None):
    '''
    Show the running configuration for the hanode_fis_binding config key.

    name(str): Filters results that only match the name field.

    routemonitor(str): Filters results that only match the routemonitor field.

    id(int): Filters results that only match the id field.

    CLI Example:

    .. code-block:: bash

    salt '*' high_availability.get_hanode_fis_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if routemonitor:
        search_filter.append(['routemonitor', routemonitor])

    if id:
        search_filter.append(['id', id])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/hanode_fis_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'hanode_fis_binding')

    return response


def get_hanode_partialfailureinterfaces_binding(pfifaces=None, routemonitor=None, id=None):
    '''
    Show the running configuration for the hanode_partialfailureinterfaces_binding config key.

    pfifaces(str): Filters results that only match the pfifaces field.

    routemonitor(str): Filters results that only match the routemonitor field.

    id(int): Filters results that only match the id field.

    CLI Example:

    .. code-block:: bash

    salt '*' high_availability.get_hanode_partialfailureinterfaces_binding

    '''

    search_filter = []

    if pfifaces:
        search_filter.append(['pfifaces', pfifaces])

    if routemonitor:
        search_filter.append(['routemonitor', routemonitor])

    if id:
        search_filter.append(['id', id])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/hanode_partialfailureinterfaces_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'hanode_partialfailureinterfaces_binding')

    return response


def get_hanode_routemonitor6_binding(routemonitor=None, id=None, netmask=None):
    '''
    Show the running configuration for the hanode_routemonitor6_binding config key.

    routemonitor(str): Filters results that only match the routemonitor field.

    id(int): Filters results that only match the id field.

    netmask(str): Filters results that only match the netmask field.

    CLI Example:

    .. code-block:: bash

    salt '*' high_availability.get_hanode_routemonitor6_binding

    '''

    search_filter = []

    if routemonitor:
        search_filter.append(['routemonitor', routemonitor])

    if id:
        search_filter.append(['id', id])

    if netmask:
        search_filter.append(['netmask', netmask])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/hanode_routemonitor6_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'hanode_routemonitor6_binding')

    return response


def get_hanode_routemonitor_binding(routemonitor=None, id=None, netmask=None):
    '''
    Show the running configuration for the hanode_routemonitor_binding config key.

    routemonitor(str): Filters results that only match the routemonitor field.

    id(int): Filters results that only match the id field.

    netmask(str): Filters results that only match the netmask field.

    CLI Example:

    .. code-block:: bash

    salt '*' high_availability.get_hanode_routemonitor_binding

    '''

    search_filter = []

    if routemonitor:
        search_filter.append(['routemonitor', routemonitor])

    if id:
        search_filter.append(['id', id])

    if netmask:
        search_filter.append(['netmask', netmask])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/hanode_routemonitor_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'hanode_routemonitor_binding')

    return response


def unset_hanode(id=None, ipaddress=None, inc=None, hastatus=None, hasync=None, haprop=None, hellointerval=None,
                 deadinterval=None, failsafe=None, maxflips=None, maxfliptime=None, syncvlan=None, save=False):
    '''
    Unsets values from the hanode configuration key.

    id(bool): Unsets the id value.

    ipaddress(bool): Unsets the ipaddress value.

    inc(bool): Unsets the inc value.

    hastatus(bool): Unsets the hastatus value.

    hasync(bool): Unsets the hasync value.

    haprop(bool): Unsets the haprop value.

    hellointerval(bool): Unsets the hellointerval value.

    deadinterval(bool): Unsets the deadinterval value.

    failsafe(bool): Unsets the failsafe value.

    maxflips(bool): Unsets the maxflips value.

    maxfliptime(bool): Unsets the maxfliptime value.

    syncvlan(bool): Unsets the syncvlan value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' high_availability.unset_hanode <args>

    '''

    result = {}

    payload = {'hanode': {}}

    if id:
        payload['hanode']['id'] = True

    if ipaddress:
        payload['hanode']['ipaddress'] = True

    if inc:
        payload['hanode']['inc'] = True

    if hastatus:
        payload['hanode']['hastatus'] = True

    if hasync:
        payload['hanode']['hasync'] = True

    if haprop:
        payload['hanode']['haprop'] = True

    if hellointerval:
        payload['hanode']['hellointerval'] = True

    if deadinterval:
        payload['hanode']['deadinterval'] = True

    if failsafe:
        payload['hanode']['failsafe'] = True

    if maxflips:
        payload['hanode']['maxflips'] = True

    if maxfliptime:
        payload['hanode']['maxfliptime'] = True

    if syncvlan:
        payload['hanode']['syncvlan'] = True

    execution = __proxy__['citrixns.post']('config/hanode?action=unset', payload)

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


def update_hanode(id=None, ipaddress=None, inc=None, hastatus=None, hasync=None, haprop=None, hellointerval=None,
                  deadinterval=None, failsafe=None, maxflips=None, maxfliptime=None, syncvlan=None, save=False):
    '''
    Update the running configuration for the hanode config key.

    id(int): Number that uniquely identifies the node. For self node, it will always be 0. Peer node values can range from
        1-64. Minimum value = 1 Maximum value = 64

    ipaddress(str): The NSIP or NSIP6 address of the node to be added for an HA configuration. This setting is neither
        propagated nor synchronized. Minimum length = 1

    inc(str): This option is required if the HA nodes reside on different networks. When this mode is enabled, the following
        independent network entities and configurations are neither propagated nor synced to the other node: MIPs, SNIPs,
        VLANs, routes (except LLB routes), route monitors, RNAT rules (except any RNAT rule with a VIP as the NAT IP),
        and dynamic routing configurations. They are maintained independently on each node. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    hastatus(str): The HA status of the node. The HA status STAYSECONDARY is used to force the secondary device stay as
        secondary independent of the state of the Primary device. For example, in an existing HA setup, the Primary node
        has to be upgraded and this process would take few seconds. During the upgradation, it is possible that the
        Primary node may suffer from a downtime for a few seconds. However, the Secondary should not take over as the
        Primary node. Thus, the Secondary node should remain as Secondary even if there is a failure in the Primary node.
         STAYPRIMARY configuration keeps the node in primary state in case if it is healthy, even if the peer node was
        the primary node initially. If the node with STAYPRIMARY setting (and no peer node) is added to a primary node
        (which has this node as the peer) then this node takes over as the new primary and the older node becomes
        secondary. ENABLED state means normal HA operation without any constraints/preferences. DISABLED state disables
        the normal HA operation of the node. Possible values = ENABLED, STAYSECONDARY, DISABLED, STAYPRIMARY

    hasync(str): Automatically maintain synchronization by duplicating the configuration of the primary node on the secondary
        node. This setting is not propagated. Automatic synchronization requires that this setting be enabled (the
        default) on the current secondary node. Synchronization uses TCP port 3010. Default value: ENABLED Possible
        values = ENABLED, DISABLED

    haprop(str): Automatically propagate all commands from the primary to the secondary node, except the following: * All HA
        configuration related commands. For example, add ha node, set ha node, and bind ha node.  * All Interface related
        commands. For example, set interface and unset interface. * All channels related commands. For example, add
        channel, set channel, and bind channel. The propagated command is executed on the secondary node before it is
        executed on the primary. If command propagation fails, or if command execution fails on the secondary, the
        primary node executes the command and logs an error. Command propagation uses port 3010. Note: After enabling
        propagation, run force synchronization on either node. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    hellointerval(int): Interval, in milliseconds, between heartbeat messages sent to the peer node. The heartbeat messages
        are UDP packets sent to port 3003 of the peer node. Default value: 200 Minimum value = 200 Maximum value = 1000

    deadinterval(int): Number of seconds after which a peer node is marked DOWN if heartbeat messages are not received from
        the peer node. Default value: 3 Minimum value = 3 Maximum value = 60

    failsafe(str): Keep one node primary if both nodes fail the health check, so that a partially available node can back up
        data and handle traffic. This mode is set independently on each node. Default value: OFF Possible values = ON,
        OFF

    maxflips(int): Max number of flips allowed before becoming sticky primary. Default value: 0

    maxfliptime(int): Interval after which flipping of node states can again start. Default value: 0

    syncvlan(int): Vlan on which HA related communication is sent. This include sync, propagation , connection mirroring , LB
        persistency config sync, persistent session sync and session state sync. However HA heartbeats can go all
        interfaces. Minimum value = 1 Maximum value = 4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' high_availability.update_hanode <args>

    '''

    result = {}

    payload = {'hanode': {}}

    if id:
        payload['hanode']['id'] = id

    if ipaddress:
        payload['hanode']['ipaddress'] = ipaddress

    if inc:
        payload['hanode']['inc'] = inc

    if hastatus:
        payload['hanode']['hastatus'] = hastatus

    if hasync:
        payload['hanode']['hasync'] = hasync

    if haprop:
        payload['hanode']['haprop'] = haprop

    if hellointerval:
        payload['hanode']['hellointerval'] = hellointerval

    if deadinterval:
        payload['hanode']['deadinterval'] = deadinterval

    if failsafe:
        payload['hanode']['failsafe'] = failsafe

    if maxflips:
        payload['hanode']['maxflips'] = maxflips

    if maxfliptime:
        payload['hanode']['maxfliptime'] = maxfliptime

    if syncvlan:
        payload['hanode']['syncvlan'] = syncvlan

    execution = __proxy__['citrixns.put']('config/hanode', payload)

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
