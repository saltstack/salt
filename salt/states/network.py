# -*- coding: utf-8 -*-
'''
Configuration of network interfaces
===================================

The network module is used to create and manage network settings,
interfaces can be set as either managed or ignored. By default
all interfaces are ignored unless specified.

Please note that only Redhat and Debian style networking is currently
supported. This module will therefore only work on RH/CentOS/Fedora and
Debian/Ubuntu.

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
        - type: slave
        - master: bond0

    eth3:
      network.managed:
        - type: slave
        - master: bond0

    eth4:
      network.managed:
        - enabled: True
        - type: eth
        - proto: dhcp
        - bridge: br0

    bond0:
      network.managed:
        - type: bond
        - ipaddr: 10.1.0.1
        - netmask: 255.255.255.0
        - dns:
          - 8.8.8.8
          - 8.8.4.4
        - ipv6:
        - enabled: False
        - use_in:
          - network: eth2
          - network: eth3
        - require:
          - network: eth2
          - network: eth3
        - mode: 802.3ad
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
        - bypassfirewall: True
        - use:
          - network: eth4
        - require:
          - network: eth4
'''

# Import python libs
import difflib
import salt.utils
from salt.loader import _create_loader

# Define the module's virtual name
__virtualname__ = 'network'

# Set up logging
import logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Confine this module to non-Windows systems with the required execution
    module available.
    '''
    if not salt.utils.is_windows() and 'ip.get_interface' in __salt__:
        return __virtualname__
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
    if not 'test' in kwargs:
        kwargs['test'] = __opts__.get('test', False)

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
                diff = difflib.unified_diff(old, new)
                ret['result'] = None
                ret['comment'] = 'Interface {0} is set to be ' \
                                 'updated.'.format(name)
                ret['changes']['interface'] = ''.join(diff)
        else:
            if not old and new:
                ret['comment'] = 'Interface {0} ' \
                                 'added.'.format(name)
                ret['changes']['interface'] = 'Added network interface.'
            elif old != new:
                diff = difflib.unified_diff(old, new)
                ret['comment'] = 'Interface {0} ' \
                                 'updated.'.format(name)
                ret['changes']['interface'] = ''.join(diff)
    except AttributeError as error:
        ret['result'] = False
        ret['comment'] = error.message
        return ret

    # Setup up bond modprobe script if required
    if type == 'bond':
        try:
            old = __salt__['ip.get_bond'](name)
            new = __salt__['ip.build_bond'](name, **kwargs)
            if kwargs['test']:
                if old == new:
                    pass
                if not old and new:
                    ret['result'] = None
                    ret['comment'] = 'Bond interface {0} is set to be ' \
                                     'added.'.format(name)
                elif old != new:
                    diff = difflib.unified_diff(old, new)
                    ret['result'] = None
                    ret['comment'] = 'Bond interface {0} is set to be ' \
                                     'updated.'.format(name)
                    ret['changes']['bond'] = ''.join(diff)
            else:
                if not old and new:
                    ret['comment'] = 'Bond interface {0} ' \
                                     'added.'.format(name)
                    ret['changes']['bond'] = 'Added bond {0}.'.format(name)
                elif old != new:
                    diff = difflib.unified_diff(old, new)
                    ret['comment'] = 'Bond interface {0} ' \
                                     'updated.'.format(name)
                    ret['changes']['bond'] = ''.join(diff)
        except AttributeError as error:
            #TODO Add a way of reversing the interface changes.
            ret['result'] = False
            ret['comment'] = error.message
            return ret

    if kwargs['test']:
        return ret

    # Bring up/shutdown interface
    try:
        if enabled:
            __salt__['ip.up'](name, type)
        else:
            __salt__['ip.down'](name, type)
    except Exception as error:
        ret['result'] = False
        ret['comment'] = error.message
        return ret

    load = _create_loader(__opts__, 'grains', 'grain', ext_dirs=False)
    grains_info = load.gen_grains()
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
    if not 'test' in kwargs:
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
                diff = difflib.unified_diff(old, new)
                ret['result'] = None
                ret['comment'] = 'Interface {0} routes are set to be updated.'.format(name)
                ret['changes']['network_routes'] = ''.join(diff)
                return ret
        if not old and new:
            apply_routes = True
            ret['comment'] = 'Interface {0} routes added.'.format(name)
            ret['changes']['network_routes'] = 'Added interface {0} routes.'.format(name)
        elif old != new:
            diff = difflib.unified_diff(old, new)
            apply_routes = True
            ret['comment'] = 'Interface {0} routes updated.'.format(name)
            ret['changes']['network_routes'] = ''.join(diff)
    except AttributeError as error:
        ret['result'] = False
        ret['comment'] = error.message
        return ret

    # Apply interface routes
    if apply_routes:
        try:
            __salt__['ip.apply_network_settings'](**kwargs)
        except AttributeError as error:
            ret['result'] = False
            ret['comment'] = error.message
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
                diff = difflib.unified_diff(old, new)
                ret['result'] = None
                ret['comment'] = 'Global network settings are set to be updated.'
                ret['changes']['network_settings'] = ''.join(diff)
                return ret
        if not old and new:
            apply_net_settings = True
            ret['changes']['network_settings'] = 'Added global network settings.'
        elif old != new:
            diff = difflib.unified_diff(old, new)
            apply_net_settings = True
            ret['changes']['network_settings'] = ''.join(diff)
    except AttributeError as error:
        ret['result'] = False
        ret['comment'] = error.message
        return ret

    # Apply global network settings
    if apply_net_settings:
        try:
            __salt__['ip.apply_network_settings'](**kwargs)
        except AttributeError as error:
            ret['result'] = False
            ret['comment'] = error.message
            return ret

    return ret
