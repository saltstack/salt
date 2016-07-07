# -*- coding: utf-8 -*-
'''
Module for managing timezone on POSIX-like systems.
'''
from __future__ import absolute_import

# Import python libs
import os
import errno
import logging
import re
import string

# Import salt libs
import salt.utils
import salt.utils.itertools
from salt.exceptions import SaltInvocationError, CommandExecutionError

log = logging.getLogger(__name__)

__virtualname__ = 'timezone'


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    if salt.utils.is_windows():
        return (False, 'The timezone execution module failed to load: '
                       'win_timezone.py should replace this module on Windows.'
                       'There was a problem loading win_timezone.py.')

    if salt.utils.is_darwin():
        return (False, 'The timezone execution module failed to load: '
                       'mac_timezone.py should replace this module on OS X.'
                       'There was a problem loading mac_timezone.py.')

    return __virtualname__


def _timedatectl():
    '''
    get the output of timedatectl
    '''
    ret = __salt__['cmd.run_all'](['timedatectl'], python_shell=False)

    if ret['retcode'] != 0:
        msg = 'timedatectl failed: {0}'.format(ret['stderr'])
        raise CommandExecutionError(msg)

    return ret


def _get_zone_solaris():
    tzfile = '/etc/TIMEZONE'
    with salt.utils.fopen(tzfile, 'r') as fp_:
        for line in fp_:
            if 'TZ=' in line:
                zonepart = line.rstrip('\n').split('=')[-1]
                return zonepart.strip('\'"') or 'UTC'
    raise CommandExecutionError('Unable to get timezone from ' + tzfile)


def _get_zone_sysconfig():
    tzfile = '/etc/sysconfig/clock'
    with salt.utils.fopen(tzfile, 'r') as fp_:
        for line in fp_:
            if re.match(r'^\s*#', line):
                continue
            if 'ZONE' in line and '=' in line:
                zonepart = line.rstrip('\n').split('=')[-1]
                return zonepart.strip('\'"') or 'UTC'
    raise CommandExecutionError('Unable to get timezone from ' + tzfile)


def _get_zone_etc_localtime():
    tzfile = '/etc/localtime'
    tzdir = '/usr/share/zoneinfo/'
    tzdir_len = len(tzdir)
    try:
        olson_name = os.path.normpath(
            os.path.join('/etc', os.readlink(tzfile))
        )
        if olson_name.startswith(tzdir):
            return olson_name[tzdir_len:]
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            raise CommandExecutionError(tzfile + ' does not exist')
        elif exc.errno == errno.EINVAL:
            log.warning(
                tzfile + ' is not a symbolic link, attempting to match ' +
                tzfile + ' to zoneinfo files'
            )
            # Regular file. Try to match the hash.
            hash_type = __opts__.get('hash_type', 'md5')
            tzfile_hash = salt.utils.get_hash(tzfile, hash_type)
            # Not a link, just a copy of the tzdata file
            for root, dirs, files in os.walk(tzdir):
                for filename in files:
                    full_path = os.path.join(root, filename)
                    olson_name = full_path[tzdir_len:]
                    if olson_name[0] in string.ascii_lowercase:
                        continue
                    if tzfile_hash == \
                            salt.utils.get_hash(full_path, hash_type):
                        return olson_name
    raise CommandExecutionError('Unable to determine timezone')


def _get_zone_etc_timezone():
    with salt.utils.fopen('/etc/timezone', 'r') as fp_:
        return fp_.read().strip()


