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

# Don't shadow built-in's.
__func_alias__ = {
    'list_': 'list'
}

PKGUTIL = "/usr/sbin/pkgutil"


def __virtual__():
    if __grains__['os'] == 'MacOS':
        return 'darwin_pkgutil'
    return False


def list_():
    '''
    List the installed packages.

    CLI Example:

    .. code-block:: bash

        salt '*' darwin_pkgutil.list
    '''
    cmd = PKGUTIL + ' --pkgs'
    return __salt__['cmd.run_stdout'](cmd)


def is_installed(package_id):
    '''
    Returns whether a given package id is installed.

    CLI Example:

    .. code-block:: bash

        salt '*' darwin_pkgutil.is_installed com.apple.pkg.gcc4.2Leo
    '''
    def has_package_id(lines):
        for line in lines:
            if line == package_id:
                return True
        return False

    cmd = PKGUTIL + ' --pkgs'
    out = __salt__['cmd.run_stdout'](cmd)
    return has_package_id(out.splitlines())


def _install_from_path(path):
    if not os.path.exists(path):
        msg = "Path {0!r} does not exist, cannot install".format(path)
        raise ValueError(msg)
    else:
        cmd = 'installer -pkg "{0}" -target /'.format(path)
        return __salt__['cmd.retcode'](cmd)


def install(source, package_id=None):
    '''
    Install a .pkg from an URI or an absolute path.

    CLI Example:

    .. code-block:: bash

        salt '*' darwin_pkgutil.install source=/vagrant/build_essentials.pkg \
            package_id=com.apple.pkg.gcc4.2Leo
    '''
    if package_id is not None and is_installed(package_id):
        return ''

    uri = urllib.parse.urlparse(source)
    if uri.scheme == "":
        return _install_from_path(source)
    else:
        msg = "Unsupported scheme for source uri: {0!r}".format(uri.scheme)
        raise ValueError(msg)
