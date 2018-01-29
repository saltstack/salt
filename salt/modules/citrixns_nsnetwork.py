# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the network key.

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

__virtualname__ = 'nsnetwork'


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

    return False, 'The network execution module can only be loaded for citrixns proxy minions.'


def add_arp(ipaddress=None, td=None, mac=None, ifnum=None, vxlan=None, vtep=None, vlan=None, ownernode=None, nodeid=None,
            save=False):
    '''
    Add a new arp to the running configuration.

    ipaddress(str): IP address of the network device that you want to add to the ARP table. Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    mac(str): MAC address of the network device.

    ifnum(str): Interface through which the network device is accessible. Specify the interface in (slot/port) notation. For
        example, 1/3.

    vxlan(int): ID of the VXLAN on which the IP address of this ARP entry is reachable. Minimum value = 1 Maximum value =
        16777215

    vtep(str): IP address of the VXLAN tunnel endpoint (VTEP) through which the IP address of this ARP entry is reachable.
        Minimum length = 1

    vlan(int): The VLAN ID through which packets are to be sent after matching the ARP entry. This is a numeric value.

    ownernode(int): The owner node for the Arp entry. Minimum value = 0 Maximum value = 31

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_arp <args>

    '''

    result = {}

    payload = {'arp': {}}

    if ipaddress:
        payload['arp']['ipaddress'] = ipaddress

    if td:
        payload['arp']['td'] = td

    if mac:
        payload['arp']['mac'] = mac

    if ifnum:
        payload['arp']['ifnum'] = ifnum

    if vxlan:
        payload['arp']['vxlan'] = vxlan

    if vtep:
        payload['arp']['vtep'] = vtep

    if vlan:
        payload['arp']['vlan'] = vlan

    if ownernode:
        payload['arp']['ownernode'] = ownernode

    if nodeid:
        payload['arp']['nodeid'] = nodeid

    execution = __proxy__['citrixns.post']('config/arp', payload)

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


def add_bridgegroup(id=None, dynamicrouting=None, ipv6dynamicrouting=None, save=False):
    '''
    Add a new bridgegroup to the running configuration.

    id(int): An integer that uniquely identifies the bridge group. Minimum value = 1 Maximum value = 1000

    dynamicrouting(str): Enable dynamic routing for this bridgegroup. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    ipv6dynamicrouting(str): Enable all IPv6 dynamic routing protocols on all VLANs bound to this bridgegroup. Note: For the
        ENABLED setting to work, you must configure IPv6 dynamic routing protocols from the VTYSH command line. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_bridgegroup <args>

    '''

    result = {}

    payload = {'bridgegroup': {}}

    if id:
        payload['bridgegroup']['id'] = id

    if dynamicrouting:
        payload['bridgegroup']['dynamicrouting'] = dynamicrouting

    if ipv6dynamicrouting:
        payload['bridgegroup']['ipv6dynamicrouting'] = ipv6dynamicrouting

    execution = __proxy__['citrixns.post']('config/bridgegroup', payload)

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


def add_bridgegroup_nsip6_binding(ownergroup=None, netmask=None, id=None, td=None, ipaddress=None, save=False):
    '''
    Add a new bridgegroup_nsip6_binding to the running configuration.

    ownergroup(str): The owner node group in a Cluster for this vlan. Default value: DEFAULT_NG Minimum length = 1

    netmask(str): A subnet mask associated with the network address. Minimum length = 1

    id(int): The integer that uniquely identifies the bridge group. Minimum value = 1 Maximum value = 1000

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    ipaddress(str): The IP address assigned to the bridge group.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_bridgegroup_nsip6_binding <args>

    '''

    result = {}

    payload = {'bridgegroup_nsip6_binding': {}}

    if ownergroup:
        payload['bridgegroup_nsip6_binding']['ownergroup'] = ownergroup

    if netmask:
        payload['bridgegroup_nsip6_binding']['netmask'] = netmask

    if id:
        payload['bridgegroup_nsip6_binding']['id'] = id

    if td:
        payload['bridgegroup_nsip6_binding']['td'] = td

    if ipaddress:
        payload['bridgegroup_nsip6_binding']['ipaddress'] = ipaddress

    execution = __proxy__['citrixns.post']('config/bridgegroup_nsip6_binding', payload)

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


def add_bridgegroup_nsip_binding(ownergroup=None, id=None, netmask=None, td=None, ipaddress=None, save=False):
    '''
    Add a new bridgegroup_nsip_binding to the running configuration.

    ownergroup(str): The owner node group in a Cluster for this vlan. Default value: DEFAULT_NG Minimum length = 1

    id(int): The integer that uniquely identifies the bridge group. Minimum value = 1 Maximum value = 1000

    netmask(str): The network mask for the subnet defined for the bridge group.

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    ipaddress(str): The IP address assigned to the bridge group.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_bridgegroup_nsip_binding <args>

    '''

    result = {}

    payload = {'bridgegroup_nsip_binding': {}}

    if ownergroup:
        payload['bridgegroup_nsip_binding']['ownergroup'] = ownergroup

    if id:
        payload['bridgegroup_nsip_binding']['id'] = id

    if netmask:
        payload['bridgegroup_nsip_binding']['netmask'] = netmask

    if td:
        payload['bridgegroup_nsip_binding']['td'] = td

    if ipaddress:
        payload['bridgegroup_nsip_binding']['ipaddress'] = ipaddress

    execution = __proxy__['citrixns.post']('config/bridgegroup_nsip_binding', payload)

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


def add_bridgegroup_vlan_binding(vlan=None, id=None, save=False):
    '''
    Add a new bridgegroup_vlan_binding to the running configuration.

    vlan(int): Names of all member VLANs.

    id(int): The integer that uniquely identifies the bridge group. Minimum value = 1 Maximum value = 1000

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_bridgegroup_vlan_binding <args>

    '''

    result = {}

    payload = {'bridgegroup_vlan_binding': {}}

    if vlan:
        payload['bridgegroup_vlan_binding']['vlan'] = vlan

    if id:
        payload['bridgegroup_vlan_binding']['id'] = id

    execution = __proxy__['citrixns.post']('config/bridgegroup_vlan_binding', payload)

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


def add_bridgetable(mac=None, vxlan=None, vtep=None, vni=None, devicevlan=None, bridgeage=None, nodeid=None, vlan=None,
                    ifnum=None, save=False):
    '''
    Add a new bridgetable to the running configuration.

    mac(str): The MAC address of the target.

    vxlan(int): The VXLAN to which this address is associated. Minimum value = 1 Maximum value = 16777215

    vtep(str): The IP address of the destination VXLAN tunnel endpoint where the Ethernet MAC ADDRESS resides. Minimum length
        = 1

    vni(int): The VXLAN VNI Network Identifier (or VXLAN Segment ID) to use to connect to the remote VXLAN tunnel endpoint.
        If omitted the value specified as vxlan will be used. Minimum value = 1 Maximum value = 16777215

    devicevlan(int): The vlan on which to send multicast packets when the VXLAN tunnel endpoint is a muticast group address.
        Minimum value = 1 Maximum value = 4094

    bridgeage(int): Time-out value for the bridge table entries, in seconds. The new value applies only to the entries that
        are dynamically learned after the new value is set. Previously existing bridge table entries expire after the
        previously configured time-out value. Default value: 300 Minimum value = 60 Maximum value = 300

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    vlan(int): VLAN whose entries are to be removed. Minimum value = 1 Maximum value = 4094

    ifnum(str): INTERFACE whose entries are to be removed.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_bridgetable <args>

    '''

    result = {}

    payload = {'bridgetable': {}}

    if mac:
        payload['bridgetable']['mac'] = mac

    if vxlan:
        payload['bridgetable']['vxlan'] = vxlan

    if vtep:
        payload['bridgetable']['vtep'] = vtep

    if vni:
        payload['bridgetable']['vni'] = vni

    if devicevlan:
        payload['bridgetable']['devicevlan'] = devicevlan

    if bridgeage:
        payload['bridgetable']['bridgeage'] = bridgeage

    if nodeid:
        payload['bridgetable']['nodeid'] = nodeid

    if vlan:
        payload['bridgetable']['vlan'] = vlan

    if ifnum:
        payload['bridgetable']['ifnum'] = ifnum

    execution = __proxy__['citrixns.post']('config/bridgetable', payload)

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


def add_channel(id=None, ifnum=None, state=None, mode=None, conndistr=None, macdistr=None, lamac=None, speed=None,
                flowctl=None, hamonitor=None, haheartbeat=None, tagall=None, trunk=None, ifalias=None, throughput=None,
                bandwidthhigh=None, bandwidthnormal=None, mtu=None, lrminthroughput=None, linkredundancy=None,
                save=False):
    '''
    Add a new channel to the running configuration.

    id(str): ID for the LA channel or cluster LA channel or LR channel to be created. Specify an LA channel in LA/x notation,
        where x can range from 1 to 8 or cluster LA channel in CLA/x notation or Link redundant channel in LR/x notation,
        where x can range from 1 to 4. Cannot be changed after the LA channel is created.

    ifnum(list(str)): Interfaces to be bound to the LA channel of a NetScaler appliance or to the LA channel of a cluster
        configuration. For an LA channel of a NetScaler appliance, specify an interface in C/U notation (for example,
        1/3).  For an LA channel of a cluster configuration, specify an interface in N/C/U notation (for example, 2/1/3).
        where C can take one of the following values: * 0 - Indicates a management interface. * 1 - Indicates a 1 Gbps
        port. * 10 - Indicates a 10 Gbps port. U is a unique integer for representing an interface in a particular port
        group. N is the ID of the node to which an interface belongs in a cluster configuration. Use spaces to separate
        multiple entries.

    state(str): Enable or disable the LA channel. Default value: ENABLED Possible values = ENABLED, DISABLED

    mode(str): The initital mode for the LA channel. Possible values = MANUAL, AUTO

    conndistr(str): The connection distribution mode for the LA channel. Possible values = DISABLED, ENABLED

    macdistr(str): The MAC distribution mode for the LA channel. Possible values = SOURCE, DESTINATION, BOTH

    lamac(str): Specifies a MAC address for the LA channels configured in NetScaler virtual appliances (VPX). This MAC
        address is persistent after each reboot.  If you dont specify this parameter, a MAC address is generated randomly
        for each LA channel. These MAC addresses change after each reboot.

    speed(str): Ethernet speed of the channel, in Mbps. If the speed of any bound interface is greater than or equal to the
        value set for this parameter, the state of the interface is UP. Otherwise, the state is INACTIVE. Bound
        Interfaces whose state is INACTIVE do not process any traffic. Default value: AUTO Possible values = AUTO, 10,
        100, 1000, 10000, 40000

    flowctl(str): Specifies the flow control type for this LA channel to manage the flow of frames. Flow control is a
        function as mentioned in clause 31 of the IEEE 802.3 standard. Flow control allows congested ports to pause
        traffic from the peer device. Flow control is achieved by sending PAUSE frames. Default value: OFF Possible
        values = OFF, RX, TX, RXTX, ON

    hamonitor(str): In a High Availability (HA) configuration, monitor the LA channel for failure events. Failure of any LA
        channel that has HA MON enabled triggers HA failover. Default value: ON Possible values = ON, OFF

    haheartbeat(str): In a High Availability (HA) configuration, configure the LA channel for sending heartbeats. LA channel
        that has HA Heartbeat disabled should not send the heartbeats. Default value: ON Possible values = OFF, ON

    tagall(str): Adds a four-byte 802.1q tag to every packet sent on this channel. The ON setting applies tags for all VLANs
        that are bound to this channel. OFF applies the tag for all VLANs other than the native VLAN. Default value: OFF
        Possible values = ON, OFF

    trunk(str): This is deprecated by tagall. Default value: OFF Possible values = ON, OFF

    ifalias(str): Alias name for the LA channel. Used only to enhance readability. To perform any operations, you have to
        specify the LA channel ID. Default value: " " Maximum length = 31

    throughput(int): Low threshold value for the throughput of the LA channel, in Mbps. In an high availability (HA)
        configuration, failover is triggered when the LA channel has HA MON enabled and the throughput is below the
        specified threshold. Minimum value = 0 Maximum value = 160000

    bandwidthhigh(int): High threshold value for the bandwidth usage of the LA channel, in Mbps. The NetScaler appliance
        generates an SNMP trap message when the bandwidth usage of the LA channel is greater than or equal to the
        specified high threshold value. Minimum value = 0 Maximum value = 160000

    bandwidthnormal(int): Normal threshold value for the bandwidth usage of the LA channel, in Mbps. When the bandwidth usage
        of the LA channel returns to less than or equal to the specified normal threshold after exceeding the high
        threshold, the NetScaler appliance generates an SNMP trap message to indicate that the bandwidth usage has
        returned to normal. Minimum value = 0 Maximum value = 160000

    mtu(int): The maximum transmission unit (MTU) is the largest packet size, measured in bytes excluding 14 bytes ethernet
        header and 4 bytes crc, that can be transmitted and received by this interface. Default value of MTU is 1500 on
        all the interface of Netscaler appliance any value configured more than 1500 on the interface will make the
        interface as jumbo enabled. In case of cluster backplane interface MTU value will be changed to 1514 by default,
        user has to change the backplane interface value to maximum mtu configured on any of the interface in cluster
        system plus 14 bytes more for backplane interface if Jumbo is enabled on any of the interface in a cluster
        system. Changing the backplane will bring back the MTU of backplane interface to default value of 1500. If a
        channel is configured as backplane then the same holds true for channel as well as member interfaces. Default
        value: 1500 Minimum value = 1500 Maximum value = 9216

    lrminthroughput(int): Specifies the minimum throughput threshold (in Mbps) to be met by the active subchannel. Setting
        this parameter automatically divides an LACP channel into logical subchannels, with one subchannel active and the
        others in standby mode. When the maximum supported throughput of the active channel falls below the
        lrMinThroughput value, link failover occurs and a standby subchannel becomes active. Minimum value = 0 Maximum
        value = 80000

    linkredundancy(str): Link Redundancy for Cluster LAG. Default value: OFF Possible values = ON, OFF

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_channel <args>

    '''

    result = {}

    payload = {'channel': {}}

    if id:
        payload['channel']['id'] = id

    if ifnum:
        payload['channel']['ifnum'] = ifnum

    if state:
        payload['channel']['state'] = state

    if mode:
        payload['channel']['mode'] = mode

    if conndistr:
        payload['channel']['conndistr'] = conndistr

    if macdistr:
        payload['channel']['macdistr'] = macdistr

    if lamac:
        payload['channel']['lamac'] = lamac

    if speed:
        payload['channel']['speed'] = speed

    if flowctl:
        payload['channel']['flowctl'] = flowctl

    if hamonitor:
        payload['channel']['hamonitor'] = hamonitor

    if haheartbeat:
        payload['channel']['haheartbeat'] = haheartbeat

    if tagall:
        payload['channel']['tagall'] = tagall

    if trunk:
        payload['channel']['trunk'] = trunk

    if ifalias:
        payload['channel']['ifalias'] = ifalias

    if throughput:
        payload['channel']['throughput'] = throughput

    if bandwidthhigh:
        payload['channel']['bandwidthhigh'] = bandwidthhigh

    if bandwidthnormal:
        payload['channel']['bandwidthnormal'] = bandwidthnormal

    if mtu:
        payload['channel']['mtu'] = mtu

    if lrminthroughput:
        payload['channel']['lrminthroughput'] = lrminthroughput

    if linkredundancy:
        payload['channel']['linkredundancy'] = linkredundancy

    execution = __proxy__['citrixns.post']('config/channel', payload)

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


def add_channel_interface_binding(ifnum=None, id=None, save=False):
    '''
    Add a new channel_interface_binding to the running configuration.

    ifnum(list(str)): Interfaces to be bound to the LA channel of a NetScaler appliance or to the LA channel of a cluster
        configuration. For an LA channel of a NetScaler appliance, specify an interface in C/U notation (for example,
        1/3). For an LA channel of a cluster configuration, specify an interface in N/C/U notation (for example, 2/1/3).
        where C can take one of the following values: * 0 - Indicates a management interface. * 1 - Indicates a 1 Gbps
        port. * 10 - Indicates a 10 Gbps port. U is a unique integer for representing an interface in a particular port
        group. N is the ID of the node to which an interface belongs in a cluster configuration. Use spaces to separate
        multiple entries.

    id(str): ID of the LA channel or the cluster LA channel to which you want to bind interfaces. Specify an LA channel in
        LA/x notation, where x can range from 1 to 8 or a cluster LA channel in CLA/x notation or Link redundant channel
        in LR/x notation , where x can range from 1 to 4.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_channel_interface_binding <args>

    '''

    result = {}

    payload = {'channel_interface_binding': {}}

    if ifnum:
        payload['channel_interface_binding']['ifnum'] = ifnum

    if id:
        payload['channel_interface_binding']['id'] = id

    execution = __proxy__['citrixns.post']('config/channel_interface_binding', payload)

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


def add_fis(name=None, ownernode=None, save=False):
    '''
    Add a new fis to the running configuration.

    name(str): Name for the FIS to be created. Leading character must be a number or letter. Other characters allowed, after
        the first character, are @ _ - . (period) : (colon) # and space ( ). Note: In a cluster setup, the FIS name on
        each node must be unique. Minimum length = 1

    ownernode(int): ID of the cluster node for which you are creating the FIS. Can be configured only through the cluster IP
        address. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_fis <args>

    '''

    result = {}

    payload = {'fis': {}}

    if name:
        payload['fis']['name'] = name

    if ownernode:
        payload['fis']['ownernode'] = ownernode

    execution = __proxy__['citrixns.post']('config/fis', payload)

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


def add_fis_channel_binding(ownernode=None, name=None, ifnum=None, save=False):
    '''
    Add a new fis_channel_binding to the running configuration.

    ownernode(int): ID of the cluster node for which you are creating the FIS. Can be configured only through the cluster IP
        address. Minimum value = 0 Maximum value = 31

    name(str): The name of the FIS to which you want to bind interfaces. Minimum length = 1

    ifnum(str): Interface to be bound to the FIS, specified in slot/port notation (for example, 1/3).

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_fis_channel_binding <args>

    '''

    result = {}

    payload = {'fis_channel_binding': {}}

    if ownernode:
        payload['fis_channel_binding']['ownernode'] = ownernode

    if name:
        payload['fis_channel_binding']['name'] = name

    if ifnum:
        payload['fis_channel_binding']['ifnum'] = ifnum

    execution = __proxy__['citrixns.post']('config/fis_channel_binding', payload)

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


def add_fis_interface_binding(ownernode=None, name=None, ifnum=None, save=False):
    '''
    Add a new fis_interface_binding to the running configuration.

    ownernode(int): ID of the cluster node for which you are creating the FIS. Can be configured only through the cluster IP
        address. Minimum value = 0 Maximum value = 31

    name(str): The name of the FIS to which you want to bind interfaces. Minimum length = 1

    ifnum(str): Interface to be bound to the FIS, specified in slot/port notation (for example, 1/3).

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_fis_interface_binding <args>

    '''

    result = {}

    payload = {'fis_interface_binding': {}}

    if ownernode:
        payload['fis_interface_binding']['ownernode'] = ownernode

    if name:
        payload['fis_interface_binding']['name'] = name

    if ifnum:
        payload['fis_interface_binding']['ifnum'] = ifnum

    execution = __proxy__['citrixns.post']('config/fis_interface_binding', payload)

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


def add_forwardingsession(name=None, network=None, netmask=None, acl6name=None, aclname=None, td=None, connfailover=None,
                          sourceroutecache=None, processlocal=None, save=False):
    '''
    Add a new forwardingsession to the running configuration.

    name(str): Name for the forwarding session rule. Can begin with a letter, number, or the underscore character (_), and
        can consist of letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after the rule is created. The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my rule" or my rule). Minimum length = 1

    network(str): An IPv4 network address or IPv6 prefix of a network from which the forwarded traffic originates or to which
        it is destined. Minimum length = 1

    netmask(str): Subnet mask associated with the network. Minimum length = 1

    acl6name(str): Name of any configured ACL6 whose action is ALLOW. The rule of the ACL6 is used as a forwarding session
        rule. Minimum length = 1

    aclname(str): Name of any configured ACL whose action is ALLOW. The rule of the ACL is used as a forwarding session rule.
        Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    connfailover(str): Synchronize connection information with the secondary appliance in a high availability (HA) pair. That
        is, synchronize all connection-related information for the forwarding session. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    sourceroutecache(str): Cache the source ip address and mac address of the DA servers. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    processlocal(str): Enabling this option on forwarding session will not steer the packet to flow processor. Instead,
        packet will be routed. Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_forwardingsession <args>

    '''

    result = {}

    payload = {'forwardingsession': {}}

    if name:
        payload['forwardingsession']['name'] = name

    if network:
        payload['forwardingsession']['network'] = network

    if netmask:
        payload['forwardingsession']['netmask'] = netmask

    if acl6name:
        payload['forwardingsession']['acl6name'] = acl6name

    if aclname:
        payload['forwardingsession']['aclname'] = aclname

    if td:
        payload['forwardingsession']['td'] = td

    if connfailover:
        payload['forwardingsession']['connfailover'] = connfailover

    if sourceroutecache:
        payload['forwardingsession']['sourceroutecache'] = sourceroutecache

    if processlocal:
        payload['forwardingsession']['processlocal'] = processlocal

    execution = __proxy__['citrixns.post']('config/forwardingsession', payload)

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


def add_inat(name=None, publicip=None, privateip=None, mode=None, tcpproxy=None, ftp=None, tftp=None, usip=None,
             usnip=None, proxyip=None, useproxyport=None, td=None, save=False):
    '''
    Add a new inat to the running configuration.

    name(str): Name for the Inbound NAT (INAT) entry. Leading character must be a number or letter. Other characters allowed,
        after the first character, are @ _ - . (period) : (colon) # and space ( ). Minimum length = 1

    publicip(str): Public IP address of packets received on the NetScaler appliance. Can be aNetScaler-owned VIP or VIP6
        address. Minimum length = 1

    privateip(str): IP address of the server to which the packet is sent by the NetScaler. Can be an IPv4 or IPv6 address.
        Minimum length = 1

    mode(str): Stateless translation. Possible values = STATELESS

    tcpproxy(str): Enable TCP proxy, which enables the NetScaler appliance to optimize the RNAT TCP traffic by using Layer 4
        features. Default value: DISABLED Possible values = ENABLED, DISABLED

    ftp(str): Enable the FTP protocol on the server for transferring files between the client and the server. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    tftp(str): To enable/disable TFTP (Default DISABLED). Default value: DISABLED Possible values = ENABLED, DISABLED

    usip(str): Enable the NetScaler appliance to retain the source IP address of packets before sending the packets to the
        server. Possible values = ON, OFF

    usnip(str): Enable the NetScaler appliance to use a SNIP address as the source IP address of packets before sending the
        packets to the server. Possible values = ON, OFF

    proxyip(str): Unique IP address used as the source IP address in packets sent to the server. Must be a MIP or SNIP
        address.

    useproxyport(str): Enable the NetScaler appliance to proxy the source port of packets before sending the packets to the
        server. Default value: ENABLED Possible values = ENABLED, DISABLED

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_inat <args>

    '''

    result = {}

    payload = {'inat': {}}

    if name:
        payload['inat']['name'] = name

    if publicip:
        payload['inat']['publicip'] = publicip

    if privateip:
        payload['inat']['privateip'] = privateip

    if mode:
        payload['inat']['mode'] = mode

    if tcpproxy:
        payload['inat']['tcpproxy'] = tcpproxy

    if ftp:
        payload['inat']['ftp'] = ftp

    if tftp:
        payload['inat']['tftp'] = tftp

    if usip:
        payload['inat']['usip'] = usip

    if usnip:
        payload['inat']['usnip'] = usnip

    if proxyip:
        payload['inat']['proxyip'] = proxyip

    if useproxyport:
        payload['inat']['useproxyport'] = useproxyport

    if td:
        payload['inat']['td'] = td

    execution = __proxy__['citrixns.post']('config/inat', payload)

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


def add_interfacepair(id=None, ifnum=None, save=False):
    '''
    Add a new interfacepair to the running configuration.

    id(int): The Interface pair id. Minimum value = 1 Maximum value = 255

    ifnum(list(str)): The constituent interfaces in the interface pair. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_interfacepair <args>

    '''

    result = {}

    payload = {'interfacepair': {}}

    if id:
        payload['interfacepair']['id'] = id

    if ifnum:
        payload['interfacepair']['ifnum'] = ifnum

    execution = __proxy__['citrixns.post']('config/interfacepair', payload)

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


def add_ip6tunnel(name=None, remote=None, local=None, ownergroup=None, save=False):
    '''
    Add a new ip6tunnel to the running configuration.

    name(str): Name for the IPv6 Tunnel. Cannot be changed after the service group is created. Must begin with a number or
        letter, and can consist of letters, numbers, and the @ _ - . (period) : (colon) # and space ( ) characters.
        Minimum length = 1 Maximum length = 31

    remote(str): An IPv6 address of the remote NetScaler appliance used to set up the tunnel. Minimum length = 1

    local(str): An IPv6 address of the local NetScaler appliance used to set up the tunnel.

    ownergroup(str): The owner node group in a Cluster for the tunnel. Default value: DEFAULT_NG Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_ip6tunnel <args>

    '''

    result = {}

    payload = {'ip6tunnel': {}}

    if name:
        payload['ip6tunnel']['name'] = name

    if remote:
        payload['ip6tunnel']['remote'] = remote

    if local:
        payload['ip6tunnel']['local'] = local

    if ownergroup:
        payload['ip6tunnel']['ownergroup'] = ownergroup

    execution = __proxy__['citrixns.post']('config/ip6tunnel', payload)

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


def add_ipset(name=None, td=None, save=False):
    '''
    Add a new ipset to the running configuration.

    name(str): Name for the IP set. Must begin with a letter, number, or the underscore character (_), and can consist of
        letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the IP set is created. Choose a name that helps identify the IP
        set. Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_ipset <args>

    '''

    result = {}

    payload = {'ipset': {}}

    if name:
        payload['ipset']['name'] = name

    if td:
        payload['ipset']['td'] = td

    execution = __proxy__['citrixns.post']('config/ipset', payload)

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


def add_ipset_nsip6_binding(name=None, ipaddress=None, save=False):
    '''
    Add a new ipset_nsip6_binding to the running configuration.

    name(str): Name of the IP set to which to bind IP addresses. Minimum length = 1

    ipaddress(str): One or more IP addresses bound to the IP set. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_ipset_nsip6_binding <args>

    '''

    result = {}

    payload = {'ipset_nsip6_binding': {}}

    if name:
        payload['ipset_nsip6_binding']['name'] = name

    if ipaddress:
        payload['ipset_nsip6_binding']['ipaddress'] = ipaddress

    execution = __proxy__['citrixns.post']('config/ipset_nsip6_binding', payload)

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


def add_ipset_nsip_binding(name=None, ipaddress=None, save=False):
    '''
    Add a new ipset_nsip_binding to the running configuration.

    name(str): Name of the IP set to which to bind IP addresses. Minimum length = 1

    ipaddress(str): One or more IP addresses bound to the IP set. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_ipset_nsip_binding <args>

    '''

    result = {}

    payload = {'ipset_nsip_binding': {}}

    if name:
        payload['ipset_nsip_binding']['name'] = name

    if ipaddress:
        payload['ipset_nsip_binding']['ipaddress'] = ipaddress

    execution = __proxy__['citrixns.post']('config/ipset_nsip_binding', payload)

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


def add_iptunnel(name=None, remote=None, remotesubnetmask=None, local=None, protocol=None, grepayload=None,
                 ipsecprofilename=None, vlan=None, ownergroup=None, save=False):
    '''
    Add a new iptunnel to the running configuration.

    name(str): Name for the IP tunnel. Leading character must be a number or letter. Other characters allowed, after the
        first character, are @ _ - . (period) : (colon) # and space ( ). Minimum length = 1

    remote(str): Public IPv4 address, of the remote device, used to set up the tunnel. For this parameter, you can
        alternatively specify a network address. Minimum length = 1

    remotesubnetmask(str): Subnet mask of the remote IP address of the tunnel.

    local(str): Type ofNetScaler owned public IPv4 address, configured on the local NetScaler appliance and used to set up
        the tunnel.

    protocol(str): Name of the protocol to be used on this tunnel. Default value: IPIP Possible values = IPIP, GRE, IPSEC

    grepayload(str): The payload GRE will carry. Default value: ETHERNETwithDOT1Q Possible values = ETHERNETwithDOT1Q,
        ETHERNET, IP

    ipsecprofilename(str): Name of IPSec profile to be associated. Default value: "ns_ipsec_default_profile"

    vlan(int): The vlan for mulicast packets. Minimum value = 1 Maximum value = 4094

    ownergroup(str): The owner node group in a Cluster for the iptunnel. Default value: DEFAULT_NG Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_iptunnel <args>

    '''

    result = {}

    payload = {'iptunnel': {}}

    if name:
        payload['iptunnel']['name'] = name

    if remote:
        payload['iptunnel']['remote'] = remote

    if remotesubnetmask:
        payload['iptunnel']['remotesubnetmask'] = remotesubnetmask

    if local:
        payload['iptunnel']['local'] = local

    if protocol:
        payload['iptunnel']['protocol'] = protocol

    if grepayload:
        payload['iptunnel']['grepayload'] = grepayload

    if ipsecprofilename:
        payload['iptunnel']['ipsecprofilename'] = ipsecprofilename

    if vlan:
        payload['iptunnel']['vlan'] = vlan

    if ownergroup:
        payload['iptunnel']['ownergroup'] = ownergroup

    execution = __proxy__['citrixns.post']('config/iptunnel', payload)

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


def add_linkset(id=None, save=False):
    '''
    Add a new linkset to the running configuration.

    id(str): Unique identifier for the linkset. Must be of the form LS/x, where x can be an integer from 1 to 32.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_linkset <args>

    '''

    result = {}

    payload = {'linkset': {}}

    if id:
        payload['linkset']['id'] = id

    execution = __proxy__['citrixns.post']('config/linkset', payload)

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


def add_linkset_channel_binding(ifnum=None, id=None, save=False):
    '''
    Add a new linkset_channel_binding to the running configuration.

    ifnum(str): The interfaces to be bound to the linkset.

    id(str): ID of the linkset to which to bind the interfaces.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_linkset_channel_binding <args>

    '''

    result = {}

    payload = {'linkset_channel_binding': {}}

    if ifnum:
        payload['linkset_channel_binding']['ifnum'] = ifnum

    if id:
        payload['linkset_channel_binding']['id'] = id

    execution = __proxy__['citrixns.post']('config/linkset_channel_binding', payload)

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


def add_linkset_interface_binding(ifnum=None, id=None, save=False):
    '''
    Add a new linkset_interface_binding to the running configuration.

    ifnum(str): The interfaces to be bound to the linkset.

    id(str): ID of the linkset to which to bind the interfaces.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_linkset_interface_binding <args>

    '''

    result = {}

    payload = {'linkset_interface_binding': {}}

    if ifnum:
        payload['linkset_interface_binding']['ifnum'] = ifnum

    if id:
        payload['linkset_interface_binding']['id'] = id

    execution = __proxy__['citrixns.post']('config/linkset_interface_binding', payload)

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


def add_mapbmr(name=None, ruleipv6prefix=None, psidoffset=None, eabitlength=None, psidlength=None, save=False):
    '''
    Add a new mapbmr to the running configuration.

    name(str): Name for the Basic Mapping Rule. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the MAP Basic Mapping Rule is created. The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "add network MapBmr bmr1 -natprefix 2005::/64 -EAbitLength 16 -psidoffset 6
        -portsharingratio 8" ).  The Basic Mapping Rule information allows a MAP BR to determine source IPv4 address from
        the IPv6 packet sent from MAP CE device.  Also it allows to determine destination IPv6 address of MAP CE before
        sending packets to MAP CE. Minimum length = 1 Maximum length = 127

    ruleipv6prefix(str): IPv6 prefix of Customer Edge(CE) device.MAP-T CE will send ipv6 packets with this ipv6 prefix as
        source ipv6 address prefix.

    psidoffset(int): Start bit position of Port Set Identifier(PSID) value in Embedded Address (EA) bits. Default value: 6
        Minimum value = 1 Maximum value = 15

    eabitlength(int): The Embedded Address (EA) bit field encodes the CE-specific IPv4 address and port information. The EA
        bit field, which is unique for a   given Rule IPv6 prefix. Default value: 16 Minimum value = 2 Maximum value =
        47

    psidlength(int): Length of Port Set IdentifierPort Set Identifier(PSID) in Embedded Address (EA) bits. Default value: 8
        Minimum value = 1 Maximum value = 16

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_mapbmr <args>

    '''

    result = {}

    payload = {'mapbmr': {}}

    if name:
        payload['mapbmr']['name'] = name

    if ruleipv6prefix:
        payload['mapbmr']['ruleipv6prefix'] = ruleipv6prefix

    if psidoffset:
        payload['mapbmr']['psidoffset'] = psidoffset

    if eabitlength:
        payload['mapbmr']['eabitlength'] = eabitlength

    if psidlength:
        payload['mapbmr']['psidlength'] = psidlength

    execution = __proxy__['citrixns.post']('config/mapbmr', payload)

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


def add_mapbmr_bmrv4network_binding(network=None, name=None, save=False):
    '''
    Add a new mapbmr_bmrv4network_binding to the running configuration.

    network(str): IPv4 NAT address range of Customer Edge (CE). Minimum length = 1

    name(str): Name for the Basic Mapping Rule. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_mapbmr_bmrv4network_binding <args>

    '''

    result = {}

    payload = {'mapbmr_bmrv4network_binding': {}}

    if network:
        payload['mapbmr_bmrv4network_binding']['network'] = network

    if name:
        payload['mapbmr_bmrv4network_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/mapbmr_bmrv4network_binding', payload)

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


