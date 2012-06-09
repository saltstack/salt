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
    cmd = 'service jail onerestart {0}'.format(jail)
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


def show_config(jail):
    '''
    Display specified jail's configuration

    CLI Example::

        salt '*' jail.show_config <jail name>
    '''
    ret = {}
    for rconf in ('/etc/rc.conf', '/etc/rc.conf.local'):
        if os.path.isfile(rconf):
            for line in open(rconf, 'r').readlines():
                if not line.strip():
                    continue
                if not line.startswith('jail_{0}_'.format(jail)):
                    continue
                k, v = line.split('=')
                ret[k.split('_',2)[2]] = v.split('"')[1]
    return ret


def fstab(jail):
    '''
    Display contents of a fstab(5) file defined in specified
    jail's configuration. If no file defined return False.

    CLI Example::

        salt '*' jail.fstab <jail name>
    '''
    ret = []
    config = __salt__['jail.show_config'](jail)
    if 'fstab' in config:
        fstab = config['fstab']
        if os.path.isfile(fstab):
            for line in open(fstab, 'r').readlines():
                if not line.strip():
                    continue
                if line.strip().startswith('#'):
                    continue
                dv, m, f, o, dm, p = line.split()
                ret.append({
                    'device': dv, 'mountpoint': m,
                    'fstype': f,  'options': o,
                    'dump': dm,   'pass': p
                    })
        else:
            ret = False
    else:
        ret = False
    return ret


def status(jail):
    '''
    See if specified jail is currently running

    CLI Example::

        salt '*' jail.status <jail name>
    '''
    cmd='jls | grep {0}'.format(jail)
    return not __salt__['cmd.retcode'](cmd)


def sysctl():
    '''
    Dump all jail related kernel states (sysctl)
    '''
    ret = {}
    sysctl=__salt__['cmd.run']('sysctl security.jail')
    for s in sysctl.split('\n'):
        k, v = s.split(':')
        ret[k.strip()] = v.strip()
    return ret
