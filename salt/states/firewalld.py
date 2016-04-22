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
        - runtime: True
        - persist: True
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

    return (False, 'firewall-cmd is not available, firewalld is probably not installed.')


def present(name,
            block_icmp=None,
            default=None,
            masquerade=False,
            ports=None,
            port_fwd=None,
            services=None,
            interfaces=None,
            sources=None,
            rich_rules=None,
            runtime=True,
            persist=True):

    '''
    Ensure a zone has specific attributes.
    '''

    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}

    if runtime:
        ret_runtime = _present(name, False, block_icmp, default, masquerade, ports,
                               port_fwd, services, interfaces, sources, rich_rules)

        ret['changes'].update(ret_runtime['changes'])

    if persist:
        ret_persist = _present(name, True, block_icmp, default, masquerade, ports,
                               port_fwd, services, interfaces, sources, rich_rules)

        for k, v in ret_persist['changes'].items():
            ret['changes'].update({k + "_permanent": v})

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


def _present(name,
            permanent,
            block_icmp=None,
            default=None,
            masquerade=False,
            ports=None,
            port_fwd=None,
            services=None,
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
        zones = __salt__['firewalld.get_zones'](permanent)
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
        _valid_icmp_types = __salt__['firewalld.get_icmp_types'](permanent)
        _current_icmp_blocks = __salt__['firewalld.list_icmp_block'](name, permanent)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret

    for icmp_type in set(block_icmp):
        if icmp_type in _valid_icmp_types:
            if icmp_type not in _current_icmp_blocks:
                new_icmp_types.append(icmp_type)
                if not __opts__['test']:
                    try:
                        __salt__['firewalld.block_icmp'](name, icmp_type, permanent)
                    except CommandExecutionError as err:
                        ret['comment'] = 'Error: {0}'.format(err)
                        return ret
        else:
            log.error('{0} is an invalid ICMP type'.format(icmp_type))

    for icmp_type in _current_icmp_blocks:
        if icmp_type not in set(block_icmp):
            old_icmp_types.append(icmp_type)
            if not __opts__['test']:
                try:
                    __salt__['firewalld.allow_icmp'](name, icmp_type, permanent)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret

    if new_icmp_types or old_icmp_types:
        ret['changes'].update({'icmp_types':
                                {'old': _current_icmp_blocks,
                                'new': block_icmp}})

    # that's the only parameter that can't be permanent or runtime, it's directly both
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
            masquerade_ret = __salt__['firewalld.get_masquerade'](name, permanent)
        except CommandExecutionError as err:
            ret['comment'] = 'Error: {0}'.format(err)
            return ret
        if not masquerade_ret:
            if not __opts__['test']:
                try:
                    __salt__['firewalld.add_masquerade'](name, permanent)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
            ret['changes'].update({'masquerade':
                                  {'old': '',
                                   'new': 'Masquerading successfully set.'}})

    if not masquerade:
        try:
            masquerade_ret = __salt__['firewalld.get_masquerade'](name, permanent)
        except CommandExecutionError as err:
            ret['comment'] = 'Error: {0}'.format(err)
            return ret
        if masquerade_ret:
            if not __opts__['test']:
                try:
                    __salt__['firewalld.remove_masquerade'](name, permanent)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
            ret['changes'].update({'masquerade':
                                  {'old': '',
                                   'new': 'Masquerading successfully disabled.'}})

    ports = ports or []
    new_ports = []
    old_ports = []
    try:
        _current_ports = __salt__['firewalld.list_ports'](name, permanent)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret
    for port in ports:
        if port not in _current_ports:
            new_ports.append(port)
            if not __opts__['test']:
                try:
                    __salt__['firewalld.add_port'](name, port, permanent)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
    for port in _current_ports:
        if port not in ports:
            old_ports.append(port)
            if not __opts__['test']:
                try:
                    __salt__['firewalld.remove_port'](name, port, permanent)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret

    if new_ports or old_ports:
        ret['changes'].update({'ports':
                                {'old': _current_ports,
                                'new': ports}})

    port_fwd = port_fwd or []
    new_port_fwds = []
    old_port_fwds = []
    try:
        _current_port_fwd = __salt__['firewalld.list_port_fwd'](name, permanent)
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
                    __salt__['firewalld.add_port_fwd'](name, src, dest, protocol, dstaddr, permanent)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret

    for port in _current_port_fwd:
        dstaddr = ''
        rule_exists = False

        for item in port_fwd:
            if len(item.split(':')) > 3:
                (src, dest, protocol, dstaddr) = item.split(':')
            else:
                (src, dest, protocol) = item.split(':')

            if (src == port['Source port'] and dest == port['Destination port'] and
                    protocol == port['Protocol'] and dstaddr == port['Destination address']):
                rule_exists = True

        if rule_exists is False:
            old_port_fwds.append(port)
            if not __opts__['test']:
                try:
                    __salt__['firewalld.remove_port_fwd'](name, port['Source port'], port['Destination port'],
                                                          port['Protocol'], port['Destination address'], permanent)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret

    if new_port_fwds or old_port_fwds:
        ret['changes'].update({'port_fwd':
                                {'old': _current_port_fwd,
                                'new': port_fwd}})

    services = services or []
    new_services = []
    old_services = []
    try:
        _current_services = __salt__['firewalld.list_services'](name, permanent)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret
    for service in services:
        if service not in _current_services:
            new_services.append(service)
            if not __opts__['test']:
                try:
                    __salt__['firewalld.add_service'](service, name, permanent)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
    for service in _current_services:
        if service not in services:
            old_services.append(service)
            if not __opts__['test']:
                try:
                    __salt__['firewalld.remove_service'](service, name, permanent)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret

    if new_services or old_services:
        ret['changes'].update({'services':
                                {'old': _current_services,
                                'new': services}})

    interfaces = interfaces or []
    new_interfaces = []
    old_interfaces = []
    try:
        _current_interfaces = __salt__['firewalld.get_interfaces'](name, permanent)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret
    for interface in interfaces:
        if interface not in _current_interfaces:
            new_interfaces.append(interface)
            if not __opts__['test']:
                try:
                    __salt__['firewalld.add_interface'](name, interface, permanent)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
    for interface in _current_interfaces:
        if interface not in interfaces:
            old_interfaces.append(interface)
            if not __opts__['test']:
                try:
                    __salt__['firewalld.remove_interface'](name, interface, permanent)
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
        _current_sources = __salt__['firewalld.get_sources'](name, permanent)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret
    for source in sources:
        if source not in _current_sources:
            new_sources.append(source)
            if not __opts__['test']:
                try:
                    __salt__['firewalld.add_source'](name, source, permanent)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
    for source in _current_sources:
        if source not in sources:
            old_sources.append(source)
            if not __opts__['test']:
                try:
                    __salt__['firewalld.remove_source'](name, source, permanent)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
    if new_sources or old_sources:
        ret['changes'].update({'sources':
                                {'old': _current_sources,
                                'new': sources}})

    rich_rules = rich_rules or []
    new_rich_rules = []
    old_rich_rules = []
    try:
        _current_rich_rules = __salt__['firewalld.get_rich_rules'](name, permanent)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret
    for rich_rule in rich_rules:
        if rich_rule not in _current_rich_rules:
            new_rich_rules.append(rich_rule)
            if not __opts__['test']:
                try:
                    __salt__['firewalld.add_rich_rule'](name, rich_rule, permanent)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
    for rich_rule in _current_rich_rules:
        if rich_rule not in rich_rules:
            old_rich_rules.append(rich_rule)
            if not __opts__['test']:
                try:
                    __salt__['firewalld.remove_rich_rule'](name, rich_rule, permanent)
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
