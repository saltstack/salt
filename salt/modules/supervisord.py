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
    except exceptions.CommandNotFoundError:
        return False

    return 'supervisord'


def _ctl_cmd(cmd, name):
    return 'supervisorctl {cmd} {name}'.format(
        cmd=cmd, name=name)


def start(name='all'):
    '''
    Start the named service

    CLI Example::
        salt '*' supervisord.start <service>
    '''
    return __salt__['cmd.run_all'](_ctl_cmd('start', name))


def restart(name):
    '''
    Restart the named service.

    CLI Example::
        salt '*' supervisord.restart <service>
    '''
    return not __salt__['cmd.retcode'](_ctl_cmd('restart', name))
