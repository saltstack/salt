# -*- coding: utf-8 -*-
'''
Module for managing locales on POSIX-like systems.
'''
from __future__ import absolute_import

# Import python libs
import logging
import re
import os
HAS_DBUS = False
try:
    import dbus
    HAS_DBUS = True
except ImportError:
    pass

# Import salt libs
import salt.utils
import salt.utils.locales
import salt.ext.six as six
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'locale'


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    if HAS_DBUS is False and _uses_dbus():
        return (False, 'Cannot load locale module: dbus python module unavailable')
    if salt.utils.is_windows():
        return (False, 'Cannot load locale module: windows platforms are unsupported')

    return __virtualname__


def _uses_dbus():
    if 'Arch' in __grains__['os_family']:
        return True
    elif 'RedHat' in __grains__['os_family']:
        return False
    elif 'Debian' in __grains__['os_family']:
        return False
    elif 'Gentoo' in __grains__['os_family']:
        return False
    else:  # when unknown, assume no dbus
        return False


def _parse_dbus_locale():
    '''
    Get the 'System Locale' parameters from dbus
    '''
    ret = {}

    bus = dbus.SystemBus()
    localed = bus.get_object('org.freedesktop.locale1',
                             '/org/freedesktop/locale1')
    properties = dbus.Interface(localed, 'org.freedesktop.DBus.Properties')
    system_locale = properties.Get('org.freedesktop.locale1', 'Locale')

    try:
        key, val = re.match('^([A-Z_]+)=(.*)$', system_locale[0]).groups()
    except AttributeError:
        log.error('Odd locale parameter "{0}" detected in dbus locale '
                  'output. This should not happen. You should '
                  'probably investigate what caused this.'.format(
                      system_locale[0]))
    else:
        ret[key] = val.replace('"', '')

    return ret


def _locale_get():
    '''
    Use dbus to get the current locale
    '''
    return _parse_dbus_locale().get('LANG', '')


def _localectl_set(locale=''):
    '''
    Use systemd's localectl command to set the LANG locale parameter, making
    sure not to trample on other params that have been set.
    '''
    locale_params = _parse_dbus_locale()
    locale_params['LANG'] = str(locale)
    args = ' '.join(['{0}="{1}"'.format(k, v)
                     for k, v in six.iteritems(locale_params)])
    cmd = 'localectl set-locale {0}'.format(args)
    return __salt__['cmd.retcode'](cmd, python_shell=False) == 0


def list_avail():
    '''
    Lists available (compiled) locales

    CLI Example:

    .. code-block:: bash

        salt '*' locale.list_avail
    '''
    cmd = 'locale -a'
    out = __salt__['cmd.run'](cmd).split('\n')
    return out


def get_locale():
    '''
    Get the current system locale

    CLI Example:

    .. code-block:: bash

        salt '*' locale.get_locale
    '''
    cmd = ''
    if 'Arch' in __grains__['os_family']:
        return _locale_get()
    elif 'RedHat' in __grains__['os_family']:
        cmd = 'grep "^LANG=" /etc/sysconfig/i18n'
    elif 'Suse' in __grains__['os_family']:
        cmd = 'grep "^RC_LANG" /etc/sysconfig/language'
    elif 'Debian' in __grains__['os_family']:
        if salt.utils.which('localectl'):
            return _locale_get()
        cmd = 'grep "^LANG=" /etc/default/locale'
    elif 'Gentoo' in __grains__['os_family']:
        cmd = 'eselect --brief locale show'
        return __salt__['cmd.run'](cmd).strip()
    elif 'Solaris' in __grains__['os_family']:
        cmd = 'grep "^LANG=" /etc/default/init'
    else:  # don't wast time on a failing cmd.run
        raise CommandExecutionError(
            'Error: Unsupported platform!'
        )

    try:
        return __salt__['cmd.run'](cmd).split('=')[1].replace('"', '')
    except IndexError:
        return ''


def set_locale(locale):
    '''
    Sets the current system locale

    CLI Example:

    .. code-block:: bash

        salt '*' locale.set_locale 'en_US.UTF-8'
    '''
    if 'Arch' in __grains__['os_family']:
        return _localectl_set(locale)
    elif 'RedHat' in __grains__['os_family']:
        if not __salt__['file.file_exists']('/etc/sysconfig/i18n'):
            __salt__['file.touch']('/etc/sysconfig/i18n')
        __salt__['file.replace'](
            '/etc/sysconfig/i18n',
            '^LANG=.*',
            'LANG="{0}"'.format(locale),
            append_if_not_found=True
        )
    elif 'Suse' in __grains__['os_family']:
        if not __salt__['file.file_exists']('/etc/sysconfig/language'):
            __salt__['file.touch']('/etc/sysconfig/language')
        __salt__['file.replace'](
            '/etc/sysconfig/language',
            '^RC_LANG=.*',
            'RC_LANG="{0}"'.format(locale),
            append_if_not_found=True
        )
    elif 'Debian' in __grains__['os_family']:
        if salt.utils.which('localectl'):
            return _localectl_set(locale)

        update_locale = salt.utils.which('update-locale')
        if update_locale is None:
            raise CommandExecutionError(
                'Cannot set locale: "update-locale" was not found.')
        __salt__['cmd.run'](update_locale)  # (re)generate /etc/default/locale

        # FIXME: why are we writing to a file that is dynamically generated?
        __salt__['file.replace'](
            '/etc/default/locale',
            '^LANG=.*',
            'LANG="{0}"'.format(locale),
            append_if_not_found=True
        )
    elif 'Gentoo' in __grains__['os_family']:
        cmd = 'eselect --brief locale set {0}'.format(locale)
        return __salt__['cmd.retcode'](cmd, python_shell=False) == 0
    elif 'Solaris' in __grains__['os_family']:
        if locale not in __salt__['locale.list_avail']():
            return False
        __salt__['file.replace'](
            '/etc/default/init',
            '^LANG=.*',
            'LANG="{0}"'.format(locale),
            append_if_not_found=True
        )
    else:
        raise CommandExecutionError(
            'Error: Unsupported platform!'
        )

    return True


