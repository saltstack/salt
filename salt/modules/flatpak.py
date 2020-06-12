# -*- coding: utf-8 -*-
'''
Manage flatpak packages via Salt

.. versionadded:: Neon

:depends: flatpak for distribution
'''

from __future__ import absolute_import, print_function, unicode_literals
import re

import salt.utils.path

FLATPAK_BINARY_NAME = 'flatpak'

__virtualname__ = 'flatpak'


def __virtual__():
    if salt.utils.path.which('flatpak'):
        return __virtualname__

    return False, 'The flatpak execution module cannot be loaded: the "flatpak" binary is not in the path.'


def install(location, name):
    '''
    Install the specified flatpak package or runtime from the specified location.

    Args:
        location (str): The location or remote to install from.
        name (str): The name of the package or runtime.

    Returns:
        dict: The ``result`` and ``output``.

    CLI Example:

    .. code-block:: bash

        salt '*' flatpak.install flathub org.gimp.GIMP
    '''
    ret = {'result': None, 'output': ''}

    out = __salt__['cmd.run_all'](FLATPAK_BINARY_NAME + ' install ' + location + ' ' + name)

    if out['retcode'] and out['stderr']:
        ret['stderr'] = out['stderr'].strip()
        ret['result'] = False
    else:
        ret['stdout'] = out['stdout'].strip()
        ret['result'] = True

    return ret


def is_installed(name):
    '''
    Determine if a package or runtime is installed.

    Args:
        name (str): The name of the package or the runtime.

    Returns:
        bool: True if the specified package or runtime is installed.

    CLI Example:

    .. code-block:: bash

        salt '*' flatpak.is_installed org.gimp.GIMP
    '''
    out = __salt__['cmd.run_all'](FLATPAK_BINARY_NAME + ' info ' + name)

    if out['retcode'] and out['stderr']:
        return False
    else:
        return True


def uninstall(pkg):
    '''
    Uninstall the specified package.

    Args:
        pkg (str): The package name.

    Returns:
        dict: The ``result`` and ``output``.

    CLI Example:

    .. code-block:: bash

        salt '*' flatpak.uninstall org.gimp.GIMP
    '''
    ret = {'result': None, 'output': ''}

    out = __salt__['cmd.run_all'](FLATPAK_BINARY_NAME + ' uninstall ' + pkg)

    if out['retcode'] and out['stderr']:
        ret['stderr'] = out['stderr'].strip()
        ret['result'] = False
    else:
        ret['stdout'] = out['stdout'].strip()
        ret['result'] = True

    return ret


def add_remote(name, location):
    '''
    Adds a new location to install flatpak packages from.

    Args:
        name (str): The repository's name.
        location (str): The location of the repository.

    Returns:
        dict: The ``result`` and ``output``.

    CLI Example:

    .. code-block:: bash

        salt '*' flatpak.add_remote flathub https://flathub.org/repo/flathub.flatpakrepo
    '''
    ret = {'result': None, 'output': ''}
    out = __salt__['cmd.run_all'](FLATPAK_BINARY_NAME + ' remote-add ' + name + ' ' + location)

    if out['retcode'] and out['stderr']:
        ret['stderr'] = out['stderr'].strip()
        ret['result'] = False
    else:
        ret['stdout'] = out['stdout'].strip()
        ret['result'] = True

    return ret


def is_remote_added(remote):
    '''
    Determines if a remote exists.

    Args:
        remote (str): The remote's name.

    Returns:
        bool: True if the remote has already been added.

    CLI Example:

    .. code-block:: bash

        salt '*' flatpak.is_remote_added flathub
    '''
    out = __salt__['cmd.run_all'](FLATPAK_BINARY_NAME + ' remotes')

    lines = out.splitlines()
    for item in lines:
        i = re.split(r'\t+', item.rstrip('\t'))
        if i[0] == remote:
            return True
    return False