def add_mapdmr(name=None, bripv6prefix=None, save=False):
    '''
    Add a new mapdmr to the running configuration.

    name(str): Name for the Default Mapping Rule. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the MAP Default Mapping Rule is created. The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "add network MapDmr map1 -BRIpv6Prefix 2003::/96").  Default Mapping Rule (DMR) is
        defined in terms of the IPv6 prefix advertised by one or more BRs, which provide external connectivity. A typical
        MAP-T CE will install an IPv4 default route using this rule. A BR will use this rule when translating all outside
        IPv4 source addresses to the IPv6 MAP domain. Minimum length = 1 Maximum length = 127

    bripv6prefix(str): IPv6 prefix of Border Relay (Netscaler) device.MAP-T CE will send ipv6 packets to this ipv6 prefix.The
        DMR IPv6 prefix length SHOULD be 64 bits long by default and in any case MUST NOT exceed 96 bits.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_mapdmr <args>

    '''

    result = {}

    payload = {'mapdmr': {}}

    if name:
        payload['mapdmr']['name'] = name

    if bripv6prefix:
        payload['mapdmr']['bripv6prefix'] = bripv6prefix

    execution = __proxy__['citrixns.post']('config/mapdmr', payload)

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


def add_mapdomain(name=None, mapdmrname=None, save=False):
    '''
    Add a new mapdomain to the running configuration.

    name(str): Name for the MAP Domain. Must begin with an ASCII alphanumeric or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after the MAP Domain is created . The following requirement applies only to the
        NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for
        example, "add network MapDomain map1"). Minimum length = 1 Maximum length = 127

    mapdmrname(str): Default Mapping rule name.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_mapdomain <args>

    '''

    result = {}

    payload = {'mapdomain': {}}

    if name:
        payload['mapdomain']['name'] = name

    if mapdmrname:
        payload['mapdomain']['mapdmrname'] = mapdmrname

    execution = __proxy__['citrixns.post']('config/mapdomain', payload)

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


def add_mapdomain_mapbmr_binding(mapbmrname=None, name=None, save=False):
    '''
    Add a new mapdomain_mapbmr_binding to the running configuration.

    mapbmrname(str): Basic Mapping rule name.

    name(str): Name for the MAP Domain. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_mapdomain_mapbmr_binding <args>

    '''

    result = {}

    payload = {'mapdomain_mapbmr_binding': {}}

    if mapbmrname:
        payload['mapdomain_mapbmr_binding']['mapbmrname'] = mapbmrname

    if name:
        payload['mapdomain_mapbmr_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/mapdomain_mapbmr_binding', payload)

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


def add_nat64(name=None, acl6name=None, netprofile=None, save=False):
    '''
    Add a new nat64 to the running configuration.

    name(str): Name for the NAT64 rule. Must begin with a letter, number, or the underscore character (_), and can consist of
        letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the rule is created. Choose a name that helps identify the NAT64
        rule. Minimum length = 1

    acl6name(str): Name of any configured ACL6 whose action is ALLOW. IPv6 Packets matching the condition of this ACL6 rule
        and destination IP address of these packets matching the NAT64 IPv6 prefix are considered for NAT64 translation.
        Minimum length = 1

    netprofile(str): Name of the configured netprofile. The NetScaler appliance selects one of the IP address in the
        netprofile as the source IP address of the translated IPv4 packet to be sent to the IPv4 server. Minimum length =
        1 Maximum length = 127

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_nat64 <args>

    '''

    result = {}

    payload = {'nat64': {}}

    if name:
        payload['nat64']['name'] = name

    if acl6name:
        payload['nat64']['acl6name'] = acl6name

    if netprofile:
        payload['nat64']['netprofile'] = netprofile

    execution = __proxy__['citrixns.post']('config/nat64', payload)

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


def add_nd6(neighbor=None, mac=None, ifnum=None, vlan=None, vxlan=None, vtep=None, td=None, nodeid=None, save=False):
    '''
    Add a new nd6 to the running configuration.

    neighbor(str): Link-local IPv6 address of the adjacent network device to add to the ND6 table.

    mac(str): MAC address of the adjacent network device.

    ifnum(str): Interface through which the adjacent network device is available, specified in slot/port notation (for
        example, 1/3). Use spaces to separate multiple entries.

    vlan(int): Integer value that uniquely identifies the VLAN on which the adjacent network device exists. Minimum value = 1
        Maximum value = 4094

    vxlan(int): ID of the VXLAN on which the IPv6 address of this ND6 entry is reachable. Minimum value = 1 Maximum value =
        16777215

    vtep(str): IP address of the VXLAN tunnel endpoint (VTEP) through which the IPv6 address of this ND6 entry is reachable.
        Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_nd6 <args>

    '''

    result = {}

    payload = {'nd6': {}}

    if neighbor:
        payload['nd6']['neighbor'] = neighbor

    if mac:
        payload['nd6']['mac'] = mac

    if ifnum:
        payload['nd6']['ifnum'] = ifnum

    if vlan:
        payload['nd6']['vlan'] = vlan

    if vxlan:
        payload['nd6']['vxlan'] = vxlan

    if vtep:
        payload['nd6']['vtep'] = vtep

    if td:
        payload['nd6']['td'] = td

    if nodeid:
        payload['nd6']['nodeid'] = nodeid

    execution = __proxy__['citrixns.post']('config/nd6', payload)

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


def add_nd6ravariables_onlinkipv6prefix_binding(ipv6prefix=None, vlan=None, save=False):
    '''
    Add a new nd6ravariables_onlinkipv6prefix_binding to the running configuration.

    ipv6prefix(str): Onlink prefixes for RA messages.

    vlan(int): The VLAN number. Minimum value = 1 Maximum value = 4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_nd6ravariables_onlinkipv6prefix_binding <args>

    '''

    result = {}

    payload = {'nd6ravariables_onlinkipv6prefix_binding': {}}

    if ipv6prefix:
        payload['nd6ravariables_onlinkipv6prefix_binding']['ipv6prefix'] = ipv6prefix

    if vlan:
        payload['nd6ravariables_onlinkipv6prefix_binding']['vlan'] = vlan

    execution = __proxy__['citrixns.post']('config/nd6ravariables_onlinkipv6prefix_binding', payload)

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


def add_netbridge(name=None, vxlanvlanmap=None, save=False):
    '''
    Add a new netbridge to the running configuration.

    name(str): The name of the network bridge.

    vxlanvlanmap(str): The vlan to vxlan mapping to be applied to this netbridge.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_netbridge <args>

    '''

    result = {}

    payload = {'netbridge': {}}

    if name:
        payload['netbridge']['name'] = name

    if vxlanvlanmap:
        payload['netbridge']['vxlanvlanmap'] = vxlanvlanmap

    execution = __proxy__['citrixns.post']('config/netbridge', payload)

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


def add_netbridge_iptunnel_binding(name=None, tunnel=None, save=False):
    '''
    Add a new netbridge_iptunnel_binding to the running configuration.

    name(str): The name of the network bridge.

    tunnel(str): The name of the tunnel that is a part of this bridge.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_netbridge_iptunnel_binding <args>

    '''

    result = {}

    payload = {'netbridge_iptunnel_binding': {}}

    if name:
        payload['netbridge_iptunnel_binding']['name'] = name

    if tunnel:
        payload['netbridge_iptunnel_binding']['tunnel'] = tunnel

    execution = __proxy__['citrixns.post']('config/netbridge_iptunnel_binding', payload)

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


def add_netbridge_nsip6_binding(name=None, netmask=None, ipaddress=None, save=False):
    '''
    Add a new netbridge_nsip6_binding to the running configuration.

    name(str): The name of the network bridge.

    netmask(str): The network mask for the subnet.

    ipaddress(str): The subnet that is extended by this network bridge. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_netbridge_nsip6_binding <args>

    '''

    result = {}

    payload = {'netbridge_nsip6_binding': {}}

    if name:
        payload['netbridge_nsip6_binding']['name'] = name

    if netmask:
        payload['netbridge_nsip6_binding']['netmask'] = netmask

    if ipaddress:
        payload['netbridge_nsip6_binding']['ipaddress'] = ipaddress

    execution = __proxy__['citrixns.post']('config/netbridge_nsip6_binding', payload)

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


def add_netbridge_nsip_binding(name=None, netmask=None, ipaddress=None, save=False):
    '''
    Add a new netbridge_nsip_binding to the running configuration.

    name(str): The name of the network bridge.

    netmask(str): The network mask for the subnet.

    ipaddress(str): The subnet that is extended by this network bridge. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_netbridge_nsip_binding <args>

    '''

    result = {}

    payload = {'netbridge_nsip_binding': {}}

    if name:
        payload['netbridge_nsip_binding']['name'] = name

    if netmask:
        payload['netbridge_nsip_binding']['netmask'] = netmask

    if ipaddress:
        payload['netbridge_nsip_binding']['ipaddress'] = ipaddress

    execution = __proxy__['citrixns.post']('config/netbridge_nsip_binding', payload)

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


def add_netbridge_vlan_binding(name=None, vlan=None, save=False):
    '''
    Add a new netbridge_vlan_binding to the running configuration.

    name(str): The name of the network bridge.

    vlan(int): The VLAN that is extended by this network bridge. Minimum value = 1 Maximum value = 4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_netbridge_vlan_binding <args>

    '''

    result = {}

    payload = {'netbridge_vlan_binding': {}}

    if name:
        payload['netbridge_vlan_binding']['name'] = name

    if vlan:
        payload['netbridge_vlan_binding']['vlan'] = vlan

    execution = __proxy__['citrixns.post']('config/netbridge_vlan_binding', payload)

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


def add_netprofile(name=None, td=None, srcip=None, srcippersistency=None, overridelsn=None, save=False):
    '''
    Add a new netprofile to the running configuration.

    name(str): Name for the net profile. Must begin with a letter, number, or the underscore character (_), and can consist
        of letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the profile is created. Choose a name that helps identify the net
        profile. Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    srcip(str): IP address or the name of an IP set.

    srcippersistency(str): When the net profile is associated with a virtual server or its bound services, this option
        enables the NetScaler appliance to use the same address, specified in the net profile, to communicate to servers
        for all sessions initiated from a particular client to the virtual server. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    overridelsn(str): USNIP/USIP settings override LSN settings for configured  service/virtual server traffic.. . Default
        value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_netprofile <args>

    '''

    result = {}

    payload = {'netprofile': {}}

    if name:
        payload['netprofile']['name'] = name

    if td:
        payload['netprofile']['td'] = td

    if srcip:
        payload['netprofile']['srcip'] = srcip

    if srcippersistency:
        payload['netprofile']['srcippersistency'] = srcippersistency

    if overridelsn:
        payload['netprofile']['overridelsn'] = overridelsn

    execution = __proxy__['citrixns.post']('config/netprofile', payload)

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


def add_netprofile_natrule_binding(rewriteip=None, name=None, netmask=None, natrule=None, save=False):
    '''
    Add a new netprofile_natrule_binding to the running configuration.

    rewriteip(str): .

    name(str): Name of the netprofile to which to bind port ranges. Minimum length = 1

    netmask(str): .

    natrule(str): IPv4 network address on whose traffic you want the NetScaler appliance to do rewrite ip prefix.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_netprofile_natrule_binding <args>

    '''

    result = {}

    payload = {'netprofile_natrule_binding': {}}

    if rewriteip:
        payload['netprofile_natrule_binding']['rewriteip'] = rewriteip

    if name:
        payload['netprofile_natrule_binding']['name'] = name

    if netmask:
        payload['netprofile_natrule_binding']['netmask'] = netmask

    if natrule:
        payload['netprofile_natrule_binding']['natrule'] = natrule

    execution = __proxy__['citrixns.post']('config/netprofile_natrule_binding', payload)

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


def add_netprofile_srcportset_binding(srcportrange=None, name=None, save=False):
    '''
    Add a new netprofile_srcportset_binding to the running configuration.

    srcportrange(str): When the source port range is configured and associated with the netprofile bound to a service group,
        Netscaler will choose a port from the range configured for connection establishment at the backend servers.
        Minimum length = 1024 Maximum length = 65535

    name(str): Name of the netprofile to which to bind port ranges. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_netprofile_srcportset_binding <args>

    '''

    result = {}

    payload = {'netprofile_srcportset_binding': {}}

    if srcportrange:
        payload['netprofile_srcportset_binding']['srcportrange'] = srcportrange

    if name:
        payload['netprofile_srcportset_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/netprofile_srcportset_binding', payload)

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


def add_onlinkipv6prefix(ipv6prefix=None, onlinkprefix=None, autonomusprefix=None, depricateprefix=None,
                         decrementprefixlifetimes=None, prefixvalidelifetime=None, prefixpreferredlifetime=None,
                         save=False):
    '''
    Add a new onlinkipv6prefix to the running configuration.

    ipv6prefix(str): Onlink prefixes for RA messages.

    onlinkprefix(str): RA Prefix onlink flag. Default value: YES Possible values = YES, NO

    autonomusprefix(str): RA Prefix Autonomus flag. Default value: YES Possible values = YES, NO

    depricateprefix(str): Depricate the prefix. Default value: NO Possible values = YES, NO

    decrementprefixlifetimes(str): RA Prefix Autonomus flag. Default value: NO Possible values = YES, NO

    prefixvalidelifetime(int): Valide life time of the prefix, in seconds. Default value: 2592000

    prefixpreferredlifetime(int): Preferred life time of the prefix, in seconds. Default value: 604800

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_onlinkipv6prefix <args>

    '''

    result = {}

    payload = {'onlinkipv6prefix': {}}

    if ipv6prefix:
        payload['onlinkipv6prefix']['ipv6prefix'] = ipv6prefix

    if onlinkprefix:
        payload['onlinkipv6prefix']['onlinkprefix'] = onlinkprefix

    if autonomusprefix:
        payload['onlinkipv6prefix']['autonomusprefix'] = autonomusprefix

    if depricateprefix:
        payload['onlinkipv6prefix']['depricateprefix'] = depricateprefix

    if decrementprefixlifetimes:
        payload['onlinkipv6prefix']['decrementprefixlifetimes'] = decrementprefixlifetimes

    if prefixvalidelifetime:
        payload['onlinkipv6prefix']['prefixvalidelifetime'] = prefixvalidelifetime

    if prefixpreferredlifetime:
        payload['onlinkipv6prefix']['prefixpreferredlifetime'] = prefixpreferredlifetime

    execution = __proxy__['citrixns.post']('config/onlinkipv6prefix', payload)

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


def add_rnat6(name=None, network=None, acl6name=None, redirectport=None, td=None, srcippersistency=None, ownergroup=None,
              save=False):
    '''
    Add a new rnat6 to the running configuration.

    name(str): Name for the RNAT6 rule. Must begin with a letter, number, or the underscore character (_), and can consist of
        letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the rule is created. Choose a name that helps identify the RNAT6
        rule. Minimum length = 1

    network(str): IPv6 address of the network on whose traffic you want the NetScaler appliance to do RNAT processing.
        Minimum length = 1

    acl6name(str): Name of any configured ACL6 whose action is ALLOW. The rule of the ACL6 is used as an RNAT6 rule. Minimum
        length = 1

    redirectport(int): Port number to which the IPv6 packets are redirected. Applicable to TCP and UDP protocols. Minimum
        value = 1 Maximum value = 65535

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    srcippersistency(str): Enable source ip persistency, which enables the NetScaler appliance to use the RNAT ips using
        source ip. Default value: DISABLED Possible values = ENABLED, DISABLED

    ownergroup(str): The owner node group in a Cluster for this rnat rule. Default value: DEFAULT_NG Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_rnat6 <args>

    '''

    result = {}

    payload = {'rnat6': {}}

    if name:
        payload['rnat6']['name'] = name

    if network:
        payload['rnat6']['network'] = network

    if acl6name:
        payload['rnat6']['acl6name'] = acl6name

    if redirectport:
        payload['rnat6']['redirectport'] = redirectport

    if td:
        payload['rnat6']['td'] = td

    if srcippersistency:
        payload['rnat6']['srcippersistency'] = srcippersistency

    if ownergroup:
        payload['rnat6']['ownergroup'] = ownergroup

    execution = __proxy__['citrixns.post']('config/rnat6', payload)

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


def add_rnat6_nsip6_binding(natip6=None, name=None, ownergroup=None, save=False):
    '''
    Add a new rnat6_nsip6_binding to the running configuration.

    natip6(str): Nat IP Address. Minimum length = 1

    name(str): Name of the RNAT6 rule to which to bind NAT IPs. Minimum length = 1

    ownergroup(str): The owner node group in a Cluster for this rnat rule. Default value: DEFAULT_NG Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_rnat6_nsip6_binding <args>

    '''

    result = {}

    payload = {'rnat6_nsip6_binding': {}}

    if natip6:
        payload['rnat6_nsip6_binding']['natip6'] = natip6

    if name:
        payload['rnat6_nsip6_binding']['name'] = name

    if ownergroup:
        payload['rnat6_nsip6_binding']['ownergroup'] = ownergroup

    execution = __proxy__['citrixns.post']('config/rnat6_nsip6_binding', payload)

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


def add_rnatglobal_auditsyslogpolicy_binding(priority=None, policy=None, save=False):
    '''
    Add a new rnatglobal_auditsyslogpolicy_binding to the running configuration.

    priority(int): The priority of the policy.

    policy(str): The policy Name.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_rnatglobal_auditsyslogpolicy_binding <args>

    '''

    result = {}

    payload = {'rnatglobal_auditsyslogpolicy_binding': {}}

    if priority:
        payload['rnatglobal_auditsyslogpolicy_binding']['priority'] = priority

    if policy:
        payload['rnatglobal_auditsyslogpolicy_binding']['policy'] = policy

    execution = __proxy__['citrixns.post']('config/rnatglobal_auditsyslogpolicy_binding', payload)

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


def add_route(network=None, netmask=None, gateway=None, cost=None, td=None, distance=None, cost1=None, weight=None,
              advertise=None, protocol=None, msr=None, monitor=None, ownergroup=None, routetype=None, detail=None,
              save=False):
    '''
    Add a new route to the running configuration.

    network(str): IPv4 network address for which to add a route entry in the routing table of the NetScaler appliance.

    netmask(str): The subnet mask associated with the network address.

    gateway(str): IP address of the gateway for this route. Can be either the IP address of the gateway, or can be null to
        specify a null interface route. Minimum length = 1

    cost(int): Positive integer used by the routing algorithms to determine preference for using this route. The lower the
        cost, the higher the preference. Minimum value = 0 Maximum value = 65535

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    distance(int): Administrative distance of this route, which determines the preference of this route over other routes,
        with same destination, from different routing protocols. A lower value is preferred. Default value: 1 Minimum
        value = 0 Maximum value = 255

    cost1(int): The cost of a route is used to compare routes of the same type. The route having the lowest cost is the most
        preferred route. Possible values: 0 through 65535. Default: 0. Minimum value = 0 Maximum value = 65535

    weight(int): Positive integer used by the routing algorithms to determine preference for this route over others of equal
        cost. The lower the weight, the higher the preference. Default value: 1 Minimum value = 1 Maximum value = 65535

    advertise(str): Advertise this route. Possible values = DISABLED, ENABLED

    protocol(list(str)): Routing protocol used for advertising this route. Default value: ADV_ROUTE_FLAGS Possible values =
        OSPF, ISIS, RIP, BGP

    msr(str): Monitor this route using a monitor of type ARP or PING. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    monitor(str): Name of the monitor, of type ARP or PING, configured on the NetScaler appliance to monitor this route.
        Minimum length = 1

    ownergroup(str): The owner node group in a Cluster for this route. If owner node group is not specified then the route is
        treated as Striped route. Default value: DEFAULT_NG Minimum length = 1

    routetype(str): Protocol used by routes that you want to remove from the routing table of the NetScaler appliance.
        Possible values = CONNECTED, STATIC, DYNAMIC, OSPF, ISIS, RIP, BGP

    detail(bool): Display a detailed view.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_route <args>

    '''

    result = {}

    payload = {'route': {}}

    if network:
        payload['route']['network'] = network

    if netmask:
        payload['route']['netmask'] = netmask

    if gateway:
        payload['route']['gateway'] = gateway

    if cost:
        payload['route']['cost'] = cost

    if td:
        payload['route']['td'] = td

    if distance:
        payload['route']['distance'] = distance

    if cost1:
        payload['route']['cost1'] = cost1

    if weight:
        payload['route']['weight'] = weight

    if advertise:
        payload['route']['advertise'] = advertise

    if protocol:
        payload['route']['protocol'] = protocol

    if msr:
        payload['route']['msr'] = msr

    if monitor:
        payload['route']['monitor'] = monitor

    if ownergroup:
        payload['route']['ownergroup'] = ownergroup

    if routetype:
        payload['route']['routetype'] = routetype

    if detail:
        payload['route']['detail'] = detail

    execution = __proxy__['citrixns.post']('config/route', payload)

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


def add_route6(network=None, gateway=None, vlan=None, vxlan=None, weight=None, distance=None, cost=None, advertise=None,
               msr=None, monitor=None, td=None, ownergroup=None, routetype=None, detail=None, save=False):
    '''
    Add a new route6 to the running configuration.

    network(str): IPv6 network address for which to add a route entry to the routing table of the NetScaler appliance.

    gateway(str): The gateway for this route. The value for this parameter is either an IPv6 address or null. Default value:
        0

    vlan(int): Integer value that uniquely identifies a VLAN through which the NetScaler appliance forwards the packets for
        this route. Default value: 0 Minimum value = 0 Maximum value = 4094

    vxlan(int): Integer value that uniquely identifies a VXLAN through which the NetScaler appliance forwards the packets for
        this route. Minimum value = 1 Maximum value = 16777215

    weight(int): Positive integer used by the routing algorithms to determine preference for this route over others of equal
        cost. The lower the weight, the higher the preference. Default value: 1 Minimum value = 1 Maximum value = 65535

    distance(int): Administrative distance of this route from the appliance. Default value: 1 Minimum value = 1 Maximum value
        = 254

    cost(int): Positive integer used by the routing algorithms to determine preference for this route. The lower the cost,
        the higher the preference. Default value: 1 Minimum value = 0 Maximum value = 65535

    advertise(str): Advertise this route. Possible values = DISABLED, ENABLED

    msr(str): Monitor this route with a monitor of type ND6 or PING. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    monitor(str): Name of the monitor, of type ND6 or PING, configured on the NetScaler appliance to monitor this route.
        Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    ownergroup(str): The owner node group in a Cluster for this route6. If owner node group is not specified then the route
        is treated as Striped route. Default value: DEFAULT_NG Minimum length = 1

    routetype(str): Type of IPv6 routes to remove from the routing table of the NetScaler appliance. Possible values =
        CONNECTED, STATIC, DYNAMIC, OSPF, ISIS, BGP, RIP, ND-RA-ROUTE, FIB6

    detail(bool): To get a detailed view.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_route6 <args>

    '''

    result = {}

    payload = {'route6': {}}

    if network:
        payload['route6']['network'] = network

    if gateway:
        payload['route6']['gateway'] = gateway

    if vlan:
        payload['route6']['vlan'] = vlan

    if vxlan:
        payload['route6']['vxlan'] = vxlan

    if weight:
        payload['route6']['weight'] = weight

    if distance:
        payload['route6']['distance'] = distance

    if cost:
        payload['route6']['cost'] = cost

    if advertise:
        payload['route6']['advertise'] = advertise

    if msr:
        payload['route6']['msr'] = msr

    if monitor:
        payload['route6']['monitor'] = monitor

    if td:
        payload['route6']['td'] = td

    if ownergroup:
        payload['route6']['ownergroup'] = ownergroup

    if routetype:
        payload['route6']['routetype'] = routetype

    if detail:
        payload['route6']['detail'] = detail

    execution = __proxy__['citrixns.post']('config/route6', payload)

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


def add_vlan(id=None, aliasname=None, dynamicrouting=None, ipv6dynamicrouting=None, mtu=None, sharing=None, save=False):
    '''
    Add a new vlan to the running configuration.

    id(int): A positive integer that uniquely identifies a VLAN. Minimum value = 1 Maximum value = 4094

    aliasname(str): A name for the VLAN. Must begin with a letter, a number, or the underscore symbol, and can consist of
        from 1 to 31 letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=),
        colon (:), and underscore (_) characters. You should choose a name that helps identify the VLAN. However, you
        cannot perform any VLAN operation by specifying this name instead of the VLAN ID. Maximum length = 31

    dynamicrouting(str): Enable dynamic routing on this VLAN. Default value: DISABLED Possible values = ENABLED, DISABLED

    ipv6dynamicrouting(str): Enable all IPv6 dynamic routing protocols on this VLAN. Note: For the ENABLED setting to work,
        you must configure IPv6 dynamic routing protocols from the VTYSH command line. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    mtu(int): Specifies the maximum transmission unit (MTU), in bytes. The MTU is the largest packet size, excluding 14 bytes
        of ethernet header and 4 bytes of crc, that can be transmitted and received over this VLAN. Default value: 0
        Minimum value = 500 Maximum value = 9216

    sharing(str): If sharing is enabled, then this vlan can be shared across multiple partitions by binding it to all those
        partitions. If sharing is disabled, then this vlan can be bound to only one of the partitions. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vlan <args>

    '''

    result = {}

    payload = {'vlan': {}}

    if id:
        payload['vlan']['id'] = id

    if aliasname:
        payload['vlan']['aliasname'] = aliasname

    if dynamicrouting:
        payload['vlan']['dynamicrouting'] = dynamicrouting

    if ipv6dynamicrouting:
        payload['vlan']['ipv6dynamicrouting'] = ipv6dynamicrouting

    if mtu:
        payload['vlan']['mtu'] = mtu

    if sharing:
        payload['vlan']['sharing'] = sharing

    execution = __proxy__['citrixns.post']('config/vlan', payload)

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


def add_vlan_channel_binding(ownergroup=None, id=None, ifnum=None, tagged=None, save=False):
    '''
    Add a new vlan_channel_binding to the running configuration.

    ownergroup(str): The owner node group in a Cluster for this vlan. Default value: DEFAULT_NG Minimum length = 1

    id(int): Specifies the virtual LAN ID. Minimum value = 1 Maximum value = 4094

    ifnum(str): The interface to be bound to the VLAN, specified in slot/port notation (for example, 1/3). Minimum length =
        1

    tagged(bool): Make the interface an 802.1q tagged interface. Packets sent on this interface on this VLAN have an
        additional 4-byte 802.1q tag, which identifies the VLAN. To use 802.1q tagging, you must also configure the
        switch connected to the appliances interfaces.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vlan_channel_binding <args>

    '''

    result = {}

    payload = {'vlan_channel_binding': {}}

    if ownergroup:
        payload['vlan_channel_binding']['ownergroup'] = ownergroup

    if id:
        payload['vlan_channel_binding']['id'] = id

    if ifnum:
        payload['vlan_channel_binding']['ifnum'] = ifnum

    if tagged:
        payload['vlan_channel_binding']['tagged'] = tagged

    execution = __proxy__['citrixns.post']('config/vlan_channel_binding', payload)

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


def add_vlan_interface_binding(ownergroup=None, id=None, ifnum=None, tagged=None, save=False):
    '''
    Add a new vlan_interface_binding to the running configuration.

    ownergroup(str): The owner node group in a Cluster for this vlan. Default value: DEFAULT_NG Minimum length = 1

    id(int): Specifies the virtual LAN ID. Minimum value = 1 Maximum value = 4094

    ifnum(str): The interface to be bound to the VLAN, specified in slot/port notation (for example, 1/3). Minimum length =
        1

    tagged(bool): Make the interface an 802.1q tagged interface. Packets sent on this interface on this VLAN have an
        additional 4-byte 802.1q tag, which identifies the VLAN. To use 802.1q tagging, you must also configure the
        switch connected to the appliances interfaces.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vlan_interface_binding <args>

    '''

    result = {}

    payload = {'vlan_interface_binding': {}}

    if ownergroup:
        payload['vlan_interface_binding']['ownergroup'] = ownergroup

    if id:
        payload['vlan_interface_binding']['id'] = id

    if ifnum:
        payload['vlan_interface_binding']['ifnum'] = ifnum

    if tagged:
        payload['vlan_interface_binding']['tagged'] = tagged

    execution = __proxy__['citrixns.post']('config/vlan_interface_binding', payload)

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


def add_vlan_linkset_binding(ownergroup=None, id=None, ifnum=None, tagged=None, save=False):
    '''
    Add a new vlan_linkset_binding to the running configuration.

    ownergroup(str): The owner node group in a Cluster for this vlan. Default value: DEFAULT_NG Minimum length = 1

    id(int): Specifies the virtual LAN ID. Minimum value = 1 Maximum value = 4094

    ifnum(str): The interface to be bound to the VLAN, specified in slot/port notation (for example, 1/3). Minimum length =
        1

    tagged(bool): Make the interface an 802.1q tagged interface. Packets sent on this interface on this VLAN have an
        additional 4-byte 802.1q tag, which identifies the VLAN. To use 802.1q tagging, you must also configure the
        switch connected to the appliances interfaces.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vlan_linkset_binding <args>

    '''

    result = {}

    payload = {'vlan_linkset_binding': {}}

    if ownergroup:
        payload['vlan_linkset_binding']['ownergroup'] = ownergroup

    if id:
        payload['vlan_linkset_binding']['id'] = id

    if ifnum:
        payload['vlan_linkset_binding']['ifnum'] = ifnum

    if tagged:
        payload['vlan_linkset_binding']['tagged'] = tagged

    execution = __proxy__['citrixns.post']('config/vlan_linkset_binding', payload)

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


def add_vlan_nsip6_binding(ownergroup=None, id=None, td=None, netmask=None, ipaddress=None, save=False):
    '''
    Add a new vlan_nsip6_binding to the running configuration.

    ownergroup(str): The owner node group in a Cluster for this vlan. Default value: DEFAULT_NG Minimum length = 1

    id(int): Specifies the virtual LAN ID. Minimum value = 1 Maximum value = 4094

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    netmask(str): Subnet mask for the network address defined for this VLAN. Minimum length = 1

    ipaddress(str): The IP address assigned to the VLAN.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vlan_nsip6_binding <args>

    '''

    result = {}

    payload = {'vlan_nsip6_binding': {}}

    if ownergroup:
        payload['vlan_nsip6_binding']['ownergroup'] = ownergroup

    if id:
        payload['vlan_nsip6_binding']['id'] = id

    if td:
        payload['vlan_nsip6_binding']['td'] = td

    if netmask:
        payload['vlan_nsip6_binding']['netmask'] = netmask

    if ipaddress:
        payload['vlan_nsip6_binding']['ipaddress'] = ipaddress

    execution = __proxy__['citrixns.post']('config/vlan_nsip6_binding', payload)

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


def add_vlan_nsip_binding(ownergroup=None, id=None, td=None, netmask=None, ipaddress=None, save=False):
    '''
    Add a new vlan_nsip_binding to the running configuration.

    ownergroup(str): The owner node group in a Cluster for this vlan. Default value: DEFAULT_NG Minimum length = 1

    id(int): Specifies the virtual LAN ID. Minimum value = 1 Maximum value = 4094

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    netmask(str): Subnet mask for the network address defined for this VLAN.

    ipaddress(str): The IP address assigned to the VLAN.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vlan_nsip_binding <args>

    '''

    result = {}

    payload = {'vlan_nsip_binding': {}}

    if ownergroup:
        payload['vlan_nsip_binding']['ownergroup'] = ownergroup

    if id:
        payload['vlan_nsip_binding']['id'] = id

    if td:
        payload['vlan_nsip_binding']['td'] = td

    if netmask:
        payload['vlan_nsip_binding']['netmask'] = netmask

    if ipaddress:
        payload['vlan_nsip_binding']['ipaddress'] = ipaddress

    execution = __proxy__['citrixns.post']('config/vlan_nsip_binding', payload)

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


