# -*- coding: utf-8 -*-
'''
Management of firewalld

.. versionadded:: 2015.8.0

The following example applies changes to the public zone, blocks echo-reply
and echo-request packets, does not set the zone to be the default, enables
masquerading, and allows ports 22/tcp and 25/tcp.

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
    firewalld.bind:
      - name: public
      - interfaces:
        - eth0
      - sources:
        - 192.168.1.0/24
'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
from salt.exceptions import CommandExecutionError
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Ensure the firewall-cmd is available
    '''
    if salt.utils.which('firewall-cmd'):
        return True

    return False


def present(name,
            block_icmp=None,
            default=None,
            masquerade=False,
            ports=None,
            port_fwd=None,
            services=None):
    '''
    Ensure a zone has specific attributes.
    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}

    try:
        zones = __salt__['firewalld.get_zones']()
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

    if block_icmp:
        new_icmp_types = []
        try:
            _valid_icmp_types = __salt__['firewalld.get_icmp_types']()
            _current_icmp_blocks = __salt__['firewalld.list_icmp_block'](name)
        except CommandExecutionError as err:
            ret['comment'] = 'Error: {0}'.format(err)
            return ret

        for icmp_type in set(block_icmp):
            if icmp_type in _valid_icmp_types:
                if icmp_type not in _current_icmp_blocks:
                    new_icmp_types.append(icmp_type)
                    if not __opts__['test']:
                        try:
                            __salt__['firewalld.block_icmp'](name, icmp_type)
                        except CommandExecutionError as err:
                            ret['comment'] = 'Error: {0}'.format(err)
                            return ret
            else:
                log.error('{0} is an invalid ICMP type'.format(icmp_type))
        if new_icmp_types:
            ret['changes'].update({'icmp_blocks':
                                  {'old': _current_icmp_blocks,
                                   'new': new_icmp_types}})

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

    if masquerade:
        try:
            masquerade_ret = __salt__['firewalld.get_masquerade'](name)
        except CommandExecutionError as err:
            ret['comment'] = 'Error: {0}'.format(err)
            return ret
        if not masquerade_ret:
            if not __opts__['test']:
                try:
                    __salt__['firewalld.add_masquerade'](name)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
            ret['changes'].update({'masquerade':
                                  {'old': '',
                                   'new': 'Masquerading successfully set.'}})

    if ports:
        new_ports = []
        try:
            _current_ports = __salt__['firewalld.list_ports'](name)
        except CommandExecutionError as err:
            ret['comment'] = 'Error: {0}'.format(err)
            return ret
        for port in ports:
            if port not in _current_ports:
                new_ports.append(port)
                if not __opts__['test']:
                    try:
                        __salt__['firewalld.add_port'](name, port)
                    except CommandExecutionError as err:
                        ret['comment'] = 'Error: {0}'.format(err)
                        return ret
        if new_ports:
            ret['changes'].update({'ports':
                                  {'old': _current_ports,
                                   'new': new_ports}})

    if port_fwd:
        new_port_fwds = []
        try:
            _current_port_fwd = __salt__['firewalld.list_port_fwd'](name)
        except CommandExecutionError as err:
            ret['comment'] = 'Error: {0}'.format(err)
            return ret

        for port in port_fwd:
            dstaddr = ''
            rule_exists = False

            if len(port.split(':')) > 3:
                (src, dest, protocol, dstaddr) = port.split(':')
            else:
                (src, dest, protocol) = port.split(':')

            for item in _current_port_fwd:
                if (src == item['Source port'] and dest == item['Destination port'] and
                        protocol == item['Protocol'] and dstaddr == item['Destination address']):
                    rule_exists = True

            if rule_exists is False:
                new_port_fwds.append(port)
                if not __opts__['test']:
                    try:
                        __salt__['firewalld.add_port_fwd'](name, src, dest, protocol, dstaddr)
                    except CommandExecutionError as err:
                        ret['comment'] = 'Error: {0}'.format(err)
                        return ret

        if new_port_fwds:
            ret['changes'].update({'port_fwd':
                                  {'old': _current_port_fwd,
                                   'new': new_port_fwds}})

    if services:
        new_services = []
        try:
            _current_services = __salt__['firewalld.list_services'](name)
        except CommandExecutionError as err:
            ret['comment'] = 'Error: {0}'.format(err)
            return ret
        for service in services:
            if service not in _current_services:
                new_services.append(service)
                if not __opts__['test']:
                    try:
                        __salt__['firewalld.add_service'](service, zone=name)
                    except CommandExecutionError as err:
                        ret['comment'] = 'Error: {0}'.format(err)
                        return ret
        if new_services:
            ret['changes'].update({'services':
                                  {'old': _current_services,
                                   'new': new_services}})

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


def bind(name,
         interfaces=None,
         sources=None):
    '''
    Ensure a zone is bound to specific interfaces or sources.

    .. versionadded:: 2016.3.0

    .. note::

        This state does not enforce the existence of the zone. To ensure that
        the zone exists, use :mod:`firewalld.present <salt.states.firewalld.present>`.
    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}

    try:
        zones = __salt__['firewalld.get_zones']()
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret

    if name not in zones:
        ret['result'] = False
        ret['comment'] = 'Zone {0} does not exist'.format(name)
        return ret

    interfaces = interfaces or []
    new_interfaces = []
    old_interfaces = []
    try:
        _current_interfaces = __salt__['firewalld.get_interfaces'](name)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret
    for interface in interfaces:
        if interface not in _current_interfaces:
            new_interfaces.append(interface)
            if not __opts__['test']:
                try:
                    __salt__['firewalld.add_interface'](name, interface)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
    for interface in _current_interfaces:
        if interface not in interfaces:
            old_interfaces.append(interface)
            if not __opts__['test']:
                try:
                    __salt__['firewalld.remove_interface'](name, interface)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret

    if new_interfaces or old_interfaces:
        ret['changes'].update({'interfaces':
                                {'old': _current_interfaces,
                                'new': interfaces}})

    sources = sources or []
    new_sources = []
    old_sources = []
    try:
        _current_sources = __salt__['firewalld.get_sources'](name)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret
    for source in sources:
        if source not in _current_sources:
            new_sources.append(source)
            if not __opts__['test']:
                try:
                    __salt__['firewalld.add_source'](name, source)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
    for source in _current_sources:
        if source not in sources:
            old_sources.append(source)
            if not __opts__['test']:
                try:
                    __salt__['firewalld.remove_source'](name, source)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
    if new_sources or old_sources:
        ret['changes'].update({'sources':
                                {'old': _current_sources,
                                'new': sources}})

    if ret['changes'] != {}:
        try:
            __salt__['firewalld.make_permanent']()
        except CommandExecutionError as err:
            ret['comment'] = 'Error: {0}'.format(err)
            return ret

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
