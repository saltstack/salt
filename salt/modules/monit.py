# -*- coding: utf-8 -*-
'''
Monit service module. This module will create a monit type
service watcher.
'''
from __future__ import absolute_import

# Import python libs
import re

# Import salt libs
import salt.utils

# Function alias to make sure not to shadow built-in's
__func_alias__ = {
    'id_': 'id',
    'reload_': 'reload',
}


def __virtual__():
    if salt.utils.which('monit') is not None:
        # The monit binary exists, let the module load
        return True
    return (False, 'The monit execution module cannot be loaded: the monit binary is not in the path.')


def start(name):
    '''

    CLI Example:

    .. code-block:: bash

        salt '*' monit.start <service name>
    '''
    cmd = 'monit start {0}'.format(name)

    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def stop(name):
    '''
    Stops service via monit

    CLI Example:

    .. code-block:: bash

        salt '*' monit.stop <service name>
    '''
    cmd = 'monit stop {0}'.format(name)

    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def restart(name):
    '''
    Restart service via monit

    CLI Example:

    .. code-block:: bash

        salt '*' monit.restart <service name>
    '''
    cmd = 'monit restart {0}'.format(name)

    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def unmonitor(name):
    '''
    Unmonitor service via monit

    CLI Example:

    .. code-block:: bash

        salt '*' monit.unmonitor <service name>
    '''
    cmd = 'monit unmonitor {0}'.format(name)

    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def monitor(name):
    '''
    monitor service via monit

    CLI Example:

    .. code-block:: bash

        salt '*' monit.monitor <service name>
    '''
    cmd = 'monit monitor {0}'.format(name)

    return not __salt__['cmd.retcode'](cmd, python_shell=False)


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
        elif not line or svc_name not in line or 'The Monit daemon' in line:
            continue
        else:
            parts = line.split('\'')
            if len(parts) == 3:
                resource, name, status_ = (
                    parts[0].strip(), parts[1], parts[2].strip()
                )
                if svc_name != '' and svc_name != name:
                    continue
                if resource not in ret:
                    ret[resource] = {}
                ret[resource][name] = status_
    return ret


def status(svc_name=''):
    '''
    Display a process status from monit

    CLI Example:

    .. code-block:: bash

        salt '*' monit.status
        salt '*' monit.status <service name>
    '''
    cmd = 'monit status'
    res = __salt__['cmd.run'](cmd)
    prostr = 'Process'+' '*28
    s = res.replace('Process', prostr).replace("'", '').split('\n\n')
    entries = {}
    for process in s[1:-1]:
        pro = process.splitlines()
        tmp = {}
        for items in pro:
            key = items[:36].strip()
            tmp[key] = items[35:].strip()
        entries[pro[0].split()[1]] = tmp
    if svc_name == '':
        ret = entries
    else:
        ret = entries.get(svc_name, 'No such service')
    return ret


def reload_():
    '''
    .. versionadded:: 2016.3.0

    Reload monit configuration

    CLI Example:

    .. code-block:: bash

        salt '*' monit.reload
    '''
    cmd = 'monit reload'
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def configtest():
    '''
    .. versionadded:: 2016.3.0

    Test monit configuration syntax

    CLI Example:

    .. code-block:: bash

        salt '*' monit.configtest
    '''
    ret = {}
    cmd = 'monit -t'
    out = __salt__['cmd.run_all'](cmd)

    if out['retcode'] != 0:
        ret['comment'] = 'Syntax Error'
        ret['stderr'] = out['stderr']
        ret['result'] = False
        return ret

    ret['comment'] = 'Syntax OK'
    ret['stdout'] = out['stdout']
    ret['result'] = True
    return ret


def version():
    '''
    .. versionadded:: 2016.3.0

    Return version from monit -V

    CLI Example:

    .. code-block:: bash

        salt '*' monit.version
    '''
    cmd = 'monit -V'
    out = __salt__['cmd.run'](cmd).splitlines()
    ret = out[0].split()
    return ret[-1]


def id_(reset=False):
    '''
    .. versionadded:: 2016.3.0

    Return monit unique id.

    reset : False
        Reset current id and generate a new id when it's True.

    CLI Example:

    .. code-block:: bash

        salt '*' monit.id [reset=True]
    '''
    if reset:
        id_pattern = re.compile(r'Monit id (?P<id>[^ ]+)')
        cmd = 'echo y|monit -r'
        out = __salt__['cmd.run_all'](cmd, python_shell=True)
        ret = id_pattern.search(out['stdout']).group('id')
        return ret if ret else False
    else:
        cmd = 'monit -i'
        out = __salt__['cmd.run'](cmd)
        ret = out.split(':')[-1].strip()
    return ret


def validate():
    '''
    .. versionadded:: 2016.3.0

    Check all services

    CLI Example:

    .. code-block:: bash

        salt '*' monit.validate
    '''
    cmd = 'monit validate'
    return not __salt__['cmd.retcode'](cmd, python_shell=False)
