'''
Module for managing locales on posix-like systems.
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
    return 'locale'


def list_avail():
    '''
    Lists available (compiled) locales

    CLI Example::

        salt '*' locale.list_avail
    '''
    cmd = 'locale -a'
    out = __salt__['cmd.run'](cmd).split('\n')
    return out


def get_locale():
    '''
    Get the current system locale

    CLI Example::

        salt '*' locale.get_locale
    '''
    cmd = ''
    if 'Arch' in __grains__['os_family']:
        cmd = 'grep "^LOCALE" /etc/rc.conf | grep -vE "^#"'
    elif 'RedHat' in __grains__['os_family']:
        cmd = 'grep LANG /etc/sysconfig/i18n | grep -vE "^#"'
    elif 'Debian' in __grains__['os_family']:
        cmd = 'grep LANG /etc/default/locale | grep -vE "^#"'
    elif 'Gentoo' in __grains__['os_family']:
        cmd = 'eselect --brief locale show'
    out = __salt__['cmd.run'](cmd).split('=')
    ret = out[1].replace('"', '')
    return ret


def set_locale(locale):
    '''
    Sets the current system locale

    CLI Example::

        salt '*' locale.set_locale 'en_US.UTF-8'
    '''
    if 'Arch' in __grains__['os_family']:
        __salt__['file.sed']('/etc/rc.conf', '^LOCALE=.*', 'LOCALE="{0}"'.format(locale))
    elif 'RedHat' in __grains__['os_family']:
        __salt__['file.sed']('/etc/sysconfig/i18n', '^LANG=.*', 'LANG="{0}"'.format(locale))
    elif 'Debian' in __grains__['os_family']:
        __salt__['file.sed']('/etc/default/locale', '^LANG=.*', 'LANG="{0}"'.format(locale))
    elif 'Gentoo' in __grains__['os_family']:
        return __salt__['cmd.retcode']('eselect --brief locale set {0}'.format(locale))

    return True
