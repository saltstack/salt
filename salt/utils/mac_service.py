# -*- coding: utf-8 -*-
'''
The service salt util for macOS
.. versionadded:: 2016.11.10
'''
from __future__ import absolute_import
import logging

# Import python libs
import os
import re
import plistlib

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators
from salt.exceptions import CommandExecutionError

# Import 3rd party libs
import salt.ext.six as six

log = logging.getLogger(__name__)

LAUNCHD_PATHS = [
    '/Library/LaunchAgents',
    '/Library/LaunchDaemons',
    '/System/Library/LaunchAgents',
    '/System/Library/LaunchDaemons',
]

__func_alias__ = {
    'list_': 'list',
}


@decorators.memoize
def _available_services():
    '''
    Return a dictionary of all available services on the system
    '''
    available_services = dict()
    for launch_dir in LAUNCHD_PATHS:
        for root, dirs, files in os.walk(launch_dir):
            for file_name in files:

                # Must be a plist file
                if not file_name.endswith('.plist'):
                    continue

                # Follow symbolic links of files in LAUNCHD_PATHS
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

    Args:
        name (str): Service label, file name, or full path

    Returns:
        dict: The service information for the service

    Raises:
        CommandExecutionError: If service is not found
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

    Args:
        name (str): Service label, file name, or full path

    Returns:
        dict: The service information if the service is found

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.show('org.cups.cupsd')  # service label
        salt.utils.mac_service.show('org.cups.cupsd.plist')  # file name
        salt.utils.mac_service.show('/System/Library/LaunchDaemons/org.cups.cupsd.plist')  # full path
    '''
    return _get_service(name)


def launchctl(sub_cmd, *args, **kwargs):
    '''
    Run a launchctl command and raise an error if it fails

    Args: additional args are passed to launchctl
        sub_cmd (str): Sub command supplied to launchctl

    Kwargs: passed to ``cmd.run_all``
        return_stdout (bool): A keyword argument. If true return the stdout of
            the launchctl command

    Returns:
        bool: ``True`` if successful
        str: The stdout of the launchctl command if requested

    Raises:
        CommandExecutionError: Tf command fails

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.launchctl('debug', 'org.cups.cupsd')
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

    Args:
        name (str): The name of the service to list
        runas (str): User to run launchctl commands

    Returns:
        str: If a name is passed returns information about the named service,
            otherwise returns a list of all services and pids

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.list()
        salt.utils.mac_service.list('org.cups.cupsd')
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

    Args:
        name (str): Service label, file name, or full path
        runas (str): User to run launchctl commands

    Returns:
        bool: ``True`` if successful or if the service is already enabled

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.enable('org.cups.cupsd')
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

    Args:
        name (str): Service label, file name, or full path
        runas (str): User to run launchctl commands

    Returns:
        bool: ``True`` if successful or if the service is already disabled

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.disable('org.cups.cupsd')
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

    Args:
        name (str): Service label, file name, or full path
        runas (str): User to run launchctl commands

    Returns:
        bool: ``True`` if successful or if the service is already running

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.start('org.cups.cupsd')
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

    Args:
        name (str): Service label, file name, or full path
        runas (str): User to run launchctl commands

    Return:
        bool: ``True`` if successful or if the service is already stopped

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.stop('org.cups.cupsd')
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

    Args:
        name (str): Service label, file name, or full path
        runas (str): User to run launchctl commands

    Returns:
        bool: ``True`` if successful

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.restart('org.cups.cupsd')
    '''
    # Restart the service: will raise an error if it fails
    if enabled(name):
        stop(name, runas=runas)
    start(name, runas=runas)

    return True


def status(name, sig=None, runas=None):
    '''
    Return the status for a service.

    Args:
        name (str): Used to find the service from launchctl.  Can be any part of
            the service name or a regex expression.

        sig (str): Find the service with status.pid instead.  Note that ``name``
            must still be provided.

        runas (str): User to run launchctl commands

    Returns:
        str: The PID for the service if it is running, otherwise an empty string

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.status('cups')
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

    Args:
        name (str): The name of the service

    Returns:
        bool: True if the service is available, otherwise False

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.available('com.openssh.sshd')
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

    Args:
        name (str): The name of the service

    Returns:
        bool: True if the service is not available, otherwise False

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.missing('com.openssh.sshd')
    '''
    return not available(name)


def enabled(name, runas=None):
    '''
    Check if the specified service is enabled

    Args:
        name (str): The name of the service to look up
        runas (str): User to run launchctl commands

    Returns:
        bool: True if the specified service enabled, otherwise False

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.enabled('org.cups.cupsd')
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

    Args:
        name (str): The name to look up
        runas (str): User to run launchctl commands

    Returns:
        bool: True if the specified service is NOT enabled, otherwise False

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.disabled('org.cups.cupsd')
    '''
    # A service is disabled if it is not enabled
    return not enabled(name, runas=runas)


def get_all(runas=None):
    '''
    Return a list of services that are enabled or available. Can be used to
    find the name of a service.

    Args:
        runas (str): User to run launchctl commands

    Return:
        list: A list of all the services available or enabled

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.get_all()
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

    Args:
        runas (str): User to run launchctl commands

    Returns:
        list: A list of all the services enabled on the system

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.get_enabled()
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
