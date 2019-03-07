# -*- coding: utf-8 -*-
'''
Manage flatpak packages via Salt

.. versionadded:: Neon

:depends: flatpak for distribution
'''

from __future__ import absolute_import, print_function, unicode_literals
import subprocess
import re

import salt.utils.path

FLATPAK_BINARY_NAME = 'flatpak'

__virtualname__ = 'flatpak'


def __virtual__():
    if salt.utils.path.which('flatpak'):
        return __virtualname__

    return (False, 'The flatpak execution module cannot be loaded: the "flatpak" binary is not in the path.')


def install(location, name):
    '''
    Install the specified flatpak package or runtime from the specified location.
    Returns a dictionary of "result" and "output".
    location
        The location or remote to install from.
    name
        The name of the package or runtime
    '''
    ret = {'result': None, 'output': ""}

    try:
        ret['output'] = subprocess.check_output([FLATPAK_BINARY_NAME, 'install', location, name], stderr=subprocess.STDOUT)
        ret['result'] = True
    except subprocess.CalledProcessError as e:
        ret['output'] = e.output
        ret['result'] = False

    return ret


def is_installed(name):
    '''
    Returns True if the specified package or runtime is installed.
    name
        The name of the package or the runtime
    '''
    try:
        output = subprocess.check_output([FLATPAK_BINARY_NAME, 'info', name], stderr=subprocess.STDOUT)
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

    lines = output.splitlines()
    for item in lines:
        i = re.split(r'\t+', item.rstrip('\t'))
        if i[0] == remote:
            return True
    return False
