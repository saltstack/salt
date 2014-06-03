# -*- coding: utf-8 -*-
'''
Module for managing keyboards on supported POSIX-like systems such as
Arch, Redhat, Debian, and Gentoo systems.
'''

# Import python libs
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on supported POSIX-like systems
    '''
    if __grains__['os_family'] in ('Arch', 'Redhat', 'Debian', 'Gentoo'):
        return True
    return False


def get_sys():
    '''
    Get current system keyboard setting

    CLI Example:

    .. code-block:: bash

        salt '*' keyboard.get_sys
    '''
    cmd = ''
    if 'Arch' in __grains__['os_family']:
        cmd = 'localectl | grep Keymap | sed -e"s/: /=/" -e"s/^[ \t]*//"'
    elif 'RedHat' in __grains__['os_family']:
        cmd = 'grep LAYOUT /etc/sysconfig/keyboard | grep -vE "^#"'
    elif 'Debian' in __grains__['os_family']:
        cmd = 'grep XKBLAYOUT /etc/default/keyboard | grep -vE "^#"'
    elif 'Gentoo' in __grains__['os_family']:
        cmd = 'grep "^keymap" /etc/conf.d/keymaps | grep -vE "^#"'
    out = __salt__['cmd.run'](cmd).split('=')
    ret = out[1].replace('"', '')
    return ret


def set_sys(layout):
    '''
    Set current system keyboard setting

    CLI Example:

    .. code-block:: bash

        salt '*' keyboard.set_sys dvorak
    '''
    if 'Arch' in __grains__['os_family']:
        __salt__['cmd.run']('localectl set-keymap {0}'.format(layout))
    elif 'RedHat' in __grains__['os_family']:
        __salt__['file.sed']('/etc/sysconfig/keyboard',
                             '^LAYOUT=.*',
                             'LAYOUT={0}'.format(layout))
    elif 'Debian' in __grains__['os_family']:
        __salt__['file.sed']('/etc/default/keyboard',
                             '^XKBLAYOUT=.*',
                             'XKBLAYOUT={0}'.format(layout))
    elif 'Gentoo' in __grains__['os_family']:
        __salt__['file.sed']('/etc/conf.d/keymaps',
                             '^keymap=.*',
                             'keymap={0}'.format(layout))
    return layout


def get_x():
    '''
    Get current X keyboard setting

    CLI Example:

    .. code-block:: bash

        salt '*' keyboard.get_x
    '''
    cmd = 'setxkbmap -query | grep layout'
    out = __salt__['cmd.run'](cmd).split(':')
    return out[1].strip()


def set_x(layout):
    '''
    Set current X keyboard setting

    CLI Example:

    .. code-block:: bash

        salt '*' keyboard.set_x dvorak
    '''
    cmd = 'setxkbmap {0}'.format(layout)
    __salt__['cmd.run'](cmd)
    return layout