def add_vrid(id=None, priority=None, preemption=None, sharing=None, tracking=None, ownernode=None,
             trackifnumpriority=None, preemptiondelaytimer=None, save=False):
    '''
    Add a new vrid to the running configuration.

    id(int): Integer that uniquely identifies the VMAC address. The generic VMAC address is in the form of
        00:00:5e:00:01:;lt;VRID;gt;. For example, if you add a VRID with a value of 60 and bind it to an interface, the
        resulting VMAC address is 00:00:5e:00:01:3c, where 3c is the hexadecimal representation of 60. Minimum value = 1
        Maximum value = 255

    priority(int): Base priority (BP), in an active-active mode configuration, which ordinarily determines the master VIP
        address. Default value: 255 Minimum value = 0 Maximum value = 255

    preemption(str): In an active-active mode configuration, make a backup VIP address the master if its priority becomes
        higher than that of a master VIP address bound to this VMAC address.  If you disable pre-emption while a backup
        VIP address is the master, the backup VIP address remains master until the original master VIPs priority becomes
        higher than that of the current master. Default value: ENABLED Possible values = ENABLED, DISABLED

    sharing(str): In an active-active mode configuration, enable the backup VIP address to process any traffic instead of
        dropping it. Default value: DISABLED Possible values = ENABLED, DISABLED

    tracking(str): The effective priority (EP) value, relative to the base priority (BP) value in an active-active mode
        configuration. When EP is set to a value other than None, it is EP, not BP, which determines the master VIP
        address. Available settings function as follows: * NONE - No tracking. EP = BP * ALL - If the status of all
        virtual servers is UP, EP = BP. Otherwise, EP = 0. * ONE - If the status of at least one virtual server is UP, EP
        = BP. Otherwise, EP = 0. * PROGRESSIVE - If the status of all virtual servers is UP, EP = BP. If the status of
        all virtual servers is DOWN, EP = 0. Otherwise EP = BP (1 - K/N), where N is the total number of virtual servers
        associated with the VIP address and K is the number of virtual servers for which the status is DOWN. Default:
        NONE. Default value: NONE Possible values = NONE, ONE, ALL, PROGRESSIVE

    ownernode(int): In a cluster setup, assign a cluster node as the owner of this VMAC address for IP based VRRP
        configuration. If no owner is configured, owner node is displayed as ALL and one node is dynamically elected as
        the owner. Minimum value = 0 Maximum value = 31

    trackifnumpriority(int): Priority by which the Effective priority will be reduced if any of the tracked interfaces goes
        down in an active-active configuration. Default value: 0 Minimum value = 1 Maximum value = 255

    preemptiondelaytimer(int): Preemption delay time, in seconds, in an active-active configuration. If any high priority
        node will come in network, it will wait for these many seconds before becoming master. Default value: 0 Minimum
        value = 1 Maximum value = 36000

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vrid <args>

    '''

    result = {}

    payload = {'vrid': {}}

    if id:
        payload['vrid']['id'] = id

    if priority:
        payload['vrid']['priority'] = priority

    if preemption:
        payload['vrid']['preemption'] = preemption

    if sharing:
        payload['vrid']['sharing'] = sharing

    if tracking:
        payload['vrid']['tracking'] = tracking

    if ownernode:
        payload['vrid']['ownernode'] = ownernode

    if trackifnumpriority:
        payload['vrid']['trackifnumpriority'] = trackifnumpriority

    if preemptiondelaytimer:
        payload['vrid']['preemptiondelaytimer'] = preemptiondelaytimer

    execution = __proxy__['citrixns.post']('config/vrid', payload)

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


def add_vrid6(id=None, priority=None, preemption=None, sharing=None, tracking=None, preemptiondelaytimer=None,
              trackifnumpriority=None, ownernode=None, save=False):
    '''
    Add a new vrid6 to the running configuration.

    id(int): Integer value that uniquely identifies a VMAC6 address. Minimum value = 1 Maximum value = 255

    priority(int): Base priority (BP), in an active-active mode configuration, which ordinarily determines the master VIP
        address. Default value: 255 Minimum value = 0 Maximum value = 255

    preemption(str): In an active-active mode configuration, make a backup VIP address the master if its priority becomes
        higher than that of a master VIP address bound to this VMAC address.  If you disable pre-emption while a backup
        VIP address is the master, the backup VIP address remains master until the original master VIPs priority becomes
        higher than that of the current master. Default value: ENABLED Possible values = ENABLED, DISABLED

    sharing(str): In an active-active mode configuration, enable the backup VIP address to process any traffic instead of
        dropping it. Default value: DISABLED Possible values = ENABLED, DISABLED

    tracking(str): The effective priority (EP) value, relative to the base priority (BP) value in an active-active mode
        configuration. When EP is set to a value other than None, it is EP, not BP, which determines the master VIP
        address. Available settings function as follows: * NONE - No tracking. EP = BP * ALL - If the status of all
        virtual servers is UP, EP = BP. Otherwise, EP = 0. * ONE - If the status of at least one virtual server is UP, EP
        = BP. Otherwise, EP = 0. * PROGRESSIVE - If the status of all virtual servers is UP, EP = BP. If the status of
        all virtual servers is DOWN, EP = 0. Otherwise EP = BP (1 - K/N), where N is the total number of virtual servers
        associated with the VIP address and K is the number of virtual servers for which the status is DOWN. Default:
        NONE. Default value: NONE Possible values = NONE, ONE, ALL, PROGRESSIVE

    preemptiondelaytimer(int): Preemption delay time in seconds, in an active-active configuration. If any high priority node
        will come in network, it will wait for these many seconds before becoming master. Default value: 0 Minimum value
        = 1 Maximum value = 36000

    trackifnumpriority(int): Priority by which the Effective priority will be reduced if any of the tracked interfaces goes
        down in an active-active configuration. Default value: 0 Minimum value = 1 Maximum value = 255

    ownernode(int): In a cluster setup, assign a cluster node as the owner of this VMAC address for IP based VRRP
        configuration. If no owner is configured, ow ner node is displayed as ALL and one node is dynamically elected as
        the owner. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vrid6 <args>

    '''

    result = {}

    payload = {'vrid6': {}}

    if id:
        payload['vrid6']['id'] = id

    if priority:
        payload['vrid6']['priority'] = priority

    if preemption:
        payload['vrid6']['preemption'] = preemption

    if sharing:
        payload['vrid6']['sharing'] = sharing

    if tracking:
        payload['vrid6']['tracking'] = tracking

    if preemptiondelaytimer:
        payload['vrid6']['preemptiondelaytimer'] = preemptiondelaytimer

    if trackifnumpriority:
        payload['vrid6']['trackifnumpriority'] = trackifnumpriority

    if ownernode:
        payload['vrid6']['ownernode'] = ownernode

    execution = __proxy__['citrixns.post']('config/vrid6', payload)

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


def add_vrid6_channel_binding(id=None, ifnum=None, save=False):
    '''
    Add a new vrid6_channel_binding to the running configuration.

    id(int): Integer value that uniquely identifies a VMAC6 address. Minimum value = 1 Maximum value = 255

    ifnum(str): Interfaces to bind to the VMAC6, specified in (slot/port) notation (for example, 1/2).Use spaces to separate
        multiple entries.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vrid6_channel_binding <args>

    '''

    result = {}

    payload = {'vrid6_channel_binding': {}}

    if id:
        payload['vrid6_channel_binding']['id'] = id

    if ifnum:
        payload['vrid6_channel_binding']['ifnum'] = ifnum

    execution = __proxy__['citrixns.post']('config/vrid6_channel_binding', payload)

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


def add_vrid6_interface_binding(id=None, ifnum=None, save=False):
    '''
    Add a new vrid6_interface_binding to the running configuration.

    id(int): Integer value that uniquely identifies a VMAC6 address. Minimum value = 1 Maximum value = 255

    ifnum(str): Interfaces to bind to the VMAC6, specified in (slot/port) notation (for example, 1/2).Use spaces to separate
        multiple entries.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vrid6_interface_binding <args>

    '''

    result = {}

    payload = {'vrid6_interface_binding': {}}

    if id:
        payload['vrid6_interface_binding']['id'] = id

    if ifnum:
        payload['vrid6_interface_binding']['ifnum'] = ifnum

    execution = __proxy__['citrixns.post']('config/vrid6_interface_binding', payload)

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


def add_vrid6_trackinterface_binding(trackifnum=None, id=None, save=False):
    '''
    Add a new vrid6_trackinterface_binding to the running configuration.

    trackifnum(str): Interfaces which need to be tracked for this vrID.

    id(int): Integer value that uniquely identifies a VMAC6 address. Minimum value = 1 Maximum value = 255

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vrid6_trackinterface_binding <args>

    '''

    result = {}

    payload = {'vrid6_trackinterface_binding': {}}

    if trackifnum:
        payload['vrid6_trackinterface_binding']['trackifnum'] = trackifnum

    if id:
        payload['vrid6_trackinterface_binding']['id'] = id

    execution = __proxy__['citrixns.post']('config/vrid6_trackinterface_binding', payload)

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


def add_vrid_channel_binding(id=None, ifnum=None, save=False):
    '''
    Add a new vrid_channel_binding to the running configuration.

    id(int): Integer that uniquely identifies the VMAC address. The generic VMAC address is in the form of
        00:00:5e:00:01:;lt;VRID;gt;. For example, if you add a VRID with a value of 60 and bind it to an interface, the
        resulting VMAC address is 00:00:5e:00:01:3c, where 3c is the hexadecimal representation of 60. Minimum value = 1
        Maximum value = 255

    ifnum(str): Interfaces to bind to the VMAC, specified in (slot/port) notation (for example, 1/2).Use spaces to separate
        multiple entries.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vrid_channel_binding <args>

    '''

    result = {}

    payload = {'vrid_channel_binding': {}}

    if id:
        payload['vrid_channel_binding']['id'] = id

    if ifnum:
        payload['vrid_channel_binding']['ifnum'] = ifnum

    execution = __proxy__['citrixns.post']('config/vrid_channel_binding', payload)

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


def add_vrid_interface_binding(id=None, ifnum=None, save=False):
    '''
    Add a new vrid_interface_binding to the running configuration.

    id(int): Integer that uniquely identifies the VMAC address. The generic VMAC address is in the form of
        00:00:5e:00:01:;lt;VRID;gt;. For example, if you add a VRID with a value of 60 and bind it to an interface, the
        resulting VMAC address is 00:00:5e:00:01:3c, where 3c is the hexadecimal representation of 60. Minimum value = 1
        Maximum value = 255

    ifnum(str): Interfaces to bind to the VMAC, specified in (slot/port) notation (for example, 1/2).Use spaces to separate
        multiple entries.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vrid_interface_binding <args>

    '''

    result = {}

    payload = {'vrid_interface_binding': {}}

    if id:
        payload['vrid_interface_binding']['id'] = id

    if ifnum:
        payload['vrid_interface_binding']['ifnum'] = ifnum

    execution = __proxy__['citrixns.post']('config/vrid_interface_binding', payload)

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


def add_vrid_trackinterface_binding(id=None, trackifnum=None, save=False):
    '''
    Add a new vrid_trackinterface_binding to the running configuration.

    id(int): Integer that uniquely identifies the VMAC address. The generic VMAC address is in the form of
        00:00:5e:00:01:;lt;VRID;gt;. For example, if you add a VRID with a value of 60 and bind it to an interface, the
        resulting VMAC address is 00:00:5e:00:01:3c, where 3c is the hexadecimal representation of 60. Minimum value = 1
        Maximum value = 255

    trackifnum(str): Interfaces which need to be tracked for this vrID.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vrid_trackinterface_binding <args>

    '''

    result = {}

    payload = {'vrid_trackinterface_binding': {}}

    if id:
        payload['vrid_trackinterface_binding']['id'] = id

    if trackifnum:
        payload['vrid_trackinterface_binding']['trackifnum'] = trackifnum

    execution = __proxy__['citrixns.post']('config/vrid_trackinterface_binding', payload)

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


def add_vxlan(id=None, vlan=None, port=None, dynamicrouting=None, ipv6dynamicrouting=None, ns_type=None, protocol=None,
              innervlantagging=None, save=False):
    '''
    Add a new vxlan to the running configuration.

    id(int): A positive integer, which is also called VXLAN Network Identifier (VNI), that uniquely identifies a VXLAN.
        Minimum value = 1 Maximum value = 16777215

    vlan(int): ID of VLANs whose traffic is allowed over this VXLAN. If you do not specify any VLAN IDs, the NetScaler allows
        traffic of all VLANs that are not part of any other VXLANs. Minimum value = 2 Maximum value = 4094

    port(int): Specifies UDP destination port for VXLAN packets. Default value: 4789 Minimum value = 1 Maximum value = 65534

    dynamicrouting(str): Enable dynamic routing on this VXLAN. Default value: DISABLED Possible values = ENABLED, DISABLED

    ipv6dynamicrouting(str): Enable all IPv6 dynamic routing protocols on this VXLAN. Note: For the ENABLED setting to work,
        you must configure IPv6 dynamic routing protocols from the VTYSH command line. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    ns_type(str): VXLAN encapsulation type. VXLAN, VXLANGPE. Default value: VXLAN Possible values = VXLAN, VXLANGPE

    protocol(str): VXLAN-GPE next protocol. RESERVED, IPv4, IPv6, ETHERNET, NSH. Default value: ETHERNET Possible values =
        IPv4, IPv6, ETHERNET, NSH

    innervlantagging(str): Specifies whether NS should generate VXLAN packets with inner VLAN tag. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vxlan <args>

    '''

    result = {}

    payload = {'vxlan': {}}

    if id:
        payload['vxlan']['id'] = id

    if vlan:
        payload['vxlan']['vlan'] = vlan

    if port:
        payload['vxlan']['port'] = port

    if dynamicrouting:
        payload['vxlan']['dynamicrouting'] = dynamicrouting

    if ipv6dynamicrouting:
        payload['vxlan']['ipv6dynamicrouting'] = ipv6dynamicrouting

    if ns_type:
        payload['vxlan']['type'] = ns_type

    if protocol:
        payload['vxlan']['protocol'] = protocol

    if innervlantagging:
        payload['vxlan']['innervlantagging'] = innervlantagging

    execution = __proxy__['citrixns.post']('config/vxlan', payload)

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


def add_vxlan_nsip6_binding(id=None, netmask=None, ipaddress=None, save=False):
    '''
    Add a new vxlan_nsip6_binding to the running configuration.

    id(int): A positive integer, which is also called VXLAN Network Identifier (VNI), that uniquely identifies a VXLAN.
        Minimum value = 1 Maximum value = 16777215

    netmask(str): Subnet mask for the network address defined for this VXLAN. Minimum length = 1

    ipaddress(str): The IP address assigned to the VXLAN.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vxlan_nsip6_binding <args>

    '''

    result = {}

    payload = {'vxlan_nsip6_binding': {}}

    if id:
        payload['vxlan_nsip6_binding']['id'] = id

    if netmask:
        payload['vxlan_nsip6_binding']['netmask'] = netmask

    if ipaddress:
        payload['vxlan_nsip6_binding']['ipaddress'] = ipaddress

    execution = __proxy__['citrixns.post']('config/vxlan_nsip6_binding', payload)

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


def add_vxlan_nsip_binding(id=None, netmask=None, ipaddress=None, save=False):
    '''
    Add a new vxlan_nsip_binding to the running configuration.

    id(int): A positive integer, which is also called VXLAN Network Identifier (VNI), that uniquely identifies a VXLAN.
        Minimum value = 1 Maximum value = 16777215

    netmask(str): Subnet mask for the network address defined for this VXLAN.

    ipaddress(str): The IP address assigned to the VXLAN.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vxlan_nsip_binding <args>

    '''

    result = {}

    payload = {'vxlan_nsip_binding': {}}

    if id:
        payload['vxlan_nsip_binding']['id'] = id

    if netmask:
        payload['vxlan_nsip_binding']['netmask'] = netmask

    if ipaddress:
        payload['vxlan_nsip_binding']['ipaddress'] = ipaddress

    execution = __proxy__['citrixns.post']('config/vxlan_nsip_binding', payload)

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


def add_vxlan_srcip_binding(id=None, srcip=None, save=False):
    '''
    Add a new vxlan_srcip_binding to the running configuration.

    id(int): A positive integer, which is also called VXLAN Network Identifier (VNI), that uniquely identifies a VXLAN.
        Minimum value = 1 Maximum value = 16777215

    srcip(str): The source IP address to use in outgoing vxlan packets. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vxlan_srcip_binding <args>

    '''

    result = {}

    payload = {'vxlan_srcip_binding': {}}

    if id:
        payload['vxlan_srcip_binding']['id'] = id

    if srcip:
        payload['vxlan_srcip_binding']['srcip'] = srcip

    execution = __proxy__['citrixns.post']('config/vxlan_srcip_binding', payload)

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


def add_vxlanvlanmap(name=None, save=False):
    '''
    Add a new vxlanvlanmap to the running configuration.

    name(str): Name of the mapping table. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vxlanvlanmap <args>

    '''

    result = {}

    payload = {'vxlanvlanmap': {}}

    if name:
        payload['vxlanvlanmap']['name'] = name

    execution = __proxy__['citrixns.post']('config/vxlanvlanmap', payload)

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


def add_vxlanvlanmap_vxlan_binding(name=None, vxlan=None, vlan=None, save=False):
    '''
    Add a new vxlanvlanmap_vxlan_binding to the running configuration.

    name(str): Name of the mapping table. Minimum length = 1

    vxlan(int): The VXLAN assigned to the vlan inside the cloud. Minimum value = 1 Maximum value = 16777215

    vlan(list(str)): The vlan id or the range of vlan ids in the on-premise network. Minimum length = 1 Maximum length =
        4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.add_vxlanvlanmap_vxlan_binding <args>

    '''

    result = {}

    payload = {'vxlanvlanmap_vxlan_binding': {}}

    if name:
        payload['vxlanvlanmap_vxlan_binding']['name'] = name

    if vxlan:
        payload['vxlanvlanmap_vxlan_binding']['vxlan'] = vxlan

    if vlan:
        payload['vxlanvlanmap_vxlan_binding']['vlan'] = vlan

    execution = __proxy__['citrixns.post']('config/vxlanvlanmap_vxlan_binding', payload)

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


def disable_interface(id=None, save=False):
    '''
    Disables a interface matching the specified filter.

    id(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.disable_interface id=foo

    '''

    result = {}

    payload = {'Interface': {}}

    if id:
        payload['Interface']['id'] = id
    else:
        result['result'] = 'False'
        result['error'] = 'id value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/Interface?action=disable', payload)

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


def enable_interface(id=None, save=False):
    '''
    Enables a interface matching the specified filter.

    id(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.enable_interface id=foo

    '''

    result = {}

    payload = {'Interface': {}}

    if id:
        payload['Interface']['id'] = id
    else:
        result['result'] = 'False'
        result['error'] = 'id value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/Interface?action=enable', payload)

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


def get_appalgparam():
    '''
    Show the running configuration for the appalgparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_appalgparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appalgparam'), 'appalgparam')

    return response


def get_arp(ipaddress=None, td=None, mac=None, ifnum=None, vxlan=None, vtep=None, vlan=None, ownernode=None,
            nodeid=None):
    '''
    Show the running configuration for the arp config key.

    ipaddress(str): Filters results that only match the ipaddress field.

    td(int): Filters results that only match the td field.

    mac(str): Filters results that only match the mac field.

    ifnum(str): Filters results that only match the ifnum field.

    vxlan(int): Filters results that only match the vxlan field.

    vtep(str): Filters results that only match the vtep field.

    vlan(int): Filters results that only match the vlan field.

    ownernode(int): Filters results that only match the ownernode field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_arp

    '''

    search_filter = []

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if td:
        search_filter.append(['td', td])

    if mac:
        search_filter.append(['mac', mac])

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    if vxlan:
        search_filter.append(['vxlan', vxlan])

    if vtep:
        search_filter.append(['vtep', vtep])

    if vlan:
        search_filter.append(['vlan', vlan])

    if ownernode:
        search_filter.append(['ownernode', ownernode])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/arp{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'arp')

    return response


def get_arpparam():
    '''
    Show the running configuration for the arpparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_arpparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/arpparam'), 'arpparam')

    return response


def get_bridgegroup(id=None, dynamicrouting=None, ipv6dynamicrouting=None):
    '''
    Show the running configuration for the bridgegroup config key.

    id(int): Filters results that only match the id field.

    dynamicrouting(str): Filters results that only match the dynamicrouting field.

    ipv6dynamicrouting(str): Filters results that only match the ipv6dynamicrouting field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_bridgegroup

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if dynamicrouting:
        search_filter.append(['dynamicrouting', dynamicrouting])

    if ipv6dynamicrouting:
        search_filter.append(['ipv6dynamicrouting', ipv6dynamicrouting])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/bridgegroup{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'bridgegroup')

    return response


def get_bridgegroup_binding():
    '''
    Show the running configuration for the bridgegroup_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_bridgegroup_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/bridgegroup_binding'), 'bridgegroup_binding')

    return response


def get_bridgegroup_nsip6_binding(ownergroup=None, netmask=None, id=None, td=None, ipaddress=None):
    '''
    Show the running configuration for the bridgegroup_nsip6_binding config key.

    ownergroup(str): Filters results that only match the ownergroup field.

    netmask(str): Filters results that only match the netmask field.

    id(int): Filters results that only match the id field.

    td(int): Filters results that only match the td field.

    ipaddress(str): Filters results that only match the ipaddress field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_bridgegroup_nsip6_binding

    '''

    search_filter = []

    if ownergroup:
        search_filter.append(['ownergroup', ownergroup])

    if netmask:
        search_filter.append(['netmask', netmask])

    if id:
        search_filter.append(['id', id])

    if td:
        search_filter.append(['td', td])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/bridgegroup_nsip6_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'bridgegroup_nsip6_binding')

    return response


def get_bridgegroup_nsip_binding(ownergroup=None, id=None, netmask=None, td=None, ipaddress=None):
    '''
    Show the running configuration for the bridgegroup_nsip_binding config key.

    ownergroup(str): Filters results that only match the ownergroup field.

    id(int): Filters results that only match the id field.

    netmask(str): Filters results that only match the netmask field.

    td(int): Filters results that only match the td field.

    ipaddress(str): Filters results that only match the ipaddress field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_bridgegroup_nsip_binding

    '''

    search_filter = []

    if ownergroup:
        search_filter.append(['ownergroup', ownergroup])

    if id:
        search_filter.append(['id', id])

    if netmask:
        search_filter.append(['netmask', netmask])

    if td:
        search_filter.append(['td', td])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/bridgegroup_nsip_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'bridgegroup_nsip_binding')

    return response


def get_bridgegroup_vlan_binding(vlan=None, id=None):
    '''
    Show the running configuration for the bridgegroup_vlan_binding config key.

    vlan(int): Filters results that only match the vlan field.

    id(int): Filters results that only match the id field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_bridgegroup_vlan_binding

    '''

    search_filter = []

    if vlan:
        search_filter.append(['vlan', vlan])

    if id:
        search_filter.append(['id', id])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/bridgegroup_vlan_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'bridgegroup_vlan_binding')

    return response


def get_bridgetable(mac=None, vxlan=None, vtep=None, vni=None, devicevlan=None, bridgeage=None, nodeid=None, vlan=None,
                    ifnum=None):
    '''
    Show the running configuration for the bridgetable config key.

    mac(str): Filters results that only match the mac field.

    vxlan(int): Filters results that only match the vxlan field.

    vtep(str): Filters results that only match the vtep field.

    vni(int): Filters results that only match the vni field.

    devicevlan(int): Filters results that only match the devicevlan field.

    bridgeage(int): Filters results that only match the bridgeage field.

    nodeid(int): Filters results that only match the nodeid field.

    vlan(int): Filters results that only match the vlan field.

    ifnum(str): Filters results that only match the ifnum field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_bridgetable

    '''

    search_filter = []

    if mac:
        search_filter.append(['mac', mac])

    if vxlan:
        search_filter.append(['vxlan', vxlan])

    if vtep:
        search_filter.append(['vtep', vtep])

    if vni:
        search_filter.append(['vni', vni])

    if devicevlan:
        search_filter.append(['devicevlan', devicevlan])

    if bridgeage:
        search_filter.append(['bridgeage', bridgeage])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    if vlan:
        search_filter.append(['vlan', vlan])

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/bridgetable{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'bridgetable')

    return response


def get_channel(id=None, ifnum=None, state=None, mode=None, conndistr=None, macdistr=None, lamac=None, speed=None,
                flowctl=None, hamonitor=None, haheartbeat=None, tagall=None, trunk=None, ifalias=None, throughput=None,
                bandwidthhigh=None, bandwidthnormal=None, mtu=None, lrminthroughput=None, linkredundancy=None):
    '''
    Show the running configuration for the channel config key.

    id(str): Filters results that only match the id field.

    ifnum(list(str)): Filters results that only match the ifnum field.

    state(str): Filters results that only match the state field.

    mode(str): Filters results that only match the mode field.

    conndistr(str): Filters results that only match the conndistr field.

    macdistr(str): Filters results that only match the macdistr field.

    lamac(str): Filters results that only match the lamac field.

    speed(str): Filters results that only match the speed field.

    flowctl(str): Filters results that only match the flowctl field.

    hamonitor(str): Filters results that only match the hamonitor field.

    haheartbeat(str): Filters results that only match the haheartbeat field.

    tagall(str): Filters results that only match the tagall field.

    trunk(str): Filters results that only match the trunk field.

    ifalias(str): Filters results that only match the ifalias field.

    throughput(int): Filters results that only match the throughput field.

    bandwidthhigh(int): Filters results that only match the bandwidthhigh field.

    bandwidthnormal(int): Filters results that only match the bandwidthnormal field.

    mtu(int): Filters results that only match the mtu field.

    lrminthroughput(int): Filters results that only match the lrminthroughput field.

    linkredundancy(str): Filters results that only match the linkredundancy field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_channel

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    if state:
        search_filter.append(['state', state])

    if mode:
        search_filter.append(['mode', mode])

    if conndistr:
        search_filter.append(['conndistr', conndistr])

    if macdistr:
        search_filter.append(['macdistr', macdistr])

    if lamac:
        search_filter.append(['lamac', lamac])

    if speed:
        search_filter.append(['speed', speed])

    if flowctl:
        search_filter.append(['flowctl', flowctl])

    if hamonitor:
        search_filter.append(['hamonitor', hamonitor])

    if haheartbeat:
        search_filter.append(['haheartbeat', haheartbeat])

    if tagall:
        search_filter.append(['tagall', tagall])

    if trunk:
        search_filter.append(['trunk', trunk])

    if ifalias:
        search_filter.append(['ifalias', ifalias])

    if throughput:
        search_filter.append(['throughput', throughput])

    if bandwidthhigh:
        search_filter.append(['bandwidthhigh', bandwidthhigh])

    if bandwidthnormal:
        search_filter.append(['bandwidthnormal', bandwidthnormal])

    if mtu:
        search_filter.append(['mtu', mtu])

    if lrminthroughput:
        search_filter.append(['lrminthroughput', lrminthroughput])

    if linkredundancy:
        search_filter.append(['linkredundancy', linkredundancy])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/channel{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'channel')

    return response


def get_channel_binding():
    '''
    Show the running configuration for the channel_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_channel_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/channel_binding'), 'channel_binding')

    return response


def get_channel_interface_binding(ifnum=None, id=None):
    '''
    Show the running configuration for the channel_interface_binding config key.

    ifnum(list(str)): Filters results that only match the ifnum field.

    id(str): Filters results that only match the id field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_channel_interface_binding

    '''

    search_filter = []

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    if id:
        search_filter.append(['id', id])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/channel_interface_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'channel_interface_binding')

    return response


def get_ci():
    '''
    Show the running configuration for the ci config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_ci

    '''

    search_filter = []

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/ci{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'ci')

    return response


def get_fis(name=None, ownernode=None):
    '''
    Show the running configuration for the fis config key.

    name(str): Filters results that only match the name field.

    ownernode(int): Filters results that only match the ownernode field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_fis

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ownernode:
        search_filter.append(['ownernode', ownernode])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/fis{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'fis')

    return response


def get_fis_binding():
    '''
    Show the running configuration for the fis_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_fis_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/fis_binding'), 'fis_binding')

    return response


def get_fis_channel_binding(ownernode=None, name=None, ifnum=None):
    '''
    Show the running configuration for the fis_channel_binding config key.

    ownernode(int): Filters results that only match the ownernode field.

    name(str): Filters results that only match the name field.

    ifnum(str): Filters results that only match the ifnum field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_fis_channel_binding

    '''

    search_filter = []

    if ownernode:
        search_filter.append(['ownernode', ownernode])

    if name:
        search_filter.append(['name', name])

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/fis_channel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'fis_channel_binding')

    return response


def get_forwardingsession(name=None, network=None, netmask=None, acl6name=None, aclname=None, td=None, connfailover=None,
                          sourceroutecache=None, processlocal=None):
    '''
    Show the running configuration for the forwardingsession config key.

    name(str): Filters results that only match the name field.

    network(str): Filters results that only match the network field.

    netmask(str): Filters results that only match the netmask field.

    acl6name(str): Filters results that only match the acl6name field.

    aclname(str): Filters results that only match the aclname field.

    td(int): Filters results that only match the td field.

    connfailover(str): Filters results that only match the connfailover field.

    sourceroutecache(str): Filters results that only match the sourceroutecache field.

    processlocal(str): Filters results that only match the processlocal field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_forwardingsession

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if network:
        search_filter.append(['network', network])

    if netmask:
        search_filter.append(['netmask', netmask])

    if acl6name:
        search_filter.append(['acl6name', acl6name])

    if aclname:
        search_filter.append(['aclname', aclname])

    if td:
        search_filter.append(['td', td])

    if connfailover:
        search_filter.append(['connfailover', connfailover])

    if sourceroutecache:
        search_filter.append(['sourceroutecache', sourceroutecache])

    if processlocal:
        search_filter.append(['processlocal', processlocal])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/forwardingsession{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'forwardingsession')

    return response


def get_inat(name=None, publicip=None, privateip=None, mode=None, tcpproxy=None, ftp=None, tftp=None, usip=None,
             usnip=None, proxyip=None, useproxyport=None, td=None):
    '''
    Show the running configuration for the inat config key.

    name(str): Filters results that only match the name field.

    publicip(str): Filters results that only match the publicip field.

    privateip(str): Filters results that only match the privateip field.

    mode(str): Filters results that only match the mode field.

    tcpproxy(str): Filters results that only match the tcpproxy field.

    ftp(str): Filters results that only match the ftp field.

    tftp(str): Filters results that only match the tftp field.

    usip(str): Filters results that only match the usip field.

    usnip(str): Filters results that only match the usnip field.

    proxyip(str): Filters results that only match the proxyip field.

    useproxyport(str): Filters results that only match the useproxyport field.

    td(int): Filters results that only match the td field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_inat

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if publicip:
        search_filter.append(['publicip', publicip])

    if privateip:
        search_filter.append(['privateip', privateip])

    if mode:
        search_filter.append(['mode', mode])

    if tcpproxy:
        search_filter.append(['tcpproxy', tcpproxy])

    if ftp:
        search_filter.append(['ftp', ftp])

    if tftp:
        search_filter.append(['tftp', tftp])

    if usip:
        search_filter.append(['usip', usip])

    if usnip:
        search_filter.append(['usnip', usnip])

    if proxyip:
        search_filter.append(['proxyip', proxyip])

    if useproxyport:
        search_filter.append(['useproxyport', useproxyport])

    if td:
        search_filter.append(['td', td])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/inat{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'inat')

    return response


def get_inatparam(nat46v6prefix=None, td=None, nat46ignoretos=None, nat46zerochecksum=None, nat46v6mtu=None,
                  nat46fragheader=None):
    '''
    Show the running configuration for the inatparam config key.

    nat46v6prefix(str): Filters results that only match the nat46v6prefix field.

    td(int): Filters results that only match the td field.

    nat46ignoretos(str): Filters results that only match the nat46ignoretos field.

    nat46zerochecksum(str): Filters results that only match the nat46zerochecksum field.

    nat46v6mtu(int): Filters results that only match the nat46v6mtu field.

    nat46fragheader(str): Filters results that only match the nat46fragheader field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_inatparam

    '''

    search_filter = []

    if nat46v6prefix:
        search_filter.append(['nat46v6prefix', nat46v6prefix])

    if td:
        search_filter.append(['td', td])

    if nat46ignoretos:
        search_filter.append(['nat46ignoretos', nat46ignoretos])

    if nat46zerochecksum:
        search_filter.append(['nat46zerochecksum', nat46zerochecksum])

    if nat46v6mtu:
        search_filter.append(['nat46v6mtu', nat46v6mtu])

    if nat46fragheader:
        search_filter.append(['nat46fragheader', nat46fragheader])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/inatparam{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'inatparam')

    return response


def get_interface(id=None, speed=None, duplex=None, flowctl=None, autoneg=None, hamonitor=None, haheartbeat=None,
                  mtu=None, tagall=None, trunk=None, trunkmode=None, trunkallowedvlan=None, lacpmode=None, lacpkey=None,
                  lagtype=None, lacppriority=None, lacptimeout=None, ifalias=None, throughput=None, linkredundancy=None,
                  bandwidthhigh=None, bandwidthnormal=None, lldpmode=None, lrsetpriority=None):
    '''
    Show the running configuration for the interface config key.

    id(str): Filters results that only match the id field.

    speed(str): Filters results that only match the speed field.

    duplex(str): Filters results that only match the duplex field.

    flowctl(str): Filters results that only match the flowctl field.

    autoneg(str): Filters results that only match the autoneg field.

    hamonitor(str): Filters results that only match the hamonitor field.

    haheartbeat(str): Filters results that only match the haheartbeat field.

    mtu(int): Filters results that only match the mtu field.

    tagall(str): Filters results that only match the tagall field.

    trunk(str): Filters results that only match the trunk field.

    trunkmode(str): Filters results that only match the trunkmode field.

    trunkallowedvlan(list(str)): Filters results that only match the trunkallowedvlan field.

    lacpmode(str): Filters results that only match the lacpmode field.

    lacpkey(int): Filters results that only match the lacpkey field.

    lagtype(str): Filters results that only match the lagtype field.

    lacppriority(int): Filters results that only match the lacppriority field.

    lacptimeout(str): Filters results that only match the lacptimeout field.

    ifalias(str): Filters results that only match the ifalias field.

    throughput(int): Filters results that only match the throughput field.

    linkredundancy(str): Filters results that only match the linkredundancy field.

    bandwidthhigh(int): Filters results that only match the bandwidthhigh field.

    bandwidthnormal(int): Filters results that only match the bandwidthnormal field.

    lldpmode(str): Filters results that only match the lldpmode field.

    lrsetpriority(int): Filters results that only match the lrsetpriority field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_interface

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if speed:
        search_filter.append(['speed', speed])

    if duplex:
        search_filter.append(['duplex', duplex])

    if flowctl:
        search_filter.append(['flowctl', flowctl])

    if autoneg:
        search_filter.append(['autoneg', autoneg])

    if hamonitor:
        search_filter.append(['hamonitor', hamonitor])

    if haheartbeat:
        search_filter.append(['haheartbeat', haheartbeat])

    if mtu:
        search_filter.append(['mtu', mtu])

    if tagall:
        search_filter.append(['tagall', tagall])

    if trunk:
        search_filter.append(['trunk', trunk])

    if trunkmode:
        search_filter.append(['trunkmode', trunkmode])

    if trunkallowedvlan:
        search_filter.append(['trunkallowedvlan', trunkallowedvlan])

    if lacpmode:
        search_filter.append(['lacpmode', lacpmode])

    if lacpkey:
        search_filter.append(['lacpkey', lacpkey])

    if lagtype:
        search_filter.append(['lagtype', lagtype])

    if lacppriority:
        search_filter.append(['lacppriority', lacppriority])

    if lacptimeout:
        search_filter.append(['lacptimeout', lacptimeout])

    if ifalias:
        search_filter.append(['ifalias', ifalias])

    if throughput:
        search_filter.append(['throughput', throughput])

    if linkredundancy:
        search_filter.append(['linkredundancy', linkredundancy])

    if bandwidthhigh:
        search_filter.append(['bandwidthhigh', bandwidthhigh])

    if bandwidthnormal:
        search_filter.append(['bandwidthnormal', bandwidthnormal])

    if lldpmode:
        search_filter.append(['lldpmode', lldpmode])

    if lrsetpriority:
        search_filter.append(['lrsetpriority', lrsetpriority])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/Interface{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'Interface')

    return response


def get_interfacepair(id=None, ifnum=None):
    '''
    Show the running configuration for the interfacepair config key.

    id(int): Filters results that only match the id field.

    ifnum(list(str)): Filters results that only match the ifnum field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_interfacepair

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/interfacepair{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'interfacepair')

    return response