def get_zone():
    '''
    Get current timezone (i.e. America/Denver)

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_zone
    '''
    if salt.utils.which('timedatectl'):
        ret = _timedatectl()

        for line in (x.strip() for x in salt.utils.itertools.split(ret['stdout'], '\n')):
            try:
                return re.match(r'Time ?zone:\s+(\S+)', line).group(1)
            except AttributeError:
                pass

        msg = ('Failed to parse timedatectl output: {0}\n'
               'Please file an issue with SaltStack').format(ret['stdout'])
        raise CommandExecutionError(msg)

    else:
        if __grains__['os'].lower() == 'centos':
            return _get_zone_etc_localtime()
        os_family = __grains__['os_family']
        for family in ('RedHat', 'SUSE'):
            if family in os_family:
                return _get_zone_sysconfig()
        for family in ('Debian', 'Gentoo'):
            if family in os_family:
                return _get_zone_etc_timezone()
        if os_family in ('FreeBSD', 'OpenBSD', 'NetBSD'):
            return _get_zone_etc_localtime()
        elif 'Solaris' in os_family:
            return _get_zone_solaris()
    raise CommandExecutionError('Unable to get timezone')


def get_zonecode():
    '''
    Get current timezone (i.e. PST, MDT, etc)

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_zonecode
    '''
    return __salt__['cmd.run'](['date', '+%Z'], python_shell=False)


def get_offset():
    '''
    Get current numeric timezone offset from UCT (i.e. -0700)

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_offset
    '''
    return __salt__['cmd.run'](['date', '+%z'], python_shell=False)


