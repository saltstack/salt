# -*- coding: utf-8 -*-
'''
The service module for Mac OS X
.. versionadded:: 2016.3.0
'''
from __future__ import absolute_import

# Import python libs
import os
import re
import plistlib
from distutils.version import LooseVersion

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators
import salt.ext.six as six
from salt.exceptions import CommandExecutionError

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
            for file_name in files:
                file_path = os.path.join(root, file_name)
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
                    plist_xml = __salt__['cmd.run'](
                        cmd, python_shell=False, output_loglevel='trace')
                    if six.PY2:
                        plist = plistlib.readPlistFromString(plist_xml)
                    else:
                        plist = plistlib.readPlistFromBytes(
                            salt.utils.to_bytes(plist_xml))

                available_services[plist.Label.lower()] = {
                    'file_name': file_name,
                    'file_path': true_path,
                    'plist': plist,
                }

    return available_services


def _get_service(name):
    '''
    Get information about a service.  If the service is not found, raise an
    error

    :param str name: Service label, file name, or full path

    :return: The service information if the service is found, ``False``
        otherwise
    :rtype: dict
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
        basename, ext = os.path.splitext(service['file_name'])
        if basename.lower() == name:
            # Match on basename
            return service

    # Could not find service
    raise CommandExecutionError('Service not found: {0}'.format(name))


def show(name):
    '''
    Show properties of a launchctl service

    :param str name: Service label, file name, or full path

    :return: The service information if the service is found, ``False``
        otherwise
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' service.show org.cups.cupsd  # service label
        salt '*' service.show org.cups.cupsd.plist  # file name
        salt '*' service.show /System/Library/LaunchDaemons/org.cups.cupsd.plist  # full path
    '''
    return _get_service(name)


def _cmd_error(ret, msg):
    '''
    Format error information returned from cmd.run_all
    '''
    out = '{0}:\n'.format(msg)
    out += 'stdout: {0}'.format(ret['stdout'])
    out += 'stderr: {0}\n'.format(ret['stderr'])
    out += 'retcode: {0}\n'.format(ret['retcode'])
    raise CommandExecutionError(out)


def _launchctl(sub_cmd, *args, **kwargs):
    '''
    Run a launchctl command and raise an error if it fails

    :param str sub_cmd: Sub command supplied to launchctl

    :param tuple args: Tuple containing additional arguments

    :param dict kwargs: Dictionary containing arguments to pass to
        ``cmd.run_all``

    :param bool return_stdout: A keyword argument.  If true return the stdout
        of the launchctl command

    :return: ``True`` if successful, raise ``CommandExecutionError`` if not, or
        the stdout of the launchctl command if requested
    :rtype: bool
    '''
    # Get return type
    return_stdout = kwargs.pop('return_stdout', False)

    # Construct command
    cmd = ['launchctl', sub_cmd]
    cmd.extend(args)

    # Run command
    kwargs['python_shell'] = False
    ret = __salt__['cmd.run_all'](cmd, **kwargs)

    # Handle command result
    if ret['retcode']:
        _cmd_error(ret, 'Failed to {0} service'.format(sub_cmd))
    else:
        return ret['stdout'] if return_stdout else True


def start(name, domain='system', runas=None):
    '''
    Bootstraps domains and services. The service is enabled, bootstrapped and
    kickstarted. See `man launchctl` on a Mac OS X El Capitan system for more
    details.

    :param str name: Service label, file name, or full path

    :param str domain: Target domain. May be one of the following:
        - system : this is the default
        - user/<uid> : <uid> is the user id
        - login/<asid> : <asid> is the audit session id
        - gui/<uid> : <uid> is the user id
        - session/<asid> : <asid> is the audit session id
        - pid/<pid> : <pid> is the process id

    :param str runas: User to run launchctl commands

    :return: ``True`` if successful or if the service is already running,
        ``False`` if the service failed to start
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.start org.cups.cupsd
    '''
    # Get service information
    service = _get_service(name)

    # Set service label, target domain, and path
    service_label = service['plist']['Label']
    service_target = os.path.join(domain, service_label)
    service_path = service['file_path']

    # Return if service is already running
    if service_label in get_all():
        return True

    # Enable the Launch Daemon
    _launchctl('enable', service_target, runas=runas)

    # Bootstrap the Launch Daemon
    _launchctl('bootstrap', domain, service_path, runas=runas)

    # Kickstart the Launch Daemon
    _launchctl('kickstart', '-kp', service_target, runas=runas)

    return service_label in get_all()


def stop(name, domain='system', runas=None):
    '''
    Removes (bootout) domains and services. The service is disabled and removed
    from the bootstrap. See `man launchctl` on a Mac OS X El Capitan system for
    more details.

    :param str name: Service label, file name, or full path

    :param str domain: Target domain. May be one of the following:
        - system : this is the default
        - user/<uid> : <uid> is the user id
        - login/<asid> : <asid> is the audit session id
        - gui/<uid> : <uid> is the user id
        - session/<asid> : <asid> is the audit session id
        - pid/<pid> : <pid> is the process id

    :param str runas: User to run launchctl commands

    :return: ``True`` if successful or if the service is already stopped,
        ``False`` if the service failed to stop
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop org.cups.cupsd
    '''
    # Get service information
    service = _get_service(name)

    # Set service label, target domain, and path
    service_label = service['plist']['Label']
    service_target = os.path.join(domain, service_label)
    service_path = service['file_path']

    # Return if service is already stopped
    if service_label not in get_all():
        return False

    # Disable the Launch Daemon
    _launchctl('disable', service_target, runas=runas)

    # Remove the Launch Daemon
    _launchctl('bootout', domain, service_path, runas=runas)

    # Kill the Launch Daemon
    if service_target in get_all():
        _launchctl('kill', 'SIGKILL', service_target, runas=runas)

    return service_label not in get_all()


def restart(name, domain='system', runas=None):
    '''
    Instructs launchd to kickstart the specified service. If the service is
    already running, the running service will be killed before restarting.

    :param str name: Service label, file name, or full path

    :param str domain: Target domain. May be one of the following:
        - system : this is the default
        - user/<uid> : <uid> is the user id
        - login/<asid> : <asid> is the audit session id
        - gui/<uid> : <uid> is the user id
        - session/<asid> : <asid> is the audit session id
        - pid/<pid> : <pid> is the process id

    :param str runas: User to run launchctl commands

    :return: ``True`` if successful, ``False`` if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart org.cups.cupsd
    '''
    # Get service information
    service = _get_service(name)

    # Set service target domain
    service_target = os.path.join(domain, service['plist']['Label'])
    print(service['plist']['Label'], service_target)

    # Kickstart the Launch Daemon
    return _launchctl('kickstart', '-kp', service_target)


def status(name, sig=None):
    '''
    Return the status for a service.

    :param str name: Used to find the service from launchctl.  Can be any part
        of the service name or a regex expression.

    :param str sig: Find the service with status.pid instead.  Note that
        ``name`` must still be provided.

    :return: The PID for the service if it is running, otherwise an empty string
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' service.status cups
    '''
    # Find service with ps
    if sig:
        return __salt__['status.pid'](sig)

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
    return True if _get_service(name) else False


def missing(name):
    '''
    The inverse of service.available
    Check that the given service is not available.

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing com.openssh.sshd
    '''
    return False if _get_service(name) else True


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
    ret = _launchctl('list', return_stdout=True)
    service_lines = [
        line for line in ret.splitlines()
        if not line.startswith('PID')
        ]

    service_labels_from_list = [
        line.split("\t")[2] for line in service_lines
        ]
    service_labels_from_services = list(_available_services().keys())

    return sorted(set(service_labels_from_list + service_labels_from_services))


def _get_enabled():
    '''
    Return a list of enabled services
    '''
    ret = _launchctl('list', return_stdout=True)

    services = []
    for line in ret.splitlines():
        if line.split('\t')[2] != 'Label':
            services.append(line.split('\t')[2].strip())

    return sorted(services)
