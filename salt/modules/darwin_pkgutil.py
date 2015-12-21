# -*- coding: utf-8 -*-
'''
Installer support for OS X.

Installer is the native .pkg/.mpkg package manager for OS X.
'''

# Import Python libs
from __future__ import absolute_import
import os.path

# Import 3rd-party libs
from salt.ext.six.moves import urllib  # pylint: disable=import-error

# Import salt libs
import salt.utils.itertools

# Don't shadow built-in's.
__func_alias__ = {
    'list_': 'list'
}

__PKGUTIL = '/usr/sbin/pkgutil'

# Define the module's virtual name
__virtualname__ = 'darwin_pkgutil'


def __virtual__():
    if __grains__['os'] == 'MacOS':
        return __virtualname__
    return (False, 'The darwin_pkgutil execution module cannot be loaded: '
            'only available on MacOS systems.')


def list_():
    '''
    List the installed packages.

    CLI Example:

    .. code-block:: bash

        salt '*' darwin_pkgutil.list
    '''
    cmd = [__PKGUTIL, '--pkgs']
    return __salt__['cmd.run_stdout'](cmd, python_shell=False)


def is_installed(package_id):
    '''
    Returns whether a given package id is installed.

    CLI Example:

    .. code-block:: bash

        salt '*' darwin_pkgutil.is_installed com.apple.pkg.gcc4.2Leo
    '''
    for line in salt.utils.itertools.split(list_(), '\n'):
        if line == package_id:
            return True
    return False


def _install_from_path(path):
    if not os.path.exists(path):
        msg = 'Path \'{0}\' does not exist, cannot install'.format(path)
        raise ValueError(msg)
    else:
        cmd = 'installer -pkg "{0}" -target /'.format(path)
        return __salt__['cmd.retcode'](cmd)


def install(source, package_id=None):
    '''
    Install a .pkg from an URI or an absolute path.

    CLI Example:

    .. code-block:: bash

        salt '*' darwin_pkgutil.install source=/vagrant/build_essentials.pkg package_id=com.apple.pkg.gcc4.2Leo
    '''
    if package_id is not None and is_installed(package_id):
        return ''

    uri = urllib.parse.urlparse(source)
    if uri.scheme == "":
        return _install_from_path(source)
    else:
        msg = 'Unsupported scheme for source uri: \'{0}\''.format(uri.scheme)
        raise ValueError(msg)
