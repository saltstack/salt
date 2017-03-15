# -*- coding: utf-8 -*-
'''
Configuration of network interfaces
===================================

The network module is used to create and manage network settings,
interfaces can be set as either managed or ignored. By default
all interfaces are ignored unless specified.

.. note::

    Prior to version 2014.1.0, only RedHat-based systems (RHEL,
    CentOS, Scientific Linux, etc.) are supported. Support for Debian/Ubuntu is
    new in 2014.1.0 and should be considered experimental.

    Other platforms are not yet supported.

.. code-block:: yaml

    system:
      network.system:
        - enabled: True
        - hostname: server1.example.com
        - gateway: 192.168.0.1
        - gatewaydev: eth0
        - nozeroconf: True
        - nisdomain: example.com
        - require_reboot: True

    eth0:
      network.managed:
        - enabled: True
        - type: eth
        - proto: none
        - ipaddr: 10.1.0.1
        - netmask: 255.255.255.0
        - dns:
          - 8.8.8.8
          - 8.8.4.4

    eth0-range0:
      network.managed:
        - type: eth
        - ipaddr_start: 192.168.1.1
        - ipaddr_end: 192.168.1.10
        - clonenum_start: 10
        - mtu: 9000

    bond0-range0:
      network.managed:
        - type: eth
        - ipaddr_start: 192.168.1.1
        - ipaddr_end: 192.168.1.10
        - clonenum_start: 10
        - mtu: 9000

    eth1.0-range0:
      network.managed:
        - type: eth
        - ipaddr_start: 192.168.1.1
        - ipaddr_end: 192.168.1.10
        - clonenum_start: 10
        - vlan: True
        - mtu: 9000

    bond0.1-range0:
      network.managed:
        - type: eth
        - ipaddr_start: 192.168.1.1
        - ipaddr_end: 192.168.1.10
        - clonenum_start: 10
        - vlan: True
        - mtu: 9000

    .. note::
        add support of ranged interfaces (vlan, bond and eth) for redhat system,
        Important:type must be eth.

    routes:
      network.routes:
        - name: eth0
        - routes:
          - name: secure_network
            ipaddr: 10.2.0.0
            netmask: 255.255.255.0
            gateway: 10.1.0.3
          - name: HQ_network
            ipaddr: 10.100.0.0
            netmask: 255.255.0.0
            gateway: 10.1.0.10

    eth2:
      network.managed:
        - enabled: True
        - type: slave
        - master: bond0

    eth3:
      network.managed:
        - enabled: True
        - type: slave
        - master: bond0

    eth4:
      network.managed:
        - enabled: True
        - type: eth
        - proto: dhcp
        - bridge: br0

    eth5:
      network.managed:
        - enabled: True
        - type: eth
        - proto: dhcp
        - noifupdown: True  # Do not restart the interface
                            # you need to reboot/reconfigure manualy

    bond0:
      network.managed:
        - type: bond
        - ipaddr: 10.1.0.1
        - netmask: 255.255.255.0
        - mode: active-backup
        - proto: static
        - dns:
          - 8.8.8.8
          - 8.8.4.4
        - ipv6:
        - enabled: False
        - slaves: eth2 eth3
        - require:
          - network: eth2
          - network: eth3
        - miimon: 100
        - arp_interval: 250
        - downdelay: 200
        - lacp_rate: fast
        - max_bonds: 1
        - updelay: 0
        - use_carrier: on
        - xmit_hash_policy: layer2
        - mtu: 9000
        - autoneg: on
        - speed: 1000
        - duplex: full
        - rx: on
        - tx: off
        - sg: on
        - tso: off
        - ufo: off
        - gso: off
        - gro: off
        - lro: off

    bond0.2:
      network.managed:
        - type: vlan
        - ipaddr: 10.1.0.2
        - use:
          - network: bond0
        - require:
          - network: bond0

    bond0.3:
      network.managed:
        - type: vlan
        - ipaddr: 10.1.0.3
        - use:
          - network: bond0
        - require:
          - network: bond0

    bond0.10:
      network.managed:
        - type: vlan
        - ipaddr: 10.1.0.4
        - use:
          - network: bond0
        - require:
          - network: bond0

    bond0.12:
      network.managed:
        - type: vlan
        - ipaddr: 10.1.0.5
        - use:
          - network: bond0
        - require:
          - network: bond0
    br0:
      network.managed:
        - enabled: True
        - type: bridge
        - proto: dhcp
        - bridge: br0
        - delay: 0
        - ports: eth4
        - bypassfirewall: True
        - use:
          - network: eth4
        - require:
          - network: eth4

    system:
      network.system:
        - enabled: True
        - hostname: server1.example.com
        - gateway: 192.168.0.1
        - gatewaydev: eth0
        - nozeroconf: True
        - nisdomain: example.com
        - require_reboot: True
        - apply_hostname: True

    lo:
      network.managed:
        - name: lo
        - type: eth
        - onboot: yes
        - userctl: no
        - ipv6_autoconf: no
        - enable_ipv6: true
        - ipaddrs:
          - 127.0.0.1/8
          - 10.1.0.4/32
          - 10.1.0.12/32
        - ipv6addrs:
          - fc00::1/128
          - fc00::100/128

    .. note::
        Apply changes to hostname immediately.

    .. versionadded:: 2015.5.0

    system:
      network.system:
        - hostname: server2.example.com
        - apply_hostname: True
        - retain_settings: True

    .. note::
        Use `retain_settings` to retain current network settings that are not
        otherwise specified in the state. Particularly useful if only setting
        the hostname. Default behavior is to delete unspecified network
        settings.

    .. versionadded:: 2016.11.0

.. note::

    When managing bridged interfaces on a Debian or Ubuntu based system, the
    ports argument is required.  Red Hat systems will ignore the argument.
'''
from __future__ import absolute_import

