# -*- coding: utf-8 -*-
'''
    salt.modules.alternatives
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Support for Alternatives system

    :codeauthor: Radek Rada <radek.rada@gmail.com>
    :copyright: © 2012 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.

'''

# Import python libs
import os

__outputter__ = {
    'display': 'txt',
    'install': 'txt',
    'remove': 'txt',
}


def __virtual__():
    '''
    Only if alternatives dir is available
    '''
    if os.path.isdir("/etc/alternatives"):
        return 'alternatives'
    return False


def _get_cmd():
    '''
    Alteratives commands and differ across distributions
    '''
    if __grains__['os_family'] == 'RedHat':
        return 'alternatives'
    else:
        return 'update-alternatives'


def display(name):
    '''
    Display alternatives settings for defined command name.

    CLI Example::

        salt '*' alternatives.display <command name>
    '''

    cmd = "{0} --display {1}".format(_get_cmd(), name)
    out = __salt__['cmd.run_all'](cmd)
    if out['retcode'] > 0 and out['stderr'] != '':
        return out['stderr']
    return out['stdout']

def show_current(name):
    '''
    Display the current alternatives for the given name

    CLI Example::

        salt '*' alternatives.show_current emacs
    '''
    alt_link_path = '/etc/alternatives/{0}'.format(name)
    if os.path.islink(alt_link_path):
        path = os.path.realpath(alt_link_path)
        return path
    return False


def check_installed(name, path):
    '''
    Check if the alternatives link is set to desired path.

    CLI Example::

        salt '*' alternatives.check_installed name path
    '''

    alt_link_path = '/etc/alternatives/{0}'.format(name)
    if os.path.realpath(alt_link_path) == path:
        return True
    return False


def install(name, link, path, priority):
    '''
    Install symbolic links determining default commands.

    CLI Example::

        salt '*' alternatives.install name link path priority
    '''

    cmd = "{0} --install {1} {2} {3} {4}".format(_get_cmd(), link, name, path, priority)
    out = __salt__['cmd.run_all'](cmd)
    if out['retcode'] > 0 and out['stderr'] != '':
        return out['stderr']
    return out['stdout']


def remove(name, path):
    '''
    Remove symbolic links determining the default commands.

    CLI Example::

        salt '*' alternatives.remove name path
    '''

    cmd = "{0} --remove {1} {2}".format(_get_cmd(), name, path)
    out = __salt__['cmd.run_all'](cmd)
    if out['retcode'] > 0:
        return out['stderr']
    return out['stdout']
