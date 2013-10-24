# -*- coding: utf-8 -*-
'''
Configuration of network interfaces on Windows hosts
====================================================

The network module is used to create and manage network settings,
interfaces can be set as either managed or ignored. By default
all interfaces are ignored unless specified.

Please note that only Redhat-style networking is currently
supported. This module will therefore only work on RH/CentOS/Fedora.

.. code-block:: yaml

    Local Area Connection #2:
      network.managed:
        - dns_proto: dhcp
        - ip_proto: static
        - ip_addrs:
          - 10.2.3.4/24
'''

# Import python libs
import logging

# Import salt libs
import salt.utils
import salt.utils.network

# Set up logging
log = logging.getLogger(__name__)

__VALID_PROTO = ('static', 'dhcp')

# Define the module's virtual name
__virtualname__ = 'ip'


def __virtual__():
    '''
    Confine this module to Windows systems with the required execution module
    available.
    '''
    if salt.utils.is_windows() and 'ip.get_interface' in __salt__:
        return __virtualname__
    return False


def _validate(dns_proto, dns_servers, ip_proto, ip_addrs, gateway):
    '''
    Ensure that the configuration passed is formatted correctly and contains
    valid IP addresses, etc.
    '''
    errors = []
    # Validate DNS configuration
    if dns_proto == 'dhcp':
        if dns_servers is not None:
            errors.append(
                'The dns_servers param cannot be set if unless dns_proto is '
                'set to \'static\'.'
            )
    else:
        if not isinstance(dns_servers, list):
            errors.append(
                'The dns_servers param must be formatted as a list.'
            )
        else:
            bad_ips = [x for x in dns_servers
                       if not salt.utils.network.valid_ipv4(x)]
            if bad_ips:
                errors.append('The following DNS server IPs are invalid: '
                              '{0}'.format(', '.format(bad_ips)))

    # Validate IP configuration
    if ip_proto == 'dhcp':
        if ip_addrs is not None:
            errors.append(
                'The ip_addrs param cannot be set if unless ip_proto is set '
                'to \'static\'.'
            )
        if gateway is not None:
            errors.append(
                'A gateway IP cannot be set if unless ip_proto is set to '
                '\'static\'.'
            )
    else:
        if not isinstance(dns_servers, list):
            errors.append(
                'The ip_addrs param must be formatted as a list.'
            )
        else:
            bad_ips = [x for x in dns_servers
                       if not salt.utils.network.valid_ipv4(x)]
            if bad_ips:
                errors.append('The following static IPs are invalid: '
                              '{0}'.format(', '.format(bad_ips)))

            # Validate default gateway
            if gateway is not None:
                if not salt.utils.network.valid_ipv4(gateway):
                    errors.append('Gateway IP {0} is invalid'.format(gateway))

    return errors


def _changes(cur, dns_proto, dns_servers, ip_proto, ip_addrs, gateway):
    '''
    Compares the current interface against the desired configuration and
    returns a dictionary describing the changes that need to be made.
    '''
    changes = {}
    cur_dns_proto = ('static' if 'Statically Configured DNS Servers' in cur
                     else 'dhcp')
    cur_dns_servers = cur.get('Statically Configured DNS Servers', [])
    cur_ip_proto = 'static' if 'ip_addrs' in cur else 'dhcp'
    cur_ip_addrs = cur.get('ip_addrs', [])
    cur_gateway = cur.get('Default Gateway')

    if dns_proto != cur_dns_proto:
        changes['dns_proto'] = dns_proto
    if set(dns_servers) != set(cur_dns_servers):
        changes['dns_servers'] = dns_servers
    if ip_proto != cur_ip_proto:
        changes['ip_proto'] = ip_proto
    if set(ip_addrs) != set(cur_ip_addrs):
        changes['ip_addrs'] = ip_addrs
    if gateway != cur_gateway:
        changes['gateway'] = gateway
    return changes


