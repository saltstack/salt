'''
Provide the service module for supervisord
'''

# Import salt libs
from salt import exceptions, utils


def __virtual__():
    '''
    Check for supervisor.
    '''
    try:
        utils.check_or_die('supervisorctl')
    except exceptions.CommandNotFoundError:
        return False

    return 'supervisord'


def _ctl_cmd(cmd, name):
    return 'supervisorctl {cmd} {name}'.format(
        cmd=cmd, name=(name or ''))


def _get_return(ret):
    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        return ''


def start(name='all', user=None):
    '''
    Start the named service

    CLI Example::
        salt '*' supervisord.start <service>
    '''
    ret = __salt__['cmd.run_all'](_ctl_cmd('start', name), runas=user)
    return _get_return(ret)


def restart(name='all', user=None):
    '''
    Restart the named service.

    CLI Example::
        salt '*' supervisord.restart <service>
    '''
    ret = __salt__['cmd.run_all'](_ctl_cmd('restart', name), runas=user)
    return _get_return(ret)


def stop(name='all', user=None):
    '''
    Stop the named service.

    CLI Example::
        salt '*' supervisord.stop <service>
    '''
    ret = __salt__['cmd.run_all'](_ctl_cmd('stop', name), runas=user)
    return _get_return(ret)

def add(name, user=None):
    '''
    Activates any updates in config for process/group

    CLI Example::
        salt '*' supervisord.add <name>
    '''
    ret = __salt__['cmd.run_all'](_ctl_cmd('add', name), runas=user)
    return _get_return(ret)

def remove(name, user=None):
    '''
    Removes process/group from active config

    CLI Example::
        salt '*' supervisord.remove <name>
    '''
    ret = __salt__['cmd.run_all'](_ctl_cmd('remove', name), runas=user)
    return _get_return(ret)

def reread(user=None):
    '''
    Reload the daemon's configuration files

    CLI Example::
        salt '*' supervisord.reread
    '''
    ret = __salt__['cmd.run_all'](_ctl_cmd('reread', None), runas=user)
    return _get_return(ret)

def update(user=None):
    '''
    Reload config and add/remove as necessary

    CLI Example::
        salt '*' supervisord.update
    '''
    ret = __salt__['cmd.run_all'](_ctl_cmd('update', None), runas=user)
    return _get_return(ret)

def status(name=None, user=None):
    '''
    List programs and its state

    CLI Example::
        salt '*' supervisord.status
    '''
    all_process = {}
    for line in status_raw(name, user).splitlines():
        if len(line.split()) > 2:
            process, state, reason = line.split(None, 2)
        else:
            process, state, reason = line.split() + ['']
        all_process[process] = {'state': state, 'reason': reason}
    return all_process

def status_raw(name=None, user=None):
    '''
    Display the raw output of status

    CLI Example::

        salt '*' supervisord.status_raw
    '''
    ret = __salt__['cmd.run_all'](_ctl_cmd('status', name), runas=user)
    return _get_return(ret)

def custom(command, user=None):
    '''
    Run any custom supervisord command

    CLI Example::
        salt '*' supervisord.custom "mstop '*gunicorn*'"
    '''
    ret = __salt__['cmd.run_all'](_ctl_cmd(command, None), runas=user)
    return _get_return(ret)
