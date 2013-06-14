'''
Module for managing timezone on POSIX-like systems.
'''

# Import python libs
import os
import hashlib
import salt.utils
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    if salt.utils.is_windows():
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
        cmd = ('timedatectl | grep Timezone |'
               'sed -e"s/: /=/" -e"s/^[ \t]*//" | cut -d" " -f1')
    elif 'RedHat' in __grains__['os_family']:
        cmd = 'grep ZONE /etc/sysconfig/clock | grep -vE "^#"'
    elif 'Suse' in __grains__['os_family']:
        cmd = 'grep ZONE /etc/sysconfig/clock | grep -vE "^#"'
    elif 'Debian' in __grains__['os_family']:
        return open('/etc/timezone', 'r').read()
    elif 'Gentoo' in __grains__['os_family']:
        return open('/etc/timezone', 'r').read()
    elif 'FreeBSD' in __grains__['os_family']:
        return ('FreeBSD does not store a human-readable timezone. Please'
                'consider using timezone.get_zonecode or timezone.zonecompare')
    elif 'Solaris' in __grains__['os_family']:
        cmd = 'grep "TZ=" /etc/TIMEZONE'
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
    Unlinks, then symlinks /etc/localtime to the set timezone.

    The timezone is crucial to several system processes, each of which SHOULD
    be restarted (for instance, whatever you system uses as its cron and
    syslog daemons). This will not be magically done for you!

    CLI Example::

        salt '*' timezone.set_zone 'America/Denver'
    '''
    if 'Solaris' in __grains__['os_family']:
        zonepath = '/usr/share/lib/zoneinfo/{0}'.format(timezone)
    else:
        zonepath = '/usr/share/zoneinfo/{0}'.format(timezone)
    if not os.path.exists(zonepath):
        return 'Zone does not exist: {0}'.format(zonepath)

    if os.path.exists('/etc/localtime'):
        os.unlink('/etc/localtime')

    if 'Solaris' in __grains__['os_family']:
        __salt__['file.sed']('/etc/default/init', '^TZ=.*', 'TZ={0}'.format(timezone))
    else:
        os.symlink(zonepath, '/etc/localtime')

    if 'Arch' in __grains__['os_family']:
        __salt__['file.sed']('/etc/rc.conf', '^TIMEZONE=.*', 'TIMEZONE="{0}"'.format(timezone))
    elif 'RedHat' in __grains__['os_family']:
        __salt__['file.sed']('/etc/sysconfig/clock', '^ZONE=.*', 'ZONE="{0}"'.format(timezone))
    elif 'Suse' in __grains__['os_family']:
        __salt__['file.sed']('/etc/sysconfig/clock', '^ZONE=.*', 'ZONE="{0}"'.format(timezone))
    elif 'Debian' in __grains__['os_family']:
        open('/etc/timezone', 'w').write(timezone)
    elif 'Gentoo' in __grains__['os_family']:
        open('/etc/timezone', 'w').write(timezone)

    return True


def zone_compare(timezone):
    '''
    Checks the md5sum between the given timezone, and the one set in
    /etc/localtime. Returns True if they match, and False if not. Mostly useful
    for running state checks.

    Example::

        salt '*' timezone.zone_compare 'America/Denver'
    '''
    if 'Solaris' in __grains__['os_family']:
        return 'Not implemented for Solaris family'

    tzfile = '/etc/localtime'
    zonepath = '/usr/share/zoneinfo/{0}'.format(timezone)

    if not os.path.exists(tzfile):
        return 'Error: {0} does not exist.'.format(tzfile)

    with salt.utils.fopen(zonepath, 'r') as fp_:
        usrzone = hashlib.md5(fp_.read()).hexdigest()

    with salt.utils.fopen(tzfile, 'r') as fp_:
        etczone = hashlib.md5(fp_.read()).hexdigest()

    if usrzone == etczone:
        return True
    return False


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
    elif 'Suse' in __grains__['os_family']:
        cmd = 'tail -n 1 /etc/adjtime'
        return __salt__['cmd.run'](cmd)
    elif 'Debian' in __grains__['os_family']:
        #Original way to look up hwclock on Debian-based systems
        cmd = 'grep "UTC=" /etc/default/rcS | grep -vE "^#"'
        out = __salt__['cmd.run'](cmd).split('=')
        if len(out) > 1:
            if out[1] == 'yes':
                return 'UTC'
            else:
                return 'localtime'
        else:
            #Since Wheezy
            cmd = 'tail -n 1 /etc/adjtime'
            return __salt__['cmd.run'](cmd)
    elif 'Gentoo' in __grains__['os_family']:
        cmd = 'grep "^clock=" /etc/conf.d/hwclock | grep -vE "^#"'
        out = __salt__['cmd.run'](cmd).split('=')
        return out[1].replace('"', '')
    elif 'Solaris' in __grains__['os_family']:
        if os.path.isfile('/etc/rtc_config'):
            with salt.utils.fopen('/etc/rtc_config', 'r') as fp_:
                for line in fp_:
                    if line.startswith('zone_info=GMT'):
                        return 'UTC'
            return 'localtime'
        else:
            return 'UTC'


def set_hwclock(clock):
    '''
    Sets the hardware clock to be either UTC or localtime

    CLI Example::

        salt '*' timezone.set_hwclock UTC
    '''
    timezone = get_zone()

    if 'Solaris' in __grains__['os_family']:
        if 'sparc' in __grains__['cpuarch']:
            return 'UTC is the only choice for SPARC architecture'
        if clock == 'localtime':
            cmd = 'rtc -z {0}'.format(timezone)
            __salt__['cmd.run'](cmd)
            return True
        elif clock == 'UTC':
            cmd = 'rtc -z GMT'
            __salt__['cmd.run'](cmd)
            return True
    else:
        zonepath = '/usr/share/zoneinfo/{0}'.format(timezone)

    if not os.path.exists(zonepath):
        return 'Zone does not exist: {0}'.format(zonepath)

    if 'Solaris' not in __grains__['os_family']:
        os.unlink('/etc/localtime')
        os.symlink(zonepath, '/etc/localtime')

    if 'Arch' in __grains__['os_family']:
        __salt__['file.sed']('/etc/rc.conf', '^HARDWARECLOCK=.*', 'HARDWARECLOCK="{0}"'.format(clock))
    elif 'RedHat' in __grains__['os_family']:
        __salt__['file.sed']('/etc/sysconfig/clock', '^ZONE=.*', 'ZONE="{0}"'.format(timezone))
    elif 'Suse' in __grains__['os_family']:
        __salt__['file.sed']('/etc/sysconfig/clock', '^ZONE=.*', 'ZONE="{0}"'.format(timezone))
    elif 'Debian' in __grains__['os_family']:
        if clock == 'UTC':
            __salt__['file.sed']('/etc/default/rcS', '^UTC=.*', 'UTC=yes')
        elif clock == 'localtime':
            __salt__['file.sed']('/etc/default/rcS', '^UTC=.*', 'UTC=no')
    elif 'Gentoo' in __grains__['os_family']:
        __salt__['file.sed']('/etc/conf.d/hwclock', '^clock=.*', 'clock="{0}"'.format(clock))

    return True
