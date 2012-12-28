'''
The jail module for FreeBSD
'''

# Import python libs
import os

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only runs on FreeBSD systems
    '''
    return 'jail' if __grains__['os'] == 'FreeBSD' else False


# TODO: This docstring needs updating to make sense
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
    cmd = 'service -e | grep jail'
    return not __salt__['cmd.retcode'](cmd)


def get_enabled():
    '''
    Return which jails are set to be run
    '''
    ret = []
    for rconf in ('/etc/rc.conf', '/etc/rc.conf.local'):
        if os.access(rconf, os.R_OK):
            with salt.utils.fopen(rconf, 'r') as _fp:
                for line in _fp:
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
        if os.access(rconf, os.R_OK):
            with salt.utils.fopen(rconf, 'r') as _fp:
                for line in _fp:
                    if not line.strip():
                        continue
                    if not line.startswith('jail_{0}_'.format(jail)):
                        continue
                    key, value = line.split('=')
                    ret[key.split('_', 2)[2]] = value.split('"')[1]
    return ret


def fstab(jail):
    '''
    Display contents of a fstab(5) file defined in specified
    jail's configuration. If no file is defined, return False.

    CLI Example::

        salt '*' jail.fstab <jail name>
    '''
    ret = []
    config = show_config(jail)
    if 'fstab' in config:
        c_fstab = config['fstab']
        if os.access(c_fstab, os.R_OK):
            with salt.utils.fopen(c_fstab, 'r') as _fp:
                for line in _fp:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith('#'):
                        continue
                    try:
                        device, mpoint, fstype, opts, dump, pas_ = line.split()
                    except ValueError:
                        # Gracefully continue on invalid lines
                        continue
                    ret.append({
                        'device': device,
                        'mountpoint': mpoint,
                        'fstype': fstype,
                        'options': opts,
                        'dump': dump,
                        'pass': pas_
                        })
    if not ret:
        ret = False
    return ret


def status(jail):
    '''
    See if specified jail is currently running

    CLI Example::

        salt '*' jail.status <jail name>
    '''
    cmd = 'jls | grep {0}'.format(jail)
    return not __salt__['cmd.retcode'](cmd)


def sysctl():
    '''
    Dump all jail related kernel states (sysctl)
    '''
    ret = {}
    sysctl_jail = __salt__['cmd.run']('sysctl security.jail')
    for line in sysctl_jail.splitlines():
        key, value = line.split(':', 1)
        ret[key.strip()] = value.strip()
    return ret
