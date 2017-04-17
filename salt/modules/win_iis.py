# -*- coding: utf-8 -*-
'''
Microsoft IIS site management via WebAdministration powershell module

:platform:      Windows

.. versionadded:: 2016.3.0

'''


from __future__ import absolute_import

# Import salt libs
import salt.utils

# Define the module's virtual name
__virtualname__ = 'win_iis'


def __virtual__():
    '''
    Load only on Windows
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return (False, 'Module win_iis: module only works on Windows systems')


def _srvmgr(func):
    '''
    Execute a function from the WebAdministration PS module
    '''

    return __salt__['cmd.run'](
        'Import-Module WebAdministration; {0}'.format(func),
        shell='powershell',
        python_shell=True)


def list_sites():
    '''
    List all the currently deployed websites

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.list_sites
    '''
    pscmd = []
    pscmd.append(r'Get-WebSite -erroraction silentlycontinue -warningaction silentlycontinue')
    pscmd.append(r' | foreach {')
    pscmd.append(r' $_.Name')
    pscmd.append(r'};')

    command = ''.join(pscmd)
    return _srvmgr(command)


def create_site(
        name,
        protocol,
        sourcepath,
        port,
        apppool='',
        hostheader='',
        ipaddress=''):
    '''
    Create a basic website in IIS

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.create_site name='My Test Site' protocol='http' sourcepath='c:\\stage' port='80' apppool='TestPool'

    '''

    pscmd = []
    pscmd.append(r'cd IIS:\Sites\;')
    pscmd.append(r'New-Item \'iis:\Sites\{0}\''.format(name))
    pscmd.append(r' -bindings @{{protocol=\'{0}\';bindingInformation=\':{1}:{2}\'}}'.format(
        protocol, port, hostheader.replace(' ', '')))
    pscmd.append(r'-physicalPath {0};'.format(sourcepath))

    if apppool:
        pscmd.append(r'Set-ItemProperty \'iis:\Sites\{0}\''.format(name))
        pscmd.append(r' -name applicationPool -value \'{0}\';'.format(apppool))

    command = ''.join(pscmd)
    return _srvmgr(command)


def remove_site(name):
    '''
    Delete website from IIS

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.remove_site name='My Test Site'

    '''

    pscmd = []
    pscmd.append(r'cd IIS:\Sites\;')
    pscmd.append(r'Remove-WebSite -Name \'{0}\''.format(name))

    command = ''.join(pscmd)
    return _srvmgr(command)


def list_apppools():
    '''
    List all configured IIS Application pools

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.list_apppools
    '''
    pscmd = []
    pscmd.append(r'Get-ChildItem IIS:\AppPools\ -erroraction silentlycontinue -warningaction silentlycontinue')
    pscmd.append(r' | foreach {')
    pscmd.append(r' $_.Name')
    pscmd.append(r'};')

    command = ''.join(pscmd)
    return _srvmgr(command)


def create_apppool(name):
    '''
    Create IIS Application pools

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.create_apppool name='MyTestPool'
    '''
    pscmd = []
    pscmd.append(r'New-Item \'IIS:\AppPools\{0}\''.format(name))

    command = ''.join(pscmd)
    return _srvmgr(command)


def remove_apppool(name):
    '''
    Removes IIS Application pools

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.remove_apppool name='MyTestPool'
    '''
    pscmd = []
    pscmd.append(r'Remove-Item \'IIS:\AppPools\{0}\' -recurse'.format(name))

    command = ''.join(pscmd)
    return _srvmgr(command)