# Import python libs
import difflib
import salt.utils
import salt.utils.network
import salt.loader

# Set up logging
import logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Confine this module to non-Windows systems with the required execution
    module available.
    '''
    if not salt.utils.is_windows() and 'ip.get_interface' in __salt__:
        return True
    return False


def managed(name, type, enabled=True, **kwargs):
    '''
    Ensure that the named interface is configured properly.

    name
        The name of the interface to manage

    type
        Type of interface and configuration.

    enabled
        Designates the state of this interface.

    kwargs
        The IP parameters for this interface.

    '''
    # For this function we are purposefully overwriting a bif
    # to enhance the user experience. This does not look like
    # it will cause a problem. Just giving a heads up in case
    # it does create a problem.
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': 'Interface {0} is up to date.'.format(name),
    }
    if 'test' not in kwargs:
        kwargs['test'] = __opts__.get('test', False)

    # set ranged status
    apply_ranged_setting = False

    # Build interface
    try:
        old = __salt__['ip.get_interface'](name)
        new = __salt__['ip.build_interface'](name, type, enabled, **kwargs)
        if kwargs['test']:
            if old == new:
                pass
            if not old and new:
                ret['result'] = None
                ret['comment'] = 'Interface {0} is set to be ' \
                                 'added.'.format(name)
            elif old != new:
                diff = difflib.unified_diff(old, new, lineterm='')
                ret['result'] = None
                ret['comment'] = 'Interface {0} is set to be ' \
                                 'updated:\n{1}'.format(name, '\n'.join(diff))
        else:
            if not old and new:
                ret['comment'] = 'Interface {0} ' \
                                 'added.'.format(name)
                ret['changes']['interface'] = 'Added network interface.'
                apply_ranged_setting = True
            elif old != new:
                diff = difflib.unified_diff(old, new, lineterm='')
                ret['comment'] = 'Interface {0} ' \
                                 'updated.'.format(name)
                ret['changes']['interface'] = '\n'.join(diff)
                apply_ranged_setting = True
    except AttributeError as error:
        ret['result'] = False
        ret['comment'] = str(error)
        return ret

    # Debian based system can have a type of source
    # in the interfaces file, we don't ifup or ifdown it
    if type == 'source':
        return ret

    # Setup up bond modprobe script if required
    if type == 'bond':
        try:
            old = __salt__['ip.get_bond'](name)
            new = __salt__['ip.build_bond'](name, **kwargs)
            if kwargs['test']:
                if not old and new:
                    ret['result'] = None
                    ret['comment'] = 'Bond interface {0} is set to be ' \
                                     'added.'.format(name)
                elif old != new:
                    diff = difflib.unified_diff(old, new, lineterm='')
                    ret['result'] = None
                    ret['comment'] = 'Bond interface {0} is set to be ' \
                                     'updated:\n{1}'.format(name, '\n'.join(diff))
            else:
                if not old and new:
                    ret['comment'] = 'Bond interface {0} ' \
                                     'added.'.format(name)
                    ret['changes']['bond'] = 'Added bond {0}.'.format(name)
                    apply_ranged_setting = True
                elif old != new:
                    diff = difflib.unified_diff(old, new, lineterm='')
                    ret['comment'] = 'Bond interface {0} ' \
                                     'updated.'.format(name)
                    ret['changes']['bond'] = '\n'.join(diff)
                    apply_ranged_setting = True
        except AttributeError as error:
            #TODO Add a way of reversing the interface changes.
            ret['result'] = False
            ret['comment'] = str(error)
            return ret

    if kwargs['test']:
        return ret

    # For Redhat/Centos ranged network
    if "range" in name:
        if apply_ranged_setting:
            try:
                ret['result'] = __salt__['service.restart']('network')
                ret['comment'] = "network restarted for change of ranged interfaces"
                return ret
            except Exception as error:
                ret['result'] = False
                ret['comment'] = str(error)
                return ret
        ret['result'] = True
        ret['comment'] = "no change, passing it"
        return ret

    # Bring up/shutdown interface
    try:
        # Get Interface current status
        interfaces = salt.utils.network.interfaces()
        interface_status = False
        if name in interfaces:
            interface_status = interfaces[name].get('up')
        else:
            for iface in interfaces:
                if 'secondary' in interfaces[iface]:
                    for second in interfaces[iface]['secondary']:
                        if second.get('label', '') == name:
                            interface_status = True
        if enabled:
            if 'noifupdown' not in kwargs:
                if interface_status:
                    if ret['changes']:
                        # Interface should restart to validate if it's up
                        __salt__['ip.down'](name, type)
                        __salt__['ip.up'](name, type)
                        ret['changes']['status'] = 'Interface {0} restart to validate'.format(name)
                else:
                    __salt__['ip.up'](name, type)
                    ret['changes']['status'] = 'Interface {0} is up'.format(name)
        else:
            if 'noifupdown' not in kwargs:
                if interface_status:
                    __salt__['ip.down'](name, type)
                    ret['changes']['status'] = 'Interface {0} down'.format(name)
    except Exception as error:
        ret['result'] = False
        ret['comment'] = str(error)
        return ret

    # Try to enslave bonding interfaces after master was created
    if type == 'bond' and 'noifupdown' not in kwargs:

        if 'slaves' in kwargs and kwargs['slaves']:
            # Check that there are new slaves for this master
            present_slaves = __salt__['cmd.run'](
                ['cat', '/sys/class/net/{0}/bonding/slaves'.format(name)]).split()
            desired_slaves = kwargs['slaves'].split()
            missing_slaves = set(desired_slaves) - set(present_slaves)

            # Enslave only slaves missing in master
            if missing_slaves:
                ifenslave_path = __salt__['cmd.run'](['which', 'ifenslave']).strip()
                if ifenslave_path:
                    log.info("Adding slaves '{0}' to the master {1}".format(' '.join(missing_slaves), name))
                    cmd = [ifenslave_path, name] + list(missing_slaves)
                    __salt__['cmd.run'](cmd, python_shell=False)
                else:
                    log.error("Command 'ifenslave' not found")
                ret['changes']['enslave'] = (
                    "Added slaves '{0}' to master '{1}'"
                    .format(' '.join(missing_slaves), name))
            else:
                log.info("All slaves '{0}' are already added to the master {1}"
                         ", no actions required".format(' '.join(missing_slaves), name))

    if enabled and interface_status:
        # Interface was restarted, return
        return ret

    # TODO: create saltutil.refresh_grains that fires events to the minion daemon
    grains_info = salt.loader.grains(__opts__, True)
    __grains__.update(grains_info)
    __salt__['saltutil.refresh_modules']()
    return ret


def routes(name, **kwargs):
    '''
    Manage network interface static routes.

    name
        Interface name to apply the route to.

    kwargs
        Named routes
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': 'Interface {0} routes are up to date.'.format(name),
    }
    apply_routes = False
    if 'test' not in kwargs:
        kwargs['test'] = __opts__.get('test', False)

    # Build interface routes
    try:
        old = __salt__['ip.get_routes'](name)
        new = __salt__['ip.build_routes'](name, **kwargs)
        if kwargs['test']:
            if old == new:
                return ret
            if not old and new:
                ret['result'] = None
                ret['comment'] = 'Interface {0} routes are set to be added.'.format(name)
                return ret
            elif old != new:
                diff = difflib.unified_diff(old, new, lineterm='')
                ret['result'] = None
                ret['comment'] = 'Interface {0} routes are set to be ' \
                                 'updated:\n{1}'.format(name, '\n'.join(diff))
                return ret
        if not old and new:
            apply_routes = True
            ret['comment'] = 'Interface {0} routes added.'.format(name)
            ret['changes']['network_routes'] = 'Added interface {0} routes.'.format(name)
        elif old != new:
            diff = difflib.unified_diff(old, new, lineterm='')
            apply_routes = True
            ret['comment'] = 'Interface {0} routes updated.'.format(name)
            ret['changes']['network_routes'] = '\n'.join(diff)
    except AttributeError as error:
        ret['result'] = False
        ret['comment'] = str(error)
        return ret

    # Apply interface routes
    if apply_routes:
        try:
            __salt__['ip.apply_network_settings'](**kwargs)
        except AttributeError as error:
            ret['result'] = False
            ret['comment'] = str(error)
            return ret

    return ret


