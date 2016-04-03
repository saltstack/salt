# -*- coding: utf-8 -*-
'''
Microsoft IIS site management via WebAdministration powershell module

:platform:      Windows

.. versionadded:: 2016.3.0

'''

# Import python libs
from __future__ import absolute_import
import json
import logging

# Import salt libs
from salt.exceptions import SaltInvocationError
import salt.utils

_LOG = logging.getLogger(__name__)
_VALID_PROTOCOLS = ('ftp', 'http', 'https')

# Define the module's virtual name
__virtualname__ = 'win_iis'


def __virtual__():
    '''
    Load only on Windows
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return (False, 'Module win_iis: module only works on Windows systems')


def _srvmgr(func, as_json=False):
    '''
    Execute a function from the WebAdministration PS module.
    '''
    command = 'Import-Module WebAdministration;'

    if as_json:
        command = '{0} ConvertTo-Json -Compress -Depth 4 -InputObject @({1})'.format(command,
                                                                                     func)
    else:
        command = '{0} {1}'.format(command, func)

    cmd_ret = __salt__['cmd.run_all'](command, shell='powershell', python_shell=True)

    if cmd_ret['retcode'] != 0:
        _LOG.error('Unable to execute command: %s\nError: %s', command, cmd_ret['stderr'])
    return cmd_ret


def list_sites():
    '''
    List all the currently deployed websites.

    :return: A dictionary of the IIS sites and their properties.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.list_sites
    '''
    ret = dict()
    pscmd = []
    pscmd.append(r"Get-ChildItem -Path 'IIS:\Sites'")
    pscmd.append(' | Select-Object applicationPool, Bindings, ID, Name, PhysicalPath, State')
    keep_keys = ('bindingInformation', 'certificateHash', 'certificateStoreName',
                 'protocol', 'sslFlags')

    cmd_ret = _srvmgr(func=str().join(pscmd), as_json=True)

    try:
        items = json.loads(cmd_ret['stdout'], strict=False)
    except ValueError:
        _LOG.error('Unable to parse return data as Json.')

    for item in items:
        bindings = list()

        for binding in item['bindings']['Collection']:
            filtered_binding = dict()

            for key in binding:
                if key in keep_keys:
                    filtered_binding.update({key: binding[key]})
            bindings.append(filtered_binding)

        ret[item['name']] = {'apppool': item['applicationPool'], 'bindings': bindings,
                             'id': item['id'], 'state': item['state'],
                             'sourcepath': item['physicalPath']}

    if not ret:
        _LOG.warning('No sites found in output: %s', cmd_ret['stdout'])
    return ret


def create_site(name, sourcepath, apppool='', hostheader='',
                ipaddress='*', port=80, protocol='http'):
    '''
    Create a basic website in IIS.

    ..note:

        This function only validates against the site name, and will return True even
        if the site already exists with a different configuration. It will not modify
        the configuration of an existing site.

    :param str name: The IIS site name.
    :param str sourcepath: The physical path of the IIS site.
    :param str apppool: The name of the IIS application pool.
    :param str hostheader: The host header of the binding.
    :param str ipaddress: The IP address of the binding.
    :param str port: The TCP port of the binding.
    :param str protocol: The application protocol of the binding.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    ..note:

        If an application pool is specified, and that application pool does not already exist,
        it will be created.

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.create_site name='My Test Site' sourcepath='c:\\stage' apppool='TestPool'
    '''
    pscmd = []
    protocol = str(protocol).lower()
    site_path = r'IIS:\Sites\{0}'.format(name)
    binding_info = r'{0}:{1}:{2}'.format(ipaddress, port, hostheader.replace(' ', ''))
    current_sites = list_sites()

    if name in current_sites:
        _LOG.debug("Site '%s' already present.", name)
        return True

    if protocol not in _VALID_PROTOCOLS:
        message = ("Invalid protocol '{0}' specified. Valid formats:"
                   ' {1}').format(protocol, _VALID_PROTOCOLS)
        raise SaltInvocationError(message)

    pscmd.append(r"New-Item -Path '{0}' -Bindings".format(site_path))
    pscmd.append(r" @{{ protocol='{0}'; bindingInformation='{1}' }}".format(protocol,
                                                                            binding_info))
    pscmd.append(r" -physicalPath '{0}';".format(sourcepath))

    if apppool:
        if apppool in list_apppools():
            _LOG.debug('Utilizing pre-existing application pool: %s', apppool)
        else:
            _LOG.debug('Application pool will be created: %s', apppool)
            create_apppool(apppool)

        pscmd.append(r" Set-ItemProperty -Path '{0}'".format(site_path))
        pscmd.append(r" -Name applicationPool -Value '{0}'".format(apppool))

    cmd_ret = _srvmgr(str().join(pscmd))

    if cmd_ret['retcode'] == 0:
        _LOG.debug('Site created successfully: %s', name)
        return True
    _LOG.error('Unable to create site: %s', name)
    return False


def remove_site(name):
    '''
    Delete a website from IIS.

    :param str name: The IIS site name.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.remove_site name='My Test Site'

    '''
    pscmd = []
    current_sites = list_sites()

    if name not in current_sites:
        _LOG.debug('Site already absent: %s', name)
        return True

    pscmd.append(r"Remove-WebSite -Name '{0}'".format(name))

    cmd_ret = _srvmgr(str().join(pscmd))

    if cmd_ret['retcode'] == 0:
        _LOG.debug('Site removed successfully: %s', name)
        return True
    _LOG.error('Unable to remove site: %s', name)
    return False


def list_apppools():
    '''
    List all configured IIS application pools.

    :return: A dictionary of IIS application pools and their details.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.list_apppools
    '''
    ret = dict()
    pscmd = []

    pscmd.append(r"Get-ChildItem -Path 'IIS:\AppPools' | Select-Object Name, State")

    # Include the equivalient of output from the Applications column, since this isn't
    # a normal property, we have to populate it via filtered output from the
    # Get-WebConfigurationProperty cmdlet.

    pscmd.append(r", @{ Name = 'Applications'; Expression = { $AppPool = $_.Name;")
    pscmd.append(" $AppPath = 'machine/webroot/apphost';")
    pscmd.append(" $FilterBase = '/system.applicationHost/sites/site/application';")
    pscmd.append(' $FilterBase += "[@applicationPool = \'$($AppPool)\' and @path";')
    pscmd.append(' $FilterRoot = "$($FilterBase) = \'/\']/parent::*";')
    pscmd.append(' $FilterNonRoot = "$($FilterBase) != \'/\']";')
    pscmd.append(' Get-WebConfigurationProperty -Filter $FilterRoot -PsPath $AppPath -Name Name')
    pscmd.append(r' | ForEach-Object { $_.Value };')
    pscmd.append(' Get-WebConfigurationProperty -Filter $FilterNonRoot -PsPath $AppPath -Name Path')
    pscmd.append(r" | ForEach-Object { $_.Value } | Where-Object { $_ -ne '/' }")
    pscmd.append(r' } }')

    cmd_ret = _srvmgr(func=str().join(pscmd), as_json=True)

    try:
        items = json.loads(cmd_ret['stdout'], strict=False)
    except ValueError:
        _LOG.error('Unable to parse return data as Json.')

    for item in items:
        applications = list()

        # If there are no associated apps, Applications will be an empty dict,
        # if there is one app, it will be a string, and if there are multiple,
        # it will be a dict with 'Count' and 'value' as the keys.

        if isinstance(item['Applications'], dict):
            if 'value' in item['Applications']:
                applications += item['Applications']['value']
        else:
            applications.append(item['Applications'])

        ret[item['name']] = {'state': item['state'], 'applications': applications}

    if not ret:
        _LOG.warning('No application pools found in output: %s', cmd_ret['stdout'])
    return ret


def create_apppool(name):
    '''
    Create an IIS application pool.

    ..note:

        This function only validates against the application pool name, and will return
        True even if the application pool already exists with a different configuration.
        It will not modify the configuration of an existing application pool.

    :param str name: The name of the IIS application pool.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.create_apppool name='MyTestPool'
    '''
    pscmd = []
    current_apppools = list_apppools()
    apppool_path = r'IIS:\AppPools\{0}'.format(name)

    if name in current_apppools:
        _LOG.debug("Application pool '%s' already present.", name)
        return True

    pscmd.append(r"New-Item -Path '{0}'".format(apppool_path))

    cmd_ret = _srvmgr(str().join(pscmd))

    if cmd_ret['retcode'] == 0:
        _LOG.debug('Application pool created successfully: %s', name)
        return True
    _LOG.error('Unable to create application pool: %s', name)
    return False


def remove_apppool(name):
    '''
    Remove an IIS application pool.

    :param str name: The name of the IIS application pool.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.remove_apppool name='MyTestPool'
    '''
    pscmd = []
    current_apppools = list_apppools()
    apppool_path = r'IIS:\AppPools\{0}'.format(name)

    if name not in current_apppools:
        _LOG.debug('Application pool already absent: %s', name)
        return True

    pscmd.append(r"Remove-Item -Path '{0}' -Recurse".format(apppool_path))

    cmd_ret = _srvmgr(str().join(pscmd))

    if cmd_ret['retcode'] == 0:
        _LOG.debug('Application pool removed successfully: %s', name)
        return True
    _LOG.error('Unable to remove application pool: %s', name)
    return False