def avail(locale):
    '''
    Check if a locale is available.

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' locale.avail 'en_US.UTF-8'
    '''
    try:
        normalized_locale = salt.utils.locales.normalize_locale(locale)
    except IndexError:
        log.error('Unable to validate locale "{0}"'.format(locale))
        return False
    avail_locales = __salt__['locale.list_avail']()
    locale_exists = next((True for x in avail_locales
       if salt.utils.locales.normalize_locale(x.strip()) == normalized_locale), False)
    return locale_exists


def gen_locale(locale, **kwargs):
    '''
    Generate a locale. Options:

    .. versionadded:: 2014.7.0

    :param locale: Any locale listed in /usr/share/i18n/locales or
        /usr/share/i18n/SUPPORTED for Debian and Gentoo based distributions,
        which require the charmap to be specified as part of the locale
        when generating it.

    verbose
        Show extra warnings about errors that are normally ignored.

    CLI Example:

    .. code-block:: bash

        salt '*' locale.gen_locale en_US.UTF-8
        salt '*' locale.gen_locale 'en_IE.UTF-8 UTF-8'    # Debian/Gentoo only
    '''
    on_debian = __grains__.get('os') == 'Debian'
    on_ubuntu = __grains__.get('os') == 'Ubuntu'
    on_gentoo = __grains__.get('os_family') == 'Gentoo'
    on_suse = __grains__.get('os_family') == 'Suse'
    on_solaris = __grains__.get('os_family') == 'Solaris'

    if on_solaris:  # all locales are pre-generated
        return locale in __salt__['locale.list_avail']()

    locale_info = salt.utils.locales.split_locale(locale)

    # if the charmap has not been supplied, normalize by appening it
    if not locale_info['charmap'] and not on_ubuntu:
        locale_info['charmap'] = locale_info['codeset']
        locale = salt.utils.locales.join_locale(locale_info)

    if on_debian or on_gentoo:  # file-based search
        search = '/usr/share/i18n/SUPPORTED'
        valid = __salt__['file.search'](search,
                                        '^{0}$'.format(locale),
                                        flags=re.MULTILINE)
    else:  # directory-based search
        if on_suse:
            search = '/usr/share/locale'
        else:
            search = '/usr/share/i18n/locales'
        try:
            valid = "{0}_{1}".format(locale_info['language'],
                                     locale_info['territory']) in os.listdir(search)
        except OSError as ex:
            log.error(ex)
            raise CommandExecutionError(
                "Locale \"{0}\" is not available.".format(locale))

    if not valid:
        log.error(
            'The provided locale "{0}" is not found in {1}'.format(locale, search))
        return False

    if os.path.exists('/etc/locale.gen'):
        __salt__['file.replace'](
            '/etc/locale.gen',
            r'^\s*#\s*{0}\s*$'.format(locale),
            '{0}\n'.format(locale),
            append_if_not_found=True
        )
    elif on_ubuntu:
        __salt__['file.touch'](
            '/var/lib/locales/supported.d/{0}'.format(locale_info['language'])
        )
        __salt__['file.replace'](
            '/var/lib/locales/supported.d/{0}'.format(locale_info['language']),
            locale,
            locale,
            append_if_not_found=True
        )

    if salt.utils.which("locale-gen") is not None:
        cmd = ['locale-gen']
        if on_gentoo:
            cmd.append('--generate')
        cmd.append(locale)
    elif salt.utils.which("localedef") is not None:
        cmd = ['localedef', '--force',
               '-i', "{0}_{1}".format(locale_info['language'],
                                      locale_info['territory']),
               '-f', locale_info['codeset'],
               '{0}_{1}.{2}'.format(locale_info['language'],
                                    locale_info['territory'],
                                    locale_info['codeset'])]
        cmd.append(kwargs.get('verbose', False) and '--verbose' or '--quiet')
    else:
        raise CommandExecutionError(
            'Command "locale-gen" or "localedef" was not found on this system.')

    res = __salt__['cmd.run_all'](cmd)
    if res['retcode']:
        log.error(res['stderr'])

    if kwargs.get('verbose'):
        return res
    else:
        return res['retcode'] == 0
