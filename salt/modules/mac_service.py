# -*- coding: utf-8 -*-
'''
The service module for FreeBSD
'''
from __future__ import absolute_import

# Import python libs
import logging
import os

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

__func_alias__ = {
    'reload_': 'reload'
}

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'service'


def __virtual__():
    '''
    Only for Mac OS X
    '''
    if not salt.utils.is_darwin():
        return (False, 'Failed to load the mac_service module:\n'
                       'Only available on Mac OS X systems.')

    if not os.path.exists('/bin/launchctl'):
        return (False, 'Failed to load the mac_service module:\n'
                       'Required binary not found: "/bin/launchctl"')

    return __virtualname__


def _parse_return(data):
    '''
    Parse a return in the format:
    ``Time Zone: America/Denver``
    to return only:
    ``America/Denver``

    Returns: The value portion of a return
    '''

    if ': ' in data:
        return data.split(': ')[1]
    if ':\n' in data:
        return data.split(':\n')[1]
    else:
        return data


def start(service_path, domain='system'):
    '''
    Bootstraps domains and services. See `man launchctl` on a Mac OS X El
    Capitan system for more details.

    .. note::
       If the service already exists it will be restarted

    :param str service_path: Full path to the plist file

    :param str domain: Target domain. May be one of the following:
    - system : this is the default
    - user/<uid> : <uid> is the user id
    - login/<asid> : <asid> is the audit session id
    - gui/<uid> : <uid> is the user id
    - session/<asid> : <asid> is the audit session id
    - pid/<pid> : <pid> is the process id

    :return: The process ID of the new service
    '''
    if not os.path.exists(service_path):
        msg = 'Service Path not found:\n' \
              'Path: {0}'.format(service_path)
        raise CommandExecutionError(msg)

    # Enable the Launch Daemon
    service_name = os.path.splitext(os.path.basename(service_path))[0]
    if domain.endswith('/'):
        service_target = '{0}{1}'.format(domain, service_name)
    else:
        service_target = '{0}/{1}'.format(domain, service_name)
    cmd = ['launchctl', 'enable', service_target]
    ret = __salt__['cmd.ret_all'](cmd, python_shell=False)
    if ret['retcode']:
        msg = 'Failed to enable service:\n' \
              'Path: {0}\n'.format(service_path)
        msg += 'Error: {0}\n'.format(ret['stderr'])
        msg += 'StdOut: {0}'.format(ret['stdout'])
        raise CommandExecutionError(msg)

    # Bootstrap the Launch Daemon
    cmd = ['launchctl', 'bootstrap', domain, service_path]
    ret = __salt__['cmd.ret_all'](cmd, python_shell=False)
    if ret['retcode']:
        msg = 'Failed to bootstrap service:\n' \
              'Path: {0}\n'.format(service_path)
        msg += 'Error: {0}\n'.format(ret['stderr'])
        msg += 'StdOut: {0}'.format(ret['stdout'])
        raise CommandExecutionError(msg)

    # Kickstart the Launch Daemon
    cmd = ['launchctl', 'kickstart', '-kp', service_target]
    ret = __salt__['cmd.ret_all'](cmd, python_shell=False)
    if ret['retcode']:
        msg = 'Failed to kickstart service:\n' \
              'Path: {0}'.format(service_path)
        msg += 'Error: {0}'.format(ret['stderr'])
        msg += 'StdOut: {0}'.format(ret['stdout'])
        raise CommandExecutionError(msg)

    return _parse_return(ret['stdout'])[1]


def stop(service_path, domain='system'):
    if not os.path.exists(service_path):
        msg = 'Service Path not found:\n' \
              'Path: {0}'.format(service_path)
        raise CommandExecutionError(msg)

    # Disable the Launch Daemon
    service_name = os.path.splitext(os.path.basename(service_path))[0]
    if domain.endswith('/'):
        service_target = '{0}{1}'.format(domain, service_name)
    else:
        service_target = '{0}/{1}'.format(domain, service_name)
    cmd = ['launchctl', 'disable', service_target]
    ret = __salt__['cmd.ret_all'](cmd, python_shell=False)
    if ret['retcode']:
        msg = 'Failed to enable service:\n' \
              'Path: {0}\n'.format(service_path)
        msg += 'Error: {0}\n'.format(ret['stderr'])
        msg += 'StdOut: {0}'.format(ret['stdout'])
        raise CommandExecutionError(msg)

    # Remove the Launch Daemon
    cmd = ['launchctl', 'bootout', domain, service_path]
    ret = __salt__['cmd.ret_all'](cmd, python_shell=False)
    if ret['retcode']:
        msg = 'Failed to bootstrap service:\n' \
              'Path: {0}\n'.format(service_path)
        msg += 'Error: {0}\n'.format(ret['stderr'])
        msg += 'StdOut: {0}'.format(ret['stdout'])
        raise CommandExecutionError(msg)

    return _parse_return(ret['stdout'])[1]


def restart(service_target):
    # Kickstart the Launch Daemon
    cmd = ['launchctl', 'kickstart', '-kp', service_target]
    ret = __salt__['cmd.ret_all'](cmd, python_shell=False)
    if ret['retcode']:
        msg = 'Failed to kickstart service:\n' \
              'Path: {0}\n'.format(service_target)
        msg += 'Error: {0}\n'.format(ret['stderr'])
        msg += 'StdOut: {0}'.format(ret['stdout'])
        raise CommandExecutionError(msg)

    return _parse_return(ret['stdout'])[1]


def status():
    pass


def reload_():
    pass


def available():
    pass


def missing():
    pass


def get_all():
    # This command is deprecated, however there is no new command in launchctl
    # to list daemons
    cmd = ['launchctl', 'list']
    ret = __salt__['cmd.run'](cmd)

    services = []
    for line in ret.splitlines():
        if line.split('\t')[2] != 'Label':
            services.append(line.split('\t')[2].strip())

    return sorted(services)
