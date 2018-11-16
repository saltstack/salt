# -*- coding: utf-8 -*-
'''
Microsoft Update files management via wusa.exe

:maintainer:    Thomas Lemarchand
:platform:      Windows
:depends:       PowerShell

.. versionadded:: Neon
'''

# Import python libs
from __future__ import absolute_import, unicode_literals
import logging

# Import salt libs
import salt.utils.platform

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'win_wusa'


def __virtual__():
    '''
    Load only on Windows
    '''
    if not salt.utils.platform.is_windows():
        return False, 'Only available on Windows systems'

    powershell_info = __salt__['cmd.shell_info'](shell='powershell', list_modules=False)
    if not powershell_info['installed']:
        return False, 'PowerShell not available'

    return __virtualname__


def is_installed(kb):
    '''
    Check if a specific KB is installed.

    CLI Example:

    .. code-block:: bash

        salt '*' win_wusa.is_installed KB123456
    '''
    get_hotfix_result = __salt__['cmd.powershell_all']('Get-HotFix -Id {0}'.format(kb), ignore_retcode=True)

    return get_hotfix_result['retcode'] == 0


def install(path):
    '''
    Install a KB from a .msu file.
    Some KBs will need a reboot, but this function does not manage it.
    You may have to manage reboot yourself after installation.

    CLI Example:

    .. code-block:: bash

        salt '*' win_wusa.install C:/temp/KB123456.msu
    '''
    return __salt__['cmd.run_all']('wusa.exe {0} /quiet /norestart'.format(path), ignore_retcode=True)


def uninstall(kb):
    '''
    Uninstall a specific KB.

    CLI Example:

    .. code-block:: bash

        salt '*' win_wusa.uninstall KB123456
    '''
    return __salt__['cmd.run_all']('wusa.exe /uninstall /kb:{0} /quiet /norestart'.format(kb[2:]), ignore_retcode=True)


def list_kbs():
    '''
    Return a list of dictionaries, one dictionary for each installed KB.
    The HotFixID key contains the ID of the KB.

    CLI Example:

    .. code-block:: bash

        salt '*' win_wusa.list_kbs
    '''
    return __salt__['cmd.powershell']('Get-HotFix')
