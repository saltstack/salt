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
_VALID_SSL_FLAGS = tuple(range(0, 4))

# Define the module's virtual name
__virtualname__ = 'win_iis'


def __virtual__():
    '''
    Load only on Windows
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return (False, 'Module win_iis: module only works on Windows systems')


def _get_binding_info(hostheader='', ipaddress='*', port=80):
    '''
    Combine the host header, IP address, and TCP port into bindingInformation format.
    '''
    ret = r'{0}:{1}:{2}'.format(ipaddress, port, hostheader.replace(' ', ''))

    return ret


def _list_certs(certificatestore='My'):
    '''
    List details of available certificates.
    '''
    ret = dict()
    pscmd = list()
    blacklist_keys = ['DnsNameList', 'Thumbprint']
    cert_path = r"Cert:\LocalMachine\{0}".format(certificatestore)

    pscmd.append(r"Get-ChildItem -Path '{0}' | Select-Object".format(cert_path))
    pscmd.append(' DnsNameList, SerialNumber, Subject, Thumbprint, Version')

    cmd_ret = _srvmgr(func=str().join(pscmd), as_json=True)

    try:
        items = json.loads(cmd_ret['stdout'], strict=False)
    except ValueError:
        _LOG.error('Unable to parse return data as Json.')

    for item in items:
        cert_info = dict()
        for key in item:
            if key not in blacklist_keys:
                cert_info[key.lower()] = item[key]

        cert_info['dnsnames'] = [name['Unicode'] for name in item['DnsNameList']]
        ret[item['Thumbprint']] = cert_info

    return ret


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
    keep_keys = ('certificateHash', 'certificateStoreName', 'protocol', 'sslFlags')

    cmd_ret = _srvmgr(func=str().join(pscmd), as_json=True)

    try:
        items = json.loads(cmd_ret['stdout'], strict=False)
    except ValueError:
        _LOG.error('Unable to parse return data as Json.')

    for item in items:
        bindings = dict()

        for binding in item['bindings']['Collection']:
            filtered_binding = dict()

            for key in binding:
                if key in keep_keys:
                    filtered_binding.update({key.lower(): binding[key]})

            binding_info = binding['bindingInformation'].split(':', 2)
            ipaddress, port, hostheader = [element.strip() for element in binding_info]
            filtered_binding.update({'hostheader': hostheader, 'ipaddress': ipaddress,
                                     'port': port})
            bindings[binding['bindingInformation']] = filtered_binding

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
    binding_info = _get_binding_info(hostheader, ipaddress, port)
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
    sites = list_sites()

    if site not in sites:
        _LOG.warning('Site not found: %s', site)
        return ret

    ret = sites[site]['bindings']

    if not ret:
        _LOG.warning('No bindings found for site: %s', site)
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
    name = _get_binding_info(hostheader, ipaddress, port)

    if protocol not in _VALID_PROTOCOLS:
        message = ("Invalid protocol '{0}' specified. Valid formats:"
                   ' {1}').format(protocol, _VALID_PROTOCOLS)
        raise SaltInvocationError(message)

    if sslflags not in _VALID_SSL_FLAGS:
        message = ("Invalid sslflags '{0}' specified. Valid sslflags range:"
                   ' {1}..{2}').format(sslflags, _VALID_SSL_FLAGS[0], _VALID_SSL_FLAGS[-1])
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
    name = _get_binding_info(hostheader, ipaddress, port)
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


def list_cert_bindings(site):
    '''
    List certificate bindings for an IIS site.

    :param str site: The IIS site name.

    :return: A dictionary of the binding names and properties.
    :rtype: dict

    .. versionadded:: Carbon

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.list_bindings site
    '''
    ret = dict()
    sites = list_sites()

    if site not in sites:
        _LOG.warning('Site not found: %s', site)
        return ret

    for binding in sites[site]['bindings']:
        if sites[site]['bindings'][binding]['certificatehash']:
            ret[binding] = sites[site]['bindings'][binding]

    if not ret:
        _LOG.warning('No certificate bindings found for site: %s', site)
    return ret


def create_cert_binding(name, site, hostheader='', ipaddress='*', port=443, sslflags=0):
    '''
    Assign a certificate to an IIS binding.

    .. note:

        The web binding that the certificate is being assigned to must already exist.

    :param str name: The thumbprint of the certificate.
    :param str site: The IIS site name.
    :param str hostheader: The host header of the binding.
    :param str ipaddress: The IP address of the binding.
    :param str port: The TCP port of the binding.
    :param str sslflags: Flags representing certificate type and certificate storage of the binding.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    .. versionadded:: Carbon

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.create_cert_binding name='AAA000' site='site0' hostheader='example' ipaddress='*' port='443'
    '''
    pscmd = list()
    name = str(name).upper()
    binding_info = _get_binding_info(hostheader, ipaddress, port)
    binding_path = r"IIS:\SslBindings\{0}".format(binding_info.replace(':', '!'))

    if sslflags not in _VALID_SSL_FLAGS:
        message = ("Invalid sslflags '{0}' specified. Valid sslflags range:"
                   ' {1}..{2}').format(sslflags, _VALID_SSL_FLAGS[0], _VALID_SSL_FLAGS[-1])
        raise SaltInvocationError(message)

    # Verify that the target binding exists.
    current_bindings = list_bindings(site)

    if binding_info not in current_bindings:
        _LOG.error('Binding not present: %s', binding_info)
        return False

    # Check to see if the certificate is already assigned.
    current_name = None

    for current_binding in current_bindings:
        if binding_info == current_binding:
            current_name = current_bindings[current_binding]['certificatehash']

    _LOG.debug('Current certificate thumbprint: %s', current_name)
    _LOG.debug('New certificate thumbprint: %s', name)

    if name == current_name:
        _LOG.debug('Certificate already present for binding: %s', name)
        return True

    # Verify that the certificate exists.
    certs = _list_certs()

    if name not in certs:
        _LOG.error('Certificate not present: %s', name)
        return False

    pscmd.append("New-Item -Path '{0}' -Thumbprint '{1}'".format(binding_path, name))
    pscmd.append(" -SSLFlags {0}".format(sslflags))

    cmd_ret = _srvmgr(str().join(pscmd))

    if cmd_ret['retcode'] == 0:
        new_cert_bindings = list_cert_bindings(site)

        if binding_info not in new_cert_bindings:
            _LOG.error('Binding not present: %s', binding_info)
            return False

        if name == new_cert_bindings[binding_info]['certificatehash']:
            _LOG.debug('Certificate binding created successfully: %s', name)
            return True
    _LOG.error('Unable to create certificate binding: %s', name)
    return False


def remove_cert_binding(name, site, hostheader='', ipaddress='*', port=443):
    '''
    Remove a certificate from an IIS binding.

    .. note:

        This function only removes the certificate from the web binding. It does
        not remove the web binding itself.

    :param str name: The thumbprint of the certificate.
    :param str site: The IIS site name.
    :param str hostheader: The host header of the binding.
    :param str ipaddress: The IP address of the binding.
    :param str port: The TCP port of the binding.

    .. versionadded:: Carbon

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.remove_cert_binding name='AAA000' site='site0' hostheader='example' ipaddress='*' port='443'
    '''
    pscmd = list()
    name = str(name).upper()
    binding_info = _get_binding_info(hostheader, ipaddress, port)

    # Child items of IIS:\SslBindings do not return populated host header info
    # in all circumstances, so it's necessary to use IIS:\Sites instead.
    pscmd.append(r"$Site = Get-ChildItem -Path 'IIS:\Sites' | Where-Object")
    pscmd.append(r" {{ $_.Name -Eq '{0}' }};".format(site))
    pscmd.append(' $Binding = $Site.Bindings.Collection')
    pscmd.append(r" | Where-Object { $_.bindingInformation")
    pscmd.append(r" -Eq '{0}' }};".format(binding_info))
    pscmd.append(' $Binding.RemoveSslCertificate()')

    # Verify that the binding exists for the site, and that the target
    # certificate is assigned to the binding.
    current_cert_bindings = list_cert_bindings(site)

    if binding_info not in current_cert_bindings:
        _LOG.warning('Binding not found: %s', binding_info)
        return True

    if name != current_cert_bindings[binding_info]['certificatehash']:
        _LOG.debug('Certificate binding already absent: %s', name)
        return True

    cmd_ret = _srvmgr(str().join(pscmd))

    if cmd_ret['retcode'] == 0:
        new_cert_bindings = list_cert_bindings(site)

        if binding_info not in new_cert_bindings:
            _LOG.warning('Binding not found: %s', binding_info)
            return True

        if name != new_cert_bindings[binding_info]['certificatehash']:
            _LOG.debug('Certificate binding removed successfully: %s', name)
            return True
    _LOG.error('Unable to remove certificate binding: %s', name)
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
