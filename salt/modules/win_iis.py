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
import os

# Import salt libs
from salt.exceptions import SaltInvocationError
import salt.utils

_DEFAULT_APP = '/'
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

    .. note:

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

    .. note:

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


def list_bindings(site):
    '''
    Get all configured IIS bindings for the specified site.

    :param str site: The IIS site name.

    :return: A dictionary of the binding names and properties.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.list_bindings site
    '''
    ret = dict()
    pscmd = list()

    pscmd.append("Get-WebBinding -Name '{0}'".format(site))
    pscmd.append(' | Select-Object bindingInformation, protocol, sslFlags')

    cmd_ret = _srvmgr(func=str().join(pscmd), as_json=True)

    try:
        items = json.loads(cmd_ret['stdout'], strict=False)
    except ValueError:
        _LOG.error('Unable to parse return data as Json.')

    for item in items:
        name = item['bindingInformation']
        binding_info = item['bindingInformation'].split(':', 2)
        ipaddress, port, hostheader = [element.strip() for element in binding_info]

        ret[name] = {'hostheader': hostheader, 'ipaddress': ipaddress,
                     'port': port, 'protocol': item['protocol'],
                     'sslflags': item['sslFlags']}

    if not ret:
        _LOG.warning('No bindings found in output: %s', cmd_ret)
    return ret


def create_binding(site, hostheader='', ipaddress='*', port=80, protocol='http', sslflags=0):
    '''
    Create an IIS binding.

    .. note:

        This function only validates against the binding ipaddress:port:hostheader combination,
        and will return True even if the binding already exists with a different configuration.
        It will not modify the configuration of an existing binding.

    :param str site: The IIS site name.
    :param str hostheader: The host header of the binding.
    :param str ipaddress: The IP address of the binding.
    :param str port: The TCP port of the binding.
    :param str protocol: The application protocol of the binding.
    :param str sslflags: The flags representing certificate type and storage of the binding.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.create_binding site='site0' hostheader='example' ipaddress='*' port='80'
    '''
    pscmd = list()
    protocol = str(protocol).lower()
    sslflags = int(sslflags)
    name = "{0}:{1}:{2}".format(ipaddress, port, hostheader)
    valid_ssl_flags = tuple(range(0, 4))

    if protocol not in _VALID_PROTOCOLS:
        message = ("Invalid protocol '{0}' specified. Valid formats:"
                   ' {1}').format(protocol, _VALID_PROTOCOLS)
        raise SaltInvocationError(message)

    if sslflags not in valid_ssl_flags:
        message = ("Invalid sslflags '{0}' specified. Valid sslflags range:"
                   ' {1}..{2}').format(sslflags, valid_ssl_flags[0], valid_ssl_flags[-1])
        raise SaltInvocationError(message)

    current_bindings = list_bindings(site)

    if name in current_bindings:
        _LOG.debug("Binding already present: %s", name)
        return True

    pscmd.append("New-WebBinding -Name '{0}' -HostHeader '{1}'".format(site, hostheader))
    pscmd.append(" -IpAddress '{0}' -Port '{1}'".format(ipaddress, port))
    pscmd.append(" -Protocol '{0}' -SslFlags {1}".format(protocol, sslflags))

    cmd_ret = _srvmgr(str().join(pscmd))

    if cmd_ret['retcode'] == 0:
        new_bindings = list_bindings(site)

        if name in new_bindings:
            _LOG.debug('Binding created successfully: %s', name)
            return True
    _LOG.error('Unable to create binding: %s', name)
    return False


def remove_binding(site, hostheader='', ipaddress='*', port=80):
    '''
    Remove an IIS binding.

    :param str site: The IIS site name.
    :param str hostheader: The host header of the binding.
    :param str ipaddress: The IP address of the binding.
    :param str port: The TCP port of the binding.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.remove_binding site='site0' hostheader='example' ipaddress='*' port='80'
    '''
    pscmd = list()
    name = "{0}:{1}:{2}".format(ipaddress, port, hostheader)
    current_bindings = list_bindings(site)

    if name not in current_bindings:
        _LOG.debug('Binding already absent: %s', name)
        return True

    pscmd.append("Remove-WebBinding -HostHeader '{0}' ".format(hostheader))
    pscmd.append(" -IpAddress '{0}' -Port '{1}'".format(ipaddress, port))

    cmd_ret = _srvmgr(str().join(pscmd))

    if cmd_ret['retcode'] == 0:
        new_bindings = list_bindings(site)

        if name not in new_bindings:
            _LOG.debug('Binding removed successfully: %s', name)
            return True
    _LOG.error('Unable to remove binding: %s', name)
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

    .. note:

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


