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


def status(name=None, user=None):
    ret = __salt__['cmd.run_all'](_ctl_cmd('status', name), runas=user)
    return _get_return(ret)
