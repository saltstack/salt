# -*- coding: utf-8 -*-
'''
Management of firewalld

.. versionadded:: 2015.8.0

The following example applies changes to the public zone, blocks echo-reply
and echo-request packets, does not set the zone to be the default, enables
masquerading, and allows ports 22/tcp and 25/tcp.

.. code-block:: yaml

    public:
      - name: public
      - block_icmp
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
'''
from __future__ import absolute_import

import logging
import salt.exceptions

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
    Ensure a zone has specific attributes
    '''
    ret = {'name': name,
           'result': True,
           'changes': {'icmp_blocks': [],
                       'ports': [],
                       'port_fwd': [],
                       'services': []},
           'comment': {'icmp_blocks': [],
                       'ports': [],
                       'port_fwd': [],
                       'services': []}}

    if name not in __salt__['firewalld.get_zones']():
        if __opts__['test']:
            ret['comment'][name] = '`{0}` will be created'.format(name)
        else:
            __salt__['firewalld.new_zone'](name)
            ret['changes'][name] = '`{0}` zone has been successfully created'.format(name)
    else:
        ret['comment'][name] = '`{0}` zone already exists'.format(name)

    if block_icmp:
        _valid_icmp_types = __salt__['firewalld.get_icmp_types']()
        _current_icmp_blocks = __salt__['firewalld.list_icmp_block'](name)

        for icmp_type in set(block_icmp):
            if icmp_type in _valid_icmp_types:
                if icmp_type in _current_icmp_blocks:
                    ret['comment']['icmp_blocks'].append(
                        '`{0}` already exists'.format(icmp_type)
                    )
                else:
                    if __opts__['test']:
                        ret['comment']['icmp_blocks'].append(
                            '`{0}` will be blocked'.format(icmp_type)
                        )
                    else:
                        __salt__['firewalld.block_icmp'](name, icmp_type)
                        ret['changes']['icmp_blocks'].append(
                            '`{0}` has been blocked'.format(icmp_type)
                        )
            else:
                log.error('{0} is an invalid ICMP type'.format(icmp_type))

    if default:
        if __salt__['firewalld.default_zone']() == name:
            ret['comment']['default'] = '`{0}` is already the default zone'.format(name)
        else:
            if __opts__['test']:
                ret['comment']['default'] = '`{0}` wll be set to the default zone'.format(name)
            else:
                __salt__['firewalld.set_default_zone'](name)
                ret['changes']['default'] = '`{0}` has been set to the default zone'.format(name)

    if masquerade:
        if __salt__['firewalld.get_masquerade'](name):
            ret['comment']['masquerade'] = 'masquerading is already enabed'
        else:
            if __opts__['test']:
                ret['comment']['masquerade'] = 'masquerading will be enabled'
            else:
                __salt__['firewalld.add_masquerade'](name)
                ret['changes']['masquerade'] = 'masquerading successfully set'

    if ports:
        _current_ports = __salt__['firewalld.list_ports'](name)

        for port in ports:
            if port in _current_ports:
                ret['comment']['ports'].append(
                    '`{0}` already exists'.format(port)
                )
            else:
                if __opts__['test']:
                    ret['comment']['ports'].append(
                        '{0} will be added'.format(port)
                    )
                else:
                    __salt__['firewalld.add_port'](name, port)
                    ret['changes']['ports'].append(
                        '`{0}` has been added to the firewall'.format(port)
                    )

    if port_fwd:
        _current_port_fwd = __salt__['firewalld.list_port_fwd'](name)

        for port in port_fwd:
            dstaddr = ''
            rule_exists = False

            if len(port.split(':')) > 3:
                (src, dest, protocol, dstaddr) = port.split(':')
            else:
                (src, dest, protocol) = port.split(':')

            for i in _current_port_fwd:
                if (src == i['Source port'] and dest == i['Destination port'] and
                        protocol == i['Protocol'] and dstaddr == i['Destination address']):
                    rule_exists = True

            if rule_exists:
                ret['comment']['port_fwd'].append(
                    '`{0}` port forwarding already exists'.format(port)
                )
            else:
                if __opts__['test']:
                    ret['comment']['port_fwd'].append(
                        '`{0}` port will be added'.format(port)
                    )
                else:
                    __salt__['firewalld.add_port_fwd'](
                        name, src, dest, protocol, dstaddr
                    )
                    ret['changes']['port_fwd'].append(
                        '`{0}` port forwarding has been added'.format(port)
                    )

    if services:
        _current_services = __salt__['firewalld.list_services'](name)

        for service in services:
            if service in _current_services:
                ret['comment']['services'].append(
                    '`{0}` service already exists'.format(service)
                )
            else:
                if __opts__['test']:
                    ret['comment']['services'].append(
                        '`{0}` service will be added'.format(service)
                    )
                else:
                    __salt__['firewalld.new_service'](service)
                    ret['changes']['services'].append(
                        '`{0}` has been successfully added'.format(service)
                    )

    return ret