def managed(name,
            dns_proto=None,
            dns_servers=None,
            ip_proto=None,
            ip_addrs=None,
            gateway=None,
            enabled=True,
            **kwargs):
    '''
    Ensure that the named interface is configured properly.

    name
        The name of the interface to manage

    dns_proto : dhcp
        Set to ``static`` and use the ``dns_servers`` parameter to provide a
        list of DNS nameservers. The default is to get the nameservers via
        DHCP.

    dns_servers : None
        A list of static DNS servers.

    ip_proto : dhcp
        Set to ``static`` and use the ``ip_addrs`` and ``gateway`` parameters
        to provide a list of static IP addresses and the default gateway. The
        default is to get the IP and default gateway via DHCP.

    ip_addrs : None
        A list of static IP addresses.

    gateway : None
        A list of static IP addresses.

    enabled : True
        Set to ``False`` to ensure that this interface is disabled.

    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': 'Interface {0!r} is up to date.'.format(name)
    }

    dns_proto = str(dns_proto).lower()
    ip_proto = str(ip_proto).lower()

    if dns_proto not in __VALID_PROTO:
        ret['result'] = False
        ret['comment'] = ('dns_proto must be one of the following: {0}'
                          .format(', '.join(__VALID_PROTO)))
        return ret

    if ip_proto not in __VALID_PROTO:
        ret['result'] = False
        ret['comment'] = ('ip_proto must be one of the following: {0}'
                          .format(', '.join(__VALID_PROTO)))
        return ret

    if not enabled:
        if __salt__['ip.is_enabled'](name):
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = ('Interface {0!r} will be disabled'
                                  .format(name))
            else:
                ret['result'] = __salt__['ip.disable'](name)
                if not ret['result']:
                    ret['comment'] = ('Failed to disable interface {0!r}'
                                      .format(name))
        else:
            ret['comment'] += ' (already disabled)'
        return ret
    else:
        currently_enabled = __salt__['ip.is_disabled'](name)
        if not currently_enabled:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = ('Interface {0!r} will be enabled'
                                  .format(name))
            else:
                result = __salt__['ip.enable'](name)
                if not result:
                    ret['result'] = False
                    ret['comment'] = ('Failed to enable interface {0!r} to '
                                      'make changes'.format(name))
                    return ret

        errors = _validate(dns_proto, dns_servers, ip_proto, ip_addrs, gateway)
        if errors:
            ret['result'] = False
            ret['comment'] = ('The following SLS configuration errors were '
                              'detected: {0}.'.format('. '.join(errors)))
            return ret

        cur = __salt__['ip.get_interface'](name)
        if not cur:
            ret['result'] = False
            ret['comment'] = ('Unable to get current configuration for '
                              'interface {0!r}'.format(name))
            return ret

        changes = _changes(cur,
                           dns_proto,
                           dns_servers,
                           ip_proto,
                           ip_addrs,
                           gateway)
        if not changes:
            return ret

        if __opts__['test']:
            comments = []
            if 'dns_proto' in changes:
                comments.append('DNS protocol will be changed to: {0}.'
                                .format(changes['dns_proto']))
            if dns_proto == 'static' and 'dns_servers' in changes:
                comments.append(
                    'DNS servers will be set to the following: {0}.'
                    .format(', '.join(changes['dns_servers']))
                )
            if 'ip_proto' in changes:
                comments.append('IP protocol will be changed to: {0}.'
                                .format(changes['ip_proto']))
            if ip_proto == 'static':
                if 'ip_addrs' in changes:
                    comments.append(
                        'IP addresses will be set to the following: {0}.'
                        .format(', '.join(changes['ip_addrs']))
                    )
                if 'gateway' in changes:
                    if changes['gateway'] is None:
                        comments.append('Default gateway will be removed.')
                    else:
                        comments.append(
                            'Default gateway will be set to {0}.'
                            .format(changes['gateway'])
                        )

            ret['result'] = None
            ret['comment'] = ('The following changes will be made to '
                              'interface {0!r}: {1}.'
                              .format(name, ' '.join(comments)))
            return ret

        if changes.get('dns_proto') is not None:
            if changes.get('dns_proto') == 'dhcp':
                __salt__['ip.set_dhcp_dns'](name)
            else:
                if changes.get('dns_servers'):
                    __salt__['ip.set_static_dns'](name,
                                                  *changes['dns_servers'])

        if changes.get('ip_proto') is not None:
            if changes.get('ip_proto') == 'dhcp':
                __salt__['ip.set_dhcp_ip'](name)
            else:
                if changes.get('ip_addrs'):
                    for idx in xrange(len(changes['ip_addrs'])):
                        if idx == 0:
                            __salt__['ip.set_static_ip'](
                                name,
                                changes['ip_addrs'][idx],
                                gateway=gateway
                            )
                        else:
                            __salt__['ip.set_static_ip'](
                                name,
                                changes['ip_addrs'][idx],
                                gateway=None,
                                append=True
                            )

        new = __salt__['ip.get_interface'](name)
        ret['changes'] = salt.utils.compare_dicts(old, new)
        if _changes(new, dns_proto, dns_servers, ip_proto, ip_addrs, gateway):
            ret['result'] = False
            ret['comment'] = ('Failed to set desired configuration settings '
                              'for interface {0!r}'.format(name))
        else:
            ret['comment'] = ('Successfully updated configuration for '
                              'interface {0!r}'.format(name))
        return ret
