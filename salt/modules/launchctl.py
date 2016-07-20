# -*- coding: utf-8 -*-
'''
Module for the management of MacOS systems that use launchd/launchctl

.. important::
    If you feel that Salt should be using this module to manage services on a
    minion, and it is using a different module (or gives an error similar to
    *'service.start' is not available*), see :ref:`here
    <module-provider-override>`.

:depends:   - plistlib Python module
'''
from __future__ import absolute_import

# Import python libs
import os
import plistlib

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators
import salt.ext.six as six

# Define the module's virtual name
__virtualname__ = 'service'


def __virtual__():
    '''
    Only work on MacOS
    '''
    if __grains__['os'] == 'MacOS':
        return __virtualname__
    return False


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
                    # This assumes most of the plist files will be already in XML format
                    with salt.utils.fopen(file_path):
                        plist = plistlib.readPlist(true_path)

                except Exception:
                    # If plistlib is unable to read the file we'll need to use
                    # the system provided plutil program to do the conversion
                    cmd = '/usr/bin/plutil -convert xml1 -o - -- "{0}"'.format(true_path)
                    plist_xml = __salt__['cmd.run_all'](cmd, python_shell=False)['stdout']
                    if six.PY2:
                        plist = plistlib.readPlistFromString(plist_xml)
                    else:
                        plist = plistlib.readPlistFromBytes(salt.utils.to_bytes(plist_xml))

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


def get_all():
    '''
    Return all installed services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    cmd = 'launchctl list'

    service_lines = [
        line for line in __salt__['cmd.run'](cmd).splitlines()
        if not line.startswith('PID')
    ]

    service_labels_from_list = [
        line.split("\t")[2] for line in service_lines
    ]
    service_labels_from_services = list(_available_services().keys())

    return sorted(set(service_labels_from_list + service_labels_from_services))


def _get_launchctl_data(job_label, runas=None):
    cmd = 'launchctl list -x {0}'.format(job_label)

    launchctl_xml = __salt__['cmd.run_all'](cmd, python_shell=False, runas=runas)

    if launchctl_xml['stderr'] == 'launchctl list returned unknown response':
        # The service is not loaded, further, it might not even exist
        # in either case we didn't get XML to parse, so return an empty
        # dict
        return dict()

    return dict(plistlib.readPlistFromString(launchctl_xml['stdout']))


def available(job_label):
    '''
    Check that the given service is available.

    CLI Example:

    .. code-block:: bash

        salt '*' service.available com.openssh.sshd
    '''
    return True if _service_by_name(job_label) else False


def missing(job_label):
    '''
    The inverse of service.available
    Check that the given service is not available.

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing com.openssh.sshd
    '''
    return False if _service_by_name(job_label) else True


def status(job_label, runas=None):
    '''
    Return the status for a service, returns a bool whether the service is
    running.

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service label>
    '''
    service = _service_by_name(job_label)

    lookup_name = service['plist']['Label'] if service else job_label
    launchctl_data = _get_launchctl_data(lookup_name, runas=runas)

    return 'PID' in launchctl_data


def stop(job_label, runas=None):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service label>
        salt '*' service.stop org.ntp.ntpd
        salt '*' service.stop /System/Library/LaunchDaemons/org.ntp.ntpd.plist
    '''
    service = _service_by_name(job_label)
    if service:
        cmd = 'launchctl unload -w {0}'.format(service['file_path'], runas=runas)
        return not __salt__['cmd.retcode'](cmd, runas=runas, python_shell=False)

    return False


def start(job_label, runas=None):
    '''
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service label>
        salt '*' service.start org.ntp.ntpd
        salt '*' service.start /System/Library/LaunchDaemons/org.ntp.ntpd.plist
    '''
    service = _service_by_name(job_label)
    if service:
        cmd = 'launchctl load -w {0}'.format(service['file_path'], runas=runas)
        return not __salt__['cmd.retcode'](cmd, runas=runas, python_shell=False)

    return False


def restart(job_label, runas=None):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service label>
    '''
    stop(job_label, runas=runas)
    return start(job_label, runas=runas)
