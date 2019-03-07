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

    return (False, 'The flatpak state module cannot be loaded: the "flatpak" binary is not in the path.')


def installed(location, name):
    '''
    Ensure that the named package is installed
    location
        The location or remote to install the flatpak from.
    name
        The name of the package or runtime
    '''
    ret = {'name': name,
           'changes': {},
           'pchanges': {},
           'result': None,
           'comment': ''}

    old = __salt__['flatpak.is_installed'](name)
    if not old:
        if __opts__['test']:
            ret['comment'] = 'Package "{0}" would have been installed'.format(name)
            ret['pchanges']['new'] = name
            ret['pchanges']['old'] = None
            ret['result'] = None
            return ret

        install = __salt__['flatpak.install'](name, location)
        if install['result']:
            ret['comment'] = 'Package "{0}" was installed'.format(name)
            ret['changes']['new'] = name
            ret['changes']['old'] = None
            ret['result'] = True
            return ret

        ret['comment'] = 'Package "{0}" failed to install'.format(name)
        ret['comment'] += '\noutput:\n' + install['output']
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
    Ensure that the named package is not installed
    name
        The flatpak package
    '''
    ret = {'name': name,
           'changes': {},
           'pchanges': {},
           'result': None,
           'comment': ''}

    old = __salt__['flatpak.is_installed'](name)
    if not old:
        ret['comment'] = 'Package {0} is not installed'.format(name)
        ret['result'] = True
        return ret

    if __opts__['test']:
        ret['comment'] = 'Package {0} would have been uninstalled'.format(name)
        ret['result'] = None
        ret['pchanges']['old'] = old[0]['version']
        ret['pchanges']['new'] = None
        return ret

    uninstall = __salt__['flatpak.uninstall'](name)
    ret['comment'] = 'Package {0} uninstalled'.format(name)
    ret['result'] = True
    ret['changes']['old'] = old[0]['version']
    ret['changes']['new'] = None
    return ret


def add_remote(name, location):
    '''
    Add a new location to install flatpak packages from.
    name
        The repositories name
    location
        The location of the repository
    '''
    ret = {'name': name,
           'changes': {},
           'pchanges': {},
           'result': None,
           'comment': ''}

    old = __salt__['flatpak.is_remote_added'](name)
    if not old:
        if __opts__['test']:
            ret['comment'] = 'Remote "{0}" would have been added'.format(name)
            ret['pchanges']['new'] = name
            ret['pchanges']['old'] = None
            ret['result'] = None
            return ret

        install = __salt__['flatpak.add_remote'](name)
        if install['result']:
            ret['comment'] = 'Remote "{0}" was added'.format(name)
            ret['changes']['new'] = name
            ret['changes']['old'] = None
            ret['result'] = True
            return ret

        ret['comment'] = 'Failed to add remote "{0}"'.format(name)
        ret['comment'] += '\noutput:\n' + install['output']
        ret['result'] = False
        return ret

    ret['comment'] = 'Remote "{0}" already exists'.format(name)
    if __opts__['test']:
        ret['result'] = None
        return ret

    ret['result'] = True
    return ret
