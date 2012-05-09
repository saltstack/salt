'''
The jail module for FreeBSD
'''

import os


def __virtual__():
    '''
    Only runs on FreeBSD systems
    '''
    return 'jail' if __grains__['os'] == 'FreeBSD' else False


def start(jail=''):
    '''
    Start the specified jail or all, if none specified

    CLI Example::

        salt '*' jail.start [<jail name>]
    '''
    cmd = 'service jail onestart {0}'.format(jail)
    return not __salt__['cmd.retcode'](cmd)


def stop(jail=''):
    '''
    Stop the specified jail or all, if none specified

    CLI Example::

        salt '*' jail.stop [<jail name>]
    '''
    cmd = 'service jail onestop {0}'.format(jail)
    return not __salt__['cmd.retcode'](cmd)


def restart(jail=''):
    '''
    Restart the specified jail or all, if none specified

    CLI Example::

        salt '*' jail.restart [<jail name>]
    '''
    cmd = 'service jail onerestart ${0}'.format(jail)
    return not __salt__['cmd.retcode'](cmd)


def is_enabled():
    '''
    See if jail service is actually enabled on boot
    '''
    cmd='service -e | grep jail'
    return not __salt__['cmd.retcode'](cmd)


def get_enabled():
    '''
    Return which jails are set to be run
    '''
    ret = []
    for rconf in ('/etc/rc.conf', '/etc/rc.conf.local'):
        if os.path.isfile(rconf):
            for line in open(rconf, 'r').readlines():
                if not line.strip():
                    continue
		if not line.startswith('jail_list='):
                    continue
                jails = line.split('"')[1].split()
		for j in jails:
		    ret.append(j)
    return ret


