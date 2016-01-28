# -*- coding: utf-8 -*-
'''
The service module for FreeBSD
'''
from __future__ import absolute_import

# Import python libs
import logging
import os
import re

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
    Only for Mac OS X with launchctl
    '''
    if not salt.utils.is_darwin():
        return (False, 'Failed to load the mac_service module:\n'
                       'Only available on Mac OS X systems.')

    if not os.path.exists('/bin/launchctl'):
        return (False, 'Failed to load the mac_service module:\n'
                       'Required binary not found: "/bin/launchctl"')

    return __virtualname__


def start(service_path, domain='system'):
    '''
    Bootstraps domains and services. The service is enabled, bootstrapped and
    kickstarted. See `man launchctl` on a Mac OS X El Capitan system for more
    details.

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

    :return: True if Successful, False if not or if the service is already
    started
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.start /System/Library/LaunchDaemons/org.cups.cupsd.plist
    '''
    if not os.path.exists(service_path):
        msg = 'Service Path not found:\n' \
              'Path: {0}'.format(service_path)
        raise CommandExecutionError(msg)

    # Get service_target from service_path
    service_name = os.path.splitext(os.path.basename(service_path))[0]
    if domain.endswith('/'):
        service_target = '{0}{1}'.format(domain, service_name)
    else:
        service_target = '{0}/{1}'.format(domain, service_name)

    # Is service running
    if service_name in get_all():
        return False

    # Enable the Launch Daemon
    cmd = ['launchctl', 'enable', service_target]
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode']:
        msg = 'Failed to enable service:\n' \
              'Path: {0}\n'.format(service_path)
        msg += 'Error: {0}\n'.format(ret['stderr'])
        msg += 'StdOut: {0}'.format(ret['stdout'])
        raise CommandExecutionError(msg)

    # Bootstrap the Launch Daemon
    cmd = ['launchctl', 'bootstrap', domain, service_path]
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode']:
        if 'service already loaded' not in ret['stderr']:
            msg = 'Failed to bootstrap service:\n' \
                  'Path: {0}\n'.format(service_path)
            msg += 'Error: {0}\n'.format(ret['stderr'])
            msg += 'StdOut: {0}'.format(ret['stdout'])
            raise CommandExecutionError(msg)

    # Kickstart the Launch Daemon
    cmd = ['launchctl', 'kickstart', '-kp', service_target]
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode']:
        msg = 'Failed to kickstart service:\n' \
              'Path: {0}\n'.format(service_path)
        msg += 'Error: {0}\n'.format(ret['stderr'])
        msg += 'StdOut: {0}'.format(ret['stdout'])
        raise CommandExecutionError(msg)

    return service_name in get_all()


def stop(service_path, domain='system'):
    '''
    Removes (bootout) domains and services. The service is disabled and removed
    from the bootstrap. See `man launchctl` on a Mac OS X El Capitan system for
    more details.

    :param str service_path: Full path to the plist file

    :param str domain: Target domain. May be one of the following:
    - system : this is the default
    - user/<uid> : <uid> is the user id
    - login/<asid> : <asid> is the audit session id
    - gui/<uid> : <uid> is the user id
    - session/<asid> : <asid> is the audit session id
    - pid/<pid> : <pid> is the process id

    :return: True if Successful, False if not or if the service is already
    started
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop /System/Library/LaunchDaemons/org.cups.cupsd.plist
    '''
    if not os.path.exists(service_path):
        msg = 'Service Path not found:\n' \
              'Path: {0}'.format(service_path)
        raise CommandExecutionError(msg)

    # Get service_target from service_path
    service_name = os.path.splitext(os.path.basename(service_path))[0]
    if domain.endswith('/'):
        service_target = '{0}{1}'.format(domain, service_name)
    else:
        service_target = '{0}/{1}'.format(domain, service_name)

    # Is service running
    if service_name not in get_all():
        return False

    # Disable the Launch Daemon
    cmd = ['launchctl', 'disable', service_target]
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode']:
        msg = 'Failed to enable service:\n' \
              'Path: {0}\n'.format(service_path)
        msg += 'Error: {0}\n'.format(ret['stderr'])
        msg += 'StdOut: {0}'.format(ret['stdout'])
        raise CommandExecutionError(msg)

    # Remove the Launch Daemon
    cmd = ['launchctl', 'bootout', domain, service_path]
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode']:
        msg = 'Failed to bootstrap service:\n' \
              'Path: {0}\n'.format(service_path)
        msg += 'Error: {0}\n'.format(ret['stderr'])
        msg += 'StdOut: {0}'.format(ret['stdout'])
        raise CommandExecutionError(msg)

    if service_target in get_all():

        cmd = ['launchctl', 'kill', 'SIGKILL', service_target]
        ret = __salt__['cmd.run_all'](cmd, python_shell=False)
        if ret['retcode']:
            msg = 'Failed to kill the service:\n' \
                  'Path: {0}\n'.format(service_path)
            msg += 'Error: {0}\n'.format(ret['stderr'])
            msg += 'StdOut: {0}'.format(ret['stdout'])
            raise CommandExecutionError(msg)

    return service_name not in get_all()


def restart(service_target):
    '''
    Instructs launchd to kickstart the specified service. If the service is
    already running, the running service will be killed before restarting.

    :param str service_target: This is a combination of the domain and the label
    as defined in the plist file for the service. ``service.get_all`` will
    return a list of labels.

    :return: True if Successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart system/org.cups.cupsd
    '''
    # Kickstart the Launch Daemon
    cmd = ['launchctl', 'kickstart', '-kp', service_target]
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode']:
        msg = 'Failed to kickstart service:\n' \
              'Path: {0}\n'.format(service_target)
        msg += 'Error: {0}\n'.format(ret['stderr'])
        msg += 'StdOut: {0}'.format(ret['stdout'])
        raise CommandExecutionError(msg)

    return not ret['stderr']


def status(name):
    '''
    Return the status for a service.

    :param str name: Can be any part of the service name or a regex expression

    :return: The PID for the service if it is running, otherwise an empty string
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' service.status cups
    '''
    # TODO: Move this to mac_status function if ever created
    cmd = ['launchctl', 'list']
    output = __salt__['cmd.run_stdout'](cmd)

    # Used a string here instead of a list because that's what the linux version
    # of this module does
    pids = ''
    for line in output.splitlines():
        if 'PID' in line:
            continue
        if re.search(name, line):
            if line.split()[0].isdigit():
                if pids:
                    pids += '\n'
                pids += line.split()[0]

    return pids


def reload_(service_target):
    '''
    The linux version of this command refreshes config files by calling service
    reload and does not perform a full restart. There is not equivalent on Mac
    OS. Therefore this function is the same as ``service.restart``.

    :param str service_target: This is a combination of the domain and the label
    as defined in the plist file for the service. ``service.get_all`` will
    return a list of labels.

    :return: True if Successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload system/org.cups.cupsd
    '''
    # Not available in the same way as linux, will perform a restart
    return restart(service_target)


def available(name):
    '''
    Check if the specified service is enabled and loaded.

    :param str name: The name of the service to look up

    :return: True if the specified service is found, otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.available org.cups.cupsd
    '''
    return name in get_all()


def missing(name):
    '''
    Check if the specified service is not enabled and loaded. This is the
    opposite of ``service.available``

    :param str name: The name (or a portion of the name) to look up

    :return: True if the specified service is NOT found, otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing org.cups.cupsd
    '''
    return name not in get_all()


def get_all():
    '''
    Return a list of all services that are enabled and loaded. Can be used to
    find the name of a service.

    :return: A list of all the services enabled and loaded on the system.
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    # This command is legacy on El Capitan, however there is no new command in
    # launchctl to list daemons.
    # This only returns loaded/enabled daemons whereas the linux version
    # returns a list of all services on the system
    cmd = ['launchctl', 'list']
    ret = __salt__['cmd.run'](cmd)

    services = []
    for line in ret.splitlines():
        if line.split('\t')[2] != 'Label':
            services.append(line.split('\t')[2].strip())

    return sorted(services)