def system(name, **kwargs):
    '''
    Ensure that global network settings are configured properly.

    name
        Custom name to represent this configuration change.

    kwargs
        The global parameters for the system.

    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': 'Global network settings are up to date.',
    }
    apply_net_settings = False
    kwargs['test'] = __opts__['test']
    # Build global network settings
    try:
        old = __salt__['ip.get_network_settings']()
        new = __salt__['ip.build_network_settings'](**kwargs)
        if __opts__['test']:
            if old == new:
                return ret
            if not old and new:
                ret['result'] = None
                ret['comment'] = 'Global network settings are set to be added.'
                return ret
            elif old != new:
                diff = difflib.unified_diff(old, new, lineterm='')
                ret['result'] = None
                ret['comment'] = 'Global network settings are set to be ' \
                                 'updated:\n{0}'.format('\n'.join(diff))
                return ret
        if not old and new:
            apply_net_settings = True
            ret['changes']['network_settings'] = 'Added global network settings.'
        elif old != new:
            diff = difflib.unified_diff(old, new, lineterm='')
            apply_net_settings = True
            ret['changes']['network_settings'] = '\n'.join(diff)
    except AttributeError as error:
        ret['result'] = False
        ret['comment'] = str(error)
        return ret
    except KeyError as error:
        ret['result'] = False
        ret['comment'] = str(error)
        return ret

    # Apply global network settings
    if apply_net_settings:
        try:
            __salt__['ip.apply_network_settings'](**kwargs)
        except AttributeError as error:
            ret['result'] = False
            ret['comment'] = str(error)
            return ret

    return ret
