'''
Configuration of network interfaces.
====================================

The network module is used to create and manage network settings,
interfaces can be set as either managed or ignored. By default
all interfaces are ignored unless specified.

Please note that only Redhat-style networking is currently
supported. This module will therefore only work on RH/CentOS/Fedora.

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
from salt.loader import _create_loader

# Import salt libs
import salt.utils

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
    kwargs['test'] = __opts__['test']

    # Build interface
    try:
        old = __salt__['ip.get_interface'](name)
        new = __salt__['ip.build_interface'](name, type, enabled, **kwargs)
        if __opts__['test']:
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
                ret['changes']['interface'] = 'Added network interface.'
            elif old != new:
                diff = difflib.unified_diff(old, new)
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
            if __opts__['test']:
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
                    ret['changes']['bond'] = 'Added bond {0}.'.format(name)
                elif old != new:
                    diff = difflib.unified_diff(old, new)
                    ret['changes']['bond'] = ''.join(diff)
        except AttributeError as error:
            #TODO Add a way of reversing the interface changes.
            ret['result'] = False
            ret['comment'] = error.message
            return ret

    if __opts__['test']:
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
    kwargs['test'] = __opts__['test']
    # Build interface routes
    try:
        old = __salt__['ip.get_routes'](name)
        new = __salt__['ip.build_routes'](name, **kwargs)
        if __opts__['test']:
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
            ret['changes']['network_routes'] = 'Added interface {0} routes.'.format(name)
        elif old != new:
            diff = difflib.unified_diff(old, new)
            apply_routes = True
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


def fw_disabled(name):
    '''
    Disable all the firewall profiles (Windows only)
    '''
    
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}
    
    # Validate Windows
    if not salt.utils.is_windows():
        ret['result'] = False
        ret['comment'] = 'This state is supported only on Windows'
        return ret
    
    # Determine what to do
    action = False
    current_config = __salt__['network.get_fw_config']()
    for key in current_config:
        if current_config[key]:
            action = True
            ret['changes'] = {'fw': 'disabled'}
            break
    
    if __opts__['test']:
        return ret
    
    # Disable it
    if action:
        ret['result'] = __salt__['network.disable_fw']()
        if not ret['result']:
            ret['comment'] = 'could not disable the FW'
    else:
        ret['comment'] = 'all the firewall profiles are disabled'
    
    return ret


def dns_exists(name, servers=None, interface='Local Area Connection'):
    '''
    Configure the dns server list in the specified interface (Windows only)
    
    Example::

        config_dns_servers:
          network_win.dns_exists:
            - servers:
              - 8.8.8.8
              - 8.8.8.9
    '''
    
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}
    
    # Validate Windows
    if not salt.utils.is_windows():
        ret['result'] = False
        ret['comment'] = 'This state is supported only on Windows'
        return ret
    
    # Validate syntax
    if type(servers) != list:
        ret['result'] = False
        ret['comment'] = 'servers entry is not a list !'
        return ret
    
    # Do nothing is already configured
    configured_list = __salt__['network.get_dns_servers'](interface)
    if configured_list == servers:
        ret['comment'] = '{0} are already configured'.format( servers )
        return ret
    else:
        ret['changes'] = {'configure servers': servers}
    
    if __opts__['test']:
        return ret
    
    # add the dns servers
    for i in range(0, len(servers)):
        if not __salt__['network.add_dns'](servers[i] ,interface, i+1):
            ret['comment'] = 'failed to add {0} as dns server number {1}'.format(servers[i] ,i+1)
            ret['result'] = False
            if i != 0:
                ret['changes'] = {'configure servers': servers[0,i]}
            else:
                ret['changes'] = {}
            return ret
    
    return ret


def dns_dhcp(name, interface='Local Area Connection'):
    '''
    Configure the dns server list from DHCP Server (Windows only)
    '''
    
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}
    
    # Validate Windows
    if not salt.utils.is_windows():
        ret['result'] = False
        ret['comment'] = 'This state is supported only on Windows'
        return ret
    
    # Check the config
    config = __salt__['network.get_dns_config'](interface)
    if config == 'dhcp':
        ret['comment'] = '{0} already configured with dns from dhcp'.format( interface )
        return ret
    else:
        ret['changes'] = {'dns': 'configured from dhcp'}
    
    if __opts__['test']:
        return ret
    
    # change the configuration
    ret['result'] = __salt__['network.dns_dhcp'](interface)
    if not ret['result']:
        ret['changes'] = {}
        ret['comment'] = 'could not configure "{0}" dns servers from dhcp'.format( interface )
    
    return ret
    
