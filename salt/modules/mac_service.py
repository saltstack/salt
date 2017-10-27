# -*- coding: utf-8 -*-
'''
The service module for macOS
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
from salt.exceptions import CommandExecutionError

# Import 3rd party libs
import salt.ext.six as six

# Define the module's virtual name
__virtualname__ = 'service'

__func_alias__ = {
    'list_': 'list',
}


def __virtual__():
    '''
    Only for macOS with launchctl
    '''
    if not salt.utils.is_darwin():
        return (False, 'Failed to load the mac_service module:\n'
                       'Only available on macOS systems.')

    if not salt.utils.which('launchctl'):
        return (False, 'Failed to load the mac_service module:\n'
                       'Required binary not found: "launchctl"')

    if not salt.utils.which('plutil'):
        return (False, 'Failed to load the mac_service module:\n'
                       'Required binary not found: "plutil"')

    if LooseVersion(__grains__['osrelease']) < LooseVersion('10.11'):
        return (False, 'Failed to load the mac_service module:\n'
                       'Requires macOS 10.11 or newer')

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

                # Must be a plist file
                if not file_name.endswith('.plist'):
                    continue

                # Follow symbolic links of files in _launchd_paths
                file_path = os.path.join(root, file_name)
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
                    plist_xml = __salt__['cmd.run'](cmd, output_loglevel='quiet')
                    if six.PY2:
                        plist = plistlib.readPlistFromString(plist_xml)
                    else:
                        plist = plistlib.readPlistFromBytes(
                            salt.utils.to_bytes(plist_xml))

                try:
                    available_services[plist.Label.lower()] = {
                        'file_name': file_name,
                        'file_path': true_path,
                        'plist': plist}
                except AttributeError:
                    # Handle malformed plist files
                    available_services[os.path.basename(file_name).lower()] = {
                        'file_name': file_name,
                        'file_path': true_path,
                        'plist': plist}

    return available_services


def _get_service(name):
    '''
    Get information about a service.  If the service is not found, raise an
    error

    :param str name: Service label, file name, or full path

    :return: The service information for the service, otherwise an Error
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

    :return: The service information if the service is found
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' service.show org.cups.cupsd  # service label
        salt '*' service.show org.cups.cupsd.plist  # file name
        salt '*' service.show /System/Library/LaunchDaemons/org.cups.cupsd.plist  # full path
    '''
    return _get_service(name)


def launchctl(sub_cmd, *args, **kwargs):
    '''
    Run a launchctl command and raise an error if it fails

    :param str sub_cmd: Sub command supplied to launchctl

    :param tuple args: Tuple containing additional arguments to pass to
        launchctl

    :param dict kwargs: Dictionary containing arguments to pass to
        ``cmd.run_all``

    :param bool return_stdout: A keyword argument.  If true return the stdout
        of the launchctl command

    :return: ``True`` if successful, raise ``CommandExecutionError`` if not, or
        the stdout of the launchctl command if requested
    :rtype: bool, str

    CLI Example:

    .. code-block:: bash

        salt '*' service.launchctl debug org.cups.cupsd
    '''
    # Get return type
    return_stdout = kwargs.pop('return_stdout', False)

    # Construct command
    cmd = ['launchctl', sub_cmd]
    cmd.extend(args)

    # Run command
    kwargs['python_shell'] = False
    ret = __salt__['cmd.run_all'](cmd, **kwargs)

    # Raise an error or return successful result
    if ret['retcode']:
        out = 'Failed to {0} service:\n'.format(sub_cmd)
        out += 'stdout: {0}\n'.format(ret['stdout'])
        out += 'stderr: {0}\n'.format(ret['stderr'])
        out += 'retcode: {0}\n'.format(ret['retcode'])
        raise CommandExecutionError(out)
    else:
        return ret['stdout'] if return_stdout else True


def list_(name=None, runas=None):
    '''
    Run launchctl list and return the output

    :param str name: The name of the service to list

    :param str runas: User to run launchctl commands

    :return: If a name is passed returns information about the named service,
        otherwise returns a list of all services and pids
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' service.list
        salt '*' service.list org.cups.cupsd
    '''
    if name:
        # Get service information and label
        service = _get_service(name)
        label = service['plist']['Label']

        # Collect information on service: will raise an error if it fails
        return launchctl('list',
                         label,
                         return_stdout=True,
                         output_loglevel='trace',
                         runas=runas)

    # Collect information on all services: will raise an error if it fails
    return launchctl('list',
                     return_stdout=True,
                     output_loglevel='trace',
                     runas=runas)


def enable(name, runas=None):
    '''
    Enable a launchd service. Raises an error if the service fails to be enabled

    :param str name: Service label, file name, or full path

    :param str runas: User to run launchctl commands

    :return: ``True`` if successful or if the service is already enabled
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable org.cups.cupsd
    '''
    # Get service information and label
    service = _get_service(name)
    label = service['plist']['Label']

    # Enable the service: will raise an error if it fails
    return launchctl('enable', 'system/{0}'.format(label), runas=runas)


def disable(name, runas=None):
    '''
    Disable a launchd service. Raises an error if the service fails to be
    disabled

    :param str name: Service label, file name, or full path

    :param str runas: User to run launchctl commands

    :return: ``True`` if successful or if the service is already disabled
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable org.cups.cupsd
    '''
    # Get service information and label
    service = _get_service(name)
    label = service['plist']['Label']

    # disable the service: will raise an error if it fails
    return launchctl('disable', 'system/{0}'.format(label), runas=runas)


def start(name, runas=None):
    '''
    Start a launchd service.  Raises an error if the service fails to start

    .. note::
        To start a service in macOS the service must be enabled first. Use
        ``service.enable`` to enable the service.

    :param str name: Service label, file name, or full path

    :param str runas: User to run launchctl commands

    :return: ``True`` if successful or if the service is already running
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.start org.cups.cupsd
    '''
    # Get service information and file path
    service = _get_service(name)
    path = service['file_path']

    # Load the service: will raise an error if it fails
    return launchctl('load', path, runas=runas)


def stop(name, runas=None):
    '''
    Stop a launchd service.  Raises an error if the service fails to stop

    .. note::
        Though ``service.stop`` will unload a service in macOS, the service
        will start on next boot unless it is disabled. Use ``service.disable``
        to disable the service

    :param str name: Service label, file name, or full path

    :param str runas: User to run launchctl commands

    :return: ``True`` if successful or if the service is already stopped
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop org.cups.cupsd
    '''
    # Get service information and file path
    service = _get_service(name)
    path = service['file_path']

    # Disable the Launch Daemon: will raise an error if it fails
    return launchctl('unload', path, runas=runas)


def restart(name, runas=None):
    '''
    Unloads and reloads a launchd service.  Raises an error if the service
    fails to reload

    :param str name: Service label, file name, or full path

    :param str runas: User to run launchctl commands

    :return: ``True`` if successful
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart org.cups.cupsd
    '''
    # Restart the service: will raise an error if it fails
    if enabled(name):
        stop(name, runas=runas)
    start(name, runas=runas)

    return True


def status(name, sig=None, runas=None):
    '''
    Return the status for a service.

    :param str name: Used to find the service from launchctl.  Can be any part
        of the service name or a regex expression.

    :param str sig: Find the service with status.pid instead.  Note that
        ``name`` must still be provided.

    :param str runas: User to run launchctl commands

    :return: The PID for the service if it is running, otherwise an empty string
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' service.status cups
    '''
    # Find service with ps
    if sig:
        return __salt__['status.pid'](sig)

    output = list_(runas=runas)

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

    :param str name: The name of the service

    :return: True if the service is available, otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.available com.openssh.sshd
    '''
    try:
        _get_service(name)
        return True
    except CommandExecutionError:
        return False