def set_zone(timezone):
    '''
    Unlinks, then symlinks /etc/localtime to the set timezone.

    The timezone is crucial to several system processes, each of which SHOULD
    be restarted (for instance, whatever you system uses as its cron and
    syslog daemons). This will not be automagically done and must be done
    manually!

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.set_zone 'America/Denver'
    '''
    if salt.utils.which('timedatectl'):
        try:
            __salt__['cmd.run']('timedatectl set-timezone {0}'.format(timezone))
        except CommandExecutionError:
            pass

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
    elif 'SUSE' in __grains__['os_family']:
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
    Compares the given timezone name with the system timezone name.
    Checks the hash sum between the given timezone, and the one set in
    /etc/localtime. Returns True if names and hash sums match, and False if not.
    Mostly useful for running state checks.

    .. versionchanged:: 2016.3.0

    .. note::

        On Solaris-link operating systems only a string comparison is done.

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.zone_compare 'America/Denver'
    '''
    if 'Solaris' in __grains__['os_family']:
        return timezone == get_zone()

    curtzstring = get_zone()
    if curtzstring != timezone:
        return False

    tzfile = '/etc/localtime'
    zonepath = '/usr/share/zoneinfo/{0}'.format(timezone)

    if not os.path.exists(tzfile):
        return 'Error: {0} does not exist.'.format(tzfile)

    hash_type = __opts__.get('hash_type', 'md5')

    try:
        usrzone = salt.utils.get_hash(zonepath, hash_type)
    except IOError as exc:
        raise SaltInvocationError('Invalid timezone \'{0}\''.format(timezone))

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
    if salt.utils.which('timedatectl'):
        ret = _timedatectl()
        for line in (x.strip() for x in ret['stdout'].splitlines()):
            if 'rtc in local tz' in line.lower():
                try:
                    if line.split(':')[-1].strip().lower() == 'yes':
                        return 'localtime'
                    else:
                        return 'UTC'
                except IndexError:
                    pass

        msg = ('Failed to parse timedatectl output: {0}\n'
               'Please file an issue with SaltStack').format(ret['stdout'])
        raise CommandExecutionError(msg)

    else:
        os_family = __grains__['os_family']
        for family in ('RedHat', 'SUSE'):
            if family in os_family:
                cmd = ['tail', '-n', '1', '/etc/adjtime']
                return __salt__['cmd.run'](cmd, python_shell=False)

        if 'Debian' in __grains__['os_family']:
            # Original way to look up hwclock on Debian-based systems
            try:
                with salt.utils.fopen('/etc/default/rcS', 'r') as fp_:
                    for line in fp_:
                        if re.match(r'^\s*#', line):
                            continue
                        if 'UTC=' in line:
                            is_utc = line.rstrip('\n').split('=')[-1].lower()
                            if is_utc == 'yes':
                                return 'UTC'
                            else:
                                return 'localtime'
            except IOError as exc:
                pass
            # Since Wheezy
            cmd = ['tail', '-n', '1', '/etc/adjtime']
            return __salt__['cmd.run'](cmd, python_shell=False)

        if 'Gentoo' in __grains__['os_family']:
            if not os.path.exists('/etc/adjtime'):
                offset_file = '/etc/conf.d/hwclock'
                try:
                    with salt.utils.fopen(offset_file, 'r') as fp_:
                        for line in fp_:
                            if line.startswith('clock='):
                                line = line.rstrip('\n')
                                line = line.split('=')[-1].strip('\'"')
                                if line == 'UTC':
                                    return line
                                if line == 'local':
                                    return 'LOCAL'
                        raise CommandExecutionError(
                            'Correct offset value not found in {0}'
                            .format(offset_file)
                        )
                except IOError as exc:
                    raise CommandExecutionError(
                        'Problem reading offset file {0}: {1}'
                        .format(offset_file, exc.strerror)
                    )
            cmd = ['tail', '-n', '1', '/etc/adjtime']
            return __salt__['cmd.run'](cmd, python_shell=False)

        if 'Solaris' in __grains__['os_family']:
            offset_file = '/etc/rtc_config'
            try:
                with salt.utils.fopen(offset_file, 'r') as fp_:
                    for line in fp_:
                        if line.startswith('zone_info=GMT'):
                            return 'UTC'
                    return 'localtime'
            except IOError as exc:
                if exc.errno == errno.ENOENT:
                    # offset file does not exist
                    return 'UTC'
                raise CommandExecutionError(
                    'Problem reading offset file {0}: {1}'
                    .format(offset_file, exc.strerror)
                )


def set_hwclock(clock):
    '''
    Sets the hardware clock to be either UTC or localtime

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.set_hwclock UTC
    '''
    timezone = get_zone()

    if 'Solaris' in __grains__['os_family']:
        if clock.lower() not in ('localtime', 'utc'):
            raise SaltInvocationError(
                'localtime and UTC are the only permitted values'
            )
        if 'sparc' in __grains__['cpuarch']:
            raise SaltInvocationError(
                'UTC is the only choice for SPARC architecture'
            )
        cmd = ['rtc', '-z', 'GMT' if clock.lower() == 'utc' else timezone]
        return __salt__['cmd.retcode'](cmd, python_shell=False) == 0

    zonepath = '/usr/share/zoneinfo/{0}'.format(timezone)

    if not os.path.exists(zonepath):
        raise CommandExecutionError(
            'Zone \'{0}\' does not exist'.format(zonepath)
        )

    os.unlink('/etc/localtime')
    os.symlink(zonepath, '/etc/localtime')

    if 'Arch' in __grains__['os_family']:
        cmd = ['timezonectl', 'set-local-rtc',
               'true' if clock == 'localtime' else 'false']
        return __salt__['cmd.retcode'](cmd, python_shell=False) == 0
    elif 'RedHat' in __grains__['os_family']:
        __salt__['file.sed'](
            '/etc/sysconfig/clock', '^ZONE=.*', 'ZONE="{0}"'.format(timezone))
    elif 'SUSE' in __grains__['os_family']:
        __salt__['file.sed'](
            '/etc/sysconfig/clock', '^ZONE=.*', 'ZONE="{0}"'.format(timezone))
    elif 'Debian' in __grains__['os_family']:
        if clock == 'UTC':
            __salt__['file.sed']('/etc/default/rcS', '^UTC=.*', 'UTC=yes')
        elif clock == 'localtime':
            __salt__['file.sed']('/etc/default/rcS', '^UTC=.*', 'UTC=no')
    elif 'Gentoo' in __grains__['os_family']:
        if clock not in ('UTC', 'localtime'):
            raise SaltInvocationError(
                'Only \'UTC\' and \'localtime\' are allowed'
            )
        if clock == 'localtime':
            clock = 'local'
        __salt__['file.sed'](
            '/etc/conf.d/hwclock', '^clock=.*', 'clock="{0}"'.format(clock))

    return True
