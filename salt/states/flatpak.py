# -*- coding: utf-8 -*-
'''
Management of flatpak packages
==============================
Allows the installation and uninstallation of flatpak packages.

.. versionadded:: Neon
'''
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.path

__virtualname__ = 'flatpak'


def __virtual__():
    if salt.utils.path.which('flatpak'):
        return __virtualname__

    return False, 'The flatpak state module cannot be loaded: the "flatpak" binary is not in the path.'


def installed(location, name):
    '''
    Ensure that the named package is installed.

    Args:
        location (str): The location or remote to install the flatpak from.
        name (str): The name of the package or runtime.

    Returns:
        dict: The ``result`` and ``output``.

    Example:

    .. code-block:: yaml

        install_package:
          flatpack.installed:
            - location: flathub
            - name: gimp
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    old = __salt__['flatpak.is_installed'](name)
    if not old:
        if __opts__['test']:
            ret['comment'] = 'Package "{0}" would have been installed'.format(name)
            ret['changes']['new'] = name
            ret['changes']['old'] = None
            ret['result'] = None
            return ret

        install_ret = __salt__['flatpak.install'](name, location)
        if __salt__['flatpak.is_installed'](name):
            ret['comment'] = 'Package "{0}" was installed'.format(name)
            ret['changes']['new'] = name
            ret['changes']['old'] = None
            ret['result'] = True
            return ret

        ret['comment'] = 'Package "{0}" failed to install'.format(name)
        ret['comment'] += '\noutput:\n' + install_ret['output']
        ret['result'] = False
        return ret

    ret['comment'] = 'Package "{0}" is already installed'.format(name)
    if __opts__['test']:
        ret['result'] = None
        return ret

    ret['result'] = True
    return ret


def uninstalled(name):
    '''
    Ensure that the named package is not installed.

    Args:
        name (str): The flatpak package.

    Returns:
        dict: The ``result`` and ``output``.

    Example:

    .. code-block:: yaml

        uninstall_package:
          flatpack.uninstalled:
            - name: gimp
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    old = __salt__['flatpak.is_installed'](name)
    if not old:
        ret['comment'] = 'Package {0} is not installed'.format(name)
        ret['result'] = True
        return ret
    else:
        if __opts__['test']:
            ret['comment'] = 'Package {0} would have been uninstalled'.format(name)
            ret['changes']['old'] = old[0]['version']
            ret['changes']['new'] = None
            ret['result'] = None
            return ret

        __salt__['flatpak.uninstall'](name)
        if not __salt__['flatpak.is_installed'](name):
            ret['comment'] = 'Package {0} uninstalled'.format(name)
            ret['changes']['old'] = old[0]['version']
            ret['changes']['new'] = None
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

    Example:

    .. code-block:: yaml

        add_flathub:
          flatpack.add_remote:
            - name: flathub
            - location: https://flathub.org/repo/flathub.flatpakrepo
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    old = __salt__['flatpak.is_remote_added'](name)
    if not old:
        if __opts__['test']:
            ret['comment'] = 'Remote "{0}" would have been added'.format(name)
            ret['changes']['new'] = name
            ret['changes']['old'] = None
            ret['result'] = None
            return ret

        install_ret = __salt__['flatpak.add_remote'](name)
        if __salt__['flatpak.is_remote_added'](name):
            ret['comment'] = 'Remote "{0}" was added'.format(name)
            ret['changes']['new'] = name
            ret['changes']['old'] = None
            ret['result'] = True
            return ret

        ret['comment'] = 'Failed to add remote "{0}"'.format(name)
        ret['comment'] += '\noutput:\n' + install_ret['output']
        ret['result'] = False
        return ret

    ret['comment'] = 'Remote "{0}" already exists'.format(name)
    if __opts__['test']:
        ret['result'] = None
        return ret

    ret['result'] = True
    return ret
