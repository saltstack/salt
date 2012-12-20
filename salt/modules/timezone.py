'''
Module for managing timezone on posix-like systems.
'''

# Import python libs
import os
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on posix-like systems
    '''
    # Disable on these platorms, specific service modules exist:
    disable = [
        'Windows',
        ]
    if __grains__['os'] in disable:
        return False
    return 'timezone'


def get_zone():
    '''
    Get current timezone (i.e. America/Denver)

    CLI Example::

        salt '*' timezone.get_zone
    '''
    cmd = ''
    if 'Arch' in __grains__['os_family']:
        cmd = 'grep TIMEZONE /etc/rc.conf | grep -vE "^#"'
    elif 'RedHat' in __grains__['os_family']:
        cmd = 'grep ZONE /etc/sysconfig/clock | grep -vE "^#"'
    elif 'Debian' in __grains__['os_family']:
        return open('/etc/timezone','r').read()
    out = __salt__['cmd.run'](cmd).split('=')
    ret = out[1].replace('"', '')
    return ret


def get_zonecode():
    '''
    Get current timezone (i.e. PST, MDT, etc)

    CLI Example::

        salt '*' timezone.get_zonecode
    '''
    cmd = 'date +%Z'
    out = __salt__['cmd.run'](cmd)
    return out


def get_offset():
    '''
    Get current numeric timezone offset from UCT (i.e. -0700)

    CLI Example::

        salt '*' timezone.get_offset
    '''
    cmd = 'date +%z'
    out = __salt__['cmd.run'](cmd)
    return out


def set_zone(timezone):
    '''
    Unlinks, then symlinks /etc/localtime to the set timezone

    CLI Example::

        salt '*' timezone.set_zone 'America/Denver'
    '''
    zonepath = '/usr/share/zoneinfo/{0}'.format(timezone)
    if not os.path.exists(zonepath):
        return 'Zone does not exist: {0}'.format(zonepath)

    os.unlink('/etc/localtime')
    os.symlink(zonepath, '/etc/localtime')

    if 'Arch' in __grains__['os_family']:
        __salt__['file.sed']('/etc/rc.conf', '^TIMEZONE=.*', 'TIMEZONE="{0}"'.format(timezone))
    elif 'RedHat' in __grains__['os_family']:
        __salt__['file.sed']('/etc/sysconfig/clock', '^ZONE=.*', 'ZONE="{0}"'.format(timezone))
    elif 'Debian' in __grains__['os_family']:
        open('/etc/timezone', 'w').write(timezone)

    return True


def get_hwclock():
    '''
    Get current hardware clock setting (UTC or localtime)

    CLI Example::

        salt '*' timezone.get_hwclock
    '''
    cmd = ''
    if 'Arch' in __grains__['os_family']:
        cmd = 'grep HARDWARECLOCK /etc/rc.conf | grep -vE "^#"'
        out = __salt__['cmd.run'](cmd).split('=')
        return out[1].replace('"', '')
    elif 'RedHat' in __grains__['os_family']:
        cmd = 'tail -n 1 /etc/adjtime'
        return __salt__['cmd.run'](cmd)
    elif 'Debian' in __grains__['os_family']:
        cmd = 'grep "UTC=" /etc/default/rcS | grep -vE "^#"'
        out = __salt__['cmd.run'](cmd).split('=')
        if out[1] == 'yes':
            return 'UTC'
        else:
            return 'localtime'


def set_hwclock(clock):
    '''
    Sets the hardware clock to be either UTC or localtime

    CLI Example::

        salt '*' timezone.set_hwclock UTC
    '''
    zonepath = '/usr/share/zoneinfo/{0}'.format(timezone)
    if not os.path.exists(zonepath):
        return 'Zone does not exist: {0}'.format(zonepath)

    os.unlink('/etc/localtime')
    os.symlink(zonepath, '/etc/localtime')

    if 'Arch' in __grains__['os_family']:
        __salt__['file.sed']('/etc/rc.conf', '^HARDWARECLOCK=.*', 'HARDWARECLOCK="{0}"'.format(timezone))
    elif 'RedHat' in __grains__['os_family']:
        __salt__['file.sed']('/etc/sysconfig/clock', '^ZONE=.*', 'ZONE="{0}"'.format(timezone))
    elif 'Debian' in __grains__['os_family']:
        if clock == 'UTC':
            __salt__['file.sed']('/etc/default/rcS', '^UTC=.*', 'UTC=yes')
        elif clock == 'localtime':
            __salt__['file.sed']('/etc/default/rcS', '^UTC=.*', 'UTC=no')

    return True

