# -*- coding: utf-8 -*-
'''
Common functions for working with powershell
'''
# Import Python libs
from __future__ import absolute_import
import logging
import os

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)

__virtualname__ = 'powershell'


def __virtual__():
    '''
    Load only on Systems with PowerShell
    '''
    if not __salt__['cmd.shell_info']('powershell')['installed']:
        return (False, 'Failed to load win_powershell: '
                       'The utility only works on systems with PowerShell.')
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
    return name in get_modules()


def get_modules():
    '''
    Get a list of the PowerShell modules which are potentially available to be
    imported. The intent is to mimick the functionality of ``Get-Module
    -ListAvaiable | Select-Object -Expand Name``, without the delay of loading
    PowerShell to do so.

    Returns:
        list: A list of modules available to Powershell

    Example:

    .. code-block:: python

        import salt.utils.win_powershell
        modules = salt.utils.powershell.get_modules()
    '''
    ret = list()
    valid_extensions = ('.psd1', '.psm1', '.cdxml', '.xaml', '.dll')
    env_var = 'PSModulePath'

    if env_var not in os.environ:
        log.error('Environment variable not present: %s', env_var)
        return ret

    root_paths = [str(path) for path in os.environ[env_var].split(';') if path]
    for root_path in root_paths:

        # only recurse directories
        if not os.path.isdir(root_path):
            continue

        # get a list of all files in the root_path
        for root_dir, sub_dirs, file_names in os.walk(root_path):
            for file_name in file_names:
                base_name, file_extension = os.path.splitext(file_name)

                # If a module file or module manifest is present, check if
                # the base name matches the directory name.

                if file_extension.lower() in valid_extensions:
                    dir_name = os.path.basename(os.path.normpath(root_dir))

                    # Stop recursing once we find a match, and use
                    # the capitalization from the directory name.
                    if dir_name not in ret and base_name.lower() == dir_name.lower():
                        del sub_dirs[:]
                        ret.append(dir_name)

    return ret