def restart_apppool(name):
    '''
    Restart an IIS application pool.

    :param str name: The name of the IIS application pool.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    .. versionadded:: Carbon

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.restart_apppool name='MyTestPool'
    '''
    pscmd = list()

    pscmd.append("Restart-WebAppPool '{0}'".format(name))

    cmd_ret = _srvmgr(str().join(pscmd))
    return cmd_ret['retcode'] == 0


def list_apps(site):
    '''
    Get all configured IIS applications for the specified site.

    :param str site: The IIS site name.

    :return: A dictionary of the application names and properties.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.list_apps site
    '''
    ret = dict()
    pscmd = list()
    pscmd.append("Get-WebApplication -Site '{0}'".format(site))
    pscmd.append(r" | Select-Object applicationPool, path, PhysicalPath, preloadEnabled,")
    pscmd.append(r" @{ Name='name'; Expression={ $_.path.Split('/', 2)[-1] } },")
    pscmd.append(r" @{ Name='protocols'; Expression={ @( $_.enabledProtocols.Split(',')")
    pscmd.append(r" | Foreach-Object { $_.Trim() } ) } }")

    cmd_ret = _srvmgr(func=str().join(pscmd), as_json=True)

    try:
        items = json.loads(cmd_ret['stdout'], strict=False)
    except ValueError:
        _LOG.error('Unable to parse return data as Json.')

    for item in items:
        protocols = list()

        # If there are no associated protocols, protocols will be an empty dict,
        # if there is one protocol, it will be a string, and if there are multiple,
        # it will be a dict with 'Count' and 'value' as the keys.

        if isinstance(item['protocols'], dict):
            if 'value' in item['protocols']:
                protocols += item['protocols']['value']
        else:
            protocols.append(item['protocols'])

        ret[item['name']] = {'apppool': item['applicationPool'], 'path': item['path'],
                             'preload': item['preloadEnabled'], 'protocols': protocols,
                             'sourcepath': item['PhysicalPath']}

    if not ret:
        _LOG.warning('No apps found in output: %s', cmd_ret)
    return ret


def create_app(name, site, sourcepath, apppool=None):
    '''
    Create an IIS application.

    .. note:

        This function only validates against the application name, and will return True
        even if the application already exists with a different configuration. It will not
        modify the configuration of an existing application.

    :param str name: The IIS application.
    :param str site: The IIS site name.
    :param str sourcepath: The physical path.
    :param str apppool: The name of the IIS application pool.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.create_app name='app0' site='site0' sourcepath='C:\\site0' apppool='site0'
    '''
    pscmd = list()
    current_apps = list_apps(site)

    if name in current_apps:
        _LOG.debug("Application already present: %s", name)
        return True

    # The target physical path must exist.
    if not os.path.isdir(sourcepath):
        _LOG.error('Path is not present: %s', sourcepath)
        return False

    pscmd.append("New-WebApplication -Name '{0}' -Site '{1}'".format(name, site))
    pscmd.append(" -PhysicalPath '{0}'".format(sourcepath))

    if apppool:
        pscmd.append(" -applicationPool '{0}'".format(apppool))

    cmd_ret = _srvmgr(str().join(pscmd))

    if cmd_ret['retcode'] == 0:
        new_apps = list_apps(site)

        if name in new_apps:
            _LOG.debug('Application created successfully: %s', name)
            return True
    _LOG.error('Unable to create application: %s', name)
    return False


def remove_app(name, site):
    '''
    Remove an IIS application.

    :param str name: The application name.
    :param str site: The IIS site name.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.remove_app name='app0' site='site0'
    '''
    pscmd = list()
    current_apps = list_apps(site)

    if name not in current_apps:
        _LOG.debug('Application already absent: %s', name)
        return True

    pscmd.append("Remove-WebApplication -Name '{0}' -Site '{1}'".format(name, site))

    cmd_ret = _srvmgr(str().join(pscmd))

    if cmd_ret['retcode'] == 0:
        new_apps = list_apps(site)

        if name not in new_apps:
            _LOG.debug('Application removed successfully: %s', name)
            return True
    _LOG.error('Unable to remove application: %s', name)
    return False


