# -*- coding: utf-8 -*-
'''
Service support for Solaris 10 and 11, should work with other systems
that use SMF also. (e.g. SmartOS)
'''

__func_alias__ = {
    'reload_': 'reload'
}


def __virtual__():
    '''
    Only work on systems which default to SMF
    '''
    if 'Solaris' in __grains__['os_family']:
        # Don't let this work on Solaris 9 since SMF doesn't exist on it.
        if __grains__['kernelrelease'] == "5.9":
            return False
        return 'service'
    return False


def _get_enabled_disabled(enabled_prop="true"):
    '''
    DRY: Get all service FMRIs and their enabled property
    '''
    ret = set()
    cmd = '/usr/bin/svcprop -c -p general/enabled "*"'
    lines = __salt__['cmd.run_stdout'](cmd).splitlines()
    for line in lines:
        comps = line.split()
        if not comps:
            continue
        if comps[2] == enabled_prop:
            ret.add(comps[0].split("/:properties")[0])
    return sorted(ret)


def get_running():
    '''
    Return the running services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_running
    '''
    ret = set()
    cmd = '/usr/bin/svcs -H -o SVC,STATE -s SVC'
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        comps = line.split()
        if not comps:
            continue
        if 'online' in line:
            ret.add(comps[0])
    return sorted(ret)


def get_stopped():
    '''
    Return the stopped services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_stopped
    '''
    ret = set()
    cmd = '/usr/bin/svcs -aH -o SVC,STATE -s SVC'
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        comps = line.split()
        if not comps:
            continue
        if not 'online' in line and not 'legacy_run' in line:
            ret.add(comps[0])
    return sorted(ret)


def available(name):
    '''
    Return if the specified service is available

    CLI Example:

    .. code-block:: bash

        salt '*' service.available
    '''
    return name in get_all()


def get_all():
    '''
    Return all installed services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    ret = set()
    cmd = '/usr/bin/svcs -aH -o SVC,STATE -s SVC'
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        comps = line.split()
        if not comps:
            continue
        ret.add(comps[0])
    return sorted(ret)


def start(name):
    '''
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    cmd = '/usr/sbin/svcadm enable -s -t {0}'.format(name)
    retcode = __salt__['cmd.retcode'](cmd)
    if not retcode:
        return True
    if retcode == 3:
        # Return code 3 means there was a problem with the service
        # A common case is being in the 'maintenance' state
        # Attempt a clear and try one more time
        clear_cmd = '/usr/sbin/svcadm clear {0}'.format(name)
        __salt__['cmd.retcode'](clear_cmd)
        return not __salt__['cmd.retcode'](cmd)
    return False


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    cmd = '/usr/sbin/svcadm disable -s -t {0}'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    cmd = '/usr/sbin/svcadm restart {0}'.format(name)
    if not __salt__['cmd.retcode'](cmd):
        # calling restart doesn't clear maintenance
        # or tell us that the service is in the 'online' state
        return start(name)
    return False


def reload_(name):
    '''
    Reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    '''
    cmd = '/usr/sbin/svcadm refresh {0}'.format(name)
    if not __salt__['cmd.retcode'](cmd):
        # calling reload doesn't clear maintenance
        # or tell us that the service is in the 'online' state
        return start(name)
    return False


def status(name, sig=None):
    '''
    Return the status for a service, returns a bool whether the service is
    running.

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name>
    '''
    cmd = '/usr/bin/svcs -H -o STATE {0}'.format(name)
    line = __salt__['cmd.run'](cmd)
    if line == 'online':
        return True
    else:
        return False


def enable(name, **kwargs):
    '''
    Enable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    '''
    cmd = '/usr/sbin/svcadm enable {0}'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def disable(name, **kwargs):
    '''
    Disable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    '''
    cmd = '/usr/sbin/svcadm disable {0}'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def enabled(name):
    '''
    Check to see if the named service is enabled to start on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    '''
    # The property that reveals whether a service is enabled
    # can only be queried using the full FMRI
    # We extract the FMRI and then do the query
    fmri_cmd = '/usr/bin/svcs -H -o FMRI {0}'.format(name)
    fmri = __salt__['cmd.run'](fmri_cmd)
    cmd = '/usr/sbin/svccfg -s {0} listprop general/enabled'.format(fmri)
    comps = __salt__['cmd.run'](cmd).split()
    if comps[2] == 'true':
        return True
    else:
        return False


def disabled(name):
    '''
    Check to see if the named service is disabled to start on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    '''
    return not enabled(name)


def get_enabled():
    '''
    Return the enabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    '''
    # Note that this returns the full FMRI
    return _get_enabled_disabled("true")


def get_disabled():
    '''
    Return the disabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    '''
    # Note that this returns the full FMRI
    return _get_enabled_disabled("false")
