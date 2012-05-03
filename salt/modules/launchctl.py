'''
Module for the management of MacOS systems that use launchd/launchctl
'''

import plistlib


def __virtual__():
    '''
    Only work on MacOS
    '''
    if __grains__['os'] == 'MacOS':
        return 'service'
    return False


def get_all():
    '''
    Return all installed services

    CLI Example::

        salt '*' service.get_all
    '''
    cmd = 'launchctl list'

    service_lines = [
        line for line in __salt__['cmd.run'](cmd).splitlines()
        if not line.startswith('PID')
    ]

    return sorted([line.split("\t")[2] for line in service_lines])


def get_launchctl_data(job_label, runas=None):
    cmd = 'launchctl list -x {0}'.format(job_label)

    launchctl_xml = __salt__['cmd.run_all'](cmd, runas=runas)['stderr']

    return dict(plistlib.readPlistFromString(launchctl_xml))


def status(job_label, runas=None):
    '''
    Return the status for a service, returns a bool whether the service is
    running.

    CLI Example::

        salt '*' service.status <service name>
    '''
    launchctl_data = get_launchctl_data(job_label, runas=runas)

    return 'PID' in launchctl_data


def stop(job_label, runas=None):
    '''
    Stop the specified service

    CLI Example::

        salt '*' service.stop <service name>
    '''
    cmd = 'launchctl stop {0}'.format(job_label)

    return __salt__['cmd.run'](cmd, runas=runas)


def start(job_label, runas=None):
    '''
    Start the specified service

    CLI Example::

        salt '*' service.start <service name>
    '''
    cmd = 'launchctl start {0}'.format(job_label, runas=runas)

    return __salt__['cmd.run'](cmd, runas='marca')


def restart(job_label, runas=None):
    '''
    Restart the named service

    CLI Example::

        salt '*' service.restart <service name>
    '''
    stop(job_label, runas=runas)
    return start(job_label, runas=runas)
