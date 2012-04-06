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
    - used_in:
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
    - vlans:
      - 2
      - 3
      - 10
      - 12                
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
           
    # get current iface run through settings filter
    # get proposed iface submit to builder
    # diff iface
    try:
        old = __salt__['network.get'](name)
        new = __salt__['network.build'](name, type, kwargs)
        if not old and new:
            ret['changes']['diff'] = 'Added ifcfg script'
        elif old != new:
            diff = difflib.unified_diff(old, new)
            ret['changes']['diff'] = ''.join(diff)
    except AttributeError, error:
        ret['result'] = False
        ret['comment'] = error.message

    return ret
           