def missing(name):
    '''
    The inverse of service.available
    Check that the given service is not available.

    :param str name: The name of the service

    :return: True if the service is not available, otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing com.openssh.sshd
    '''
    return not available(name)


def enabled(name, runas=None):
    '''
    Check if the specified service is enabled

    :param str name: The name of the service to look up

    :param str runas: User to run launchctl commands

    :return: True if the specified service enabled, otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled org.cups.cupsd
    '''
    # Try to list the service.  If it can't be listed, it's not enabled
    try:
        list_(name=name, runas=runas)
        return True
    except CommandExecutionError:
        return False


def disabled(name, runas=None):
    '''
    Check if the specified service is not enabled. This is the opposite of
    ``service.enabled``

    :param str name: The name to look up

    :param str runas: User to run launchctl commands

    :return: True if the specified service is NOT enabled, otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled org.cups.cupsd
    '''
    # A service is disabled if it is not enabled
    return not enabled(name, runas=runas)


def get_all(runas=None):
    '''
    Return a list of services that are enabled or available. Can be used to
    find the name of a service.

    :param str runas: User to run launchctl commands

    :return: A list of all the services available or enabled
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    # Get list of enabled services
    enabled = get_enabled(runas=runas)

    # Get list of all services
    available = list(_available_services().keys())

    # Return composite list
    return sorted(set(enabled + available))


def get_enabled(runas=None):
    '''
    Return a list of all services that are enabled. Can be used to find the
    name of a service.

    :param str runas: User to run launchctl commands

    :return: A list of all the services enabled on the system
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
        salt '*' service.get_enabled running=True
    '''
    # Collect list of enabled services
    stdout = list_(runas=runas)
    service_lines = [line for line in stdout.splitlines()]

    # Construct list of enabled services
    enabled = []
    for line in service_lines:
        # Skip header line
        if line.startswith('PID'):
            continue

        pid, status, label = line.split('\t')
        enabled.append(label)

    return sorted(set(enabled))
