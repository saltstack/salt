import difflib

'''
Network Management
==================
The network module is used to create and manage network settings,
interfaces can be set as either managed or ignored. By default
all interfaces are ignored unless specified.

.. code-block:: yaml

eth0:
  network:
    - managed
    - enabled: True
    - type: eth
    - proto: none
    - ipaddr: 10.1.0.1
    - netmask: 255.255.255.0
    - dns:
      - 8.8.8.8
      - 8.8.4.4
eth2:
  network:
    - managed
    - type: slave
    - master: bond0

eth3:
  network:
    - managed
    - type: slave
    - master: bond0

bond0:
  network:
    - managed
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
  network:
    - managed
    - type: vlan
    - ipaddr: 10.1.0.2
    - use:
      - network: bond0
    - require:
      - network: bond0

bond0.3:
  network:
    - managed
    - type: vlan
    - ipaddr: 10.1.0.3
    - use:
      - network: bond0
    - require:
      - network: bond0

bond0.10:
  network:
    - managed
    - type: vlan
    - ipaddr: 10.1.0.4
    - use:
      - network: bond0
    - require:
      - network: bond0

bond0.12:
  network:
    - managed
    - type: vlan
    - ipaddr: 10.1.0.5
    - use:
      - network: bond0
    - require:
      - network: bond0
'''

def managed(
        name,
        type,
        enabled=True,
        **kwargs
        ):
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

    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': 'Interface {0} is up to date.'.format(name)
    }

    # Build interface
    try:
        old = __salt__['ip.get_interface'](name)
        new = __salt__['ip.build_interface'](name, type, kwargs)
        if __opts__['test']:
            if old == new:
                return ret
            if not old and new:
                ret['result'] = None
                ret['comment'] = 'Interface {0} is set to be added'.format(name)
                return ret
            elif old != new:
                ret['result'] = None
                ret['comment'] = 'Interface 0{} is set to be updated'.format(
                    name)
                return ret
        if not old and new:
            ret['changes']['interface'] = 'Added network interface'
        elif old != new:
            diff = difflib.unified_diff(old, new)
            ret['changes']['interface'] = ''.join(diff)
    except AttributeError, error:
        ret['result'] = False
        ret['comment'] = error.message
        return ret

    # Setup up bond modprobe script if required
    if type == 'bond':
        try:
            old = __salt__['ip.get_bond'](name)
            new = __salt__['ip.build_bond'](name, kwargs)
            if not old and new:
                ret['changes']['bond'] = 'Added bond'
            elif old != new:
                diff = difflib.unified_diff(old, new)
                ret['changes']['bond'] = ''.join(diff)
        except AttributeError, error:
            #TODO Add a way of reversing the interface changes.
            ret['result'] = False
            ret['comment'] = error.message
            return ret

    #Bring up/shutdown interface
    try:
        if enabled:
            __salt__['ip.up'](name)
        else:
            __salt__['ip.down'](name)
    except Exception, error:
        ret['result'] = False
        ret['comment'] = error.message
        return ret

    return ret
