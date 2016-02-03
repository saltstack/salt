# -*- coding: utf-8 -*-
'''
The service module for Mac OS X
.. versionadded:: Boron
'''
from __future__ import absolute_import

# Import python libs
import logging
import os
import re
import plistlib
from distutils.version import LooseVersion

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators
import salt.ext.six as six
from salt.exceptions import CommandExecutionError

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

    if LooseVersion(__grains__['osrelease']) < LooseVersion('10.11'):
        return (False, 'Failed to load the mac_service module:\n'
                       'Requires OS X 10.11 or newer')

    return __virtualname__


def _launchd_paths():
    '''
    Paths where launchd services can be found
    '''
    return [
        '/Library/LaunchAgents',
        '/Library/LaunchDaemons',
        '/System/Library/LaunchAgents',
        '/System/Library/LaunchDaemons',
    ]


@decorators.memoize
def _available_services():
    '''
    Return a dictionary of all available services on the system
    '''
    available_services = dict()
    for launch_dir in _launchd_paths():
        for root, dirs, files in os.walk(launch_dir):
            for filename in files:
                file_path = os.path.join(root, filename)
                # Follow symbolic links of files in _launchd_paths
                true_path = os.path.realpath(file_path)
                # ignore broken symlinks
                if not os.path.exists(true_path):
                    continue

                try:
                    # This assumes most of the plist files
                    # will be already in XML format
                    with salt.utils.fopen(file_path):
                        plist = plistlib.readPlist(true_path)

                except Exception:
                    # If plistlib is unable to read the file we'll need to use
                    # the system provided plutil program to do the conversion
                    cmd = '/usr/bin/plutil -convert xml1 -o - -- "{0}"'.format(
                        true_path)
                    plist_xml = __salt__['cmd.run_all'](
                        cmd, python_shell=False)['stdout']
                    if six.PY2:
                        plist = plistlib.readPlistFromString(plist_xml)
                    else:
                        plist = plistlib.readPlistFromBytes(
                            salt.utils.to_bytes(plist_xml))

                available_services[plist.Label.lower()] = {
                    'filename': filename,
                    'file_path': true_path,
                    'plist': plist,
                }

    return available_services


def _service_by_name(name):
    '''
    Return the service info for a service by label, filename or path
    '''
    services = _available_services()
    name = name.lower()

    if name in services:
        # Match on label
        return services[name]

    for service in six.itervalues(services):
        if service['file_path'].lower() == name:
            # Match on full path
            return service
        basename, ext = os.path.splitext(service['filename'])
        if basename.lower() == name:
            # Match on basename
            return service

    return False


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


def available(name):
    '''
    Check that the given service is available.

    CLI Example:

    .. code-block:: bash

        salt '*' service.available com.openssh.sshd
    '''
    return True if _service_by_name(name) else False


def missing(name):
    '''
    The inverse of service.available
    Check that the given service is not available.

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing com.openssh.sshd
    '''
    return False if _service_by_name(name) else True


def enabled(name):
    '''
    Check if the specified service is enabled

    :param str name: The name of the service to look up

    :return: True if the specified service enabled, otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled org.cups.cupsd
    '''
    return name in _get_enabled()


def disabled(name):
    '''
    Check if the specified service is not enabled. This is the opposite of
    ``service.enabled``

    :param str name: The name to look up

    :return: True if the specified service is NOT enabled, otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled org.cups.cupsd
    '''
    return name not in _get_enabled()


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
    cmd = ['launchctl', 'list']
    service_lines = [
        line for line in __salt__['cmd.run'](cmd).splitlines()
        if not line.startswith('PID')
        ]

    service_labels_from_list = [
        line.split("\t")[2] for line in service_lines
        ]
    service_labels_from_services = list(_available_services().keys())

    return sorted(set(service_labels_from_list + service_labels_from_services))


def _get_enabled():
    cmd = ['launchctl', 'list']
    ret = __salt__['cmd.run'](cmd)

    services = []
    for line in ret.splitlines():
        if line.split('\t')[2] != 'Label':
            services.append(line.split('\t')[2].strip())

    return sorted(services)
