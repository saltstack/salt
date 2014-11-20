# -*- coding: utf-8 -*-
'''
Module for managing timezone on POSIX-like systems.
'''
from __future__ import absolute_import

# Import python libs
import os
import logging
import re

# Import salt libs
import salt.utils
from salt.exceptions import SaltInvocationError, CommandExecutionError

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    if salt.utils.is_windows():
        return False
    return True


def get_zone():
    '''
    Get current timezone (i.e. America/Denver)

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_zone
    '''
    cmd = ''
    if salt.utils.which('timedatectl'):
        out = __salt__['cmd.run']('timedatectl')
        for line in (x.strip() for x in out.splitlines()):
            try:
                return re.match(r'Time ?zone:\s+(\S+)', line).group(1)
            except AttributeError:
                pass
        raise CommandExecutionError(
            'Failed to parse timedatectl output, this is likely a bug'
        )
    elif 'RedHat' in __grains__['os_family']:
        cmd = 'grep ZONE /etc/sysconfig/clock | grep -vE "^#"'
    elif 'Suse' in __grains__['os_family']:
        cmd = 'grep ZONE /etc/sysconfig/clock | grep -vE "^#"'
    elif 'Debian' in __grains__['os_family']:
        with salt.utils.fopen('/etc/timezone', 'r') as ofh:
            return ofh.read().strip()
    elif 'Gentoo' in __grains__['os_family']:
        with salt.utils.fopen('/etc/timezone', 'r') as ofh:
            return ofh.read().strip()
    elif __grains__['os_family'] in ('FreeBSD', 'OpenBSD', 'NetBSD'):
        return os.readlink('/etc/localtime').lstrip('/usr/share/zoneinfo/')
    elif 'Solaris' in __grains__['os_family']:
        cmd = 'grep "TZ=" /etc/TIMEZONE'
    out = __salt__['cmd.run'](cmd, python_shell=True).split('=')
    ret = out[1].replace('"', '')
    return ret


def get_zonecode():
    '''
    Get current timezone (i.e. PST, MDT, etc)

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_zonecode
    '''
    cmd = 'date +%Z'
    out = __salt__['cmd.run'](cmd)
    return out


def get_offset():
    '''
    Get current numeric timezone offset from UCT (i.e. -0700)

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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
        __salt__['file.sed'](
            '/etc/default/init', '^TZ=.*', 'TZ={0}'.format(timezone))
    else:
        os.symlink(zonepath, '/etc/localtime')

    if 'RedHat' in __grains__['os_family']:
        __salt__['file.sed'](
            '/etc/sysconfig/clock', '^ZONE=.*', 'ZONE="{0}"'.format(timezone))
    elif 'Suse' in __grains__['os_family']:
        __salt__['file.sed'](
            '/etc/sysconfig/clock', '^ZONE=.*', 'ZONE="{0}"'.format(timezone))
    elif 'Debian' in __grains__['os_family']:
        with salt.utils.fopen('/etc/timezone', 'w') as ofh:
            ofh.write(timezone.strip())
            ofh.write('\n')
    elif 'Gentoo' in __grains__['os_family']:
        with salt.utils.fopen('/etc/timezone', 'w') as ofh:
            ofh.write(timezone)

    return True


def zone_compare(timezone):
    '''
    Checks the hash sum between the given timezone, and the one set in
    /etc/localtime. Returns True if they match, and False if not. Mostly useful
    for running state checks.

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.zone_compare 'America/Denver'
    '''
    if 'Solaris' in __grains__['os_family']:
        return 'Not implemented for Solaris family'

    tzfile = '/etc/localtime'
    zonepath = '/usr/share/zoneinfo/{0}'.format(timezone)

    if not os.path.exists(tzfile):
        return 'Error: {0} does not exist.'.format(tzfile)

    hash_type = __opts__.get('hash_type', 'md5')

    try:
        usrzone = salt.utils.get_hash(zonepath, hash_type)
    except IOError as exc:
        raise SaltInvocationError('Invalid timezone {0!r}'.format(timezone))

    try:
        etczone = salt.utils.get_hash(tzfile, hash_type)
    except IOError as exc:
        raise CommandExecutionError(
            'Problem reading timezone file {0}: {1}'
            .format(tzfile, exc.strerror)
        )

    if usrzone == etczone:
        return True
    return False


def get_hwclock():
    '''
    Get current hardware clock setting (UTC or localtime)

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_hwclock
    '''
    cmd = ''
    if salt.utils.which('timedatectl'):
        out = __salt__['cmd.run']('timedatectl')
        for line in (x.strip() for x in out.splitlines()):
            if 'rtc in local tz' in line.lower():
                try:
                    if line.split(':')[-1].strip().lower() == 'yes':
                        return 'localtime'
                    else:
                        return 'UTC'
                except IndexError:
                    pass
        raise CommandExecutionError(
            'Failed to parse timedatectl output, this is likely a bug'
        )
    elif 'RedHat' in __grains__['os_family']:
        cmd = 'tail -n 1 /etc/adjtime'
        return __salt__['cmd.run'](cmd)
    elif 'Suse' in __grains__['os_family']:
        cmd = 'tail -n 1 /etc/adjtime'
        return __salt__['cmd.run'](cmd)
    elif 'Debian' in __grains__['os_family']:
        #Original way to look up hwclock on Debian-based systems
        cmd = 'grep "UTC=" /etc/default/rcS | grep -vE "^#"'
        out = __salt__['cmd.run'](
                cmd, ignore_retcode=True, python_shell=True).split('=')
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
        out = __salt__['cmd.run'](cmd, python_shell=True).split('=')
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

    CLI Example:

    .. code-block:: bash

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
        if clock == 'localtime':
            cmd = 'timezonectl set-local-rtc true'
            __salt__['cmd.run'](cmd)
        else:
            cmd = 'timezonectl set-local-rtc false'
            __salt__['cmd.run'](cmd)
    elif 'RedHat' in __grains__['os_family']:
        __salt__['file.sed'](
            '/etc/sysconfig/clock', '^ZONE=.*', 'ZONE="{0}"'.format(timezone))
    elif 'Suse' in __grains__['os_family']:
        __salt__['file.sed'](
            '/etc/sysconfig/clock', '^ZONE=.*', 'ZONE="{0}"'.format(timezone))
    elif 'Debian' in __grains__['os_family']:
        if clock == 'UTC':
            __salt__['file.sed']('/etc/default/rcS', '^UTC=.*', 'UTC=yes')
        elif clock == 'localtime':
            __salt__['file.sed']('/etc/default/rcS', '^UTC=.*', 'UTC=no')
    elif 'Gentoo' in __grains__['os_family']:
        __salt__['file.sed'](
            '/etc/conf.d/hwclock', '^clock=.*', 'clock="{0}"'.format(clock))

    return True
