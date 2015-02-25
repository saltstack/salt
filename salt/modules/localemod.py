# -*- coding: utf-8 -*-
'''
Module for managing locales on POSIX-like systems.
'''

# Import python libs
import logging
import re
import os

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'locale'


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    if salt.utils.is_windows():
        return False
    return __virtualname__


def _parse_localectl():
    '''
    Get the 'System Locale' parameters from localectl
    '''
    ret = {}
    for line in __salt__['cmd.run']('localectl').splitlines():
        cols = [x.strip() for x in line.split(':', 1)]
        if len(cols) > 1:
            cur_param = cols.pop(0)
        if cur_param == 'System Locale':
            try:
                key, val = re.match('^([A-Z_]+)=(.*)$', cols[0]).groups()
            except AttributeError:
                log.error('Odd locale parameter "{0}" detected in localectl '
                          'output. This should not happen. localectl should '
                          'catch this. You should probably investigate what '
                          'caused this.'.format(cols[0]))
            else:
                ret[key] = val.replace('"', '')
    return ret


def _localectl_get():
    '''
    Use systemd's localectl command to get the current locale
    '''
    return _parse_localectl().get('LANG', '')


def _localectl_set(locale=''):
    '''
    Use systemd's localectl command to set the LANG locale parameter, making
    sure not to trample on other params that have been set.
    '''
    locale_params = _parse_localectl()
    locale_params['LANG'] = str(locale)
    args = ' '.join(['{0}="{1}"'.format(k, v)
                     for k, v in locale_params.iteritems()])
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
        return _localectl_get()
    elif 'RedHat' in __grains__['os_family']:
        cmd = 'grep "^LANG=" /etc/sysconfig/i18n'
    elif 'Debian' in __grains__['os_family']:
        cmd = 'grep "^LANG=" /etc/default/locale'
    elif 'Gentoo' in __grains__['os_family']:
        cmd = 'eselect --brief locale show'
        return __salt__['cmd.run'](cmd).strip()

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
        if __salt__['cmd.retcode']('grep "^LANG=" /etc/sysconfig/i18n') != 0:
            __salt__['file.append']('/etc/sysconfig/i18n',
                                    '"\nLANG={0}"'.format(locale))
        else:
            __salt__['file.replace'](
                '/etc/sysconfig/i18n', '^LANG=.*', 'LANG="{0}"'.format(locale)
            )
    elif 'Debian' in __grains__['os_family']:
        __salt__['file.replace'](
            '/etc/default/locale', '^LANG=.*', 'LANG="{0}"'.format(locale)
        )
        if __salt__['cmd.retcode']('grep "^LANG=" /etc/default/locale') != 0:
            __salt__['file.append']('/etc/default/locale',
                                    '\nLANG="{0}"'.format(locale))
    elif 'Gentoo' in __grains__['os_family']:
        cmd = 'eselect --brief locale set {0}'.format(locale)
        return __salt__['cmd.retcode'](cmd, python_shell=False) == 0

    return True


def _split_locale(locale):
    '''
    Split a locale specifier.  The general format is

    language[_territory][.codeset][@modifier] [charmap]

    For example:

    ca_ES.UTF-8@valencia UTF-8
    '''
    def split(st, char):
        '''
        Split a string `st` once by `char`; always return a two-element list
        even if the second element is empty.
        '''
        split_st = st.split(char, 1)
        if len(split_st) == 1:
            split_st.append('')
        return split_st

    parts = {}
    work_st, parts['charmap'] = split(locale, ' ')
    work_st, parts['modifier'] = split(work_st, '@')
    work_st, parts['codeset'] = split(work_st, '.')
    parts['language'], parts['territory'] = split(work_st, '_')
    return parts


def _join_locale(parts):
    '''
    Join a locale specifier split in the format returned by _split_locale.
    '''
    locale = parts['language']
    if parts.get('territory'):
        locale += '_' + parts['territory']
    if parts.get('codeset'):
        locale += '.' + parts['codeset']
    if parts.get('modifier'):
        locale += '@' + parts['modifier']
    if parts.get('charmap'):
        locale += ' ' + parts['charmap']
    return locale


def _normalize_locale(locale):
    '''
    Format a locale specifier according to the format returned by `locale -a`.
    '''
    parts = _split_locale(locale)
    parts['territory'] = parts['territory'].upper()
    parts['codeset'] = parts['codeset'].lower().replace('-', '')
    parts['charmap'] = ''
    return _join_locale(parts)


def avail(locale):
    '''
    Check if a locale is available.

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' locale.avail 'en_US.UTF-8'
    '''
    try:
        normalized_locale = _normalize_locale(locale)
    except IndexError:
        log.error('Unable to validate locale "{0}"'.format(locale))
        return False
    avail_locales = __salt__['locale.list_avail']()
    locale_exists = next((True for x in avail_locales
       if _normalize_locale(x.strip()) == normalized_locale), False)
    return locale_exists


@decorators.which('locale-gen')
def gen_locale(locale):
    '''
    Generate a locale.

    .. versionadded:: 2014.7.0

    :param locale: Any locale listed in /usr/share/i18n/locales or
        /usr/share/i18n/SUPPORTED for debian and gentoo based distros

    CLI Example:

    .. code-block:: bash

        salt '*' locale.gen_locale en_US.UTF-8
        salt '*' locale.gen_locale 'en_IE@euro ISO-8859-15'
    '''
    on_debian = __grains__.get('os') == 'Debian'
    on_gentoo = __grains__.get('os_family') == 'Gentoo'

    if on_debian or on_gentoo:
        search = '/usr/share/i18n/SUPPORTED'
        valid = __salt__['file.search'](search, '^{0}$'.format(locale))
    else:
        parts = _split_locale(locale)
        parts['codeset'] = ''
        parts['charmap'] = ''
        search_locale = _join_locale(parts)

        search = '/usr/share/i18n/locales'
        valid = search_locale in os.listdir(search)

    if not valid:
        log.error('The provided locale "{0}" is not found in {1}'.format(locale, search))
        return False

    if on_debian or on_gentoo:
        __salt__['file.replace'](
            '/etc/locale.gen',
            r'^#\s*{0}$'.format(locale),
            '{0}'.format(locale),
            append_if_not_found=True
        )

    cmd = ['locale-gen']
    if on_gentoo:
        cmd.append('--generate')
    cmd.append(locale)

    return __salt__['cmd.retcode'](cmd, python_shell=False)