def get_ip6tunnel(name=None, remote=None, local=None, ownergroup=None):
    '''
    Show the running configuration for the ip6tunnel config key.

    name(str): Filters results that only match the name field.

    remote(str): Filters results that only match the remote field.

    local(str): Filters results that only match the local field.

    ownergroup(str): Filters results that only match the ownergroup field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_ip6tunnel

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if remote:
        search_filter.append(['remote', remote])

    if local:
        search_filter.append(['local', local])

    if ownergroup:
        search_filter.append(['ownergroup', ownergroup])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/ip6tunnel{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'ip6tunnel')

    return response


def get_ip6tunnelparam():
    '''
    Show the running configuration for the ip6tunnelparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_ip6tunnelparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/ip6tunnelparam'), 'ip6tunnelparam')

    return response


def get_ipset(name=None, td=None):
    '''
    Show the running configuration for the ipset config key.

    name(str): Filters results that only match the name field.

    td(int): Filters results that only match the td field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_ipset

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if td:
        search_filter.append(['td', td])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/ipset{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'ipset')

    return response


def get_ipset_binding():
    '''
    Show the running configuration for the ipset_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_ipset_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/ipset_binding'), 'ipset_binding')

    return response


def get_ipset_nsip6_binding(name=None, ipaddress=None):
    '''
    Show the running configuration for the ipset_nsip6_binding config key.

    name(str): Filters results that only match the name field.

    ipaddress(str): Filters results that only match the ipaddress field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_ipset_nsip6_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/ipset_nsip6_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'ipset_nsip6_binding')

    return response


def get_ipset_nsip_binding(name=None, ipaddress=None):
    '''
    Show the running configuration for the ipset_nsip_binding config key.

    name(str): Filters results that only match the name field.

    ipaddress(str): Filters results that only match the ipaddress field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_ipset_nsip_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/ipset_nsip_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'ipset_nsip_binding')

    return response


def get_iptunnel(name=None, remote=None, remotesubnetmask=None, local=None, protocol=None, grepayload=None,
                 ipsecprofilename=None, vlan=None, ownergroup=None):
    '''
    Show the running configuration for the iptunnel config key.

    name(str): Filters results that only match the name field.

    remote(str): Filters results that only match the remote field.

    remotesubnetmask(str): Filters results that only match the remotesubnetmask field.

    local(str): Filters results that only match the local field.

    protocol(str): Filters results that only match the protocol field.

    grepayload(str): Filters results that only match the grepayload field.

    ipsecprofilename(str): Filters results that only match the ipsecprofilename field.

    vlan(int): Filters results that only match the vlan field.

    ownergroup(str): Filters results that only match the ownergroup field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_iptunnel

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if remote:
        search_filter.append(['remote', remote])

    if remotesubnetmask:
        search_filter.append(['remotesubnetmask', remotesubnetmask])

    if local:
        search_filter.append(['local', local])

    if protocol:
        search_filter.append(['protocol', protocol])

    if grepayload:
        search_filter.append(['grepayload', grepayload])

    if ipsecprofilename:
        search_filter.append(['ipsecprofilename', ipsecprofilename])

    if vlan:
        search_filter.append(['vlan', vlan])

    if ownergroup:
        search_filter.append(['ownergroup', ownergroup])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/iptunnel{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'iptunnel')

    return response


def get_iptunnelparam():
    '''
    Show the running configuration for the iptunnelparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_iptunnelparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/iptunnelparam'), 'iptunnelparam')

    return response


def get_ipv6(ralearning=None, routerredirection=None, ndbasereachtime=None, ndretransmissiontime=None, natprefix=None,
             td=None, dodad=None):
    '''
    Show the running configuration for the ipv6 config key.

    ralearning(str): Filters results that only match the ralearning field.

    routerredirection(str): Filters results that only match the routerredirection field.

    ndbasereachtime(int): Filters results that only match the ndbasereachtime field.

    ndretransmissiontime(int): Filters results that only match the ndretransmissiontime field.

    natprefix(str): Filters results that only match the natprefix field.

    td(int): Filters results that only match the td field.

    dodad(str): Filters results that only match the dodad field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_ipv6

    '''

    search_filter = []

    if ralearning:
        search_filter.append(['ralearning', ralearning])

    if routerredirection:
        search_filter.append(['routerredirection', routerredirection])

    if ndbasereachtime:
        search_filter.append(['ndbasereachtime', ndbasereachtime])

    if ndretransmissiontime:
        search_filter.append(['ndretransmissiontime', ndretransmissiontime])

    if natprefix:
        search_filter.append(['natprefix', natprefix])

    if td:
        search_filter.append(['td', td])

    if dodad:
        search_filter.append(['dodad', dodad])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/ipv6{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'ipv6')

    return response


def get_l2param():
    '''
    Show the running configuration for the l2param config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_l2param

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/l2param'), 'l2param')

    return response


def get_l3param():
    '''
    Show the running configuration for the l3param config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_l3param

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/l3param'), 'l3param')

    return response


def get_l4param():
    '''
    Show the running configuration for the l4param config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_l4param

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/l4param'), 'l4param')

    return response


def get_lacp(syspriority=None, ownernode=None):
    '''
    Show the running configuration for the lacp config key.

    syspriority(int): Filters results that only match the syspriority field.

    ownernode(int): Filters results that only match the ownernode field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_lacp

    '''

    search_filter = []

    if syspriority:
        search_filter.append(['syspriority', syspriority])

    if ownernode:
        search_filter.append(['ownernode', ownernode])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lacp{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lacp')

    return response


def get_linkset(id=None):
    '''
    Show the running configuration for the linkset config key.

    id(str): Filters results that only match the id field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_linkset

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/linkset{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'linkset')

    return response


def get_linkset_binding():
    '''
    Show the running configuration for the linkset_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_linkset_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/linkset_binding'), 'linkset_binding')

    return response


def get_linkset_channel_binding(ifnum=None, id=None):
    '''
    Show the running configuration for the linkset_channel_binding config key.

    ifnum(str): Filters results that only match the ifnum field.

    id(str): Filters results that only match the id field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_linkset_channel_binding

    '''

    search_filter = []

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    if id:
        search_filter.append(['id', id])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/linkset_channel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'linkset_channel_binding')

    return response


def get_linkset_interface_binding(ifnum=None, id=None):
    '''
    Show the running configuration for the linkset_interface_binding config key.

    ifnum(str): Filters results that only match the ifnum field.

    id(str): Filters results that only match the id field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_linkset_interface_binding

    '''

    search_filter = []

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    if id:
        search_filter.append(['id', id])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/linkset_interface_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'linkset_interface_binding')

    return response


def get_mapbmr(name=None, ruleipv6prefix=None, psidoffset=None, eabitlength=None, psidlength=None):
    '''
    Show the running configuration for the mapbmr config key.

    name(str): Filters results that only match the name field.

    ruleipv6prefix(str): Filters results that only match the ruleipv6prefix field.

    psidoffset(int): Filters results that only match the psidoffset field.

    eabitlength(int): Filters results that only match the eabitlength field.

    psidlength(int): Filters results that only match the psidlength field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_mapbmr

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ruleipv6prefix:
        search_filter.append(['ruleipv6prefix', ruleipv6prefix])

    if psidoffset:
        search_filter.append(['psidoffset', psidoffset])

    if eabitlength:
        search_filter.append(['eabitlength', eabitlength])

    if psidlength:
        search_filter.append(['psidlength', psidlength])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/mapbmr{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'mapbmr')

    return response


def get_mapbmr_binding():
    '''
    Show the running configuration for the mapbmr_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_mapbmr_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/mapbmr_binding'), 'mapbmr_binding')

    return response


def get_mapbmr_bmrv4network_binding(network=None, name=None):
    '''
    Show the running configuration for the mapbmr_bmrv4network_binding config key.

    network(str): Filters results that only match the network field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_mapbmr_bmrv4network_binding

    '''

    search_filter = []

    if network:
        search_filter.append(['network', network])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/mapbmr_bmrv4network_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'mapbmr_bmrv4network_binding')

    return response


def get_mapdmr(name=None, bripv6prefix=None):
    '''
    Show the running configuration for the mapdmr config key.

    name(str): Filters results that only match the name field.

    bripv6prefix(str): Filters results that only match the bripv6prefix field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_mapdmr

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if bripv6prefix:
        search_filter.append(['bripv6prefix', bripv6prefix])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/mapdmr{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'mapdmr')

    return response


def get_mapdomain(name=None, mapdmrname=None):
    '''
    Show the running configuration for the mapdomain config key.

    name(str): Filters results that only match the name field.

    mapdmrname(str): Filters results that only match the mapdmrname field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_mapdomain

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if mapdmrname:
        search_filter.append(['mapdmrname', mapdmrname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/mapdomain{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'mapdomain')

    return response


def get_mapdomain_binding():
    '''
    Show the running configuration for the mapdomain_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_mapdomain_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/mapdomain_binding'), 'mapdomain_binding')

    return response


def get_mapdomain_mapbmr_binding(mapbmrname=None, name=None):
    '''
    Show the running configuration for the mapdomain_mapbmr_binding config key.

    mapbmrname(str): Filters results that only match the mapbmrname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_mapdomain_mapbmr_binding

    '''

    search_filter = []

    if mapbmrname:
        search_filter.append(['mapbmrname', mapbmrname])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/mapdomain_mapbmr_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'mapdomain_mapbmr_binding')

    return response


def get_nat64(name=None, acl6name=None, netprofile=None):
    '''
    Show the running configuration for the nat64 config key.

    name(str): Filters results that only match the name field.

    acl6name(str): Filters results that only match the acl6name field.

    netprofile(str): Filters results that only match the netprofile field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_nat64

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if acl6name:
        search_filter.append(['acl6name', acl6name])

    if netprofile:
        search_filter.append(['netprofile', netprofile])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nat64{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nat64')

    return response


def get_nat64param(td=None, nat64ignoretos=None, nat64zerochecksum=None, nat64v6mtu=None, nat64fragheader=None):
    '''
    Show the running configuration for the nat64param config key.

    td(int): Filters results that only match the td field.

    nat64ignoretos(str): Filters results that only match the nat64ignoretos field.

    nat64zerochecksum(str): Filters results that only match the nat64zerochecksum field.

    nat64v6mtu(int): Filters results that only match the nat64v6mtu field.

    nat64fragheader(str): Filters results that only match the nat64fragheader field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_nat64param

    '''

    search_filter = []

    if td:
        search_filter.append(['td', td])

    if nat64ignoretos:
        search_filter.append(['nat64ignoretos', nat64ignoretos])

    if nat64zerochecksum:
        search_filter.append(['nat64zerochecksum', nat64zerochecksum])

    if nat64v6mtu:
        search_filter.append(['nat64v6mtu', nat64v6mtu])

    if nat64fragheader:
        search_filter.append(['nat64fragheader', nat64fragheader])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nat64param{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nat64param')

    return response


def get_nd6(neighbor=None, mac=None, ifnum=None, vlan=None, vxlan=None, vtep=None, td=None, nodeid=None):
    '''
    Show the running configuration for the nd6 config key.

    neighbor(str): Filters results that only match the neighbor field.

    mac(str): Filters results that only match the mac field.

    ifnum(str): Filters results that only match the ifnum field.

    vlan(int): Filters results that only match the vlan field.

    vxlan(int): Filters results that only match the vxlan field.

    vtep(str): Filters results that only match the vtep field.

    td(int): Filters results that only match the td field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_nd6

    '''

    search_filter = []

    if neighbor:
        search_filter.append(['neighbor', neighbor])

    if mac:
        search_filter.append(['mac', mac])

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    if vlan:
        search_filter.append(['vlan', vlan])

    if vxlan:
        search_filter.append(['vxlan', vxlan])

    if vtep:
        search_filter.append(['vtep', vtep])

    if td:
        search_filter.append(['td', td])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nd6{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nd6')

    return response


def get_nd6ravariables(vlan=None, ceaserouteradv=None, sendrouteradv=None, srclinklayeraddroption=None,
                       onlyunicastrtadvresponse=None, managedaddrconfig=None, otheraddrconfig=None, currhoplimit=None,
                       maxrtadvinterval=None, minrtadvinterval=None, linkmtu=None, reachabletime=None, retranstime=None,
                       defaultlifetime=None):
    '''
    Show the running configuration for the nd6ravariables config key.

    vlan(int): Filters results that only match the vlan field.

    ceaserouteradv(str): Filters results that only match the ceaserouteradv field.

    sendrouteradv(str): Filters results that only match the sendrouteradv field.

    srclinklayeraddroption(str): Filters results that only match the srclinklayeraddroption field.

    onlyunicastrtadvresponse(str): Filters results that only match the onlyunicastrtadvresponse field.

    managedaddrconfig(str): Filters results that only match the managedaddrconfig field.

    otheraddrconfig(str): Filters results that only match the otheraddrconfig field.

    currhoplimit(int): Filters results that only match the currhoplimit field.

    maxrtadvinterval(int): Filters results that only match the maxrtadvinterval field.

    minrtadvinterval(int): Filters results that only match the minrtadvinterval field.

    linkmtu(int): Filters results that only match the linkmtu field.

    reachabletime(int): Filters results that only match the reachabletime field.

    retranstime(int): Filters results that only match the retranstime field.

    defaultlifetime(int): Filters results that only match the defaultlifetime field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_nd6ravariables

    '''

    search_filter = []

    if vlan:
        search_filter.append(['vlan', vlan])

    if ceaserouteradv:
        search_filter.append(['ceaserouteradv', ceaserouteradv])

    if sendrouteradv:
        search_filter.append(['sendrouteradv', sendrouteradv])

    if srclinklayeraddroption:
        search_filter.append(['srclinklayeraddroption', srclinklayeraddroption])

    if onlyunicastrtadvresponse:
        search_filter.append(['onlyunicastrtadvresponse', onlyunicastrtadvresponse])

    if managedaddrconfig:
        search_filter.append(['managedaddrconfig', managedaddrconfig])

    if otheraddrconfig:
        search_filter.append(['otheraddrconfig', otheraddrconfig])

    if currhoplimit:
        search_filter.append(['currhoplimit', currhoplimit])

    if maxrtadvinterval:
        search_filter.append(['maxrtadvinterval', maxrtadvinterval])

    if minrtadvinterval:
        search_filter.append(['minrtadvinterval', minrtadvinterval])

    if linkmtu:
        search_filter.append(['linkmtu', linkmtu])

    if reachabletime:
        search_filter.append(['reachabletime', reachabletime])

    if retranstime:
        search_filter.append(['retranstime', retranstime])

    if defaultlifetime:
        search_filter.append(['defaultlifetime', defaultlifetime])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nd6ravariables{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nd6ravariables')

    return response


def get_nd6ravariables_binding():
    '''
    Show the running configuration for the nd6ravariables_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_nd6ravariables_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nd6ravariables_binding'), 'nd6ravariables_binding')

    return response


def get_nd6ravariables_onlinkipv6prefix_binding(ipv6prefix=None, vlan=None):
    '''
    Show the running configuration for the nd6ravariables_onlinkipv6prefix_binding config key.

    ipv6prefix(str): Filters results that only match the ipv6prefix field.

    vlan(int): Filters results that only match the vlan field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_nd6ravariables_onlinkipv6prefix_binding

    '''

    search_filter = []

    if ipv6prefix:
        search_filter.append(['ipv6prefix', ipv6prefix])

    if vlan:
        search_filter.append(['vlan', vlan])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nd6ravariables_onlinkipv6prefix_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nd6ravariables_onlinkipv6prefix_binding')

    return response


def get_netbridge(name=None, vxlanvlanmap=None):
    '''
    Show the running configuration for the netbridge config key.

    name(str): Filters results that only match the name field.

    vxlanvlanmap(str): Filters results that only match the vxlanvlanmap field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_netbridge

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if vxlanvlanmap:
        search_filter.append(['vxlanvlanmap', vxlanvlanmap])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/netbridge{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'netbridge')

    return response


def get_netbridge_binding():
    '''
    Show the running configuration for the netbridge_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_netbridge_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/netbridge_binding'), 'netbridge_binding')

    return response


def get_netbridge_iptunnel_binding(name=None, tunnel=None):
    '''
    Show the running configuration for the netbridge_iptunnel_binding config key.

    name(str): Filters results that only match the name field.

    tunnel(str): Filters results that only match the tunnel field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_netbridge_iptunnel_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if tunnel:
        search_filter.append(['tunnel', tunnel])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/netbridge_iptunnel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'netbridge_iptunnel_binding')

    return response


def get_netbridge_nsip6_binding(name=None, netmask=None, ipaddress=None):
    '''
    Show the running configuration for the netbridge_nsip6_binding config key.

    name(str): Filters results that only match the name field.

    netmask(str): Filters results that only match the netmask field.

    ipaddress(str): Filters results that only match the ipaddress field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_netbridge_nsip6_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if netmask:
        search_filter.append(['netmask', netmask])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/netbridge_nsip6_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'netbridge_nsip6_binding')

    return response


def get_netbridge_nsip_binding(name=None, netmask=None, ipaddress=None):
    '''
    Show the running configuration for the netbridge_nsip_binding config key.

    name(str): Filters results that only match the name field.

    netmask(str): Filters results that only match the netmask field.

    ipaddress(str): Filters results that only match the ipaddress field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_netbridge_nsip_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if netmask:
        search_filter.append(['netmask', netmask])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/netbridge_nsip_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'netbridge_nsip_binding')

    return response


def get_netbridge_vlan_binding(name=None, vlan=None):
    '''
    Show the running configuration for the netbridge_vlan_binding config key.

    name(str): Filters results that only match the name field.

    vlan(int): Filters results that only match the vlan field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_netbridge_vlan_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if vlan:
        search_filter.append(['vlan', vlan])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/netbridge_vlan_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'netbridge_vlan_binding')

    return response


def get_netprofile(name=None, td=None, srcip=None, srcippersistency=None, overridelsn=None):
    '''
    Show the running configuration for the netprofile config key.

    name(str): Filters results that only match the name field.

    td(int): Filters results that only match the td field.

    srcip(str): Filters results that only match the srcip field.

    srcippersistency(str): Filters results that only match the srcippersistency field.

    overridelsn(str): Filters results that only match the overridelsn field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_netprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if td:
        search_filter.append(['td', td])

    if srcip:
        search_filter.append(['srcip', srcip])

    if srcippersistency:
        search_filter.append(['srcippersistency', srcippersistency])

    if overridelsn:
        search_filter.append(['overridelsn', overridelsn])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/netprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'netprofile')

    return response


def get_netprofile_binding():
    '''
    Show the running configuration for the netprofile_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_netprofile_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/netprofile_binding'), 'netprofile_binding')

    return response


def get_netprofile_natrule_binding(rewriteip=None, name=None, netmask=None, natrule=None):
    '''
    Show the running configuration for the netprofile_natrule_binding config key.

    rewriteip(str): Filters results that only match the rewriteip field.

    name(str): Filters results that only match the name field.

    netmask(str): Filters results that only match the netmask field.

    natrule(str): Filters results that only match the natrule field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_netprofile_natrule_binding

    '''

    search_filter = []

    if rewriteip:
        search_filter.append(['rewriteip', rewriteip])

    if name:
        search_filter.append(['name', name])

    if netmask:
        search_filter.append(['netmask', netmask])

    if natrule:
        search_filter.append(['natrule', natrule])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/netprofile_natrule_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'netprofile_natrule_binding')

    return response


def get_netprofile_srcportset_binding(srcportrange=None, name=None):
    '''
    Show the running configuration for the netprofile_srcportset_binding config key.

    srcportrange(str): Filters results that only match the srcportrange field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_netprofile_srcportset_binding

    '''

    search_filter = []

    if srcportrange:
        search_filter.append(['srcportrange', srcportrange])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/netprofile_srcportset_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'netprofile_srcportset_binding')

    return response


def get_onlinkipv6prefix(ipv6prefix=None, onlinkprefix=None, autonomusprefix=None, depricateprefix=None,
                         decrementprefixlifetimes=None, prefixvalidelifetime=None, prefixpreferredlifetime=None):
    '''
    Show the running configuration for the onlinkipv6prefix config key.

    ipv6prefix(str): Filters results that only match the ipv6prefix field.

    onlinkprefix(str): Filters results that only match the onlinkprefix field.

    autonomusprefix(str): Filters results that only match the autonomusprefix field.

    depricateprefix(str): Filters results that only match the depricateprefix field.

    decrementprefixlifetimes(str): Filters results that only match the decrementprefixlifetimes field.

    prefixvalidelifetime(int): Filters results that only match the prefixvalidelifetime field.

    prefixpreferredlifetime(int): Filters results that only match the prefixpreferredlifetime field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_onlinkipv6prefix

    '''

    search_filter = []

    if ipv6prefix:
        search_filter.append(['ipv6prefix', ipv6prefix])

    if onlinkprefix:
        search_filter.append(['onlinkprefix', onlinkprefix])

    if autonomusprefix:
        search_filter.append(['autonomusprefix', autonomusprefix])

    if depricateprefix:
        search_filter.append(['depricateprefix', depricateprefix])

    if decrementprefixlifetimes:
        search_filter.append(['decrementprefixlifetimes', decrementprefixlifetimes])

    if prefixvalidelifetime:
        search_filter.append(['prefixvalidelifetime', prefixvalidelifetime])

    if prefixpreferredlifetime:
        search_filter.append(['prefixpreferredlifetime', prefixpreferredlifetime])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/onlinkipv6prefix{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'onlinkipv6prefix')

    return response