def list_vdirs(site, app=_DEFAULT_APP):
    '''
    Get all configured IIS virtual directories for the specified site, or for the
    combination of site and application.

    :param str site: The IIS site name.
    :param str app: The IIS application.

    :return: A dictionary of the virtual directory names and properties.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.list_vdirs site
    '''
    ret = dict()
    pscmd = list()

    pscmd.append(r"Get-WebVirtualDirectory -Site '{0}' -Application '{1}'".format(site, app))
    pscmd.append(r" | Select-Object PhysicalPath, @{ Name = 'name';")
    pscmd.append(r" Expression = { $_.path.Split('/')[-1] } }")

    cmd_ret = _srvmgr(func=str().join(pscmd), as_json=True)

    try:
        items = json.loads(cmd_ret['stdout'], strict=False)
    except ValueError:
        _LOG.error('Unable to parse return data as Json.')

    for item in items:
        ret[item['name']] = {'sourcepath': item['physicalPath']}

    if not ret:
        _LOG.warning('No vdirs found in output: %s', cmd_ret)
    return ret


def create_vdir(name, site, sourcepath, app=_DEFAULT_APP):
    '''
    Create an IIS virtual directory.

    .. note:

        This function only validates against the virtual directory name, and will return
        True even if the virtual directory already exists with a different configuration.
        It will not modify the configuration of an existing virtual directory.

    :param str name: The virtual directory name.
    :param str site: The IIS site name.
    :param str sourcepath: The physical path.
    :param str app: The IIS application.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.create_vdir name='vd0' site='site0' sourcepath='C:\\inetpub\\vdirs\\vd0'
    '''
    pscmd = list()
    current_vdirs = list_vdirs(site, app)

    if name in current_vdirs:
        _LOG.debug("Virtual directory already present: %s", name)
        return True

    # The target physical path must exist.
    if not os.path.isdir(sourcepath):
        _LOG.error('Path is not present: %s', sourcepath)
        return False

    pscmd.append(r"New-WebVirtualDirectory -Name '{0}' -Site '{1}'".format(name, site))
    pscmd.append(r" -PhysicalPath '{0}'".format(sourcepath))

    if app != _DEFAULT_APP:
        pscmd.append(r" -Application '{0}'".format(app))

    cmd_ret = _srvmgr(str().join(pscmd))

    if cmd_ret['retcode'] == 0:
        new_vdirs = list_vdirs(site, app)

        if name in new_vdirs:
            _LOG.debug('Virtual directory created successfully: %s', name)
            return True
    _LOG.error('Unable to create virtual directory: %s', name)
    return False


def remove_vdir(name, site, app=_DEFAULT_APP):
    '''
    Remove an IIS virtual directory.

    :param str name: The virtual directory name.
    :param str site: The IIS site name.
    :param str app: The IIS application.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.remove_vdir name='vdir0' site='site0'
    '''
    pscmd = list()
    current_vdirs = list_vdirs(site, app)
    app_path = os.path.join(*app.rstrip('/').split('/'))

    if app_path:
        app_path = '{0}\\'.format(app_path)
    vdir_path = r'IIS:\Sites\{0}\{1}{2}'.format(site, app_path, name)

    if name not in current_vdirs:
        _LOG.debug('Virtual directory already absent: %s', name)
        return True

    # We use Remove-Item here instead of Remove-WebVirtualDirectory, since the
    # latter has a bug that causes it to always prompt for user input.

    pscmd.append(r"Remove-Item -Path '{0}' -Recurse".format(vdir_path))

    cmd_ret = _srvmgr(str().join(pscmd))

    if cmd_ret['retcode'] == 0:
        new_vdirs = list_vdirs(site, app)

        if name not in new_vdirs:
            _LOG.debug('Virtual directory removed successfully: %s', name)
            return True
    _LOG.error('Unable to remove virtual directory: %s', name)
    return False
