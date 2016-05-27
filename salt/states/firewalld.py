# -*- coding: utf-8 -*-
'''
Management of firewalld

.. versionadded:: 2015.8.0

The following example applies changes to the public zone, blocks echo-reply
and echo-request packets, does not set the zone to be the default, enables
masquerading, and allows ports 22/tcp and 25/tcp.
It will be applied permanently and directly before restart/reload.

.. code-block:: yaml

    public:
      firewalld.present:
        - name: public
        - block_icmp:
          - echo-reply
          - echo-request
        - default: False
        - masquerade: True
        - ports:
          - 22/tcp
          - 25/tcp

The following example applies changes to the public zone, enables
masquerading and configures port forwarding TCP traffic from port 22
to 2222, and forwards TCP traffic from port 80 to 443 at 192.168.0.1.

.. code-block:: yaml

  my_zone:
    firewalld.present:
      - name: public
      - masquerade: True
      - port_fwd:
        - 22:2222:tcp
        - 80:443:tcp:192.168.0.1

The following example binds the public zone to interface eth0 and to all
packets coming from the 192.168.1.0/24 subnet. It also removes the zone
from all other interfaces or sources.

.. code-block:: yaml

  public:
    firewalld.present:
      - name: public
      - interfaces:
        - eth0
      - sources:
        - 192.168.1.0/24

Here, we define a new service that encompasses TCP ports 4505 4506:

.. code-block:: yaml

  saltmaster:
    firewalld.service:
      - name: saltmaster
      - ports:
        - 4505/tcp
        - 4506/tcp

To make this new service available in a zone, the following can be used, which
would allow access to the salt master from the 10.0.0.0/8 subnet:

.. code-block:: yaml

  saltzone:
    firewalld.present:
      - name: saltzone
      - services:
        - saltmaster
      - sources:
        - 10.0.0.0/8
'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
from salt.exceptions import CommandExecutionError
import salt.utils

log = logging.getLogger(__name__)


class ForwardingMapping(object):
    '''
    Represents a port forwarding statement mapping a local port to a remote
    port for a specific protocol (TCP or UDP)
    '''
    def __init__(self, srcport, destport, protocol, destaddr):
        self.srcport = srcport
        self.destport = destport
        self.protocol = protocol
        self.destaddr = destaddr

    def __eq__(self, other):
        return (self.srcport == other.srcport and
                self.destport == other.destport and
                self.protocol == other.protocol and
                self.destaddr == other.destaddr)

    def __ne__(self, other):
        return not self.__eq__(other)

    # hash is needed for set operations
    def __hash__(self):
        return (hash(self.srcport) ^
            hash(self.destport) ^
            hash(self.protocol) ^
            hash(self.destaddr))

    def todict(self):
        '''
        Returns a pretty dictionary meant for command line output.
        '''
        return {
            'Source port': self.srcport,
            'Destination port': self.destport,
            'Protocol': self.protocol,
            'Destination address': self.destaddr}


def _parse_forward(mapping):
    '''
    Parses a port forwarding statement in the form used by this state:

    from_port:to_port:protocol[:destination]

    and returns a ForwardingMapping object
    '''
    if len(mapping.split(':')) > 3:
        (srcport, destport, protocol, destaddr) = mapping.split(':')
    else:
        (srcport, destport, protocol) = mapping.split(':')
        destaddr = ''
    return ForwardingMapping(srcport, destport, protocol, destaddr)


def __virtual__():
    '''
    Ensure the firewall-cmd is available
    '''
    if salt.utils.which('firewall-cmd'):
        return True

    return (False, 'firewall-cmd is not available, firewalld is probably not installed.')


def present(name,
            block_icmp=None,
            default=None,
            masquerade=False,
            ports=None,
            port_fwd=None,
            services=None,
            prune_services=True,
            interfaces=None,
            sources=None,
            rich_rules=None):

    '''
    Ensure a zone has specific attributes.
    '''

    ret = _present(name, block_icmp, default, masquerade, ports, port_fwd,
                   services, prune_services, interfaces, sources, rich_rules)

    if ret['changes'] != {}:
        __salt__['firewalld.reload_rules']()

    ret['result'] = True
    if ret['changes'] == {}:
        ret['comment'] = '\'{0}\' is already in the desired state.'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Configuration for \'{0}\' will change.'.format(name)
        return ret

    ret['comment'] = '\'{0}\' was configured.'.format(name)
    return ret


def service(name,
            ports=None,
            protocols=None):
    '''
    Ensure the service exists and encompasses the specified ports and
    protocols.

    .. versionadded:: Boron
    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}

    if name not in __salt__['firewalld.get_services']():
        __salt__['firewalld.new_service'](name, restart=False)

    ports = ports or []

    try:
        _current_ports = __salt__['firewalld.get_service_ports'](name)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret

    new_ports = set(ports) - set(_current_ports)
    old_ports = set(_current_ports) - set(ports)

    for port in new_ports:
        if not __opts__['test']:
            try:
                __salt__['firewalld.add_service_port'](name, port)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

    for port in old_ports:
        if not __opts__['test']:
            try:
                __salt__['firewalld.remove_service_port'](name, port)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

    if new_ports or old_ports:
        ret['changes'].update({'ports':
                                {'old': _current_ports,
                                 'new': ports}})

    protocols = protocols or []

    try:
        _current_protocols = __salt__['firewalld.get_service_protocols'](name)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret

    new_protocols = set(protocols) - set(_current_protocols)
    old_protocols = set(_current_protocols) - set(protocols)

    for protocol in new_protocols:
        if not __opts__['test']:
            try:
                __salt__['firewalld.add_service_protocol'](name, protocol)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

    for protocol in old_protocols:
        if not __opts__['test']:
            try:
                __salt__['firewalld.remove_service_protocol'](name, protocol)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

    if new_protocols or old_protocols:
        ret['changes'].update({'protocols':
                              {'old': _current_protocols,
                               'new': protocols}})

    if ret['changes'] != {}:
        __salt__['firewalld.reload_rules']()

    ret['result'] = True
    if ret['changes'] == {}:
        ret['comment'] = '\'{0}\' is already in the desired state.'.format(
            name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Configuration for \'{0}\' will change.'.format(name)
        return ret

    ret['comment'] = '\'{0}\' was configured.'.format(name)
    return ret


def _present(name,
            block_icmp=None,
            default=None,
            masquerade=False,
            ports=None,
            port_fwd=None,
            services=None,
            prune_services=True,
            interfaces=None,
            sources=None,
            rich_rules=None):
    '''
    Ensure a zone has specific attributes.
    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}

    try:
        zones = __salt__['firewalld.get_zones'](permanent=True)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret

    if name not in zones:
        if not __opts__['test']:
            try:
                __salt__['firewalld.new_zone'](name)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

        ret['changes'].update({name:
                              {'old': zones,
                               'new': name}})

    block_icmp = block_icmp or []
    new_icmp_types = []
    old_icmp_types = []
    try:
        _valid_icmp_types = __salt__['firewalld.get_icmp_types'](
            permanent=True)
        _current_icmp_blocks = __salt__['firewalld.list_icmp_block'](name,
            permanent=True)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret

    old_icmp_types = set(_current_icmp_blocks) - set(block_icmp)
    new_icmp_types = set(block_icmp) - set(_current_icmp_blocks)

    for icmp_type in new_icmp_types:
        if icmp_type in _valid_icmp_types:
            if not __opts__['test']:
                try:
                    __salt__['firewalld.block_icmp'](name, icmp_type,
                                                     permanent=True)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
        else:
            log.error('{0} is an invalid ICMP type'.format(icmp_type))

    for icmp_type in old_icmp_types:
        # no need to check against _valid_icmp_types here, because all
        # elements in old_icmp_types are guaranteed to be in
        # _current_icmp_blocks, whose elements are inherently valid
        if not __opts__['test']:
            try:
                __salt__['firewalld.allow_icmp'](name, icmp_type,
                                                 permanent=True)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

    if new_icmp_types or old_icmp_types:
        ret['changes'].update({'icmp_types':
                                {'old': _current_icmp_blocks,
                                'new': block_icmp}})

    # that's the only parameter that can't be permanent or runtime, it's
    # directly both
    if default:
        try:
            default_zone = __salt__['firewalld.default_zone']()
        except CommandExecutionError as err:
            ret['comment'] = 'Error: {0}'.format(err)
            return ret
        if name != default_zone:
            if not __opts__['test']:
                try:
                    __salt__['firewalld.set_default_zone'](name)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
            ret['changes'].update({'default':
                                  {'old': default_zone,
                                   'new': name}})

    masquerade = masquerade or False
    if masquerade:
        try:
            masquerade_ret = __salt__['firewalld.get_masquerade'](name,
                permanent=True)
        except CommandExecutionError as err:
            ret['comment'] = 'Error: {0}'.format(err)
            return ret
        if not masquerade_ret:
            if not __opts__['test']:
                try:
                    __salt__['firewalld.add_masquerade'](name, permanent=True)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
            ret['changes'].update({'masquerade':
                                  {'old': '',
                                   'new': 'Masquerading successfully set.'}})

    if not masquerade:
        try:
            masquerade_ret = __salt__['firewalld.get_masquerade'](name,
                permanent=True)
        except CommandExecutionError as err:
            ret['comment'] = 'Error: {0}'.format(err)
            return ret
        if masquerade_ret:
            if not __opts__['test']:
                try:
                    __salt__['firewalld.remove_masquerade'](name,
                                                            permanent=True)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
            ret['changes'].update({'masquerade':
                                  {'old': '',
                                   'new': 'Masquerading successfully '
                                   'disabled.'}})

    ports = ports or []
    try:
        _current_ports = __salt__['firewalld.list_ports'](name, permanent=True)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret

    new_ports = set(ports) - set(_current_ports)
    old_ports = set(_current_ports) - set(ports)

    for port in new_ports:
        if not __opts__['test']:
            try:
                __salt__['firewalld.add_port'](name, port, permanent=True)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

    for port in old_ports:
        if not __opts__['test']:
            try:
                __salt__['firewalld.remove_port'](name, port, permanent=True)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

    if new_ports or old_ports:
        ret['changes'].update({'ports':
                                {'old': _current_ports,
                                'new': ports}})

    port_fwd = port_fwd or []
    try:
        _current_port_fwd = __salt__['firewalld.list_port_fwd'](name,
                                                                permanent=True)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret

    port_fwd = [_parse_forward(fwd) for fwd in port_fwd]
    _current_port_fwd = [
        ForwardingMapping(
            srcport=fwd['Source port'],
            destport=fwd['Destination port'],
            protocol=fwd['Protocol'],
            destaddr=fwd['Destination address']
        ) for fwd in _current_port_fwd]

    new_port_fwd = set(port_fwd) - set(_current_port_fwd)
    old_port_fwd = set(_current_port_fwd) - set(port_fwd)

    for fwd in new_port_fwd:
        if not __opts__['test']:
            try:
                __salt__['firewalld.add_port_fwd'](name, fwd.srcport,
                    fwd.destport, fwd.protocol, fwd.destaddr, permanent=True)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

    for fwd in old_port_fwd:
        if not __opts__['test']:
            try:
                __salt__['firewalld.remove_port_fwd'](name, fwd.srcport,
                    fwd.destport, fwd.protocol, fwd.destaddr, permanent=True)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

    if new_port_fwd or old_port_fwd:
        ret['changes'].update({'port_fwd':
                                {'old': [fwd.todict() for fwd in
                                         _current_port_fwd],
                                'new': [fwd.todict() for fwd in port_fwd]}})

    services = services or []
    try:
        _current_services = __salt__['firewalld.list_services'](name,
            permanent=True)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret

    new_services = set(services) - set(_current_services)
    old_services = []

    for new_service in new_services:
        if not __opts__['test']:
            try:
                __salt__['firewalld.add_service'](new_service, name,
                                                  permanent=True)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

    if prune_services:
        old_services = set(_current_services) - set(services)
        for old_service in old_services:
            if not __opts__['test']:
                try:
                    __salt__['firewalld.remove_service'](old_service, name,
                                                         permanent=True)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret

    if new_services or old_services:
        ret['changes'].update({'services':
                                {'old': _current_services,
                                'new': services}})

    interfaces = interfaces or []
    try:
        _current_interfaces = __salt__['firewalld.get_interfaces'](name,
            permanent=True)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret

    new_interfaces = set(interfaces) - set(_current_interfaces)
    old_interfaces = set(_current_interfaces) - set(interfaces)

    for interface in new_interfaces:
        if not __opts__['test']:
            try:
                __salt__['firewalld.add_interface'](name, interface,
                                                    permanent=True)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

    for interface in old_interfaces:
        if not __opts__['test']:
            try:
                __salt__['firewalld.remove_interface'](name, interface,
                                                       permanent=True)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

    if new_interfaces or old_interfaces:
        ret['changes'].update({'interfaces':
                                {'old': _current_interfaces,
                                'new': interfaces}})

    sources = sources or []
    try:
        _current_sources = __salt__['firewalld.get_sources'](name,
                                                             permanent=True)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret

    new_sources = set(sources) - set(_current_sources)
    old_sources = set(_current_sources) - set(sources)

    for source in new_sources:
        if not __opts__['test']:
            try:
                __salt__['firewalld.add_source'](name, source, permanent=True)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

    for source in old_sources:
        if not __opts__['test']:
            try:
                __salt__['firewalld.remove_source'](name, source,
                                                    permanent=True)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

    if new_sources or old_sources:
        ret['changes'].update({'sources':
                                {'old': _current_sources,
                                'new': sources}})

    rich_rules = rich_rules or []
    try:
        _current_rich_rules = __salt__['firewalld.get_rich_rules'](name,
            permanent=True)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret

    new_rich_rules = set(rich_rules) - set(_current_rich_rules)
    old_rich_rules = set(_current_rich_rules) - set(rich_rules)

    for rich_rule in new_rich_rules:
        if not __opts__['test']:
            try:
                __salt__['firewalld.add_rich_rule'](name, rich_rule,
                                                    permanent=True)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

    for rich_rule in old_rich_rules:
        if not __opts__['test']:
            try:
                __salt__['firewalld.remove_rich_rule'](name, rich_rule,
                                                       permanent=True)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret

    if new_rich_rules or old_rich_rules:
        ret['changes'].update({'rich_rules':
                              {'old': _current_rich_rules,
                               'new': rich_rules}})

    ret['result'] = True
    if ret['changes'] == {}:
        ret['comment'] = '\'{0}\' is already in the desired state.'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Configuration for \'{0}\' will change.'.format(name)
        return ret

    ret['comment'] = '\'{0}\' was configured.'.format(name)
    return ret
