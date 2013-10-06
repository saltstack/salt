# -*- coding: utf-8 -*-
'''
Monit service module. This module will create a monit type
service watcher.
'''

# Import salt libs
import salt.utils


def __virtual__():
    if salt.utils.which('monit') is not None:
        # The monit binary exists, let the module load
        return True
    return False


def start(name):
    '''

    CLI Example:

    .. code-block:: bash

        salt '*' monit.start <service name>
    '''
    cmd = 'monit start {0}'.format(name)

    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stops service via monit

    CLI Example:

    .. code-block:: bash

        salt '*' monit.stop <service name>
    '''
    cmd = 'monit stop {0}'.format(name)

    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart service via monit

    CLI Example:

    .. code-block:: bash

        salt '*' monit.restart <service name>
    '''
    cmd = 'monit restart {0}'.format(name)

    return not __salt__['cmd.retcode'](cmd)


def unmonitor(name):
    '''
    Unmonitor service via monit

    CLI Example:

    .. code-block:: bash

        salt '*' monit.unmonitor <service name>
    '''
    cmd = 'monit unmonitor {0}'.format(name)

    return not __salt__['cmd.retcode'](cmd)


def monitor(name):
    '''
    monitor service via monit

    CLI Example:

    .. code-block:: bash

        salt '*' monit.monitor <service name>
    '''
    cmd = 'monit monitor {0}'.format(name)

    return not __salt__['cmd.retcode'](cmd)


def summary(svc_name=''):
    '''
    Display a summary from monit

    CLI Example:

    .. code-block:: bash

        salt '*' monit.summary
        salt '*' monit.summary <service name>
    '''
    ret = {}
    cmd = 'monit summary'
    res = __salt__['cmd.run'](cmd).splitlines()
    for line in res:
        if 'daemon is not running' in line:
            return dict(monit='daemon is not running', result=False)
        elif svc_name not in line or 'The Monit daemon' in line:
            continue
        else:
            parts = line.split('\'')
            resource, name, status = (
                parts[0].strip(), parts[1], parts[2].strip()
            )
            if resource not in ret:
                ret[resource] = {}
            ret[resource][name] = status
    return ret
