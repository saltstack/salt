# -*- coding: utf-8 -*-
'''
Manage flatpak packages via Salt

.. versionadded:: Neon

:depends: flatpak for distribution
'''

from __future__ import absolute_import, print_function, unicode_literals
import subprocess

import salt.utils.path

FLATPAK_BINARY_NAME = 'flatpak'

log = logging.getLogger(__name__)

__virtualname__ = 'flatpak'


def __virtual__():
    if salt.utils.path.which('flatpak'):
        return __virtualname__

    return (False, 'The flatpak execution module cannot be loaded: the "flatpak" binary is not in the path.')


def install(location, pkg):
    '''
    Install the specified flatpak package from the specified location.
    Returns a dictionary of "result" and "output".
    location
        The location or remote to install the flatpak from.
    pkg
        The flatpak package name
    '''
    ret = {'result': None, 'output': ""}

    try:
        # Try to run it, merging stderr into output
        ret['output'] = subprocess.check_output([FLATPAK_BINARY_NAME, 'install', location, pkg], stderr=subprocess.STDOUT)
        ret['result'] = True
    except subprocess.CalledProcessError as e:
        ret['output'] = e.output
        ret['result'] = False

    return ret


def is_installed(pkg):
    '''
    Returns True if there is any version of the specified package installed.
    pkg
        The package name
    '''
    try:
        output = subprocess.check_output([FLATPAK_BINARY_NAME, 'info', pkg], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        return False

    return True


def uninstall(pkg):
    '''
    Uninstall the specified package. Returns a dictionary of "result" and "output".
    pkg
        The package name
    '''
    ret = {'result': None, 'output': ""}
    try:
        ret['output'] = subprocess.check_output([FLATPAK_BINARY_NAME, 'uninstall', pkg])
        ret['result'] = True
    except subprocess.CalledProcessError as e:
        ret['output'] = e.output
        ret['result'] = False


def add_remote(name, location):
    '''
    Add a new location to install flatpak packages from.
    name
        The repositories name
    location
        The location of the repository
    '''
    ret = {'result': None, 'output': ""}
    try:
        ret['output'] = subprocess.check_output([FLATPAK_BINARY_NAME, 'remote-add', name, location])
        ret['result'] = True
    except subprocess.CalledProcessError as e:
        ret['output'] = e.output
        ret['result'] = False

def is_remote_added(remote):
    '''
    Returns True if the remote has already been added.
    remote
        The remote's name
    '''
    try:
        output = subprocess.check_output([FLATPAK_BINARY_NAME, 'remotes'], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        return []

    lines = output.splitlines()[1:] 
    for item in lines:
        i = item.split()
        if i[0] == remote:
            return True
    return False
