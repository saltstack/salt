# -*- coding: utf-8 -*-
'''
Common functions for working with powershell
'''
# Import Python libs
from __future__ import absolute_import
import logging
import os

log = logging.getLogger(__name__)

__virtualname__ = 'powershell'


def __virtual__():
    '''
    Load only on Windows
    '''
    if not salt.utils.is_windows():
        return (False, 'Failed to load win_powershell: '
                       'The utility only works on Windows systems.')
    return __virtualname__


def module_exists(name):
    '''
    See if a module is installed
    Look in paths specified in PSModulePath environment variable

    Use this utility instead of attempting to import the module with powershell.
    Using powershell to try to import the module is expensive.

    Args:

        name (str):
            The name of the module to check

    Returns:
        bool: True if present, otherwise returns False

    Example:

    .. code-block:: python

        import salt.utils.win_powershell
        exists = salt.utils.win_powershell.module_exists('ServerManager')
    '''
    ps_module_paths = os.environ['PSModulePath']
    for path in ps_module_paths.split(';'):
        mod_path = '\\'.join([path, name, ''.join([name, '.psd1'])])
        if os.path.isfile(mod_path):
            return True

    log.debug('Powershell Module {0} not installed'.format(name))
    return False
