# -*- coding: utf-8 -*-
'''
Support for firewalld.

.. versionadded:: 2015.2.0
'''

# Import Python Libs
from __future__ import absolute_import
import logging
import re

# Import Salt Libs
from salt.exceptions import CommandExecutionError
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Check to see if firewall-cmd exists
    '''
    if salt.utils.which('firewall-cmd'):
        return True

    return False


def __firewall_cmd(cmd):
    '''
    Return the firewall-cmd location
    '''
    firewall_cmd = '{0} {1}'.format(salt.utils.which('firewall-cmd'), cmd)
    out = __salt__['cmd.run_all'](firewall_cmd)

    if out['retcode'] != 0:
        if not out['stderr']:
            msg = out['stdout']
        else:
            msg = out['stderr']
        raise CommandExecutionError(
            'firewall-cmd failed: {0}'.format(msg)
        )
    return out['stdout']


def __mgmt(name, _type, action):
    '''
    Perform zone management
    '''
    return __firewall_cmd('--{0}-{1}={2} --permanent'.format(action, _type, name))


def version():
    '''
    Return version from firewall-cmd

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.version
    '''
    return __firewall_cmd('--version')


def default_zone():
    '''
    Print default zone for connections and interfaces

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.default_zone
    '''
    return __firewall_cmd('--get-default-zone')


def list_zones():
    '''
    List everything added for or enabled in all zones

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.list_zones
    '''
    zones = {}

    for i in __firewall_cmd('--list-all-zones').splitlines():
        if i.strip():
            if bool(re.match('^[a-z0-9]', i, re.I)):
                zone_name = i.rstrip()
            else:
                (id_, val) = i.strip().split(':')

                if zones.get(zone_name, None):
                    zones[zone_name].update({id_: val})
                else:
                    zones[zone_name] = {id_: val}

    return zones


def get_zones():
    '''
    Print predefined zones

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.get_zones
    '''
    return __firewall_cmd('--get-zones').split()


def get_services():
    '''
    Print predefined services

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.get_services
    '''
    return __firewall_cmd('--get-services').split()


def get_icmp_types():
    '''
    Print predefined icmptypes

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.get_icmp_types
    '''
    return __firewall_cmd('--get-icmptypes').split()


def new_zone(zone, restart=True):
    '''
    Add a new zone

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.new_zone my_zone

    By default firewalld will be reloaded. However, to avoid reloading
    you need to specify the restart as False

    .. code-block:: bash

        salt '*' firewalld.new_zone my_zone False
    '''
    if restart:
        out = __mgmt(zone, 'zone', 'new')

        if out == 'success':
            return __firewall_cmd('--reload')
        else:
            return out

    return __mgmt(zone, 'zone', 'new')


def delete_zone(zone, restart=True):
    '''
    Delete an existing zone

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.delete_zone my_zone

    By default firewalld will be reloaded. However, to avoid reloading
    you need to specify the restart as False

    .. code-block:: bash

        salt '*' firewalld.delete_zone my_zone False
    '''
    if restart:
        out = __mgmt(zone, 'zone', 'delete')

        if out == 'success':
            return __firewall_cmd('--reload')
        else:
            return out

    return __mgmt(zone, 'zone', 'delete')


def set_default_zone(zone):
    '''
    Set default zone

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.set_default_zone damian
    '''
    return __firewall_cmd('--set-default-zone={0}'.format(zone))


def new_service(name, restart=True):
    '''
    Add a new service

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.new_service my_service

    By default firewalld will be reloaded. However, to avoid reloading
    you need to specify the restart as False

    .. code-block:: bash

        salt '*' firewalld.new_service my_service False
    '''
    if restart:
        out = __mgmt(name, 'service', 'new')

        if out == 'success':
            return __firewall_cmd('--reload')
        else:
            return out

    return __mgmt(name, 'service', 'new')


def delete_service(name, restart=True):
    '''
    Delete an existing service

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.delete_service my_service

    By default firewalld will be reloaded. However, to avoid reloading
    you need to specify the restart as False

    .. code-block:: bash

        salt '*' firewalld.delete_service my_service False
    '''
    if restart:
        out = __mgmt(name, 'service', 'delete')

        if out == 'success':
            return __firewall_cmd('--reload')
        else:
            return out

    return __mgmt(name, 'service', 'delete')


def list_all(zone=None):
    '''
    List everything added for or enabled in a zone

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.list_all

    List a specific zone

    .. code-block:: bash

        salt '*' firewalld.list_all my_zone
    '''
    _zone = {}
    id_ = ''

    if zone:
        cmd = '--zone={0} --list-all'.format(zone)
    else:
        cmd = '--list-all'

    for i in __firewall_cmd(cmd).splitlines():
        if re.match('^[a-z0-9]', i, re.I):
            zone_name = i.rstrip()
        else:
            if i.startswith('\t'):
                _zone[zone_name][id_].append(i.strip())
                continue

            (id_, val) = i.split(':', 1)

            id_ = id_.strip()

            if _zone.get(zone_name, None):
                _zone[zone_name].update({id_: [val.strip()]})
            else:
                _zone[zone_name] = {id_: [val.strip()]}

    return _zone


def list_services(zone=None):
    '''
    List services added for zone as a space separated list.
    If zone is omitted, default zone will be used.

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.list_services

    List a specific zone

    .. code-block:: bash

        salt '*' firewalld.list_services my_zone
    '''
    if zone:
        cmd = '--zone={0} --list-services'.format(zone)
    else:
        cmd = '--list-services'

    return __firewall_cmd(cmd).split()


def add_service(name, zone=None, permanent=True):
    '''
    Add a service for zone. If zone is omitted, default zone will be used.

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.add_service ssh

    To assign a service to a specific zone:

    .. code-block:: bash

        salt '*' firewalld.add_service ssh my_zone
    '''
    if zone:
        cmd = '--zone={0} --add-service={1}'.format(zone, name)
    else:
        cmd = '--add-service={0}'.format(name)

    if permanent:
        cmd += ' --permanent'

    return __firewall_cmd(cmd)


def remove_service(name, zone=None, permanent=True):
    '''
    Remove a service from zone. This option can be specified multiple times.
    If zone is omitted, default zone will be used.

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.remove_service ssh

    To remove a service from a specific zone

    .. code-block:: bash

        salt '*' firewalld.remove_service ssh dmz
    '''
    if zone:
        cmd = '--zone={0} --remove-service={1}'.format(zone, name)
    else:
        cmd = '--remove-service={0}'.format(name)

    if permanent:
        cmd += ' --permanent'

    return __firewall_cmd(cmd)


def get_masquerade(zone):
    '''
    Show if masquerading is enabled on a zone

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.get_masquerade zone
    '''
    zone_info = list_all(zone)

    if [zone_info[i]['masquerade'][0] for i in zone_info.keys()] == 'no':
        return False

    return True


def add_masquerade(zone):
    '''
    Enable masquerade on a zone.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.add_masquerade
    '''
    return __firewall_cmd('--zone={0} --add-masquerade'.format(zone))


def remove_masquerade(zone):
    '''
    Remove masquerade on a zone.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.remove_masquerade
    '''
    return __firewall_cmd('--zone={0} --remove-masquerade'.format(zone))


def add_port(zone, port, permanent=True):
    '''
    Allow specific ports in a zone.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.add_port internal 443/tcp
    '''
    if not get_masquerade(zone):
        add_masquerade(zone)

    cmd = '--zone={0} --add-port={1}'.format(zone, port)

    if permanent:
        cmd += ' --permanent'

    return __firewall_cmd(cmd)


def remove_port(zone, port, permanent=True):
    '''
    Remove a specific port from a zone.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.remove_port internal 443/tcp
    '''
    cmd = '--zone={0} --remove-port={1}'.format(zone, port)

    if permanent:
        cmd += ' --permanent'

    return __firewall_cmd(cmd)


def list_ports(zone):
    '''
    List all ports in a zone.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.list_ports
    '''
    return __firewall_cmd('--zone={0} --list-ports'.format(zone)).split()


def add_port_fwd(zone, src, dest, proto='tcp', dstaddr=''):
    '''
    Add port forwarding.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.add_port_fwd public 80 443 tcp
    '''
    if not get_masquerade(zone):
        add_masquerade(zone)

    return __firewall_cmd(
        '--zone={0} --add-forward-port=port={1}:proto={2}:toport={3}:toaddr={4}'.format(
            zone,
            src,
            proto,
            dest,
            dstaddr
        )
    )


def remove_port_fwd(zone, src, dest, proto='tcp'):
    '''
    Remove Port Forwarding.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.remove_port_fwd public 80 443 tcp
    '''
    return __firewall_cmd(
        '--zone={0} --remove-forward-port=port={1}:proto={2}:toport={3}'.format(
            zone,
            src,
            proto,
            dest
        )
    )


def list_port_fwd(zone):
    '''
    List port forwarding

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.list_port_fwd public
    '''
    ret = []

    for i in __firewall_cmd('--zone={0} --list-forward-ports'.format(zone)).splitlines():
        (src, proto, dest, addr) = i.split(':')

        ret.append(
            {'Source port': src.split('=')[1],
             'Protocol': proto.split('=')[1],
             'Destination port': dest.split('=')[1],
             'Destination address': addr.split('=')[1]}
        )

    return ret


def block_icmp(zone, icmp):
    '''
    Block a specific ICMP type on a zone

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.block_icmp zone echo-reply
    '''
    if icmp not in get_icmp_types():
        log.error('Invalid ICMP type')
        return False

    if icmp in list_icmp_block(zone):
        log.info('ICMP block already exists')
        return 'success'

    return __firewall_cmd('--zone={0} --add-icmp-block={1}'.format(zone, icmp))


def allow_icmp(zone, icmp):
    '''
    Allow a specific ICMP type on a zone

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.allow_icmp zone echo-reply
    '''
    if icmp not in get_icmp_types():
        log.error('Invalid ICMP type')
        return False

    if icmp not in list_icmp_block(zone):
        log.info('ICMP Type is already permitted')
        return 'success'

    return __firewall_cmd('--zone={0} --remove-icmp-block={1}'.format(zone, icmp))


def list_icmp_block(zone):
    '''
    List ICMP blocks on a zone

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewlld.list_icmp_block zone
    '''
    return __firewall_cmd('--zone={0} --list-icmp-blocks'.format(zone)).split()