def get_ptp():
    '''
    Show the running configuration for the ptp config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_ptp

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/ptp'), 'ptp')

    return response


def get_rnat(network=None, netmask=None, aclname=None, redirectport=None, natip=None, td=None, ownergroup=None,
             natip2=None, srcippersistency=None, useproxyport=None, connfailover=None):
    '''
    Show the running configuration for the rnat config key.

    network(str): Filters results that only match the network field.

    netmask(str): Filters results that only match the netmask field.

    aclname(str): Filters results that only match the aclname field.

    redirectport(bool): Filters results that only match the redirectport field.

    natip(str): Filters results that only match the natip field.

    td(int): Filters results that only match the td field.

    ownergroup(str): Filters results that only match the ownergroup field.

    natip2(str): Filters results that only match the natip2 field.

    srcippersistency(str): Filters results that only match the srcippersistency field.

    useproxyport(str): Filters results that only match the useproxyport field.

    connfailover(str): Filters results that only match the connfailover field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_rnat

    '''

    search_filter = []

    if network:
        search_filter.append(['network', network])

    if netmask:
        search_filter.append(['netmask', netmask])

    if aclname:
        search_filter.append(['aclname', aclname])

    if redirectport:
        search_filter.append(['redirectport', redirectport])

    if natip:
        search_filter.append(['natip', natip])

    if td:
        search_filter.append(['td', td])

    if ownergroup:
        search_filter.append(['ownergroup', ownergroup])

    if natip2:
        search_filter.append(['natip2', natip2])

    if srcippersistency:
        search_filter.append(['srcippersistency', srcippersistency])

    if useproxyport:
        search_filter.append(['useproxyport', useproxyport])

    if connfailover:
        search_filter.append(['connfailover', connfailover])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rnat{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rnat')

    return response


def get_rnat6(name=None, network=None, acl6name=None, redirectport=None, td=None, srcippersistency=None,
              ownergroup=None):
    '''
    Show the running configuration for the rnat6 config key.

    name(str): Filters results that only match the name field.

    network(str): Filters results that only match the network field.

    acl6name(str): Filters results that only match the acl6name field.

    redirectport(int): Filters results that only match the redirectport field.

    td(int): Filters results that only match the td field.

    srcippersistency(str): Filters results that only match the srcippersistency field.

    ownergroup(str): Filters results that only match the ownergroup field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_rnat6

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if network:
        search_filter.append(['network', network])

    if acl6name:
        search_filter.append(['acl6name', acl6name])

    if redirectport:
        search_filter.append(['redirectport', redirectport])

    if td:
        search_filter.append(['td', td])

    if srcippersistency:
        search_filter.append(['srcippersistency', srcippersistency])

    if ownergroup:
        search_filter.append(['ownergroup', ownergroup])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rnat6{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rnat6')

    return response


def get_rnat6_binding():
    '''
    Show the running configuration for the rnat6_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_rnat6_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rnat6_binding'), 'rnat6_binding')

    return response


def get_rnat6_nsip6_binding(natip6=None, name=None, ownergroup=None):
    '''
    Show the running configuration for the rnat6_nsip6_binding config key.

    natip6(str): Filters results that only match the natip6 field.

    name(str): Filters results that only match the name field.

    ownergroup(str): Filters results that only match the ownergroup field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_rnat6_nsip6_binding

    '''

    search_filter = []

    if natip6:
        search_filter.append(['natip6', natip6])

    if name:
        search_filter.append(['name', name])

    if ownergroup:
        search_filter.append(['ownergroup', ownergroup])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rnat6_nsip6_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rnat6_nsip6_binding')

    return response


def get_rnatglobal_auditsyslogpolicy_binding(priority=None, policy=None):
    '''
    Show the running configuration for the rnatglobal_auditsyslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policy(str): Filters results that only match the policy field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_rnatglobal_auditsyslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policy:
        search_filter.append(['policy', policy])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rnatglobal_auditsyslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rnatglobal_auditsyslogpolicy_binding')

    return response


def get_rnatglobal_binding():
    '''
    Show the running configuration for the rnatglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_rnatglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rnatglobal_binding'), 'rnatglobal_binding')

    return response


def get_rnatparam():
    '''
    Show the running configuration for the rnatparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_rnatparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rnatparam'), 'rnatparam')

    return response


def get_route(network=None, netmask=None, gateway=None, cost=None, td=None, distance=None, cost1=None, weight=None,
              advertise=None, protocol=None, msr=None, monitor=None, ownergroup=None, routetype=None, detail=None):
    '''
    Show the running configuration for the route config key.

    network(str): Filters results that only match the network field.

    netmask(str): Filters results that only match the netmask field.

    gateway(str): Filters results that only match the gateway field.

    cost(int): Filters results that only match the cost field.

    td(int): Filters results that only match the td field.

    distance(int): Filters results that only match the distance field.

    cost1(int): Filters results that only match the cost1 field.

    weight(int): Filters results that only match the weight field.

    advertise(str): Filters results that only match the advertise field.

    protocol(list(str)): Filters results that only match the protocol field.

    msr(str): Filters results that only match the msr field.

    monitor(str): Filters results that only match the monitor field.

    ownergroup(str): Filters results that only match the ownergroup field.

    routetype(str): Filters results that only match the routetype field.

    detail(bool): Filters results that only match the detail field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_route

    '''

    search_filter = []

    if network:
        search_filter.append(['network', network])

    if netmask:
        search_filter.append(['netmask', netmask])

    if gateway:
        search_filter.append(['gateway', gateway])

    if cost:
        search_filter.append(['cost', cost])

    if td:
        search_filter.append(['td', td])

    if distance:
        search_filter.append(['distance', distance])

    if cost1:
        search_filter.append(['cost1', cost1])

    if weight:
        search_filter.append(['weight', weight])

    if advertise:
        search_filter.append(['advertise', advertise])

    if protocol:
        search_filter.append(['protocol', protocol])

    if msr:
        search_filter.append(['msr', msr])

    if monitor:
        search_filter.append(['monitor', monitor])

    if ownergroup:
        search_filter.append(['ownergroup', ownergroup])

    if routetype:
        search_filter.append(['routetype', routetype])

    if detail:
        search_filter.append(['detail', detail])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/route{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'route')

    return response


def get_route6(network=None, gateway=None, vlan=None, vxlan=None, weight=None, distance=None, cost=None, advertise=None,
               msr=None, monitor=None, td=None, ownergroup=None, routetype=None, detail=None):
    '''
    Show the running configuration for the route6 config key.

    network(str): Filters results that only match the network field.

    gateway(str): Filters results that only match the gateway field.

    vlan(int): Filters results that only match the vlan field.

    vxlan(int): Filters results that only match the vxlan field.

    weight(int): Filters results that only match the weight field.

    distance(int): Filters results that only match the distance field.

    cost(int): Filters results that only match the cost field.

    advertise(str): Filters results that only match the advertise field.

    msr(str): Filters results that only match the msr field.

    monitor(str): Filters results that only match the monitor field.

    td(int): Filters results that only match the td field.

    ownergroup(str): Filters results that only match the ownergroup field.

    routetype(str): Filters results that only match the routetype field.

    detail(bool): Filters results that only match the detail field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_route6

    '''

    search_filter = []

    if network:
        search_filter.append(['network', network])

    if gateway:
        search_filter.append(['gateway', gateway])

    if vlan:
        search_filter.append(['vlan', vlan])

    if vxlan:
        search_filter.append(['vxlan', vxlan])

    if weight:
        search_filter.append(['weight', weight])

    if distance:
        search_filter.append(['distance', distance])

    if cost:
        search_filter.append(['cost', cost])

    if advertise:
        search_filter.append(['advertise', advertise])

    if msr:
        search_filter.append(['msr', msr])

    if monitor:
        search_filter.append(['monitor', monitor])

    if td:
        search_filter.append(['td', td])

    if ownergroup:
        search_filter.append(['ownergroup', ownergroup])

    if routetype:
        search_filter.append(['routetype', routetype])

    if detail:
        search_filter.append(['detail', detail])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/route6{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'route6')

    return response


def get_rsskeytype():
    '''
    Show the running configuration for the rsskeytype config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_rsskeytype

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rsskeytype'), 'rsskeytype')

    return response


def get_vlan(id=None, aliasname=None, dynamicrouting=None, ipv6dynamicrouting=None, mtu=None, sharing=None):
    '''
    Show the running configuration for the vlan config key.

    id(int): Filters results that only match the id field.

    aliasname(str): Filters results that only match the aliasname field.

    dynamicrouting(str): Filters results that only match the dynamicrouting field.

    ipv6dynamicrouting(str): Filters results that only match the ipv6dynamicrouting field.

    mtu(int): Filters results that only match the mtu field.

    sharing(str): Filters results that only match the sharing field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vlan

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if aliasname:
        search_filter.append(['aliasname', aliasname])

    if dynamicrouting:
        search_filter.append(['dynamicrouting', dynamicrouting])

    if ipv6dynamicrouting:
        search_filter.append(['ipv6dynamicrouting', ipv6dynamicrouting])

    if mtu:
        search_filter.append(['mtu', mtu])

    if sharing:
        search_filter.append(['sharing', sharing])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vlan{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vlan')

    return response


def get_vlan_binding():
    '''
    Show the running configuration for the vlan_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vlan_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vlan_binding'), 'vlan_binding')

    return response


def get_vlan_channel_binding(ownergroup=None, id=None, ifnum=None, tagged=None):
    '''
    Show the running configuration for the vlan_channel_binding config key.

    ownergroup(str): Filters results that only match the ownergroup field.

    id(int): Filters results that only match the id field.

    ifnum(str): Filters results that only match the ifnum field.

    tagged(bool): Filters results that only match the tagged field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vlan_channel_binding

    '''

    search_filter = []

    if ownergroup:
        search_filter.append(['ownergroup', ownergroup])

    if id:
        search_filter.append(['id', id])

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    if tagged:
        search_filter.append(['tagged', tagged])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vlan_channel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vlan_channel_binding')

    return response


def get_vlan_interface_binding(ownergroup=None, id=None, ifnum=None, tagged=None):
    '''
    Show the running configuration for the vlan_interface_binding config key.

    ownergroup(str): Filters results that only match the ownergroup field.

    id(int): Filters results that only match the id field.

    ifnum(str): Filters results that only match the ifnum field.

    tagged(bool): Filters results that only match the tagged field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vlan_interface_binding

    '''

    search_filter = []

    if ownergroup:
        search_filter.append(['ownergroup', ownergroup])

    if id:
        search_filter.append(['id', id])

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    if tagged:
        search_filter.append(['tagged', tagged])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vlan_interface_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vlan_interface_binding')

    return response


def get_vlan_linkset_binding(ownergroup=None, id=None, ifnum=None, tagged=None):
    '''
    Show the running configuration for the vlan_linkset_binding config key.

    ownergroup(str): Filters results that only match the ownergroup field.

    id(int): Filters results that only match the id field.

    ifnum(str): Filters results that only match the ifnum field.

    tagged(bool): Filters results that only match the tagged field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vlan_linkset_binding

    '''

    search_filter = []

    if ownergroup:
        search_filter.append(['ownergroup', ownergroup])

    if id:
        search_filter.append(['id', id])

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    if tagged:
        search_filter.append(['tagged', tagged])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vlan_linkset_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vlan_linkset_binding')

    return response


def get_vlan_nsip6_binding(ownergroup=None, id=None, td=None, netmask=None, ipaddress=None):
    '''
    Show the running configuration for the vlan_nsip6_binding config key.

    ownergroup(str): Filters results that only match the ownergroup field.

    id(int): Filters results that only match the id field.

    td(int): Filters results that only match the td field.

    netmask(str): Filters results that only match the netmask field.

    ipaddress(str): Filters results that only match the ipaddress field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vlan_nsip6_binding

    '''

    search_filter = []

    if ownergroup:
        search_filter.append(['ownergroup', ownergroup])

    if id:
        search_filter.append(['id', id])

    if td:
        search_filter.append(['td', td])

    if netmask:
        search_filter.append(['netmask', netmask])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vlan_nsip6_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vlan_nsip6_binding')

    return response


def get_vlan_nsip_binding(ownergroup=None, id=None, td=None, netmask=None, ipaddress=None):
    '''
    Show the running configuration for the vlan_nsip_binding config key.

    ownergroup(str): Filters results that only match the ownergroup field.

    id(int): Filters results that only match the id field.

    td(int): Filters results that only match the td field.

    netmask(str): Filters results that only match the netmask field.

    ipaddress(str): Filters results that only match the ipaddress field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vlan_nsip_binding

    '''

    search_filter = []

    if ownergroup:
        search_filter.append(['ownergroup', ownergroup])

    if id:
        search_filter.append(['id', id])

    if td:
        search_filter.append(['td', td])

    if netmask:
        search_filter.append(['netmask', netmask])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vlan_nsip_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vlan_nsip_binding')

    return response


def get_vrid(id=None, priority=None, preemption=None, sharing=None, tracking=None, ownernode=None,
             trackifnumpriority=None, preemptiondelaytimer=None):
    '''
    Show the running configuration for the vrid config key.

    id(int): Filters results that only match the id field.

    priority(int): Filters results that only match the priority field.

    preemption(str): Filters results that only match the preemption field.

    sharing(str): Filters results that only match the sharing field.

    tracking(str): Filters results that only match the tracking field.

    ownernode(int): Filters results that only match the ownernode field.

    trackifnumpriority(int): Filters results that only match the trackifnumpriority field.

    preemptiondelaytimer(int): Filters results that only match the preemptiondelaytimer field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vrid

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if priority:
        search_filter.append(['priority', priority])

    if preemption:
        search_filter.append(['preemption', preemption])

    if sharing:
        search_filter.append(['sharing', sharing])

    if tracking:
        search_filter.append(['tracking', tracking])

    if ownernode:
        search_filter.append(['ownernode', ownernode])

    if trackifnumpriority:
        search_filter.append(['trackifnumpriority', trackifnumpriority])

    if preemptiondelaytimer:
        search_filter.append(['preemptiondelaytimer', preemptiondelaytimer])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vrid{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vrid')

    return response


def get_vrid6(id=None, priority=None, preemption=None, sharing=None, tracking=None, preemptiondelaytimer=None,
              trackifnumpriority=None, ownernode=None):
    '''
    Show the running configuration for the vrid6 config key.

    id(int): Filters results that only match the id field.

    priority(int): Filters results that only match the priority field.

    preemption(str): Filters results that only match the preemption field.

    sharing(str): Filters results that only match the sharing field.

    tracking(str): Filters results that only match the tracking field.

    preemptiondelaytimer(int): Filters results that only match the preemptiondelaytimer field.

    trackifnumpriority(int): Filters results that only match the trackifnumpriority field.

    ownernode(int): Filters results that only match the ownernode field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vrid6

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if priority:
        search_filter.append(['priority', priority])

    if preemption:
        search_filter.append(['preemption', preemption])

    if sharing:
        search_filter.append(['sharing', sharing])

    if tracking:
        search_filter.append(['tracking', tracking])

    if preemptiondelaytimer:
        search_filter.append(['preemptiondelaytimer', preemptiondelaytimer])

    if trackifnumpriority:
        search_filter.append(['trackifnumpriority', trackifnumpriority])

    if ownernode:
        search_filter.append(['ownernode', ownernode])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vrid6{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vrid6')

    return response


def get_vrid6_binding():
    '''
    Show the running configuration for the vrid6_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vrid6_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vrid6_binding'), 'vrid6_binding')

    return response


def get_vrid6_channel_binding(id=None, ifnum=None):
    '''
    Show the running configuration for the vrid6_channel_binding config key.

    id(int): Filters results that only match the id field.

    ifnum(str): Filters results that only match the ifnum field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vrid6_channel_binding

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vrid6_channel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vrid6_channel_binding')

    return response


def get_vrid6_interface_binding(id=None, ifnum=None):
    '''
    Show the running configuration for the vrid6_interface_binding config key.

    id(int): Filters results that only match the id field.

    ifnum(str): Filters results that only match the ifnum field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vrid6_interface_binding

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vrid6_interface_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vrid6_interface_binding')

    return response


def get_vrid6_nsip6_binding(id=None, ipaddress=None):
    '''
    Show the running configuration for the vrid6_nsip6_binding config key.

    id(int): Filters results that only match the id field.

    ipaddress(str): Filters results that only match the ipaddress field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vrid6_nsip6_binding

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vrid6_nsip6_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vrid6_nsip6_binding')

    return response


def get_vrid6_nsip_binding(id=None, ipaddress=None):
    '''
    Show the running configuration for the vrid6_nsip_binding config key.

    id(int): Filters results that only match the id field.

    ipaddress(str): Filters results that only match the ipaddress field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vrid6_nsip_binding

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vrid6_nsip_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vrid6_nsip_binding')

    return response


def get_vrid6_trackinterface_binding(trackifnum=None, id=None):
    '''
    Show the running configuration for the vrid6_trackinterface_binding config key.

    trackifnum(str): Filters results that only match the trackifnum field.

    id(int): Filters results that only match the id field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vrid6_trackinterface_binding

    '''

    search_filter = []

    if trackifnum:
        search_filter.append(['trackifnum', trackifnum])

    if id:
        search_filter.append(['id', id])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vrid6_trackinterface_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vrid6_trackinterface_binding')

    return response


def get_vrid_binding():
    '''
    Show the running configuration for the vrid_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vrid_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vrid_binding'), 'vrid_binding')

    return response


def get_vrid_channel_binding(id=None, ifnum=None):
    '''
    Show the running configuration for the vrid_channel_binding config key.

    id(int): Filters results that only match the id field.

    ifnum(str): Filters results that only match the ifnum field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vrid_channel_binding

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vrid_channel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vrid_channel_binding')

    return response


def get_vrid_interface_binding(id=None, ifnum=None):
    '''
    Show the running configuration for the vrid_interface_binding config key.

    id(int): Filters results that only match the id field.

    ifnum(str): Filters results that only match the ifnum field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vrid_interface_binding

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vrid_interface_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vrid_interface_binding')

    return response


def get_vrid_nsip6_binding(id=None, ipaddress=None):
    '''
    Show the running configuration for the vrid_nsip6_binding config key.

    id(int): Filters results that only match the id field.

    ipaddress(str): Filters results that only match the ipaddress field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vrid_nsip6_binding

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vrid_nsip6_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vrid_nsip6_binding')

    return response


def get_vrid_nsip_binding(id=None, ipaddress=None):
    '''
    Show the running configuration for the vrid_nsip_binding config key.

    id(int): Filters results that only match the id field.

    ipaddress(str): Filters results that only match the ipaddress field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vrid_nsip_binding

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vrid_nsip_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vrid_nsip_binding')

    return response


def get_vrid_trackinterface_binding(id=None, trackifnum=None):
    '''
    Show the running configuration for the vrid_trackinterface_binding config key.

    id(int): Filters results that only match the id field.

    trackifnum(str): Filters results that only match the trackifnum field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vrid_trackinterface_binding

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if trackifnum:
        search_filter.append(['trackifnum', trackifnum])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vrid_trackinterface_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vrid_trackinterface_binding')

    return response


def get_vridparam():
    '''
    Show the running configuration for the vridparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vridparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vridparam'), 'vridparam')

    return response


def get_vxlan(id=None, vlan=None, port=None, dynamicrouting=None, ipv6dynamicrouting=None, ns_type=None, protocol=None,
              innervlantagging=None):
    '''
    Show the running configuration for the vxlan config key.

    id(int): Filters results that only match the id field.

    vlan(int): Filters results that only match the vlan field.

    port(int): Filters results that only match the port field.

    dynamicrouting(str): Filters results that only match the dynamicrouting field.

    ipv6dynamicrouting(str): Filters results that only match the ipv6dynamicrouting field.

    ns_type(str): Filters results that only match the type field.

    protocol(str): Filters results that only match the protocol field.

    innervlantagging(str): Filters results that only match the innervlantagging field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vxlan

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if vlan:
        search_filter.append(['vlan', vlan])

    if port:
        search_filter.append(['port', port])

    if dynamicrouting:
        search_filter.append(['dynamicrouting', dynamicrouting])

    if ipv6dynamicrouting:
        search_filter.append(['ipv6dynamicrouting', ipv6dynamicrouting])

    if ns_type:
        search_filter.append(['type', ns_type])

    if protocol:
        search_filter.append(['protocol', protocol])

    if innervlantagging:
        search_filter.append(['innervlantagging', innervlantagging])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vxlan{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vxlan')

    return response


def get_vxlan_binding():
    '''
    Show the running configuration for the vxlan_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vxlan_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vxlan_binding'), 'vxlan_binding')

    return response


def get_vxlan_iptunnel_binding(id=None, tunnel=None):
    '''
    Show the running configuration for the vxlan_iptunnel_binding config key.

    id(int): Filters results that only match the id field.

    tunnel(str): Filters results that only match the tunnel field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vxlan_iptunnel_binding

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if tunnel:
        search_filter.append(['tunnel', tunnel])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vxlan_iptunnel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vxlan_iptunnel_binding')

    return response


def get_vxlan_nsip6_binding(id=None, netmask=None, ipaddress=None):
    '''
    Show the running configuration for the vxlan_nsip6_binding config key.

    id(int): Filters results that only match the id field.

    netmask(str): Filters results that only match the netmask field.

    ipaddress(str): Filters results that only match the ipaddress field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vxlan_nsip6_binding

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if netmask:
        search_filter.append(['netmask', netmask])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vxlan_nsip6_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vxlan_nsip6_binding')

    return response


def get_vxlan_nsip_binding(id=None, netmask=None, ipaddress=None):
    '''
    Show the running configuration for the vxlan_nsip_binding config key.

    id(int): Filters results that only match the id field.

    netmask(str): Filters results that only match the netmask field.

    ipaddress(str): Filters results that only match the ipaddress field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vxlan_nsip_binding

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if netmask:
        search_filter.append(['netmask', netmask])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vxlan_nsip_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vxlan_nsip_binding')

    return response


def get_vxlan_srcip_binding(id=None, srcip=None):
    '''
    Show the running configuration for the vxlan_srcip_binding config key.

    id(int): Filters results that only match the id field.

    srcip(str): Filters results that only match the srcip field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vxlan_srcip_binding

    '''

    search_filter = []

    if id:
        search_filter.append(['id', id])

    if srcip:
        search_filter.append(['srcip', srcip])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vxlan_srcip_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vxlan_srcip_binding')

    return response


def get_vxlanvlanmap(name=None):
    '''
    Show the running configuration for the vxlanvlanmap config key.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vxlanvlanmap

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vxlanvlanmap{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vxlanvlanmap')

    return response


def get_vxlanvlanmap_binding():
    '''
    Show the running configuration for the vxlanvlanmap_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vxlanvlanmap_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vxlanvlanmap_binding'), 'vxlanvlanmap_binding')

    return response


def get_vxlanvlanmap_vxlan_binding(name=None, vxlan=None, vlan=None):
    '''
    Show the running configuration for the vxlanvlanmap_vxlan_binding config key.

    name(str): Filters results that only match the name field.

    vxlan(int): Filters results that only match the vxlan field.

    vlan(list(str)): Filters results that only match the vlan field.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.get_vxlanvlanmap_vxlan_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if vxlan:
        search_filter.append(['vxlan', vxlan])

    if vlan:
        search_filter.append(['vlan', vlan])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vxlanvlanmap_vxlan_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vxlanvlanmap_vxlan_binding')

    return response


def unset_appalgparam(pptpgreidletimeout=None, save=False):
    '''
    Unsets values from the appalgparam configuration key.

    pptpgreidletimeout(bool): Unsets the pptpgreidletimeout value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_appalgparam <args>

    '''

    result = {}

    payload = {'appalgparam': {}}

    if pptpgreidletimeout:
        payload['appalgparam']['pptpgreidletimeout'] = True

    execution = __proxy__['citrixns.post']('config/appalgparam?action=unset', payload)

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


def unset_arpparam(timeout=None, spoofvalidation=None, save=False):
    '''
    Unsets values from the arpparam configuration key.

    timeout(bool): Unsets the timeout value.

    spoofvalidation(bool): Unsets the spoofvalidation value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_arpparam <args>

    '''

    result = {}

    payload = {'arpparam': {}}

    if timeout:
        payload['arpparam']['timeout'] = True

    if spoofvalidation:
        payload['arpparam']['spoofvalidation'] = True

    execution = __proxy__['citrixns.post']('config/arpparam?action=unset', payload)

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


def unset_bridgegroup(id=None, dynamicrouting=None, ipv6dynamicrouting=None, save=False):
    '''
    Unsets values from the bridgegroup configuration key.

    id(bool): Unsets the id value.

    dynamicrouting(bool): Unsets the dynamicrouting value.

    ipv6dynamicrouting(bool): Unsets the ipv6dynamicrouting value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_bridgegroup <args>

    '''

    result = {}

    payload = {'bridgegroup': {}}

    if id:
        payload['bridgegroup']['id'] = True

    if dynamicrouting:
        payload['bridgegroup']['dynamicrouting'] = True

    if ipv6dynamicrouting:
        payload['bridgegroup']['ipv6dynamicrouting'] = True

    execution = __proxy__['citrixns.post']('config/bridgegroup?action=unset', payload)

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


def unset_bridgetable(mac=None, vxlan=None, vtep=None, vni=None, devicevlan=None, bridgeage=None, nodeid=None, vlan=None,
                      ifnum=None, save=False):
    '''
    Unsets values from the bridgetable configuration key.

    mac(bool): Unsets the mac value.

    vxlan(bool): Unsets the vxlan value.

    vtep(bool): Unsets the vtep value.

    vni(bool): Unsets the vni value.

    devicevlan(bool): Unsets the devicevlan value.

    bridgeage(bool): Unsets the bridgeage value.

    nodeid(bool): Unsets the nodeid value.

    vlan(bool): Unsets the vlan value.

    ifnum(bool): Unsets the ifnum value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_bridgetable <args>

    '''

    result = {}

    payload = {'bridgetable': {}}

    if mac:
        payload['bridgetable']['mac'] = True

    if vxlan:
        payload['bridgetable']['vxlan'] = True

    if vtep:
        payload['bridgetable']['vtep'] = True

    if vni:
        payload['bridgetable']['vni'] = True

    if devicevlan:
        payload['bridgetable']['devicevlan'] = True

    if bridgeage:
        payload['bridgetable']['bridgeage'] = True

    if nodeid:
        payload['bridgetable']['nodeid'] = True

    if vlan:
        payload['bridgetable']['vlan'] = True

    if ifnum:
        payload['bridgetable']['ifnum'] = True

    execution = __proxy__['citrixns.post']('config/bridgetable?action=unset', payload)

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


def unset_channel(id=None, ifnum=None, state=None, mode=None, conndistr=None, macdistr=None, lamac=None, speed=None,
                  flowctl=None, hamonitor=None, haheartbeat=None, tagall=None, trunk=None, ifalias=None, throughput=None,
                  bandwidthhigh=None, bandwidthnormal=None, mtu=None, lrminthroughput=None, linkredundancy=None,
                  save=False):
    '''
    Unsets values from the channel configuration key.

    id(bool): Unsets the id value.

    ifnum(bool): Unsets the ifnum value.

    state(bool): Unsets the state value.

    mode(bool): Unsets the mode value.

    conndistr(bool): Unsets the conndistr value.

    macdistr(bool): Unsets the macdistr value.

    lamac(bool): Unsets the lamac value.

    speed(bool): Unsets the speed value.

    flowctl(bool): Unsets the flowctl value.

    hamonitor(bool): Unsets the hamonitor value.

    haheartbeat(bool): Unsets the haheartbeat value.

    tagall(bool): Unsets the tagall value.

    trunk(bool): Unsets the trunk value.

    ifalias(bool): Unsets the ifalias value.

    throughput(bool): Unsets the throughput value.

    bandwidthhigh(bool): Unsets the bandwidthhigh value.

    bandwidthnormal(bool): Unsets the bandwidthnormal value.

    mtu(bool): Unsets the mtu value.

    lrminthroughput(bool): Unsets the lrminthroughput value.

    linkredundancy(bool): Unsets the linkredundancy value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_channel <args>

    '''

    result = {}

    payload = {'channel': {}}

    if id:
        payload['channel']['id'] = True

    if ifnum:
        payload['channel']['ifnum'] = True

    if state:
        payload['channel']['state'] = True

    if mode:
        payload['channel']['mode'] = True

    if conndistr:
        payload['channel']['conndistr'] = True

    if macdistr:
        payload['channel']['macdistr'] = True

    if lamac:
        payload['channel']['lamac'] = True

    if speed:
        payload['channel']['speed'] = True

    if flowctl:
        payload['channel']['flowctl'] = True

    if hamonitor:
        payload['channel']['hamonitor'] = True

    if haheartbeat:
        payload['channel']['haheartbeat'] = True

    if tagall:
        payload['channel']['tagall'] = True

    if trunk:
        payload['channel']['trunk'] = True

    if ifalias:
        payload['channel']['ifalias'] = True

    if throughput:
        payload['channel']['throughput'] = True

    if bandwidthhigh:
        payload['channel']['bandwidthhigh'] = True

    if bandwidthnormal:
        payload['channel']['bandwidthnormal'] = True

    if mtu:
        payload['channel']['mtu'] = True

    if lrminthroughput:
        payload['channel']['lrminthroughput'] = True

    if linkredundancy:
        payload['channel']['linkredundancy'] = True

    execution = __proxy__['citrixns.post']('config/channel?action=unset', payload)

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


def unset_inat(name=None, publicip=None, privateip=None, mode=None, tcpproxy=None, ftp=None, tftp=None, usip=None,
               usnip=None, proxyip=None, useproxyport=None, td=None, save=False):
    '''
    Unsets values from the inat configuration key.

    name(bool): Unsets the name value.

    publicip(bool): Unsets the publicip value.

    privateip(bool): Unsets the privateip value.

    mode(bool): Unsets the mode value.

    tcpproxy(bool): Unsets the tcpproxy value.

    ftp(bool): Unsets the ftp value.

    tftp(bool): Unsets the tftp value.

    usip(bool): Unsets the usip value.

    usnip(bool): Unsets the usnip value.

    proxyip(bool): Unsets the proxyip value.

    useproxyport(bool): Unsets the useproxyport value.

    td(bool): Unsets the td value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_inat <args>

    '''

    result = {}

    payload = {'inat': {}}

    if name:
        payload['inat']['name'] = True

    if publicip:
        payload['inat']['publicip'] = True

    if privateip:
        payload['inat']['privateip'] = True

    if mode:
        payload['inat']['mode'] = True

    if tcpproxy:
        payload['inat']['tcpproxy'] = True

    if ftp:
        payload['inat']['ftp'] = True

    if tftp:
        payload['inat']['tftp'] = True

    if usip:
        payload['inat']['usip'] = True

    if usnip:
        payload['inat']['usnip'] = True

    if proxyip:
        payload['inat']['proxyip'] = True

    if useproxyport:
        payload['inat']['useproxyport'] = True

    if td:
        payload['inat']['td'] = True

    execution = __proxy__['citrixns.post']('config/inat?action=unset', payload)

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


def unset_inatparam(nat46v6prefix=None, td=None, nat46ignoretos=None, nat46zerochecksum=None, nat46v6mtu=None,
                    nat46fragheader=None, save=False):
    '''
    Unsets values from the inatparam configuration key.

    nat46v6prefix(bool): Unsets the nat46v6prefix value.

    td(bool): Unsets the td value.

    nat46ignoretos(bool): Unsets the nat46ignoretos value.

    nat46zerochecksum(bool): Unsets the nat46zerochecksum value.

    nat46v6mtu(bool): Unsets the nat46v6mtu value.

    nat46fragheader(bool): Unsets the nat46fragheader value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_inatparam <args>

    '''

    result = {}

    payload = {'inatparam': {}}

    if nat46v6prefix:
        payload['inatparam']['nat46v6prefix'] = True

    if td:
        payload['inatparam']['td'] = True

    if nat46ignoretos:
        payload['inatparam']['nat46ignoretos'] = True

    if nat46zerochecksum:
        payload['inatparam']['nat46zerochecksum'] = True

    if nat46v6mtu:
        payload['inatparam']['nat46v6mtu'] = True

    if nat46fragheader:
        payload['inatparam']['nat46fragheader'] = True

    execution = __proxy__['citrixns.post']('config/inatparam?action=unset', payload)

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


def unset_interface(id=None, speed=None, duplex=None, flowctl=None, autoneg=None, hamonitor=None, haheartbeat=None,
                    mtu=None, tagall=None, trunk=None, trunkmode=None, trunkallowedvlan=None, lacpmode=None,
                    lacpkey=None, lagtype=None, lacppriority=None, lacptimeout=None, ifalias=None, throughput=None,
                    linkredundancy=None, bandwidthhigh=None, bandwidthnormal=None, lldpmode=None, lrsetpriority=None,
                    save=False):
    '''
    Unsets values from the interface configuration key.

    id(bool): Unsets the id value.

    speed(bool): Unsets the speed value.

    duplex(bool): Unsets the duplex value.

    flowctl(bool): Unsets the flowctl value.

    autoneg(bool): Unsets the autoneg value.

    hamonitor(bool): Unsets the hamonitor value.

    haheartbeat(bool): Unsets the haheartbeat value.

    mtu(bool): Unsets the mtu value.

    tagall(bool): Unsets the tagall value.

    trunk(bool): Unsets the trunk value.

    trunkmode(bool): Unsets the trunkmode value.

    trunkallowedvlan(bool): Unsets the trunkallowedvlan value.

    lacpmode(bool): Unsets the lacpmode value.

    lacpkey(bool): Unsets the lacpkey value.

    lagtype(bool): Unsets the lagtype value.

    lacppriority(bool): Unsets the lacppriority value.

    lacptimeout(bool): Unsets the lacptimeout value.

    ifalias(bool): Unsets the ifalias value.

    throughput(bool): Unsets the throughput value.

    linkredundancy(bool): Unsets the linkredundancy value.

    bandwidthhigh(bool): Unsets the bandwidthhigh value.

    bandwidthnormal(bool): Unsets the bandwidthnormal value.

    lldpmode(bool): Unsets the lldpmode value.

    lrsetpriority(bool): Unsets the lrsetpriority value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_interface <args>

    '''

    result = {}

    payload = {'Interface': {}}

    if id:
        payload['Interface']['id'] = True

    if speed:
        payload['Interface']['speed'] = True

    if duplex:
        payload['Interface']['duplex'] = True

    if flowctl:
        payload['Interface']['flowctl'] = True

    if autoneg:
        payload['Interface']['autoneg'] = True

    if hamonitor:
        payload['Interface']['hamonitor'] = True

    if haheartbeat:
        payload['Interface']['haheartbeat'] = True

    if mtu:
        payload['Interface']['mtu'] = True

    if tagall:
        payload['Interface']['tagall'] = True

    if trunk:
        payload['Interface']['trunk'] = True

    if trunkmode:
        payload['Interface']['trunkmode'] = True

    if trunkallowedvlan:
        payload['Interface']['trunkallowedvlan'] = True

    if lacpmode:
        payload['Interface']['lacpmode'] = True

    if lacpkey:
        payload['Interface']['lacpkey'] = True

    if lagtype:
        payload['Interface']['lagtype'] = True

    if lacppriority:
        payload['Interface']['lacppriority'] = True

    if lacptimeout:
        payload['Interface']['lacptimeout'] = True

    if ifalias:
        payload['Interface']['ifalias'] = True

    if throughput:
        payload['Interface']['throughput'] = True

    if linkredundancy:
        payload['Interface']['linkredundancy'] = True

    if bandwidthhigh:
        payload['Interface']['bandwidthhigh'] = True

    if bandwidthnormal:
        payload['Interface']['bandwidthnormal'] = True

    if lldpmode:
        payload['Interface']['lldpmode'] = True

    if lrsetpriority:
        payload['Interface']['lrsetpriority'] = True

    execution = __proxy__['citrixns.post']('config/Interface?action=unset', payload)

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


def unset_ip6tunnelparam(srcip=None, dropfrag=None, dropfragcputhreshold=None, srciproundrobin=None, save=False):
    '''
    Unsets values from the ip6tunnelparam configuration key.

    srcip(bool): Unsets the srcip value.

    dropfrag(bool): Unsets the dropfrag value.

    dropfragcputhreshold(bool): Unsets the dropfragcputhreshold value.

    srciproundrobin(bool): Unsets the srciproundrobin value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_ip6tunnelparam <args>

    '''

    result = {}

    payload = {'ip6tunnelparam': {}}

    if srcip:
        payload['ip6tunnelparam']['srcip'] = True

    if dropfrag:
        payload['ip6tunnelparam']['dropfrag'] = True

    if dropfragcputhreshold:
        payload['ip6tunnelparam']['dropfragcputhreshold'] = True

    if srciproundrobin:
        payload['ip6tunnelparam']['srciproundrobin'] = True

    execution = __proxy__['citrixns.post']('config/ip6tunnelparam?action=unset', payload)

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


def unset_iptunnelparam(srcip=None, dropfrag=None, dropfragcputhreshold=None, srciproundrobin=None, enablestrictrx=None,
                        enablestricttx=None, mac=None, save=False):
    '''
    Unsets values from the iptunnelparam configuration key.

    srcip(bool): Unsets the srcip value.

    dropfrag(bool): Unsets the dropfrag value.

    dropfragcputhreshold(bool): Unsets the dropfragcputhreshold value.

    srciproundrobin(bool): Unsets the srciproundrobin value.

    enablestrictrx(bool): Unsets the enablestrictrx value.

    enablestricttx(bool): Unsets the enablestricttx value.

    mac(bool): Unsets the mac value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_iptunnelparam <args>

    '''

    result = {}

    payload = {'iptunnelparam': {}}

    if srcip:
        payload['iptunnelparam']['srcip'] = True

    if dropfrag:
        payload['iptunnelparam']['dropfrag'] = True

    if dropfragcputhreshold:
        payload['iptunnelparam']['dropfragcputhreshold'] = True

    if srciproundrobin:
        payload['iptunnelparam']['srciproundrobin'] = True

    if enablestrictrx:
        payload['iptunnelparam']['enablestrictrx'] = True

    if enablestricttx:
        payload['iptunnelparam']['enablestricttx'] = True

    if mac:
        payload['iptunnelparam']['mac'] = True

    execution = __proxy__['citrixns.post']('config/iptunnelparam?action=unset', payload)

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


def unset_ipv6(ralearning=None, routerredirection=None, ndbasereachtime=None, ndretransmissiontime=None, natprefix=None,
               td=None, dodad=None, save=False):
    '''
    Unsets values from the ipv6 configuration key.

    ralearning(bool): Unsets the ralearning value.

    routerredirection(bool): Unsets the routerredirection value.

    ndbasereachtime(bool): Unsets the ndbasereachtime value.

    ndretransmissiontime(bool): Unsets the ndretransmissiontime value.

    natprefix(bool): Unsets the natprefix value.

    td(bool): Unsets the td value.

    dodad(bool): Unsets the dodad value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_ipv6 <args>

    '''

    result = {}

    payload = {'ipv6': {}}

    if ralearning:
        payload['ipv6']['ralearning'] = True

    if routerredirection:
        payload['ipv6']['routerredirection'] = True

    if ndbasereachtime:
        payload['ipv6']['ndbasereachtime'] = True

    if ndretransmissiontime:
        payload['ipv6']['ndretransmissiontime'] = True

    if natprefix:
        payload['ipv6']['natprefix'] = True

    if td:
        payload['ipv6']['td'] = True

    if dodad:
        payload['ipv6']['dodad'] = True

    execution = __proxy__['citrixns.post']('config/ipv6?action=unset', payload)

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


def unset_l2param(mbfpeermacupdate=None, maxbridgecollision=None, bdggrpproxyarp=None, bdgsetting=None,
                  garponvridintf=None, macmodefwdmypkt=None, usemymac=None, proxyarp=None, garpreply=None,
                  mbfinstlearning=None, rstintfonhafo=None, skipproxyingbsdtraffic=None, returntoethernetsender=None,
                  stopmacmoveupdate=None, bridgeagetimeout=None, save=False):
    '''
    Unsets values from the l2param configuration key.

    mbfpeermacupdate(bool): Unsets the mbfpeermacupdate value.

    maxbridgecollision(bool): Unsets the maxbridgecollision value.

    bdggrpproxyarp(bool): Unsets the bdggrpproxyarp value.

    bdgsetting(bool): Unsets the bdgsetting value.

    garponvridintf(bool): Unsets the garponvridintf value.

    macmodefwdmypkt(bool): Unsets the macmodefwdmypkt value.

    usemymac(bool): Unsets the usemymac value.

    proxyarp(bool): Unsets the proxyarp value.

    garpreply(bool): Unsets the garpreply value.

    mbfinstlearning(bool): Unsets the mbfinstlearning value.

    rstintfonhafo(bool): Unsets the rstintfonhafo value.

    skipproxyingbsdtraffic(bool): Unsets the skipproxyingbsdtraffic value.

    returntoethernetsender(bool): Unsets the returntoethernetsender value.

    stopmacmoveupdate(bool): Unsets the stopmacmoveupdate value.

    bridgeagetimeout(bool): Unsets the bridgeagetimeout value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_l2param <args>

    '''

    result = {}

    payload = {'l2param': {}}

    if mbfpeermacupdate:
        payload['l2param']['mbfpeermacupdate'] = True

    if maxbridgecollision:
        payload['l2param']['maxbridgecollision'] = True

    if bdggrpproxyarp:
        payload['l2param']['bdggrpproxyarp'] = True

    if bdgsetting:
        payload['l2param']['bdgsetting'] = True

    if garponvridintf:
        payload['l2param']['garponvridintf'] = True

    if macmodefwdmypkt:
        payload['l2param']['macmodefwdmypkt'] = True

    if usemymac:
        payload['l2param']['usemymac'] = True

    if proxyarp:
        payload['l2param']['proxyarp'] = True

    if garpreply:
        payload['l2param']['garpreply'] = True

    if mbfinstlearning:
        payload['l2param']['mbfinstlearning'] = True

    if rstintfonhafo:
        payload['l2param']['rstintfonhafo'] = True

    if skipproxyingbsdtraffic:
        payload['l2param']['skipproxyingbsdtraffic'] = True

    if returntoethernetsender:
        payload['l2param']['returntoethernetsender'] = True

    if stopmacmoveupdate:
        payload['l2param']['stopmacmoveupdate'] = True

    if bridgeagetimeout:
        payload['l2param']['bridgeagetimeout'] = True

    execution = __proxy__['citrixns.post']('config/l2param?action=unset', payload)

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


def unset_l3param(srcnat=None, icmpgenratethreshold=None, overridernat=None, dropdfflag=None, miproundrobin=None,
                  externalloopback=None, tnlpmtuwoconn=None, usipserverstraypkt=None, forwardicmpfragments=None,
                  dropipfragments=None, acllogtime=None, implicitaclallow=None, dynamicrouting=None,
                  ipv6dynamicrouting=None, save=False):
    '''
    Unsets values from the l3param configuration key.

    srcnat(bool): Unsets the srcnat value.

    icmpgenratethreshold(bool): Unsets the icmpgenratethreshold value.

    overridernat(bool): Unsets the overridernat value.

    dropdfflag(bool): Unsets the dropdfflag value.

    miproundrobin(bool): Unsets the miproundrobin value.

    externalloopback(bool): Unsets the externalloopback value.

    tnlpmtuwoconn(bool): Unsets the tnlpmtuwoconn value.

    usipserverstraypkt(bool): Unsets the usipserverstraypkt value.

    forwardicmpfragments(bool): Unsets the forwardicmpfragments value.

    dropipfragments(bool): Unsets the dropipfragments value.

    acllogtime(bool): Unsets the acllogtime value.

    implicitaclallow(bool): Unsets the implicitaclallow value.

    dynamicrouting(bool): Unsets the dynamicrouting value.

    ipv6dynamicrouting(bool): Unsets the ipv6dynamicrouting value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_l3param <args>

    '''

    result = {}

    payload = {'l3param': {}}

    if srcnat:
        payload['l3param']['srcnat'] = True

    if icmpgenratethreshold:
        payload['l3param']['icmpgenratethreshold'] = True

    if overridernat:
        payload['l3param']['overridernat'] = True

    if dropdfflag:
        payload['l3param']['dropdfflag'] = True

    if miproundrobin:
        payload['l3param']['miproundrobin'] = True

    if externalloopback:
        payload['l3param']['externalloopback'] = True

    if tnlpmtuwoconn:
        payload['l3param']['tnlpmtuwoconn'] = True

    if usipserverstraypkt:
        payload['l3param']['usipserverstraypkt'] = True

    if forwardicmpfragments:
        payload['l3param']['forwardicmpfragments'] = True

    if dropipfragments:
        payload['l3param']['dropipfragments'] = True

    if acllogtime:
        payload['l3param']['acllogtime'] = True

    if implicitaclallow:
        payload['l3param']['implicitaclallow'] = True

    if dynamicrouting:
        payload['l3param']['dynamicrouting'] = True

    if ipv6dynamicrouting:
        payload['l3param']['ipv6dynamicrouting'] = True

    execution = __proxy__['citrixns.post']('config/l3param?action=unset', payload)

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


def unset_l4param(l2connmethod=None, l4switch=None, save=False):
    '''
    Unsets values from the l4param configuration key.

    l2connmethod(bool): Unsets the l2connmethod value.

    l4switch(bool): Unsets the l4switch value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_l4param <args>

    '''

    result = {}

    payload = {'l4param': {}}

    if l2connmethod:
        payload['l4param']['l2connmethod'] = True

    if l4switch:
        payload['l4param']['l4switch'] = True

    execution = __proxy__['citrixns.post']('config/l4param?action=unset', payload)

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


def unset_nat64(name=None, acl6name=None, netprofile=None, save=False):
    '''
    Unsets values from the nat64 configuration key.

    name(bool): Unsets the name value.

    acl6name(bool): Unsets the acl6name value.

    netprofile(bool): Unsets the netprofile value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_nat64 <args>

    '''

    result = {}

    payload = {'nat64': {}}

    if name:
        payload['nat64']['name'] = True

    if acl6name:
        payload['nat64']['acl6name'] = True

    if netprofile:
        payload['nat64']['netprofile'] = True

    execution = __proxy__['citrixns.post']('config/nat64?action=unset', payload)

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


def unset_nat64param(td=None, nat64ignoretos=None, nat64zerochecksum=None, nat64v6mtu=None, nat64fragheader=None,
                     save=False):
    '''
    Unsets values from the nat64param configuration key.

    td(bool): Unsets the td value.

    nat64ignoretos(bool): Unsets the nat64ignoretos value.

    nat64zerochecksum(bool): Unsets the nat64zerochecksum value.

    nat64v6mtu(bool): Unsets the nat64v6mtu value.

    nat64fragheader(bool): Unsets the nat64fragheader value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_nat64param <args>

    '''

    result = {}

    payload = {'nat64param': {}}

    if td:
        payload['nat64param']['td'] = True

    if nat64ignoretos:
        payload['nat64param']['nat64ignoretos'] = True

    if nat64zerochecksum:
        payload['nat64param']['nat64zerochecksum'] = True

    if nat64v6mtu:
        payload['nat64param']['nat64v6mtu'] = True

    if nat64fragheader:
        payload['nat64param']['nat64fragheader'] = True

    execution = __proxy__['citrixns.post']('config/nat64param?action=unset', payload)

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


def unset_nd6ravariables(vlan=None, ceaserouteradv=None, sendrouteradv=None, srclinklayeraddroption=None,
                         onlyunicastrtadvresponse=None, managedaddrconfig=None, otheraddrconfig=None, currhoplimit=None,
                         maxrtadvinterval=None, minrtadvinterval=None, linkmtu=None, reachabletime=None,
                         retranstime=None, defaultlifetime=None, save=False):
    '''
    Unsets values from the nd6ravariables configuration key.

    vlan(bool): Unsets the vlan value.

    ceaserouteradv(bool): Unsets the ceaserouteradv value.

    sendrouteradv(bool): Unsets the sendrouteradv value.

    srclinklayeraddroption(bool): Unsets the srclinklayeraddroption value.

    onlyunicastrtadvresponse(bool): Unsets the onlyunicastrtadvresponse value.

    managedaddrconfig(bool): Unsets the managedaddrconfig value.

    otheraddrconfig(bool): Unsets the otheraddrconfig value.

    currhoplimit(bool): Unsets the currhoplimit value.

    maxrtadvinterval(bool): Unsets the maxrtadvinterval value.

    minrtadvinterval(bool): Unsets the minrtadvinterval value.

    linkmtu(bool): Unsets the linkmtu value.

    reachabletime(bool): Unsets the reachabletime value.

    retranstime(bool): Unsets the retranstime value.

    defaultlifetime(bool): Unsets the defaultlifetime value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_nd6ravariables <args>

    '''

    result = {}

    payload = {'nd6ravariables': {}}

    if vlan:
        payload['nd6ravariables']['vlan'] = True

    if ceaserouteradv:
        payload['nd6ravariables']['ceaserouteradv'] = True

    if sendrouteradv:
        payload['nd6ravariables']['sendrouteradv'] = True

    if srclinklayeraddroption:
        payload['nd6ravariables']['srclinklayeraddroption'] = True

    if onlyunicastrtadvresponse:
        payload['nd6ravariables']['onlyunicastrtadvresponse'] = True

    if managedaddrconfig:
        payload['nd6ravariables']['managedaddrconfig'] = True

    if otheraddrconfig:
        payload['nd6ravariables']['otheraddrconfig'] = True

    if currhoplimit:
        payload['nd6ravariables']['currhoplimit'] = True

    if maxrtadvinterval:
        payload['nd6ravariables']['maxrtadvinterval'] = True

    if minrtadvinterval:
        payload['nd6ravariables']['minrtadvinterval'] = True

    if linkmtu:
        payload['nd6ravariables']['linkmtu'] = True

    if reachabletime:
        payload['nd6ravariables']['reachabletime'] = True

    if retranstime:
        payload['nd6ravariables']['retranstime'] = True

    if defaultlifetime:
        payload['nd6ravariables']['defaultlifetime'] = True

    execution = __proxy__['citrixns.post']('config/nd6ravariables?action=unset', payload)

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


def unset_netbridge(name=None, vxlanvlanmap=None, save=False):
    '''
    Unsets values from the netbridge configuration key.

    name(bool): Unsets the name value.

    vxlanvlanmap(bool): Unsets the vxlanvlanmap value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_netbridge <args>

    '''

    result = {}

    payload = {'netbridge': {}}

    if name:
        payload['netbridge']['name'] = True

    if vxlanvlanmap:
        payload['netbridge']['vxlanvlanmap'] = True

    execution = __proxy__['citrixns.post']('config/netbridge?action=unset', payload)

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


def unset_netprofile(name=None, td=None, srcip=None, srcippersistency=None, overridelsn=None, save=False):
    '''
    Unsets values from the netprofile configuration key.

    name(bool): Unsets the name value.

    td(bool): Unsets the td value.

    srcip(bool): Unsets the srcip value.

    srcippersistency(bool): Unsets the srcippersistency value.

    overridelsn(bool): Unsets the overridelsn value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_netprofile <args>

    '''

    result = {}

    payload = {'netprofile': {}}

    if name:
        payload['netprofile']['name'] = True

    if td:
        payload['netprofile']['td'] = True

    if srcip:
        payload['netprofile']['srcip'] = True

    if srcippersistency:
        payload['netprofile']['srcippersistency'] = True

    if overridelsn:
        payload['netprofile']['overridelsn'] = True

    execution = __proxy__['citrixns.post']('config/netprofile?action=unset', payload)

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


def unset_onlinkipv6prefix(ipv6prefix=None, onlinkprefix=None, autonomusprefix=None, depricateprefix=None,
                           decrementprefixlifetimes=None, prefixvalidelifetime=None, prefixpreferredlifetime=None,
                           save=False):
    '''
    Unsets values from the onlinkipv6prefix configuration key.

    ipv6prefix(bool): Unsets the ipv6prefix value.

    onlinkprefix(bool): Unsets the onlinkprefix value.

    autonomusprefix(bool): Unsets the autonomusprefix value.

    depricateprefix(bool): Unsets the depricateprefix value.

    decrementprefixlifetimes(bool): Unsets the decrementprefixlifetimes value.

    prefixvalidelifetime(bool): Unsets the prefixvalidelifetime value.

    prefixpreferredlifetime(bool): Unsets the prefixpreferredlifetime value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_onlinkipv6prefix <args>

    '''

    result = {}

    payload = {'onlinkipv6prefix': {}}

    if ipv6prefix:
        payload['onlinkipv6prefix']['ipv6prefix'] = True

    if onlinkprefix:
        payload['onlinkipv6prefix']['onlinkprefix'] = True

    if autonomusprefix:
        payload['onlinkipv6prefix']['autonomusprefix'] = True

    if depricateprefix:
        payload['onlinkipv6prefix']['depricateprefix'] = True

    if decrementprefixlifetimes:
        payload['onlinkipv6prefix']['decrementprefixlifetimes'] = True

    if prefixvalidelifetime:
        payload['onlinkipv6prefix']['prefixvalidelifetime'] = True

    if prefixpreferredlifetime:
        payload['onlinkipv6prefix']['prefixpreferredlifetime'] = True

    execution = __proxy__['citrixns.post']('config/onlinkipv6prefix?action=unset', payload)

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


def unset_rnat(network=None, netmask=None, aclname=None, redirectport=None, natip=None, td=None, ownergroup=None,
               natip2=None, srcippersistency=None, useproxyport=None, connfailover=None, save=False):
    '''
    Unsets values from the rnat configuration key.

    network(bool): Unsets the network value.

    netmask(bool): Unsets the netmask value.

    aclname(bool): Unsets the aclname value.

    redirectport(bool): Unsets the redirectport value.

    natip(bool): Unsets the natip value.

    td(bool): Unsets the td value.

    ownergroup(bool): Unsets the ownergroup value.

    natip2(bool): Unsets the natip2 value.

    srcippersistency(bool): Unsets the srcippersistency value.

    useproxyport(bool): Unsets the useproxyport value.

    connfailover(bool): Unsets the connfailover value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_rnat <args>

    '''

    result = {}

    payload = {'rnat': {}}

    if network:
        payload['rnat']['network'] = True

    if netmask:
        payload['rnat']['netmask'] = True

    if aclname:
        payload['rnat']['aclname'] = True

    if redirectport:
        payload['rnat']['redirectport'] = True

    if natip:
        payload['rnat']['natip'] = True

    if td:
        payload['rnat']['td'] = True

    if ownergroup:
        payload['rnat']['ownergroup'] = True

    if natip2:
        payload['rnat']['natip2'] = True

    if srcippersistency:
        payload['rnat']['srcippersistency'] = True

    if useproxyport:
        payload['rnat']['useproxyport'] = True

    if connfailover:
        payload['rnat']['connfailover'] = True

    execution = __proxy__['citrixns.post']('config/rnat?action=unset', payload)

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


def unset_rnat6(name=None, network=None, acl6name=None, redirectport=None, td=None, srcippersistency=None,
                ownergroup=None, save=False):
    '''
    Unsets values from the rnat6 configuration key.

    name(bool): Unsets the name value.

    network(bool): Unsets the network value.

    acl6name(bool): Unsets the acl6name value.

    redirectport(bool): Unsets the redirectport value.

    td(bool): Unsets the td value.

    srcippersistency(bool): Unsets the srcippersistency value.

    ownergroup(bool): Unsets the ownergroup value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_rnat6 <args>

    '''

    result = {}

    payload = {'rnat6': {}}

    if name:
        payload['rnat6']['name'] = True

    if network:
        payload['rnat6']['network'] = True

    if acl6name:
        payload['rnat6']['acl6name'] = True

    if redirectport:
        payload['rnat6']['redirectport'] = True

    if td:
        payload['rnat6']['td'] = True

    if srcippersistency:
        payload['rnat6']['srcippersistency'] = True

    if ownergroup:
        payload['rnat6']['ownergroup'] = True

    execution = __proxy__['citrixns.post']('config/rnat6?action=unset', payload)

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


def unset_rnatparam(tcpproxy=None, srcippersistency=None, save=False):
    '''
    Unsets values from the rnatparam configuration key.

    tcpproxy(bool): Unsets the tcpproxy value.

    srcippersistency(bool): Unsets the srcippersistency value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_rnatparam <args>

    '''

    result = {}

    payload = {'rnatparam': {}}

    if tcpproxy:
        payload['rnatparam']['tcpproxy'] = True

    if srcippersistency:
        payload['rnatparam']['srcippersistency'] = True

    execution = __proxy__['citrixns.post']('config/rnatparam?action=unset', payload)

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


def unset_route(network=None, netmask=None, gateway=None, cost=None, td=None, distance=None, cost1=None, weight=None,
                advertise=None, protocol=None, msr=None, monitor=None, ownergroup=None, routetype=None, detail=None,
                save=False):
    '''
    Unsets values from the route configuration key.

    network(bool): Unsets the network value.

    netmask(bool): Unsets the netmask value.

    gateway(bool): Unsets the gateway value.

    cost(bool): Unsets the cost value.

    td(bool): Unsets the td value.

    distance(bool): Unsets the distance value.

    cost1(bool): Unsets the cost1 value.

    weight(bool): Unsets the weight value.

    advertise(bool): Unsets the advertise value.

    protocol(bool): Unsets the protocol value.

    msr(bool): Unsets the msr value.

    monitor(bool): Unsets the monitor value.

    ownergroup(bool): Unsets the ownergroup value.

    routetype(bool): Unsets the routetype value.

    detail(bool): Unsets the detail value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_route <args>

    '''

    result = {}

    payload = {'route': {}}

    if network:
        payload['route']['network'] = True

    if netmask:
        payload['route']['netmask'] = True

    if gateway:
        payload['route']['gateway'] = True

    if cost:
        payload['route']['cost'] = True

    if td:
        payload['route']['td'] = True

    if distance:
        payload['route']['distance'] = True

    if cost1:
        payload['route']['cost1'] = True

    if weight:
        payload['route']['weight'] = True

    if advertise:
        payload['route']['advertise'] = True

    if protocol:
        payload['route']['protocol'] = True

    if msr:
        payload['route']['msr'] = True

    if monitor:
        payload['route']['monitor'] = True

    if ownergroup:
        payload['route']['ownergroup'] = True

    if routetype:
        payload['route']['routetype'] = True

    if detail:
        payload['route']['detail'] = True

    execution = __proxy__['citrixns.post']('config/route?action=unset', payload)

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


def unset_route6(network=None, gateway=None, vlan=None, vxlan=None, weight=None, distance=None, cost=None,
                 advertise=None, msr=None, monitor=None, td=None, ownergroup=None, routetype=None, detail=None,
                 save=False):
    '''
    Unsets values from the route6 configuration key.

    network(bool): Unsets the network value.

    gateway(bool): Unsets the gateway value.

    vlan(bool): Unsets the vlan value.

    vxlan(bool): Unsets the vxlan value.

    weight(bool): Unsets the weight value.

    distance(bool): Unsets the distance value.

    cost(bool): Unsets the cost value.

    advertise(bool): Unsets the advertise value.

    msr(bool): Unsets the msr value.

    monitor(bool): Unsets the monitor value.

    td(bool): Unsets the td value.

    ownergroup(bool): Unsets the ownergroup value.

    routetype(bool): Unsets the routetype value.

    detail(bool): Unsets the detail value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_route6 <args>

    '''

    result = {}

    payload = {'route6': {}}

    if network:
        payload['route6']['network'] = True

    if gateway:
        payload['route6']['gateway'] = True

    if vlan:
        payload['route6']['vlan'] = True

    if vxlan:
        payload['route6']['vxlan'] = True

    if weight:
        payload['route6']['weight'] = True

    if distance:
        payload['route6']['distance'] = True

    if cost:
        payload['route6']['cost'] = True

    if advertise:
        payload['route6']['advertise'] = True

    if msr:
        payload['route6']['msr'] = True

    if monitor:
        payload['route6']['monitor'] = True

    if td:
        payload['route6']['td'] = True

    if ownergroup:
        payload['route6']['ownergroup'] = True

    if routetype:
        payload['route6']['routetype'] = True

    if detail:
        payload['route6']['detail'] = True

    execution = __proxy__['citrixns.post']('config/route6?action=unset', payload)

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


def unset_vlan(id=None, aliasname=None, dynamicrouting=None, ipv6dynamicrouting=None, mtu=None, sharing=None,
               save=False):
    '''
    Unsets values from the vlan configuration key.

    id(bool): Unsets the id value.

    aliasname(bool): Unsets the aliasname value.

    dynamicrouting(bool): Unsets the dynamicrouting value.

    ipv6dynamicrouting(bool): Unsets the ipv6dynamicrouting value.

    mtu(bool): Unsets the mtu value.

    sharing(bool): Unsets the sharing value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_vlan <args>

    '''

    result = {}

    payload = {'vlan': {}}

    if id:
        payload['vlan']['id'] = True

    if aliasname:
        payload['vlan']['aliasname'] = True

    if dynamicrouting:
        payload['vlan']['dynamicrouting'] = True

    if ipv6dynamicrouting:
        payload['vlan']['ipv6dynamicrouting'] = True

    if mtu:
        payload['vlan']['mtu'] = True

    if sharing:
        payload['vlan']['sharing'] = True

    execution = __proxy__['citrixns.post']('config/vlan?action=unset', payload)

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


def unset_vrid(id=None, priority=None, preemption=None, sharing=None, tracking=None, ownernode=None,
               trackifnumpriority=None, preemptiondelaytimer=None, save=False):
    '''
    Unsets values from the vrid configuration key.

    id(bool): Unsets the id value.

    priority(bool): Unsets the priority value.

    preemption(bool): Unsets the preemption value.

    sharing(bool): Unsets the sharing value.

    tracking(bool): Unsets the tracking value.

    ownernode(bool): Unsets the ownernode value.

    trackifnumpriority(bool): Unsets the trackifnumpriority value.

    preemptiondelaytimer(bool): Unsets the preemptiondelaytimer value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_vrid <args>

    '''

    result = {}

    payload = {'vrid': {}}

    if id:
        payload['vrid']['id'] = True

    if priority:
        payload['vrid']['priority'] = True

    if preemption:
        payload['vrid']['preemption'] = True

    if sharing:
        payload['vrid']['sharing'] = True

    if tracking:
        payload['vrid']['tracking'] = True

    if ownernode:
        payload['vrid']['ownernode'] = True

    if trackifnumpriority:
        payload['vrid']['trackifnumpriority'] = True

    if preemptiondelaytimer:
        payload['vrid']['preemptiondelaytimer'] = True

    execution = __proxy__['citrixns.post']('config/vrid?action=unset', payload)

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


def unset_vrid6(id=None, priority=None, preemption=None, sharing=None, tracking=None, preemptiondelaytimer=None,
                trackifnumpriority=None, ownernode=None, save=False):
    '''
    Unsets values from the vrid6 configuration key.

    id(bool): Unsets the id value.

    priority(bool): Unsets the priority value.

    preemption(bool): Unsets the preemption value.

    sharing(bool): Unsets the sharing value.

    tracking(bool): Unsets the tracking value.

    preemptiondelaytimer(bool): Unsets the preemptiondelaytimer value.

    trackifnumpriority(bool): Unsets the trackifnumpriority value.

    ownernode(bool): Unsets the ownernode value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_vrid6 <args>

    '''

    result = {}

    payload = {'vrid6': {}}

    if id:
        payload['vrid6']['id'] = True

    if priority:
        payload['vrid6']['priority'] = True

    if preemption:
        payload['vrid6']['preemption'] = True

    if sharing:
        payload['vrid6']['sharing'] = True

    if tracking:
        payload['vrid6']['tracking'] = True

    if preemptiondelaytimer:
        payload['vrid6']['preemptiondelaytimer'] = True

    if trackifnumpriority:
        payload['vrid6']['trackifnumpriority'] = True

    if ownernode:
        payload['vrid6']['ownernode'] = True

    execution = __proxy__['citrixns.post']('config/vrid6?action=unset', payload)

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


def unset_vridparam(sendtomaster=None, hellointerval=None, deadinterval=None, save=False):
    '''
    Unsets values from the vridparam configuration key.

    sendtomaster(bool): Unsets the sendtomaster value.

    hellointerval(bool): Unsets the hellointerval value.

    deadinterval(bool): Unsets the deadinterval value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_vridparam <args>

    '''

    result = {}

    payload = {'vridparam': {}}

    if sendtomaster:
        payload['vridparam']['sendtomaster'] = True

    if hellointerval:
        payload['vridparam']['hellointerval'] = True

    if deadinterval:
        payload['vridparam']['deadinterval'] = True

    execution = __proxy__['citrixns.post']('config/vridparam?action=unset', payload)

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


def unset_vxlan(id=None, vlan=None, port=None, dynamicrouting=None, ipv6dynamicrouting=None, ns_type=None, protocol=None,
                innervlantagging=None, save=False):
    '''
    Unsets values from the vxlan configuration key.

    id(bool): Unsets the id value.

    vlan(bool): Unsets the vlan value.

    port(bool): Unsets the port value.

    dynamicrouting(bool): Unsets the dynamicrouting value.

    ipv6dynamicrouting(bool): Unsets the ipv6dynamicrouting value.

    ns_type(bool): Unsets the ns_type value.

    protocol(bool): Unsets the protocol value.

    innervlantagging(bool): Unsets the innervlantagging value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.unset_vxlan <args>

    '''

    result = {}

    payload = {'vxlan': {}}

    if id:
        payload['vxlan']['id'] = True

    if vlan:
        payload['vxlan']['vlan'] = True

    if port:
        payload['vxlan']['port'] = True

    if dynamicrouting:
        payload['vxlan']['dynamicrouting'] = True

    if ipv6dynamicrouting:
        payload['vxlan']['ipv6dynamicrouting'] = True

    if ns_type:
        payload['vxlan']['type'] = True

    if protocol:
        payload['vxlan']['protocol'] = True

    if innervlantagging:
        payload['vxlan']['innervlantagging'] = True

    execution = __proxy__['citrixns.post']('config/vxlan?action=unset', payload)

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


def update_appalgparam(pptpgreidletimeout=None, save=False):
    '''
    Update the running configuration for the appalgparam config key.

    pptpgreidletimeout(int): Interval in sec, after which data sessions of PPTP GRE is cleared. Default value: 9000 Minimum
        value = 1 Maximum value = 9000

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_appalgparam <args>

    '''

    result = {}

    payload = {'appalgparam': {}}

    if pptpgreidletimeout:
        payload['appalgparam']['pptpgreidletimeout'] = pptpgreidletimeout

    execution = __proxy__['citrixns.put']('config/appalgparam', payload)

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


def update_arpparam(timeout=None, spoofvalidation=None, save=False):
    '''
    Update the running configuration for the arpparam config key.

    timeout(int): Time-out value (aging time) for the dynamically learned ARP entries, in seconds. The new value applies only
        to ARP entries that are dynamically learned after the new value is set. Previously existing ARP entries expire
        after the previously configured aging time. Default value: 1200 Minimum value = 5 Maximum value = 1200

    spoofvalidation(str): enable/disable arp spoofing validation. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_arpparam <args>

    '''

    result = {}

    payload = {'arpparam': {}}

    if timeout:
        payload['arpparam']['timeout'] = timeout

    if spoofvalidation:
        payload['arpparam']['spoofvalidation'] = spoofvalidation

    execution = __proxy__['citrixns.put']('config/arpparam', payload)

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


def update_bridgegroup(id=None, dynamicrouting=None, ipv6dynamicrouting=None, save=False):
    '''
    Update the running configuration for the bridgegroup config key.

    id(int): An integer that uniquely identifies the bridge group. Minimum value = 1 Maximum value = 1000

    dynamicrouting(str): Enable dynamic routing for this bridgegroup. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    ipv6dynamicrouting(str): Enable all IPv6 dynamic routing protocols on all VLANs bound to this bridgegroup. Note: For the
        ENABLED setting to work, you must configure IPv6 dynamic routing protocols from the VTYSH command line. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_bridgegroup <args>

    '''

    result = {}

    payload = {'bridgegroup': {}}

    if id:
        payload['bridgegroup']['id'] = id

    if dynamicrouting:
        payload['bridgegroup']['dynamicrouting'] = dynamicrouting

    if ipv6dynamicrouting:
        payload['bridgegroup']['ipv6dynamicrouting'] = ipv6dynamicrouting

    execution = __proxy__['citrixns.put']('config/bridgegroup', payload)

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


def update_bridgetable(mac=None, vxlan=None, vtep=None, vni=None, devicevlan=None, bridgeage=None, nodeid=None,
                       vlan=None, ifnum=None, save=False):
    '''
    Update the running configuration for the bridgetable config key.

    mac(str): The MAC address of the target.

    vxlan(int): The VXLAN to which this address is associated. Minimum value = 1 Maximum value = 16777215

    vtep(str): The IP address of the destination VXLAN tunnel endpoint where the Ethernet MAC ADDRESS resides. Minimum length
        = 1

    vni(int): The VXLAN VNI Network Identifier (or VXLAN Segment ID) to use to connect to the remote VXLAN tunnel endpoint.
        If omitted the value specified as vxlan will be used. Minimum value = 1 Maximum value = 16777215

    devicevlan(int): The vlan on which to send multicast packets when the VXLAN tunnel endpoint is a muticast group address.
        Minimum value = 1 Maximum value = 4094

    bridgeage(int): Time-out value for the bridge table entries, in seconds. The new value applies only to the entries that
        are dynamically learned after the new value is set. Previously existing bridge table entries expire after the
        previously configured time-out value. Default value: 300 Minimum value = 60 Maximum value = 300

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    vlan(int): VLAN whose entries are to be removed. Minimum value = 1 Maximum value = 4094

    ifnum(str): INTERFACE whose entries are to be removed.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_bridgetable <args>

    '''

    result = {}

    payload = {'bridgetable': {}}

    if mac:
        payload['bridgetable']['mac'] = mac

    if vxlan:
        payload['bridgetable']['vxlan'] = vxlan

    if vtep:
        payload['bridgetable']['vtep'] = vtep

    if vni:
        payload['bridgetable']['vni'] = vni

    if devicevlan:
        payload['bridgetable']['devicevlan'] = devicevlan

    if bridgeage:
        payload['bridgetable']['bridgeage'] = bridgeage

    if nodeid:
        payload['bridgetable']['nodeid'] = nodeid

    if vlan:
        payload['bridgetable']['vlan'] = vlan

    if ifnum:
        payload['bridgetable']['ifnum'] = ifnum

    execution = __proxy__['citrixns.put']('config/bridgetable', payload)

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


def update_channel(id=None, ifnum=None, state=None, mode=None, conndistr=None, macdistr=None, lamac=None, speed=None,
                   flowctl=None, hamonitor=None, haheartbeat=None, tagall=None, trunk=None, ifalias=None,
                   throughput=None, bandwidthhigh=None, bandwidthnormal=None, mtu=None, lrminthroughput=None,
                   linkredundancy=None, save=False):
    '''
    Update the running configuration for the channel config key.

    id(str): ID for the LA channel or cluster LA channel or LR channel to be created. Specify an LA channel in LA/x notation,
        where x can range from 1 to 8 or cluster LA channel in CLA/x notation or Link redundant channel in LR/x notation,
        where x can range from 1 to 4. Cannot be changed after the LA channel is created.

    ifnum(list(str)): Interfaces to be bound to the LA channel of a NetScaler appliance or to the LA channel of a cluster
        configuration. For an LA channel of a NetScaler appliance, specify an interface in C/U notation (for example,
        1/3).  For an LA channel of a cluster configuration, specify an interface in N/C/U notation (for example, 2/1/3).
        where C can take one of the following values: * 0 - Indicates a management interface. * 1 - Indicates a 1 Gbps
        port. * 10 - Indicates a 10 Gbps port. U is a unique integer for representing an interface in a particular port
        group. N is the ID of the node to which an interface belongs in a cluster configuration. Use spaces to separate
        multiple entries.

    state(str): Enable or disable the LA channel. Default value: ENABLED Possible values = ENABLED, DISABLED

    mode(str): The initital mode for the LA channel. Possible values = MANUAL, AUTO

    conndistr(str): The connection distribution mode for the LA channel. Possible values = DISABLED, ENABLED

    macdistr(str): The MAC distribution mode for the LA channel. Possible values = SOURCE, DESTINATION, BOTH

    lamac(str): Specifies a MAC address for the LA channels configured in NetScaler virtual appliances (VPX). This MAC
        address is persistent after each reboot.  If you dont specify this parameter, a MAC address is generated randomly
        for each LA channel. These MAC addresses change after each reboot.

    speed(str): Ethernet speed of the channel, in Mbps. If the speed of any bound interface is greater than or equal to the
        value set for this parameter, the state of the interface is UP. Otherwise, the state is INACTIVE. Bound
        Interfaces whose state is INACTIVE do not process any traffic. Default value: AUTO Possible values = AUTO, 10,
        100, 1000, 10000, 40000

    flowctl(str): Specifies the flow control type for this LA channel to manage the flow of frames. Flow control is a
        function as mentioned in clause 31 of the IEEE 802.3 standard. Flow control allows congested ports to pause
        traffic from the peer device. Flow control is achieved by sending PAUSE frames. Default value: OFF Possible
        values = OFF, RX, TX, RXTX, ON

    hamonitor(str): In a High Availability (HA) configuration, monitor the LA channel for failure events. Failure of any LA
        channel that has HA MON enabled triggers HA failover. Default value: ON Possible values = ON, OFF

    haheartbeat(str): In a High Availability (HA) configuration, configure the LA channel for sending heartbeats. LA channel
        that has HA Heartbeat disabled should not send the heartbeats. Default value: ON Possible values = OFF, ON

    tagall(str): Adds a four-byte 802.1q tag to every packet sent on this channel. The ON setting applies tags for all VLANs
        that are bound to this channel. OFF applies the tag for all VLANs other than the native VLAN. Default value: OFF
        Possible values = ON, OFF

    trunk(str): This is deprecated by tagall. Default value: OFF Possible values = ON, OFF

    ifalias(str): Alias name for the LA channel. Used only to enhance readability. To perform any operations, you have to
        specify the LA channel ID. Default value: " " Maximum length = 31

    throughput(int): Low threshold value for the throughput of the LA channel, in Mbps. In an high availability (HA)
        configuration, failover is triggered when the LA channel has HA MON enabled and the throughput is below the
        specified threshold. Minimum value = 0 Maximum value = 160000

    bandwidthhigh(int): High threshold value for the bandwidth usage of the LA channel, in Mbps. The NetScaler appliance
        generates an SNMP trap message when the bandwidth usage of the LA channel is greater than or equal to the
        specified high threshold value. Minimum value = 0 Maximum value = 160000

    bandwidthnormal(int): Normal threshold value for the bandwidth usage of the LA channel, in Mbps. When the bandwidth usage
        of the LA channel returns to less than or equal to the specified normal threshold after exceeding the high
        threshold, the NetScaler appliance generates an SNMP trap message to indicate that the bandwidth usage has
        returned to normal. Minimum value = 0 Maximum value = 160000

    mtu(int): The maximum transmission unit (MTU) is the largest packet size, measured in bytes excluding 14 bytes ethernet
        header and 4 bytes crc, that can be transmitted and received by this interface. Default value of MTU is 1500 on
        all the interface of Netscaler appliance any value configured more than 1500 on the interface will make the
        interface as jumbo enabled. In case of cluster backplane interface MTU value will be changed to 1514 by default,
        user has to change the backplane interface value to maximum mtu configured on any of the interface in cluster
        system plus 14 bytes more for backplane interface if Jumbo is enabled on any of the interface in a cluster
        system. Changing the backplane will bring back the MTU of backplane interface to default value of 1500. If a
        channel is configured as backplane then the same holds true for channel as well as member interfaces. Default
        value: 1500 Minimum value = 1500 Maximum value = 9216

    lrminthroughput(int): Specifies the minimum throughput threshold (in Mbps) to be met by the active subchannel. Setting
        this parameter automatically divides an LACP channel into logical subchannels, with one subchannel active and the
        others in standby mode. When the maximum supported throughput of the active channel falls below the
        lrMinThroughput value, link failover occurs and a standby subchannel becomes active. Minimum value = 0 Maximum
        value = 80000

    linkredundancy(str): Link Redundancy for Cluster LAG. Default value: OFF Possible values = ON, OFF

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_channel <args>

    '''

    result = {}

    payload = {'channel': {}}

    if id:
        payload['channel']['id'] = id

    if ifnum:
        payload['channel']['ifnum'] = ifnum

    if state:
        payload['channel']['state'] = state

    if mode:
        payload['channel']['mode'] = mode

    if conndistr:
        payload['channel']['conndistr'] = conndistr

    if macdistr:
        payload['channel']['macdistr'] = macdistr

    if lamac:
        payload['channel']['lamac'] = lamac

    if speed:
        payload['channel']['speed'] = speed

    if flowctl:
        payload['channel']['flowctl'] = flowctl

    if hamonitor:
        payload['channel']['hamonitor'] = hamonitor

    if haheartbeat:
        payload['channel']['haheartbeat'] = haheartbeat

    if tagall:
        payload['channel']['tagall'] = tagall

    if trunk:
        payload['channel']['trunk'] = trunk

    if ifalias:
        payload['channel']['ifalias'] = ifalias

    if throughput:
        payload['channel']['throughput'] = throughput

    if bandwidthhigh:
        payload['channel']['bandwidthhigh'] = bandwidthhigh

    if bandwidthnormal:
        payload['channel']['bandwidthnormal'] = bandwidthnormal

    if mtu:
        payload['channel']['mtu'] = mtu

    if lrminthroughput:
        payload['channel']['lrminthroughput'] = lrminthroughput

    if linkredundancy:
        payload['channel']['linkredundancy'] = linkredundancy

    execution = __proxy__['citrixns.put']('config/channel', payload)

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


def update_forwardingsession(name=None, network=None, netmask=None, acl6name=None, aclname=None, td=None,
                             connfailover=None, sourceroutecache=None, processlocal=None, save=False):
    '''
    Update the running configuration for the forwardingsession config key.

    name(str): Name for the forwarding session rule. Can begin with a letter, number, or the underscore character (_), and
        can consist of letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after the rule is created. The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my rule" or my rule). Minimum length = 1

    network(str): An IPv4 network address or IPv6 prefix of a network from which the forwarded traffic originates or to which
        it is destined. Minimum length = 1

    netmask(str): Subnet mask associated with the network. Minimum length = 1

    acl6name(str): Name of any configured ACL6 whose action is ALLOW. The rule of the ACL6 is used as a forwarding session
        rule. Minimum length = 1

    aclname(str): Name of any configured ACL whose action is ALLOW. The rule of the ACL is used as a forwarding session rule.
        Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    connfailover(str): Synchronize connection information with the secondary appliance in a high availability (HA) pair. That
        is, synchronize all connection-related information for the forwarding session. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    sourceroutecache(str): Cache the source ip address and mac address of the DA servers. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    processlocal(str): Enabling this option on forwarding session will not steer the packet to flow processor. Instead,
        packet will be routed. Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_forwardingsession <args>

    '''

    result = {}

    payload = {'forwardingsession': {}}

    if name:
        payload['forwardingsession']['name'] = name

    if network:
        payload['forwardingsession']['network'] = network

    if netmask:
        payload['forwardingsession']['netmask'] = netmask

    if acl6name:
        payload['forwardingsession']['acl6name'] = acl6name

    if aclname:
        payload['forwardingsession']['aclname'] = aclname

    if td:
        payload['forwardingsession']['td'] = td

    if connfailover:
        payload['forwardingsession']['connfailover'] = connfailover

    if sourceroutecache:
        payload['forwardingsession']['sourceroutecache'] = sourceroutecache

    if processlocal:
        payload['forwardingsession']['processlocal'] = processlocal

    execution = __proxy__['citrixns.put']('config/forwardingsession', payload)

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


def update_inat(name=None, publicip=None, privateip=None, mode=None, tcpproxy=None, ftp=None, tftp=None, usip=None,
                usnip=None, proxyip=None, useproxyport=None, td=None, save=False):
    '''
    Update the running configuration for the inat config key.

    name(str): Name for the Inbound NAT (INAT) entry. Leading character must be a number or letter. Other characters allowed,
        after the first character, are @ _ - . (period) : (colon) # and space ( ). Minimum length = 1

    publicip(str): Public IP address of packets received on the NetScaler appliance. Can be aNetScaler-owned VIP or VIP6
        address. Minimum length = 1

    privateip(str): IP address of the server to which the packet is sent by the NetScaler. Can be an IPv4 or IPv6 address.
        Minimum length = 1

    mode(str): Stateless translation. Possible values = STATELESS

    tcpproxy(str): Enable TCP proxy, which enables the NetScaler appliance to optimize the RNAT TCP traffic by using Layer 4
        features. Default value: DISABLED Possible values = ENABLED, DISABLED

    ftp(str): Enable the FTP protocol on the server for transferring files between the client and the server. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    tftp(str): To enable/disable TFTP (Default DISABLED). Default value: DISABLED Possible values = ENABLED, DISABLED

    usip(str): Enable the NetScaler appliance to retain the source IP address of packets before sending the packets to the
        server. Possible values = ON, OFF

    usnip(str): Enable the NetScaler appliance to use a SNIP address as the source IP address of packets before sending the
        packets to the server. Possible values = ON, OFF

    proxyip(str): Unique IP address used as the source IP address in packets sent to the server. Must be a MIP or SNIP
        address.

    useproxyport(str): Enable the NetScaler appliance to proxy the source port of packets before sending the packets to the
        server. Default value: ENABLED Possible values = ENABLED, DISABLED

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_inat <args>

    '''

    result = {}

    payload = {'inat': {}}

    if name:
        payload['inat']['name'] = name

    if publicip:
        payload['inat']['publicip'] = publicip

    if privateip:
        payload['inat']['privateip'] = privateip

    if mode:
        payload['inat']['mode'] = mode

    if tcpproxy:
        payload['inat']['tcpproxy'] = tcpproxy

    if ftp:
        payload['inat']['ftp'] = ftp

    if tftp:
        payload['inat']['tftp'] = tftp

    if usip:
        payload['inat']['usip'] = usip

    if usnip:
        payload['inat']['usnip'] = usnip

    if proxyip:
        payload['inat']['proxyip'] = proxyip

    if useproxyport:
        payload['inat']['useproxyport'] = useproxyport

    if td:
        payload['inat']['td'] = td

    execution = __proxy__['citrixns.put']('config/inat', payload)

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


def update_inatparam(nat46v6prefix=None, td=None, nat46ignoretos=None, nat46zerochecksum=None, nat46v6mtu=None,
                     nat46fragheader=None, save=False):
    '''
    Update the running configuration for the inatparam config key.

    nat46v6prefix(str): The prefix used for translating packets received from private IPv6 servers into IPv4 packets. This
        prefix has a length of 96 bits (128-32 = 96). The IPv6 servers embed the destination IP address of the IPv4
        servers or hosts in the last 32 bits of the destination IP address field of the IPv6 packets. The first 96 bits
        of the destination IP address field are set as the IPv6 NAT prefix. IPv6 packets addressed to this prefix have to
        be routed to the NetScaler appliance to ensure that the IPv6-IPv4 translation is done by the appliance.

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Default value: 0
        Minimum value = 0 Maximum value = 4094

    nat46ignoretos(str): Ignore TOS. Default value: NO Possible values = YES, NO

    nat46zerochecksum(str): Calculate checksum for UDP packets with zero checksum. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    nat46v6mtu(int): MTU setting for the IPv6 side. If the incoming IPv4 packet greater than this, either fragment or send
        icmp need fragmentation error. Default value: 1280 Minimum value = 1280 Maximum value = 9216

    nat46fragheader(str): When disabled, translator will not insert IPv6 fragmentation header for non fragmented IPv4
        packets. Default value: ENABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_inatparam <args>

    '''

    result = {}

    payload = {'inatparam': {}}

    if nat46v6prefix:
        payload['inatparam']['nat46v6prefix'] = nat46v6prefix

    if td:
        payload['inatparam']['td'] = td

    if nat46ignoretos:
        payload['inatparam']['nat46ignoretos'] = nat46ignoretos

    if nat46zerochecksum:
        payload['inatparam']['nat46zerochecksum'] = nat46zerochecksum

    if nat46v6mtu:
        payload['inatparam']['nat46v6mtu'] = nat46v6mtu

    if nat46fragheader:
        payload['inatparam']['nat46fragheader'] = nat46fragheader

    execution = __proxy__['citrixns.put']('config/inatparam', payload)

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


def update_interface(id=None, speed=None, duplex=None, flowctl=None, autoneg=None, hamonitor=None, haheartbeat=None,
                     mtu=None, tagall=None, trunk=None, trunkmode=None, trunkallowedvlan=None, lacpmode=None,
                     lacpkey=None, lagtype=None, lacppriority=None, lacptimeout=None, ifalias=None, throughput=None,
                     linkredundancy=None, bandwidthhigh=None, bandwidthnormal=None, lldpmode=None, lrsetpriority=None,
                     save=False):
    '''
    Update the running configuration for the interface config key.

    id(str): Interface number, in C/U format, where C can take one of the following values: * 0 - Indicates a management
        interface. * 1 - Indicates a 1 Gbps port. * 10 - Indicates a 10 Gbps port. * LA - Indicates a link aggregation
        port. * LO - Indicates a loop back port. U is a unique integer for representing an interface in a particular port
        group.

    speed(str): Ethernet speed of the interface, in Mbps.  Notes: * If you set the speed as AUTO, the NetScaler appliance
        attempts to auto-negotiate or auto-sense the link speed of the interface when it is UP. You must enable auto
        negotiation on the interface. * If you set a speed other than AUTO, you must specify the same speed for the peer
        network device. Mismatched speed and duplex settings between the peer devices of a link lead to link errors,
        packet loss, and other errors.  Some interfaces do not support certain speeds. If you specify an unsupported
        speed, an error message appears. Default value: AUTO Possible values = AUTO, 10, 100, 1000, 10000, 40000

    duplex(str): The duplex mode for the interface. Notes:* If you set the duplex mode to AUTO, the NetScaler appliance
        attempts to auto-negotiate the duplex mode of the interface when it is UP. You must enable auto negotiation on
        the interface. If you set a duplex mode other than AUTO, you must specify the same duplex mode for the peer
        network device. Mismatched speed and duplex settings between the peer devices of a link lead to link errors,
        packet loss, and other errors. Default value: AUTO Possible values = AUTO, HALF, FULL

    flowctl(str): 802.3x flow control setting for the interface. The 802.3x specification does not define flow control for 10
        Mbps and 100 Mbps speeds, but if a Gigabit Ethernet interface operates at those speeds, the flow control settings
        can be applied. The flow control setting that is finally applied to an interface depends on auto-negotiation.
        With the ON option, the peer negotiates the flow control, but the appliance then forces two-way flow control for
        the interface. Default value: OFF Possible values = OFF, RX, TX, RXTX, ON

    autoneg(str): Auto-negotiation state of the interface. With the ENABLED setting, the NetScaler appliance auto-negotiates
        the speed and duplex settings with the peer network device on the link. The NetScaler appliance auto-negotiates
        the settings of only those parameters (speed or duplex mode) for which the value is set as AUTO. Default value:
        NSA_DVC_AUTONEG_ON Possible values = DISABLED, ENABLED

    hamonitor(str): In a High Availability (HA) configuration, monitor the interface for failure events. In an HA
        configuration, an interface that has HA MON enabled and is not bound to any Failover Interface Set (FIS), is a
        critical interface. Failure or disabling of any critical interface triggers HA failover. Default value: ON
        Possible values = ON, OFF

    haheartbeat(str): In a High Availability (HA) or Cluster configuration, configure the interface for sending heartbeats.
        In an HA or Cluster configuration, an interface that has HA Heartbeat disabled should not send the heartbeats.
        Default value: ON Possible values = OFF, ON

    mtu(int): The maximum transmission unit (MTU) is the largest packet size, measured in bytes excluding 14 bytes ethernet
        header and 4 bytes crc, that can be transmitted and received by this interface. Default value of MTU is 1500 on
        all the interface of Netscaler appliance any value configured more than 1500 on the interface will make the
        interface as jumbo enabled. In case of cluster backplane interface MTU value will be changed to 1514 by default,
        user has to change the backplane interface value to maximum mtu configured on any of the interface in cluster
        system plus 14 bytes more for backplane interface if Jumbo is enabled on any of the interface in a cluster
        system. Changing the backplane will bring back the MTU of backplane interface to default value of 1500. If a
        channel is configured as backplane then the same holds true for channel as well as member interfaces. Default
        value: 1500 Minimum value = 1500 Maximum value = 9216

    tagall(str): Add a four-byte 802.1q tag to every packet sent on this interface. The ON setting applies the tag for this
        interfaces native VLAN. OFF applies the tag for all VLANs other than the native VLAN. Default value: OFF Possible
        values = ON, OFF

    trunk(str): This argument is deprecated by tagall. Default value: OFF Possible values = ON, OFF

    trunkmode(str): Accept and send 802.1q VLAN tagged packets, based on Allowed Vlan List of this interface. Default value:
        OFF Possible values = ON, OFF

    trunkallowedvlan(list(str)): VLAN ID or range of VLAN IDs will be allowed on this trunk interface. In the command line
        interface, separate the range with a hyphen. For example: 40-90. Minimum length = 1 Maximum length = 4094

    lacpmode(str): Bind the interface to a LA channel created by the Link Aggregation control protocol (LACP).  Available
        settings function as follows: * Active - The LA channel port of the NetScaler appliance generates LACPDU messages
        on a regular basis, regardless of any need expressed by its peer device to receive them. * Passive - The LA
        channel port of the NetScaler appliance does not transmit LACPDU messages unless the peer device port is in the
        active mode. That is, the port does not speak unless spoken to. * Disabled - Unbinds the interface from the LA
        channel. If this is the only interface in the LA channel, the LA channel is removed. Default value: DISABLED
        Possible values = DISABLED, ACTIVE, PASSIVE

    lacpkey(int): Integer identifying the LACP LA channel to which the interface is to be bound.  For an LA channel of the
        NetScaler appliance, this digit specifies the variable x of an LA channel in LA/x notation, where x can range
        from 1 to 8. For example, if you specify 3 as the LACP key for an LA channel, the interface is bound to the LA
        channel LA/3. For an LA channel of a cluster configuration, this digit specifies the variable y of a cluster LA
        channel in CLA/(y-4) notation, where y can range from 5 to 8. For example, if you specify 6 as the LACP key for a
        cluster LA channel, the interface is bound to the cluster LA channel CLA/2. Minimum value = 1 Maximum value = 8

    lagtype(str): Type of entity (NetScaler appliance or cluster configuration) for which to create the channel. Default
        value: NODE Possible values = NODE, CLUSTER

    lacppriority(int): LACP port priority, expressed as an integer. The lower the number, the higher the priority. The
        NetScaler appliance limits the number of interfaces in an LA channel to sixteen. Default value: 32768 Minimum
        value = 1 Maximum value = 65535

    lacptimeout(str): Interval at which the NetScaler appliance sends LACPDU messages to the peer device on the LA channel.
        Available settings function as follows: LONG - 30 seconds. SHORT - 1 second. Default value: NSA_LACP_TIMEOUT_LONG
        Possible values = LONG, SHORT

    ifalias(str): Alias name for the interface. Used only to enhance readability. To perform any operations, you have to
        specify the interface ID. Default value: " " Maximum length = 31

    throughput(int): Low threshold value for the throughput of the interface, in Mbps. In an HA configuration, failover is
        triggered if the interface has HA MON enabled and the throughput is below the specified the threshold. Minimum
        value = 0 Maximum value = 160000

    linkredundancy(str): Link Redundancy for Cluster LAG. Default value: OFF Possible values = ON, OFF

    bandwidthhigh(int): High threshold value for the bandwidth usage of the interface, in Mbps. The NetScaler appliance
        generates an SNMP trap message when the bandwidth usage of the interface is greater than or equal to the
        specified high threshold value. Minimum value = 0 Maximum value = 160000

    bandwidthnormal(int): Normal threshold value for the bandwidth usage of the interface, in Mbps. When the bandwidth usage
        of the interface becomes less than or equal to the specified normal threshold after exceeding the high threshold,
        the NetScaler appliance generates an SNMP trap message to indicate that the bandwidth usage has returned to
        normal. Minimum value = 0 Maximum value = 160000

    lldpmode(str): Link Layer Discovery Protocol (LLDP) mode for an interface. The resultant LLDP mode of an interface
        depends on the LLDP mode configured at the global and the interface levels. Possible values = NONE, TRANSMITTER,
        RECEIVER, TRANSCEIVER

    lrsetpriority(int): LRSET port priority, expressed as an integer ranging from 1 to 1024. The highest priority is 1. The
        NetScaler limits the number of interfaces in an LRSET to 8. Within a LRSET the highest LR Priority Interface is
        considered as the first candidate for the Active interface, if the interface is UP. Default value: 1024 Minimum
        value = 1 Maximum value = 1024

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_interface <args>

    '''

    result = {}

    payload = {'Interface': {}}

    if id:
        payload['Interface']['id'] = id

    if speed:
        payload['Interface']['speed'] = speed

    if duplex:
        payload['Interface']['duplex'] = duplex

    if flowctl:
        payload['Interface']['flowctl'] = flowctl

    if autoneg:
        payload['Interface']['autoneg'] = autoneg

    if hamonitor:
        payload['Interface']['hamonitor'] = hamonitor

    if haheartbeat:
        payload['Interface']['haheartbeat'] = haheartbeat

    if mtu:
        payload['Interface']['mtu'] = mtu

    if tagall:
        payload['Interface']['tagall'] = tagall

    if trunk:
        payload['Interface']['trunk'] = trunk

    if trunkmode:
        payload['Interface']['trunkmode'] = trunkmode

    if trunkallowedvlan:
        payload['Interface']['trunkallowedvlan'] = trunkallowedvlan

    if lacpmode:
        payload['Interface']['lacpmode'] = lacpmode

    if lacpkey:
        payload['Interface']['lacpkey'] = lacpkey

    if lagtype:
        payload['Interface']['lagtype'] = lagtype

    if lacppriority:
        payload['Interface']['lacppriority'] = lacppriority

    if lacptimeout:
        payload['Interface']['lacptimeout'] = lacptimeout

    if ifalias:
        payload['Interface']['ifalias'] = ifalias

    if throughput:
        payload['Interface']['throughput'] = throughput

    if linkredundancy:
        payload['Interface']['linkredundancy'] = linkredundancy

    if bandwidthhigh:
        payload['Interface']['bandwidthhigh'] = bandwidthhigh

    if bandwidthnormal:
        payload['Interface']['bandwidthnormal'] = bandwidthnormal

    if lldpmode:
        payload['Interface']['lldpmode'] = lldpmode

    if lrsetpriority:
        payload['Interface']['lrsetpriority'] = lrsetpriority

    execution = __proxy__['citrixns.put']('config/Interface', payload)

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


def update_ip6tunnelparam(srcip=None, dropfrag=None, dropfragcputhreshold=None, srciproundrobin=None, save=False):
    '''
    Update the running configuration for the ip6tunnelparam config key.

    srcip(str): Common source IPv6 address for all IPv6 tunnels. Must be a SNIP6 or VIP6 address. Minimum length = 1

    dropfrag(str): Drop any packet that requires fragmentation. Default value: NO Possible values = YES, NO

    dropfragcputhreshold(int): Threshold value, as a percentage of CPU usage, at which to drop packets that require
        fragmentation. Applies only if dropFragparameter is set to NO. Minimum value = 1 Maximum value = 100

    srciproundrobin(str): Use a different source IPv6 address for each new session through a particular IPv6 tunnel, as
        determined by round robin selection of one of the SNIP6 addresses. This setting is ignored if a common global
        source IPv6 address has been specified for all the IPv6 tunnels. This setting does not apply to a tunnel for
        which a source IPv6 address has been specified. Default value: NO Possible values = YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_ip6tunnelparam <args>

    '''

    result = {}

    payload = {'ip6tunnelparam': {}}

    if srcip:
        payload['ip6tunnelparam']['srcip'] = srcip

    if dropfrag:
        payload['ip6tunnelparam']['dropfrag'] = dropfrag

    if dropfragcputhreshold:
        payload['ip6tunnelparam']['dropfragcputhreshold'] = dropfragcputhreshold

    if srciproundrobin:
        payload['ip6tunnelparam']['srciproundrobin'] = srciproundrobin

    execution = __proxy__['citrixns.put']('config/ip6tunnelparam', payload)

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


def update_iptunnelparam(srcip=None, dropfrag=None, dropfragcputhreshold=None, srciproundrobin=None, enablestrictrx=None,
                         enablestricttx=None, mac=None, save=False):
    '''
    Update the running configuration for the iptunnelparam config key.

    srcip(str): Common source-IP address for all tunnels. For a specific tunnel, this global setting is overridden if you
        have specified another source IP address. Must be a MIP or SNIP address. Minimum length = 1

    dropfrag(str): Drop any IP packet that requires fragmentation before it is sent through the tunnel. Default value: NO
        Possible values = YES, NO

    dropfragcputhreshold(int): Threshold value, as a percentage of CPU usage, at which to drop packets that require
        fragmentation to use the IP tunnel. Applies only if dropFragparameter is set to NO. The default value, 0,
        specifies that this parameter is not set. Minimum value = 1 Maximum value = 100

    srciproundrobin(str): Use a different source IP address for each new session through a particular IP tunnel, as
        determined by round robin selection of one of the SNIP addresses. This setting is ignored if a common global
        source IP address has been specified for all the IP tunnels. This setting does not apply to a tunnel for which a
        source IP address has been specified. Default value: NO Possible values = YES, NO

    enablestrictrx(str): Strict PBR check for IPSec packets received through tunnel. Default value: NO Possible values = YES,
        NO

    enablestricttx(str): Strict PBR check for packets to be sent IPSec protected. Default value: NO Possible values = YES,
        NO

    mac(str): The shared MAC used for shared IP between cluster nodes/HA peers.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_iptunnelparam <args>

    '''

    result = {}

    payload = {'iptunnelparam': {}}

    if srcip:
        payload['iptunnelparam']['srcip'] = srcip

    if dropfrag:
        payload['iptunnelparam']['dropfrag'] = dropfrag

    if dropfragcputhreshold:
        payload['iptunnelparam']['dropfragcputhreshold'] = dropfragcputhreshold

    if srciproundrobin:
        payload['iptunnelparam']['srciproundrobin'] = srciproundrobin

    if enablestrictrx:
        payload['iptunnelparam']['enablestrictrx'] = enablestrictrx

    if enablestricttx:
        payload['iptunnelparam']['enablestricttx'] = enablestricttx

    if mac:
        payload['iptunnelparam']['mac'] = mac

    execution = __proxy__['citrixns.put']('config/iptunnelparam', payload)

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


def update_ipv6(ralearning=None, routerredirection=None, ndbasereachtime=None, ndretransmissiontime=None, natprefix=None,
                td=None, dodad=None, save=False):
    '''
    Update the running configuration for the ipv6 config key.

    ralearning(str): Enable the NetScaler appliance to learn about various routes from Router Advertisement (RA) and Router
        Solicitation (RS) messages sent by the routers. Default value: DISABLED Possible values = ENABLED, DISABLED

    routerredirection(str): Enable the NetScaler appliance to do Router Redirection. Default value: DISABLED Possible values
        = ENABLED, DISABLED

    ndbasereachtime(int): Base reachable time of the Neighbor Discovery (ND6) protocol. The time, in milliseconds, that the
        NetScaler appliance assumes an adjacent device is reachable after receiving a reachability confirmation. Default
        value: 30000 Minimum value = 1

    ndretransmissiontime(int): Retransmission time of the Neighbor Discovery (ND6) protocol. The time, in milliseconds,
        between retransmitted Neighbor Solicitation (NS) messages, to an adjacent device. Default value: 1000 Minimum
        value = 1

    natprefix(str): Prefix used for translating packets from private IPv6 servers to IPv4 packets. This prefix has a length
        of 96 bits (128-32 = 96). The IPv6 servers embed the destination IP address of the IPv4 servers or hosts in the
        last 32 bits of the destination IP address field of the IPv6 packets. The first 96 bits of the destination IP
        address field are set as the IPv6 NAT prefix. IPv6 packets addressed to this prefix have to be routed to the
        NetScaler appliance to ensure that the IPv6-IPv4 translation is done by the appliance.

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Default value: 0
        Minimum value = 0 Maximum value = 4094

    dodad(str): Enable the NetScaler appliance to do Duplicate Address Detection (DAD) for all the NetScaler owned IPv6
        addresses regardless of whether they are obtained through stateless auto configuration, DHCPv6, or manual
        configuration. Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_ipv6 <args>

    '''

    result = {}

    payload = {'ipv6': {}}

    if ralearning:
        payload['ipv6']['ralearning'] = ralearning

    if routerredirection:
        payload['ipv6']['routerredirection'] = routerredirection

    if ndbasereachtime:
        payload['ipv6']['ndbasereachtime'] = ndbasereachtime

    if ndretransmissiontime:
        payload['ipv6']['ndretransmissiontime'] = ndretransmissiontime

    if natprefix:
        payload['ipv6']['natprefix'] = natprefix

    if td:
        payload['ipv6']['td'] = td

    if dodad:
        payload['ipv6']['dodad'] = dodad

    execution = __proxy__['citrixns.put']('config/ipv6', payload)

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


def update_l2param(mbfpeermacupdate=None, maxbridgecollision=None, bdggrpproxyarp=None, bdgsetting=None,
                   garponvridintf=None, macmodefwdmypkt=None, usemymac=None, proxyarp=None, garpreply=None,
                   mbfinstlearning=None, rstintfonhafo=None, skipproxyingbsdtraffic=None, returntoethernetsender=None,
                   stopmacmoveupdate=None, bridgeagetimeout=None, save=False):
    '''
    Update the running configuration for the l2param config key.

    mbfpeermacupdate(int): When mbf_instant_learning is enabled, learn any changes in peers MAC after this time interval,
        which is in 10ms ticks. Default value: 10

    maxbridgecollision(int): Maximum bridge collision for loop detection . Default value: 20

    bdggrpproxyarp(str): Set/reset proxy ARP in bridge group deployment. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    bdgsetting(str): Bridging settings for C2C behavior. If enabled, each PE will learn MAC entries independently. Otherwise,
        when L2 mode is ON, learned MAC entries on a PE will be broadcasted to all other PEs. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    garponvridintf(str): Send GARP messagess on VRID-configured interfaces upon failover . Default value: ENABLED Possible
        values = ENABLED, DISABLED

    macmodefwdmypkt(str): Allows MAC mode vserver to pick and forward the packets even if it is destined to NetScaler owned
        VIP. Default value: DISABLED Possible values = ENABLED, DISABLED

    usemymac(str): Use Netscaler MAC for all outgoing packets. Default value: DISABLED Possible values = ENABLED, DISABLED

    proxyarp(str): Proxies the ARP as Netscaler MAC for FreeBSD. Default value: ENABLED Possible values = ENABLED, DISABLED

    garpreply(str): Set/reset REPLY form of GARP . Default value: DISABLED Possible values = ENABLED, DISABLED

    mbfinstlearning(str): Enable instant learning of MAC changes in MBF mode. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    rstintfonhafo(str): Enable the reset interface upon HA failover. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    skipproxyingbsdtraffic(str): Control source parameters (IP and Port) for FreeBSD initiated traffic. If Enabled, source
        parameters are retained. Else proxy the source parameters based on next hop. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    returntoethernetsender(str): Return to ethernet sender. Default value: DISABLED Possible values = ENABLED, DISABLED

    stopmacmoveupdate(str): Stop Update of server mac change to NAT sessions. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    bridgeagetimeout(int): Time-out value for the bridge table entries, in seconds. The new value applies only to the entries
        that are dynamically learned after the new value is set. Previously existing bridge table entries expire after
        the previously configured time-out value. Default value: 300 Minimum value = 60 Maximum value = 300

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_l2param <args>

    '''

    result = {}

    payload = {'l2param': {}}

    if mbfpeermacupdate:
        payload['l2param']['mbfpeermacupdate'] = mbfpeermacupdate

    if maxbridgecollision:
        payload['l2param']['maxbridgecollision'] = maxbridgecollision

    if bdggrpproxyarp:
        payload['l2param']['bdggrpproxyarp'] = bdggrpproxyarp

    if bdgsetting:
        payload['l2param']['bdgsetting'] = bdgsetting

    if garponvridintf:
        payload['l2param']['garponvridintf'] = garponvridintf

    if macmodefwdmypkt:
        payload['l2param']['macmodefwdmypkt'] = macmodefwdmypkt

    if usemymac:
        payload['l2param']['usemymac'] = usemymac

    if proxyarp:
        payload['l2param']['proxyarp'] = proxyarp

    if garpreply:
        payload['l2param']['garpreply'] = garpreply

    if mbfinstlearning:
        payload['l2param']['mbfinstlearning'] = mbfinstlearning

    if rstintfonhafo:
        payload['l2param']['rstintfonhafo'] = rstintfonhafo

    if skipproxyingbsdtraffic:
        payload['l2param']['skipproxyingbsdtraffic'] = skipproxyingbsdtraffic

    if returntoethernetsender:
        payload['l2param']['returntoethernetsender'] = returntoethernetsender

    if stopmacmoveupdate:
        payload['l2param']['stopmacmoveupdate'] = stopmacmoveupdate

    if bridgeagetimeout:
        payload['l2param']['bridgeagetimeout'] = bridgeagetimeout

    execution = __proxy__['citrixns.put']('config/l2param', payload)

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


def update_l3param(srcnat=None, icmpgenratethreshold=None, overridernat=None, dropdfflag=None, miproundrobin=None,
                   externalloopback=None, tnlpmtuwoconn=None, usipserverstraypkt=None, forwardicmpfragments=None,
                   dropipfragments=None, acllogtime=None, implicitaclallow=None, dynamicrouting=None,
                   ipv6dynamicrouting=None, save=False):
    '''
    Update the running configuration for the l3param config key.

    srcnat(str): Perform NAT if only the source is in the private network. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    icmpgenratethreshold(int): NS generated ICMP pkts per 10ms rate threshold. Default value: 100

    overridernat(str): USNIP/USIP settings override RNAT settings for configured  service/virtual server traffic.. . Default
        value: DISABLED Possible values = ENABLED, DISABLED

    dropdfflag(str): Enable dropping the IP DF flag. Default value: DISABLED Possible values = ENABLED, DISABLED

    miproundrobin(str): Enable round robin usage of mapped IPs. Default value: ENABLED Possible values = ENABLED, DISABLED

    externalloopback(str): Enable external loopback. Default value: DISABLED Possible values = ENABLED, DISABLED

    tnlpmtuwoconn(str): Enable/Disable learning PMTU of IP tunnel when ICMP error does not contain connection information.
        Default value: ENABLED Possible values = ENABLED, DISABLED

    usipserverstraypkt(str): Enable detection of stray server side pkts in USIP mode. Default value: DISABLED Possible values
        = ENABLED, DISABLED

    forwardicmpfragments(str): Enable forwarding of ICMP fragments. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    dropipfragments(str): Enable dropping of IP fragments. Default value: DISABLED Possible values = ENABLED, DISABLED

    acllogtime(int): Parameter to tune acl logging time. Default value: 5000

    implicitaclallow(str): Do not apply ACLs for internal ports. Default value: ENABLED Possible values = ENABLED, DISABLED

    dynamicrouting(str): Enable/Disable Dynamic routing on partition. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    ipv6dynamicrouting(str): Enable/Disable IPv6 Dynamic routing on partition. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_l3param <args>

    '''

    result = {}

    payload = {'l3param': {}}

    if srcnat:
        payload['l3param']['srcnat'] = srcnat

    if icmpgenratethreshold:
        payload['l3param']['icmpgenratethreshold'] = icmpgenratethreshold

    if overridernat:
        payload['l3param']['overridernat'] = overridernat

    if dropdfflag:
        payload['l3param']['dropdfflag'] = dropdfflag

    if miproundrobin:
        payload['l3param']['miproundrobin'] = miproundrobin

    if externalloopback:
        payload['l3param']['externalloopback'] = externalloopback

    if tnlpmtuwoconn:
        payload['l3param']['tnlpmtuwoconn'] = tnlpmtuwoconn

    if usipserverstraypkt:
        payload['l3param']['usipserverstraypkt'] = usipserverstraypkt

    if forwardicmpfragments:
        payload['l3param']['forwardicmpfragments'] = forwardicmpfragments

    if dropipfragments:
        payload['l3param']['dropipfragments'] = dropipfragments

    if acllogtime:
        payload['l3param']['acllogtime'] = acllogtime

    if implicitaclallow:
        payload['l3param']['implicitaclallow'] = implicitaclallow

    if dynamicrouting:
        payload['l3param']['dynamicrouting'] = dynamicrouting

    if ipv6dynamicrouting:
        payload['l3param']['ipv6dynamicrouting'] = ipv6dynamicrouting

    execution = __proxy__['citrixns.put']('config/l3param', payload)

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


def update_l4param(l2connmethod=None, l4switch=None, save=False):
    '''
    Update the running configuration for the l4param config key.

    l2connmethod(str): Layer 2 connection method based on the combination of channel number, MAC address and VLAN. It is
        tuned with l2conn param of lb vserver. If l2conn of lb vserver is ON then method specified here will be used to
        identify a connection in addition to the 4-tuple (;lt;source IP;gt;:;lt;source port;gt;::;lt;destination
        IP;gt;:;lt;destination port;gt;). Default value: MacVlanChannel Possible values = Channel, Vlan, VlanChannel,
        Mac, MacChannel, MacVlan, MacVlanChannel

    l4switch(str): In L4 switch topology, always clients and servers are on the same side. Enable l4switch to allow such
        connections. Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_l4param <args>

    '''

    result = {}

    payload = {'l4param': {}}

    if l2connmethod:
        payload['l4param']['l2connmethod'] = l2connmethod

    if l4switch:
        payload['l4param']['l4switch'] = l4switch

    execution = __proxy__['citrixns.put']('config/l4param', payload)

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


def update_lacp(syspriority=None, ownernode=None, save=False):
    '''
    Update the running configuration for the lacp config key.

    syspriority(int): Priority number that determines which peer device of an LACP LA channel can have control over the LA
        channel. This parameter is globally applied to all LACP channels on the NetScaler appliance. The lower the
        number, the higher the priority. Default value: 32768 Minimum value = 1 Maximum value = 65535

    ownernode(int): The owner node in a cluster for which we want to set the lacp priority. Owner node can vary from 0 to 31.
        Ownernode value of 254 is used for Cluster. Default value: 255

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_lacp <args>

    '''

    result = {}

    payload = {'lacp': {}}

    if syspriority:
        payload['lacp']['syspriority'] = syspriority

    if ownernode:
        payload['lacp']['ownernode'] = ownernode

    execution = __proxy__['citrixns.put']('config/lacp', payload)

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


def update_nat64(name=None, acl6name=None, netprofile=None, save=False):
    '''
    Update the running configuration for the nat64 config key.

    name(str): Name for the NAT64 rule. Must begin with a letter, number, or the underscore character (_), and can consist of
        letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the rule is created. Choose a name that helps identify the NAT64
        rule. Minimum length = 1

    acl6name(str): Name of any configured ACL6 whose action is ALLOW. IPv6 Packets matching the condition of this ACL6 rule
        and destination IP address of these packets matching the NAT64 IPv6 prefix are considered for NAT64 translation.
        Minimum length = 1

    netprofile(str): Name of the configured netprofile. The NetScaler appliance selects one of the IP address in the
        netprofile as the source IP address of the translated IPv4 packet to be sent to the IPv4 server. Minimum length =
        1 Maximum length = 127

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_nat64 <args>

    '''

    result = {}

    payload = {'nat64': {}}

    if name:
        payload['nat64']['name'] = name

    if acl6name:
        payload['nat64']['acl6name'] = acl6name

    if netprofile:
        payload['nat64']['netprofile'] = netprofile

    execution = __proxy__['citrixns.put']('config/nat64', payload)

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


def update_nat64param(td=None, nat64ignoretos=None, nat64zerochecksum=None, nat64v6mtu=None, nat64fragheader=None,
                      save=False):
    '''
    Update the running configuration for the nat64param config key.

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    nat64ignoretos(str): Ignore TOS. Default value: NO Possible values = YES, NO

    nat64zerochecksum(str): Calculate checksum for UDP packets with zero checksum. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    nat64v6mtu(int): MTU setting for the IPv6 side. If the incoming IPv4 packet greater than this, either fragment or send
        icmp need fragmentation error. Default value: 1280 Minimum value = 1280 Maximum value = 9216

    nat64fragheader(str): When disabled, translator will not insert IPv6 fragmentation header for non fragmented IPv4
        packets. Default value: ENABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_nat64param <args>

    '''

    result = {}

    payload = {'nat64param': {}}

    if td:
        payload['nat64param']['td'] = td

    if nat64ignoretos:
        payload['nat64param']['nat64ignoretos'] = nat64ignoretos

    if nat64zerochecksum:
        payload['nat64param']['nat64zerochecksum'] = nat64zerochecksum

    if nat64v6mtu:
        payload['nat64param']['nat64v6mtu'] = nat64v6mtu

    if nat64fragheader:
        payload['nat64param']['nat64fragheader'] = nat64fragheader

    execution = __proxy__['citrixns.put']('config/nat64param', payload)

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


def update_nd6ravariables(vlan=None, ceaserouteradv=None, sendrouteradv=None, srclinklayeraddroption=None,
                          onlyunicastrtadvresponse=None, managedaddrconfig=None, otheraddrconfig=None, currhoplimit=None,
                          maxrtadvinterval=None, minrtadvinterval=None, linkmtu=None, reachabletime=None,
                          retranstime=None, defaultlifetime=None, save=False):
    '''
    Update the running configuration for the nd6ravariables config key.

    vlan(int): The VLAN number. Minimum value = 1 Maximum value = 4094

    ceaserouteradv(str): Cease router advertisements on this vlan. Default value: NO Possible values = YES, NO

    sendrouteradv(str): whether the router sends periodic RAs and responds to Router Solicitations. Default value: NO
        Possible values = YES, NO

    srclinklayeraddroption(str): Include source link layer address option in RA messages. Default value: YES Possible values
        = YES, NO

    onlyunicastrtadvresponse(str): Send only Unicast Router Advertisements in respond to Router Solicitations. Default value:
        NO Possible values = YES, NO

    managedaddrconfig(str): Value to be placed in the Managed address configuration flag field. Default value: NO Possible
        values = YES, NO

    otheraddrconfig(str): Value to be placed in the Other configuration flag field. Default value: NO Possible values = YES,
        NO

    currhoplimit(int): Current Hop limit. Default value: 64 Minimum value = 0 Maximum value = 255

    maxrtadvinterval(int): Maximum time allowed between unsolicited multicast RAs, in seconds. Default value: 600 Minimum
        value = 4 Maximum value = 1800

    minrtadvinterval(int): Minimum time interval between RA messages, in seconds. Default value: 198 Minimum value = 3
        Maximum value = 1350

    linkmtu(int): The Link MTU. Default value: 0 Minimum value = 0 Maximum value = 1500

    reachabletime(int): Reachable time, in milliseconds. Default value: 0 Minimum value = 0 Maximum value = 3600000

    retranstime(int): Retransmission time, in milliseconds. Default value: 0

    defaultlifetime(int): Default life time, in seconds. Default value: 1800 Minimum value = 0 Maximum value = 9000

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_nd6ravariables <args>

    '''

    result = {}

    payload = {'nd6ravariables': {}}

    if vlan:
        payload['nd6ravariables']['vlan'] = vlan

    if ceaserouteradv:
        payload['nd6ravariables']['ceaserouteradv'] = ceaserouteradv

    if sendrouteradv:
        payload['nd6ravariables']['sendrouteradv'] = sendrouteradv

    if srclinklayeraddroption:
        payload['nd6ravariables']['srclinklayeraddroption'] = srclinklayeraddroption

    if onlyunicastrtadvresponse:
        payload['nd6ravariables']['onlyunicastrtadvresponse'] = onlyunicastrtadvresponse

    if managedaddrconfig:
        payload['nd6ravariables']['managedaddrconfig'] = managedaddrconfig

    if otheraddrconfig:
        payload['nd6ravariables']['otheraddrconfig'] = otheraddrconfig

    if currhoplimit:
        payload['nd6ravariables']['currhoplimit'] = currhoplimit

    if maxrtadvinterval:
        payload['nd6ravariables']['maxrtadvinterval'] = maxrtadvinterval

    if minrtadvinterval:
        payload['nd6ravariables']['minrtadvinterval'] = minrtadvinterval

    if linkmtu:
        payload['nd6ravariables']['linkmtu'] = linkmtu

    if reachabletime:
        payload['nd6ravariables']['reachabletime'] = reachabletime

    if retranstime:
        payload['nd6ravariables']['retranstime'] = retranstime

    if defaultlifetime:
        payload['nd6ravariables']['defaultlifetime'] = defaultlifetime

    execution = __proxy__['citrixns.put']('config/nd6ravariables', payload)

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


def update_netbridge(name=None, vxlanvlanmap=None, save=False):
    '''
    Update the running configuration for the netbridge config key.

    name(str): The name of the network bridge.

    vxlanvlanmap(str): The vlan to vxlan mapping to be applied to this netbridge.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_netbridge <args>

    '''

    result = {}

    payload = {'netbridge': {}}

    if name:
        payload['netbridge']['name'] = name

    if vxlanvlanmap:
        payload['netbridge']['vxlanvlanmap'] = vxlanvlanmap

    execution = __proxy__['citrixns.put']('config/netbridge', payload)

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


def update_netprofile(name=None, td=None, srcip=None, srcippersistency=None, overridelsn=None, save=False):
    '''
    Update the running configuration for the netprofile config key.

    name(str): Name for the net profile. Must begin with a letter, number, or the underscore character (_), and can consist
        of letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the profile is created. Choose a name that helps identify the net
        profile. Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    srcip(str): IP address or the name of an IP set.

    srcippersistency(str): When the net profile is associated with a virtual server or its bound services, this option
        enables the NetScaler appliance to use the same address, specified in the net profile, to communicate to servers
        for all sessions initiated from a particular client to the virtual server. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    overridelsn(str): USNIP/USIP settings override LSN settings for configured  service/virtual server traffic.. . Default
        value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_netprofile <args>

    '''

    result = {}

    payload = {'netprofile': {}}

    if name:
        payload['netprofile']['name'] = name

    if td:
        payload['netprofile']['td'] = td

    if srcip:
        payload['netprofile']['srcip'] = srcip

    if srcippersistency:
        payload['netprofile']['srcippersistency'] = srcippersistency

    if overridelsn:
        payload['netprofile']['overridelsn'] = overridelsn

    execution = __proxy__['citrixns.put']('config/netprofile', payload)

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


def update_onlinkipv6prefix(ipv6prefix=None, onlinkprefix=None, autonomusprefix=None, depricateprefix=None,
                            decrementprefixlifetimes=None, prefixvalidelifetime=None, prefixpreferredlifetime=None,
                            save=False):
    '''
    Update the running configuration for the onlinkipv6prefix config key.

    ipv6prefix(str): Onlink prefixes for RA messages.

    onlinkprefix(str): RA Prefix onlink flag. Default value: YES Possible values = YES, NO

    autonomusprefix(str): RA Prefix Autonomus flag. Default value: YES Possible values = YES, NO

    depricateprefix(str): Depricate the prefix. Default value: NO Possible values = YES, NO

    decrementprefixlifetimes(str): RA Prefix Autonomus flag. Default value: NO Possible values = YES, NO

    prefixvalidelifetime(int): Valide life time of the prefix, in seconds. Default value: 2592000

    prefixpreferredlifetime(int): Preferred life time of the prefix, in seconds. Default value: 604800

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_onlinkipv6prefix <args>

    '''

    result = {}

    payload = {'onlinkipv6prefix': {}}

    if ipv6prefix:
        payload['onlinkipv6prefix']['ipv6prefix'] = ipv6prefix

    if onlinkprefix:
        payload['onlinkipv6prefix']['onlinkprefix'] = onlinkprefix

    if autonomusprefix:
        payload['onlinkipv6prefix']['autonomusprefix'] = autonomusprefix

    if depricateprefix:
        payload['onlinkipv6prefix']['depricateprefix'] = depricateprefix

    if decrementprefixlifetimes:
        payload['onlinkipv6prefix']['decrementprefixlifetimes'] = decrementprefixlifetimes

    if prefixvalidelifetime:
        payload['onlinkipv6prefix']['prefixvalidelifetime'] = prefixvalidelifetime

    if prefixpreferredlifetime:
        payload['onlinkipv6prefix']['prefixpreferredlifetime'] = prefixpreferredlifetime

    execution = __proxy__['citrixns.put']('config/onlinkipv6prefix', payload)

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


def update_ptp(state=None, save=False):
    '''
    Update the running configuration for the ptp config key.

    state(str): Enables or disables Precision Time Protocol (PTP) on the appliance. If you disable PTP, make sure you enable
        Network Time Protocol (NTP) on the cluster. Default value: ENABLE Possible values = DISABLE, ENABLE

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_ptp <args>

    '''

    result = {}

    payload = {'ptp': {}}

    if state:
        payload['ptp']['state'] = state

    execution = __proxy__['citrixns.put']('config/ptp', payload)

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


def update_rnat(network=None, netmask=None, aclname=None, redirectport=None, natip=None, td=None, ownergroup=None,
                natip2=None, srcippersistency=None, useproxyport=None, connfailover=None, save=False):
    '''
    Update the running configuration for the rnat config key.

    network(str): The network address defined for the RNAT entry. Minimum length = 1

    netmask(str): The subnet mask for the network address. Minimum length = 1

    aclname(str): An extended ACL defined for the RNAT entry. Minimum length = 1

    redirectport(bool): The port number to which the packets are redirected.

    natip(str): The NAT IP address defined for the RNAT entry. . Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    ownergroup(str): The owner node group in a Cluster for this rnat rule. Default value: DEFAULT_NG Minimum length = 1

    natip2(str): The NAT IP(s) assigned to the RNAT. Minimum length = 1

    srcippersistency(str): Enables the NetScaler appliance to use the same NAT IP address for all RNAT sessions initiated
        from a particular server. Default value: DISABLED Possible values = ENABLED, DISABLED

    useproxyport(str): Enable source port proxying, which enables the NetScaler appliance to use the RNAT ips using proxied
        source port. Default value: ENABLED Possible values = ENABLED, DISABLED

    connfailover(str): Synchronize connection information with the secondary appliance in a high availability (HA) pair. That
        is, synchronize all connection-related information for the RNAT session. In order for this to work, tcpproxy
        should be DISABLED. To disable tcpproxy use "set rnatparam tcpproxy DISABLED". Default value: DISABLED Possible
        values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_rnat <args>

    '''

    result = {}

    payload = {'rnat': {}}

    if network:
        payload['rnat']['network'] = network

    if netmask:
        payload['rnat']['netmask'] = netmask

    if aclname:
        payload['rnat']['aclname'] = aclname

    if redirectport:
        payload['rnat']['redirectport'] = redirectport

    if natip:
        payload['rnat']['natip'] = natip

    if td:
        payload['rnat']['td'] = td

    if ownergroup:
        payload['rnat']['ownergroup'] = ownergroup

    if natip2:
        payload['rnat']['natip2'] = natip2

    if srcippersistency:
        payload['rnat']['srcippersistency'] = srcippersistency

    if useproxyport:
        payload['rnat']['useproxyport'] = useproxyport

    if connfailover:
        payload['rnat']['connfailover'] = connfailover

    execution = __proxy__['citrixns.put']('config/rnat', payload)

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


def update_rnat6(name=None, network=None, acl6name=None, redirectport=None, td=None, srcippersistency=None,
                 ownergroup=None, save=False):
    '''
    Update the running configuration for the rnat6 config key.

    name(str): Name for the RNAT6 rule. Must begin with a letter, number, or the underscore character (_), and can consist of
        letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the rule is created. Choose a name that helps identify the RNAT6
        rule. Minimum length = 1

    network(str): IPv6 address of the network on whose traffic you want the NetScaler appliance to do RNAT processing.
        Minimum length = 1

    acl6name(str): Name of any configured ACL6 whose action is ALLOW. The rule of the ACL6 is used as an RNAT6 rule. Minimum
        length = 1

    redirectport(int): Port number to which the IPv6 packets are redirected. Applicable to TCP and UDP protocols. Minimum
        value = 1 Maximum value = 65535

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    srcippersistency(str): Enable source ip persistency, which enables the NetScaler appliance to use the RNAT ips using
        source ip. Default value: DISABLED Possible values = ENABLED, DISABLED

    ownergroup(str): The owner node group in a Cluster for this rnat rule. Default value: DEFAULT_NG Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_rnat6 <args>

    '''

    result = {}

    payload = {'rnat6': {}}

    if name:
        payload['rnat6']['name'] = name

    if network:
        payload['rnat6']['network'] = network

    if acl6name:
        payload['rnat6']['acl6name'] = acl6name

    if redirectport:
        payload['rnat6']['redirectport'] = redirectport

    if td:
        payload['rnat6']['td'] = td

    if srcippersistency:
        payload['rnat6']['srcippersistency'] = srcippersistency

    if ownergroup:
        payload['rnat6']['ownergroup'] = ownergroup

    execution = __proxy__['citrixns.put']('config/rnat6', payload)

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


def update_rnatparam(tcpproxy=None, srcippersistency=None, save=False):
    '''
    Update the running configuration for the rnatparam config key.

    tcpproxy(str): Enable TCP proxy, which enables the NetScaler appliance to optimize the RNAT TCP traffic by using Layer 4
        features. Default value: ENABLED Possible values = ENABLED, DISABLED

    srcippersistency(str): Enable source ip persistency, which enables the NetScaler appliance to use the RNAT ips using
        source ip. Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_rnatparam <args>

    '''

    result = {}

    payload = {'rnatparam': {}}

    if tcpproxy:
        payload['rnatparam']['tcpproxy'] = tcpproxy

    if srcippersistency:
        payload['rnatparam']['srcippersistency'] = srcippersistency

    execution = __proxy__['citrixns.put']('config/rnatparam', payload)

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


def update_route(network=None, netmask=None, gateway=None, cost=None, td=None, distance=None, cost1=None, weight=None,
                 advertise=None, protocol=None, msr=None, monitor=None, ownergroup=None, routetype=None, detail=None,
                 save=False):
    '''
    Update the running configuration for the route config key.

    network(str): IPv4 network address for which to add a route entry in the routing table of the NetScaler appliance.

    netmask(str): The subnet mask associated with the network address.

    gateway(str): IP address of the gateway for this route. Can be either the IP address of the gateway, or can be null to
        specify a null interface route. Minimum length = 1

    cost(int): Positive integer used by the routing algorithms to determine preference for using this route. The lower the
        cost, the higher the preference. Minimum value = 0 Maximum value = 65535

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    distance(int): Administrative distance of this route, which determines the preference of this route over other routes,
        with same destination, from different routing protocols. A lower value is preferred. Default value: 1 Minimum
        value = 0 Maximum value = 255

    cost1(int): The cost of a route is used to compare routes of the same type. The route having the lowest cost is the most
        preferred route. Possible values: 0 through 65535. Default: 0. Minimum value = 0 Maximum value = 65535

    weight(int): Positive integer used by the routing algorithms to determine preference for this route over others of equal
        cost. The lower the weight, the higher the preference. Default value: 1 Minimum value = 1 Maximum value = 65535

    advertise(str): Advertise this route. Possible values = DISABLED, ENABLED

    protocol(list(str)): Routing protocol used for advertising this route. Default value: ADV_ROUTE_FLAGS Possible values =
        OSPF, ISIS, RIP, BGP

    msr(str): Monitor this route using a monitor of type ARP or PING. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    monitor(str): Name of the monitor, of type ARP or PING, configured on the NetScaler appliance to monitor this route.
        Minimum length = 1

    ownergroup(str): The owner node group in a Cluster for this route. If owner node group is not specified then the route is
        treated as Striped route. Default value: DEFAULT_NG Minimum length = 1

    routetype(str): Protocol used by routes that you want to remove from the routing table of the NetScaler appliance.
        Possible values = CONNECTED, STATIC, DYNAMIC, OSPF, ISIS, RIP, BGP

    detail(bool): Display a detailed view.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_route <args>

    '''

    result = {}

    payload = {'route': {}}

    if network:
        payload['route']['network'] = network

    if netmask:
        payload['route']['netmask'] = netmask

    if gateway:
        payload['route']['gateway'] = gateway

    if cost:
        payload['route']['cost'] = cost

    if td:
        payload['route']['td'] = td

    if distance:
        payload['route']['distance'] = distance

    if cost1:
        payload['route']['cost1'] = cost1

    if weight:
        payload['route']['weight'] = weight

    if advertise:
        payload['route']['advertise'] = advertise

    if protocol:
        payload['route']['protocol'] = protocol

    if msr:
        payload['route']['msr'] = msr

    if monitor:
        payload['route']['monitor'] = monitor

    if ownergroup:
        payload['route']['ownergroup'] = ownergroup

    if routetype:
        payload['route']['routetype'] = routetype

    if detail:
        payload['route']['detail'] = detail

    execution = __proxy__['citrixns.put']('config/route', payload)

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


def update_route6(network=None, gateway=None, vlan=None, vxlan=None, weight=None, distance=None, cost=None,
                  advertise=None, msr=None, monitor=None, td=None, ownergroup=None, routetype=None, detail=None,
                  save=False):
    '''
    Update the running configuration for the route6 config key.

    network(str): IPv6 network address for which to add a route entry to the routing table of the NetScaler appliance.

    gateway(str): The gateway for this route. The value for this parameter is either an IPv6 address or null. Default value:
        0

    vlan(int): Integer value that uniquely identifies a VLAN through which the NetScaler appliance forwards the packets for
        this route. Default value: 0 Minimum value = 0 Maximum value = 4094

    vxlan(int): Integer value that uniquely identifies a VXLAN through which the NetScaler appliance forwards the packets for
        this route. Minimum value = 1 Maximum value = 16777215

    weight(int): Positive integer used by the routing algorithms to determine preference for this route over others of equal
        cost. The lower the weight, the higher the preference. Default value: 1 Minimum value = 1 Maximum value = 65535

    distance(int): Administrative distance of this route from the appliance. Default value: 1 Minimum value = 1 Maximum value
        = 254

    cost(int): Positive integer used by the routing algorithms to determine preference for this route. The lower the cost,
        the higher the preference. Default value: 1 Minimum value = 0 Maximum value = 65535

    advertise(str): Advertise this route. Possible values = DISABLED, ENABLED

    msr(str): Monitor this route with a monitor of type ND6 or PING. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    monitor(str): Name of the monitor, of type ND6 or PING, configured on the NetScaler appliance to monitor this route.
        Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    ownergroup(str): The owner node group in a Cluster for this route6. If owner node group is not specified then the route
        is treated as Striped route. Default value: DEFAULT_NG Minimum length = 1

    routetype(str): Type of IPv6 routes to remove from the routing table of the NetScaler appliance. Possible values =
        CONNECTED, STATIC, DYNAMIC, OSPF, ISIS, BGP, RIP, ND-RA-ROUTE, FIB6

    detail(bool): To get a detailed view.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_route6 <args>

    '''

    result = {}

    payload = {'route6': {}}

    if network:
        payload['route6']['network'] = network

    if gateway:
        payload['route6']['gateway'] = gateway

    if vlan:
        payload['route6']['vlan'] = vlan

    if vxlan:
        payload['route6']['vxlan'] = vxlan

    if weight:
        payload['route6']['weight'] = weight

    if distance:
        payload['route6']['distance'] = distance

    if cost:
        payload['route6']['cost'] = cost

    if advertise:
        payload['route6']['advertise'] = advertise

    if msr:
        payload['route6']['msr'] = msr

    if monitor:
        payload['route6']['monitor'] = monitor

    if td:
        payload['route6']['td'] = td

    if ownergroup:
        payload['route6']['ownergroup'] = ownergroup

    if routetype:
        payload['route6']['routetype'] = routetype

    if detail:
        payload['route6']['detail'] = detail

    execution = __proxy__['citrixns.put']('config/route6', payload)

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


def update_rsskeytype(rsstype=None, save=False):
    '''
    Update the running configuration for the rsskeytype config key.

    rsstype(str): Type of RSS key, possible values are SYMMETRIC and ASYMMETRIC. Default value: ASYMMETRIC Possible values =
        ASYMMETRIC, SYMMETRIC

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_rsskeytype <args>

    '''

    result = {}

    payload = {'rsskeytype': {}}

    if rsstype:
        payload['rsskeytype']['rsstype'] = rsstype

    execution = __proxy__['citrixns.put']('config/rsskeytype', payload)

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


def update_vlan(id=None, aliasname=None, dynamicrouting=None, ipv6dynamicrouting=None, mtu=None, sharing=None,
                save=False):
    '''
    Update the running configuration for the vlan config key.

    id(int): A positive integer that uniquely identifies a VLAN. Minimum value = 1 Maximum value = 4094

    aliasname(str): A name for the VLAN. Must begin with a letter, a number, or the underscore symbol, and can consist of
        from 1 to 31 letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=),
        colon (:), and underscore (_) characters. You should choose a name that helps identify the VLAN. However, you
        cannot perform any VLAN operation by specifying this name instead of the VLAN ID. Maximum length = 31

    dynamicrouting(str): Enable dynamic routing on this VLAN. Default value: DISABLED Possible values = ENABLED, DISABLED

    ipv6dynamicrouting(str): Enable all IPv6 dynamic routing protocols on this VLAN. Note: For the ENABLED setting to work,
        you must configure IPv6 dynamic routing protocols from the VTYSH command line. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    mtu(int): Specifies the maximum transmission unit (MTU), in bytes. The MTU is the largest packet size, excluding 14 bytes
        of ethernet header and 4 bytes of crc, that can be transmitted and received over this VLAN. Default value: 0
        Minimum value = 500 Maximum value = 9216

    sharing(str): If sharing is enabled, then this vlan can be shared across multiple partitions by binding it to all those
        partitions. If sharing is disabled, then this vlan can be bound to only one of the partitions. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_vlan <args>

    '''

    result = {}

    payload = {'vlan': {}}

    if id:
        payload['vlan']['id'] = id

    if aliasname:
        payload['vlan']['aliasname'] = aliasname

    if dynamicrouting:
        payload['vlan']['dynamicrouting'] = dynamicrouting

    if ipv6dynamicrouting:
        payload['vlan']['ipv6dynamicrouting'] = ipv6dynamicrouting

    if mtu:
        payload['vlan']['mtu'] = mtu

    if sharing:
        payload['vlan']['sharing'] = sharing

    execution = __proxy__['citrixns.put']('config/vlan', payload)

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


def update_vrid(id=None, priority=None, preemption=None, sharing=None, tracking=None, ownernode=None,
                trackifnumpriority=None, preemptiondelaytimer=None, save=False):
    '''
    Update the running configuration for the vrid config key.

    id(int): Integer that uniquely identifies the VMAC address. The generic VMAC address is in the form of
        00:00:5e:00:01:;lt;VRID;gt;. For example, if you add a VRID with a value of 60 and bind it to an interface, the
        resulting VMAC address is 00:00:5e:00:01:3c, where 3c is the hexadecimal representation of 60. Minimum value = 1
        Maximum value = 255

    priority(int): Base priority (BP), in an active-active mode configuration, which ordinarily determines the master VIP
        address. Default value: 255 Minimum value = 0 Maximum value = 255

    preemption(str): In an active-active mode configuration, make a backup VIP address the master if its priority becomes
        higher than that of a master VIP address bound to this VMAC address.  If you disable pre-emption while a backup
        VIP address is the master, the backup VIP address remains master until the original master VIPs priority becomes
        higher than that of the current master. Default value: ENABLED Possible values = ENABLED, DISABLED

    sharing(str): In an active-active mode configuration, enable the backup VIP address to process any traffic instead of
        dropping it. Default value: DISABLED Possible values = ENABLED, DISABLED

    tracking(str): The effective priority (EP) value, relative to the base priority (BP) value in an active-active mode
        configuration. When EP is set to a value other than None, it is EP, not BP, which determines the master VIP
        address. Available settings function as follows: * NONE - No tracking. EP = BP * ALL - If the status of all
        virtual servers is UP, EP = BP. Otherwise, EP = 0. * ONE - If the status of at least one virtual server is UP, EP
        = BP. Otherwise, EP = 0. * PROGRESSIVE - If the status of all virtual servers is UP, EP = BP. If the status of
        all virtual servers is DOWN, EP = 0. Otherwise EP = BP (1 - K/N), where N is the total number of virtual servers
        associated with the VIP address and K is the number of virtual servers for which the status is DOWN. Default:
        NONE. Default value: NONE Possible values = NONE, ONE, ALL, PROGRESSIVE

    ownernode(int): In a cluster setup, assign a cluster node as the owner of this VMAC address for IP based VRRP
        configuration. If no owner is configured, owner node is displayed as ALL and one node is dynamically elected as
        the owner. Minimum value = 0 Maximum value = 31

    trackifnumpriority(int): Priority by which the Effective priority will be reduced if any of the tracked interfaces goes
        down in an active-active configuration. Default value: 0 Minimum value = 1 Maximum value = 255

    preemptiondelaytimer(int): Preemption delay time, in seconds, in an active-active configuration. If any high priority
        node will come in network, it will wait for these many seconds before becoming master. Default value: 0 Minimum
        value = 1 Maximum value = 36000

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_vrid <args>

    '''

    result = {}

    payload = {'vrid': {}}

    if id:
        payload['vrid']['id'] = id

    if priority:
        payload['vrid']['priority'] = priority

    if preemption:
        payload['vrid']['preemption'] = preemption

    if sharing:
        payload['vrid']['sharing'] = sharing

    if tracking:
        payload['vrid']['tracking'] = tracking

    if ownernode:
        payload['vrid']['ownernode'] = ownernode

    if trackifnumpriority:
        payload['vrid']['trackifnumpriority'] = trackifnumpriority

    if preemptiondelaytimer:
        payload['vrid']['preemptiondelaytimer'] = preemptiondelaytimer

    execution = __proxy__['citrixns.put']('config/vrid', payload)

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


def update_vrid6(id=None, priority=None, preemption=None, sharing=None, tracking=None, preemptiondelaytimer=None,
                 trackifnumpriority=None, ownernode=None, save=False):
    '''
    Update the running configuration for the vrid6 config key.

    id(int): Integer value that uniquely identifies a VMAC6 address. Minimum value = 1 Maximum value = 255

    priority(int): Base priority (BP), in an active-active mode configuration, which ordinarily determines the master VIP
        address. Default value: 255 Minimum value = 0 Maximum value = 255

    preemption(str): In an active-active mode configuration, make a backup VIP address the master if its priority becomes
        higher than that of a master VIP address bound to this VMAC address.  If you disable pre-emption while a backup
        VIP address is the master, the backup VIP address remains master until the original master VIPs priority becomes
        higher than that of the current master. Default value: ENABLED Possible values = ENABLED, DISABLED

    sharing(str): In an active-active mode configuration, enable the backup VIP address to process any traffic instead of
        dropping it. Default value: DISABLED Possible values = ENABLED, DISABLED

    tracking(str): The effective priority (EP) value, relative to the base priority (BP) value in an active-active mode
        configuration. When EP is set to a value other than None, it is EP, not BP, which determines the master VIP
        address. Available settings function as follows: * NONE - No tracking. EP = BP * ALL - If the status of all
        virtual servers is UP, EP = BP. Otherwise, EP = 0. * ONE - If the status of at least one virtual server is UP, EP
        = BP. Otherwise, EP = 0. * PROGRESSIVE - If the status of all virtual servers is UP, EP = BP. If the status of
        all virtual servers is DOWN, EP = 0. Otherwise EP = BP (1 - K/N), where N is the total number of virtual servers
        associated with the VIP address and K is the number of virtual servers for which the status is DOWN. Default:
        NONE. Default value: NONE Possible values = NONE, ONE, ALL, PROGRESSIVE

    preemptiondelaytimer(int): Preemption delay time in seconds, in an active-active configuration. If any high priority node
        will come in network, it will wait for these many seconds before becoming master. Default value: 0 Minimum value
        = 1 Maximum value = 36000

    trackifnumpriority(int): Priority by which the Effective priority will be reduced if any of the tracked interfaces goes
        down in an active-active configuration. Default value: 0 Minimum value = 1 Maximum value = 255

    ownernode(int): In a cluster setup, assign a cluster node as the owner of this VMAC address for IP based VRRP
        configuration. If no owner is configured, ow ner node is displayed as ALL and one node is dynamically elected as
        the owner. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_vrid6 <args>

    '''

    result = {}

    payload = {'vrid6': {}}

    if id:
        payload['vrid6']['id'] = id

    if priority:
        payload['vrid6']['priority'] = priority

    if preemption:
        payload['vrid6']['preemption'] = preemption

    if sharing:
        payload['vrid6']['sharing'] = sharing

    if tracking:
        payload['vrid6']['tracking'] = tracking

    if preemptiondelaytimer:
        payload['vrid6']['preemptiondelaytimer'] = preemptiondelaytimer

    if trackifnumpriority:
        payload['vrid6']['trackifnumpriority'] = trackifnumpriority

    if ownernode:
        payload['vrid6']['ownernode'] = ownernode

    execution = __proxy__['citrixns.put']('config/vrid6', payload)

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


def update_vridparam(sendtomaster=None, hellointerval=None, deadinterval=None, save=False):
    '''
    Update the running configuration for the vridparam config key.

    sendtomaster(str): Forward packets to the master node, in an active-active mode configuration, if the virtual server is
        in the backup state and sharing is disabled. Default value: DISABLED Possible values = ENABLED, DISABLED

    hellointerval(int): Interval, in milliseconds, between vrrp advertisement messages sent to the peer node in active-active
        mode. Default value: 1000 Minimum value = 200 Maximum value = 1000

    deadinterval(int): Number of seconds after which a peer node in active-active mode is marked down if vrrp advertisements
        are not received from the peer node. Default value: 3 Minimum value = 1 Maximum value = 3

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_vridparam <args>

    '''

    result = {}

    payload = {'vridparam': {}}

    if sendtomaster:
        payload['vridparam']['sendtomaster'] = sendtomaster

    if hellointerval:
        payload['vridparam']['hellointerval'] = hellointerval

    if deadinterval:
        payload['vridparam']['deadinterval'] = deadinterval

    execution = __proxy__['citrixns.put']('config/vridparam', payload)

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


def update_vxlan(id=None, vlan=None, port=None, dynamicrouting=None, ipv6dynamicrouting=None, ns_type=None,
                 protocol=None, innervlantagging=None, save=False):
    '''
    Update the running configuration for the vxlan config key.

    id(int): A positive integer, which is also called VXLAN Network Identifier (VNI), that uniquely identifies a VXLAN.
        Minimum value = 1 Maximum value = 16777215

    vlan(int): ID of VLANs whose traffic is allowed over this VXLAN. If you do not specify any VLAN IDs, the NetScaler allows
        traffic of all VLANs that are not part of any other VXLANs. Minimum value = 2 Maximum value = 4094

    port(int): Specifies UDP destination port for VXLAN packets. Default value: 4789 Minimum value = 1 Maximum value = 65534

    dynamicrouting(str): Enable dynamic routing on this VXLAN. Default value: DISABLED Possible values = ENABLED, DISABLED

    ipv6dynamicrouting(str): Enable all IPv6 dynamic routing protocols on this VXLAN. Note: For the ENABLED setting to work,
        you must configure IPv6 dynamic routing protocols from the VTYSH command line. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    ns_type(str): VXLAN encapsulation type. VXLAN, VXLANGPE. Default value: VXLAN Possible values = VXLAN, VXLANGPE

    protocol(str): VXLAN-GPE next protocol. RESERVED, IPv4, IPv6, ETHERNET, NSH. Default value: ETHERNET Possible values =
        IPv4, IPv6, ETHERNET, NSH

    innervlantagging(str): Specifies whether NS should generate VXLAN packets with inner VLAN tag. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nsnetwork.update_vxlan <args>

    '''

    result = {}

    payload = {'vxlan': {}}

    if id:
        payload['vxlan']['id'] = id

    if vlan:
        payload['vxlan']['vlan'] = vlan

    if port:
        payload['vxlan']['port'] = port

    if dynamicrouting:
        payload['vxlan']['dynamicrouting'] = dynamicrouting

    if ipv6dynamicrouting:
        payload['vxlan']['ipv6dynamicrouting'] = ipv6dynamicrouting

    if ns_type:
        payload['vxlan']['type'] = ns_type

    if protocol:
        payload['vxlan']['protocol'] = protocol

    if innervlantagging:
        payload['vxlan']['innervlantagging'] = innervlantagging

    execution = __proxy__['citrixns.put']('config/vxlan', payload)

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
