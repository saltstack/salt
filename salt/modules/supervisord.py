'''
Provide the service module for supervisord
'''
from salt import exceptions, utils


def __virtual__():
    '''
    Check for supervisor.
    '''
    try:
        utils.check_or_die('supervisorctl')
        return 'supervisor'
    except exceptions.CommandNotFoundError:
        return False


def _ctl_cmd(cmd, name):
    return 'supervisorctl {cmd} {name}'.format(
        cmd=cmd, name=name)

def restart(name):
    '''
    Restart the named services.

    CLI Example::
        salt '*' supervisord.restart <service1>
    '''
    return not __salt__['cmd.retcode'](_ctl_cmd('restart', name))
