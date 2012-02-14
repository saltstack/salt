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
    - ipv4:
      - proto: none
      - ipaddress: 10.1.0.1
      - netmask: 255.255.255.0
      - dns:
        - 8.8.8.8
        - 8.8.4.4
eth2:
  network:
    - managed
    - type: slave
    
eth3:
  network:
    - managed
    - type: slave

bond0:
  network:
    - managed
    - type: bond
    - ipv4:
      - ipaddress: 10.1.0.1
      - netmask: 255.255.255.0
      - dns:
        - 8.8.8.8
        - 8.8.4.4
    - ipv6:
    - enabled: False
    - watch:
      - network: eth2
      - network: eth3
    - slaves:
      - eth2
      - eth3
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
    - offload:
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
        enabled=True,
        ip=None,
        interface=None
        ):
    '''
    Ensure that the named interface is configured properly.
    
    name
        The name of the interface to manage
    
    enabled
        Designates the state of this interface.
        
    ip
        The IP parameters for this interface.
        
    interface
        Type of interface and configuration.
    
    '''
    pass
    
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Interface {0} is up to date.'.format(name)}
           
           # get current iface run through settings filter
           # get proposed iface submit to builder
           # diff iface
    pre = __salt__['network.get'](interface)
    new = __salt__['network.build'](ip, interface)

    return ret
           