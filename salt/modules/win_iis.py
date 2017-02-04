# -*- coding: utf-8 -*-
'''
Microsoft IIS site management via WebAdministration powershell module

:platform:      Windows

.. versionadded:: 2016.3.0

'''

# Import python libs
from __future__ import absolute_import, unicode_literals
import json
import logging
import os

# Import salt libs
from salt.ext.six.moves import range
from salt.exceptions import SaltInvocationError, CommandExecutionError
import salt.utils

log = logging.getLogger(__name__)

_DEFAULT_APP = '/'
_VALID_PROTOCOLS = ('ftp', 'http', 'https')
_VALID_SSL_FLAGS = tuple(range(0, 4))

# Define the module's virtual name
__virtualname__ = 'win_iis'


def __virtual__():
    '''
    Load only on Windows
    '''
    if not salt.utils.is_windows():
        return False, 'Only available on Windows systems'

    powershell_info = __salt__['cmd.shell_info']('powershell', True)
    if not powershell_info['installed']:
        return False, 'PowerShell not available'

    if 'WebAdministration' not in powershell_info['modules']:
        return False, 'IIS is not installed'

    return __virtualname__


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

    cmd_ret = _srvmgr(cmd=str().join(pscmd), return_json=True)

    try:
        items = json.loads(cmd_ret['stdout'], strict=False)
    except ValueError:
        raise CommandExecutionError('Unable to parse return data as Json.')

    for item in items:
        cert_info = dict()
        for key in item:
            if key not in blacklist_keys:
                cert_info[key.lower()] = item[key]

        cert_info['dnsnames'] = [name['Unicode'] for name in item['DnsNameList']]
        ret[item['Thumbprint']] = cert_info

    return ret


def _srvmgr(cmd, return_json=False):
    '''
    Execute a function from the WebAdministration PS module.
    '''
    if isinstance(cmd, list):
        cmd = ' '.join(cmd)

    if return_json:
        cmd = 'ConvertTo-Json -Compress -Depth 4 -InputObject @({0})' \
              ''.format(cmd)

    cmd = 'Import-Module WebAdministration; {0}'.format(cmd)

    ret = __salt__['cmd.run_all'](cmd, shell='powershell', python_shell=True)

    if ret['retcode'] != 0:
        msg = 'Unable to execute command: {0}\nError: {1}' \
              ''.format(cmd, ret['stderr'])
        log.error(msg)

    return ret


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
    ps_cmd = ['Get-ChildItem', '-Path', r"'IIS:\Sites'", '|', 'Select-Object',
              'applicationPool, Bindings, ID, Name, PhysicalPath, State']
    keep_keys = ('certificateHash', 'certificateStoreName', 'protocol', 'sslFlags')

    cmd_ret = _srvmgr(cmd=ps_cmd, return_json=True)

    try:
        items = json.loads(cmd_ret['stdout'], strict=False)
    except ValueError:
        raise CommandExecutionError('Unable to parse return data as Json.')

    for item in items:
        bindings = dict()

        for binding in item['bindings']['Collection']:
            filtered_binding = dict()

            for key in binding:
                if key in keep_keys:
                    filtered_binding.update({key.lower(): binding[key]})

            binding_info = binding['bindingInformation'].split(':', 2)
            ipaddress, port, hostheader = [element.strip() for element in binding_info]
            filtered_binding.update({'hostheader': hostheader,
                                     'ipaddress': ipaddress,
                                     'port': port})
            bindings[binding['bindingInformation']] = filtered_binding

        ret[item['name']] = {'apppool': item['applicationPool'],
                             'bindings': bindings,
                             'id': item['id'],
                             'state': item['state'],
                             'sourcepath': item['physicalPath']}

    if not ret:
        log.warning('No sites found in output: {0}'.format(cmd_ret['stdout']))

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
    protocol = str(protocol).lower()
    site_path = r'IIS:\Sites\{0}'.format(name)
    binding_info = _get_binding_info(hostheader, ipaddress, port)
    current_sites = list_sites()

    if name in current_sites:
        log.debug("Site '{0}' already present.".format(name))
        return True

    if protocol not in _VALID_PROTOCOLS:
        message = ("Invalid protocol '{0}' specified. Valid formats:"
                   ' {1}').format(protocol, _VALID_PROTOCOLS)
        raise SaltInvocationError(message)

    ps_cmd = ['New-Item', '-Path', r"'{0}'".format(site_path), '-Bindings',
              "@{{ protocol='{0}';".format(protocol),
              "bindingInformation='{0}' }}".format(binding_info),
              r" -physicalPath '{0}';".format(sourcepath)]

    if apppool:
        if apppool in list_apppools():
            log.debug('Utilizing pre-existing application pool: {0}'
                      ''.format(apppool))
        else:
            log.debug('Application pool will be created: {0}'.format(apppool))
            create_apppool(apppool)

        ps_cmd.append(r"Set-ItemProperty -Path '{0}'".format(site_path))
        ps_cmd.append(r"-Name applicationPool -Value '{0}'".format(apppool))

    cmd_ret = _srvmgr(ps_cmd)

    if cmd_ret['retcode'] != 0:
        msg = 'Unable to create site: {0}\nError: {1}' \
              ''.format(name, cmd_ret['stderr'])
        raise CommandExecutionError(msg)

    log.debug('Site created successfully: {0}'.format(name))
    return True


def remove_site(name):
    '''
    Delete a website from IIS.

    :param str name: The IIS site name.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    .. note:

        This will not remove the application pool used by the site.

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.remove_site name='My Test Site'

    '''
    current_sites = list_sites()

    if name not in current_sites:
        log.debug('Site already absent: {0}'.format(name))
        return True

    ps_cmd = ['Remove-WebSite', '-Name', r"'{0}'".format(name)]

    cmd_ret = _srvmgr(ps_cmd)

    if cmd_ret['retcode'] != 0:
        msg = 'Unable to remove site: {0}\nError: {1}' \
              ''.format(name, cmd_ret['stderr'])
        raise CommandExecutionError(msg)

    log.debug('Site removed successfully: {0}'.format(name))
    return True


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
        log.warning('Site not found: {0}'.format(site))
        return ret

    ret = sites[site]['bindings']

    if not ret:
        log.warning('No bindings found for site: {0}'.format(site))

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
        log.debug('Binding already present: {0}'.format(name))
        return True

    ps_cmd = ['New-WebBinding',
              '-Name', "'{0}'".format(site),
              '-HostHeader', "'{0}'".format(hostheader),
              '-IpAddress', "'{0}'".format(ipaddress),
              '-Port', "'{0}'".format(port),
              '-Protocol', "'{0}'".format(protocol),
              '-SslFlags', '{0}'.format(sslflags)]

    cmd_ret = _srvmgr(ps_cmd)

    if cmd_ret['retcode'] != 0:
        msg = 'Unable to create binding: {0}\nError: {1}' \
              ''.format(site, cmd_ret['stderr'])
        raise CommandExecutionError(msg)

    if name in list_bindings(site):
        log.debug('Binding created successfully: {0}'.format(site))
        return True

    log.error('Unable to create binding: {0}'.format(site))
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
    name = _get_binding_info(hostheader, ipaddress, port)
    current_bindings = list_bindings(site)

    if name not in current_bindings:
        log.debug('Binding already absent: {0}'.format(name))
        return True
    ps_cmd = ['Remove-WebBinding',
              '-HostHeader', "'{0}'".format(hostheader),
              '-IpAddress', "'{0}'".format(ipaddress),
              '-Port', "'{0}'".format(port)]

    cmd_ret = _srvmgr(ps_cmd)

    if cmd_ret['retcode'] != 0:
        msg = 'Unable to remove binding: {0}\nError: {1}' \
              ''.format(site, cmd_ret['stderr'])
        raise CommandExecutionError(msg)

    if name not in list_bindings(site):
        log.debug('Binding removed successfully: {0}'.format(site))
        return True

    log.error('Unable to remove binding: {0}'.format(site))
    return False


def list_cert_bindings(site):
    '''
    List certificate bindings for an IIS site.

    :param str site: The IIS site name.

    :return: A dictionary of the binding names and properties.
    :rtype: dict

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.list_bindings site
    '''
    ret = dict()
    sites = list_sites()

    if site not in sites:
        log.warning('Site not found: {0}'.format(site))
        return ret

    for binding in sites[site]['bindings']:
        if sites[site]['bindings'][binding]['certificatehash']:
            ret[binding] = sites[site]['bindings'][binding]

    if not ret:
        log.warning('No certificate bindings found for site: {0}'.format(site))

    return ret


def create_cert_binding(name, site, hostheader='', ipaddress='*', port=443,
                        sslflags=0):
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

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.create_cert_binding name='AAA000' site='site0' hostheader='example' ipaddress='*' port='443'
    '''
    name = str(name).upper()
    binding_info = _get_binding_info(hostheader, ipaddress, port)
    binding_path = r"IIS:\SslBindings\{0}".format(binding_info.replace(':', '!'))

    if sslflags not in _VALID_SSL_FLAGS:
        message = ("Invalid sslflags '{0}' specified. Valid sslflags range: "
                   "{1}..{2}").format(sslflags, _VALID_SSL_FLAGS[0],
                                      _VALID_SSL_FLAGS[-1])
        raise SaltInvocationError(message)

    # Verify that the target binding exists.
    current_bindings = list_bindings(site)

    if binding_info not in current_bindings:
        log.error('Binding not present: {0}'.format(binding_info))
        return False

    # Check to see if the certificate is already assigned.
    current_name = None

    for current_binding in current_bindings:
        if binding_info == current_binding:
            current_name = current_bindings[current_binding]['certificatehash']

    log.debug('Current certificate thumbprint: {0}'.format(current_name))
    log.debug('New certificate thumbprint: {0}'.format(name))

    if name == current_name:
        log.debug('Certificate already present for binding: {0}'.format(name))
        return True

    # Verify that the certificate exists.
    certs = _list_certs()

    if name not in certs:
        log.error('Certificate not present: {0}'.format(name))
        return False

    ps_cmd = ['New-Item',
              '-Path', "'{0}'".format(binding_path),
              '-Thumbprint', "'{0}'".format(name),
              '-SSLFlags', '{0}'.format(sslflags)]

    cmd_ret = _srvmgr(ps_cmd)

    if cmd_ret['retcode'] != 0:
        msg = 'Unable to create certificate binding: {0}\nError: {1}' \
              ''.format(name, cmd_ret['stderr'])
        raise CommandExecutionError(msg)

    new_cert_bindings = list_cert_bindings(site)

    if binding_info not in new_cert_bindings(site):
        log.error('Binding not present: {0}'.format(binding_info))
        return False

    if name == new_cert_bindings[binding_info]['certificatehash']:
        log.debug('Certificate binding created successfully: {0}'.format(name))
        return True

    log.error('Unable to create certificate binding: {0}'.format(name))
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

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.remove_cert_binding name='AAA000' site='site0' hostheader='example' ipaddress='*' port='443'
    '''
    name = str(name).upper()
    binding_info = _get_binding_info(hostheader, ipaddress, port)

    # Child items of IIS:\SslBindings do not return populated host header info
    # in all circumstances, so it's necessary to use IIS:\Sites instead.
    ps_cmd = ['$Site = Get-ChildItem', '-Path', r"'IIS:\Sites'",
              '|', 'Where-Object', r" {{ $_.Name -Eq '{0}' }};".format(site),
              '$Binding = $Site.Bindings.Collection',
              r"| Where-Object { $_.bindingInformation",
              r"-Eq '{0}' }};".format(binding_info),
              '$Binding.RemoveSslCertificate()']

    # Verify that the binding exists for the site, and that the target
    # certificate is assigned to the binding.
    current_cert_bindings = list_cert_bindings(site)

    if binding_info not in current_cert_bindings:
        log.warning('Binding not found: {0}'.format(binding_info))
        return True

    if name != current_cert_bindings[binding_info]['certificatehash']:
        log.debug('Certificate binding already absent: {0}'.format(name))
        return True

    cmd_ret = _srvmgr(ps_cmd)

    if cmd_ret['retcode'] != 0:
        msg = 'Unable to remove certificate binding: {0}\nError: {1}' \
              ''.format(name, cmd_ret['stderr'])
        raise CommandExecutionError(msg)

    new_cert_bindings = list_cert_bindings(site)

    if binding_info not in new_cert_bindings:
        log.warning('Binding not found: {0}'.format(binding_info))
        return True

    if name != new_cert_bindings[binding_info]['certificatehash']:
        log.debug('Certificate binding removed successfully: {0}'.format(name))
        return True

    log.error('Unable to remove certificate binding: {0}'.format(name))
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
    ps_cmd = []
    ps_cmd.append(r"Get-ChildItem -Path 'IIS:\AppPools' | Select-Object Name, State")

    # Include the equivalent of output from the Applications column, since this
    # isn't a normal property, we have to populate it via filtered output from
    # the Get-WebConfigurationProperty cmdlet.
    ps_cmd.append(r", @{ Name = 'Applications'; Expression = { $AppPool = $_.Name;")
    ps_cmd.append("$AppPath = 'machine/webroot/apphost';")
    ps_cmd.append("$FilterBase = '/system.applicationHost/sites/site/application';")
    ps_cmd.append('$FilterBase += "[@applicationPool = \'$($AppPool)\' and @path";')
    ps_cmd.append('$FilterRoot = "$($FilterBase) = \'/\']/parent::*";')
    ps_cmd.append('$FilterNonRoot = "$($FilterBase) != \'/\']";')
    ps_cmd.append('Get-WebConfigurationProperty -Filter $FilterRoot -PsPath $AppPath -Name Name')
    ps_cmd.append(r'| ForEach-Object { $_.Value };')
    ps_cmd.append('Get-WebConfigurationProperty -Filter $FilterNonRoot -PsPath $AppPath -Name Path')
    ps_cmd.append(r"| ForEach-Object { $_.Value } | Where-Object { $_ -ne '/' }")
    ps_cmd.append('} }')

    cmd_ret = _srvmgr(cmd=ps_cmd, return_json=True)

    try:
        items = json.loads(cmd_ret['stdout'], strict=False)
    except ValueError:
        raise CommandExecutionError('Unable to parse return data as Json.')

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
        log.warning('No application pools found in output: {0}'
                    ''.format(cmd_ret['stdout']))

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
    current_apppools = list_apppools()
    apppool_path = r'IIS:\AppPools\{0}'.format(name)

    if name in current_apppools:
        log.debug("Application pool '{0}' already present.".format(name))
        return True

    ps_cmd = ['New-Item', '-Path', r"'{0}'".format(apppool_path)]

    cmd_ret = _srvmgr(ps_cmd)

    if cmd_ret['retcode'] != 0:
        msg = 'Unable to create application pool: {0}\nError: {1}' \
              ''.format(name, cmd_ret['stderr'])
        raise CommandExecutionError(msg)

    log.debug('Application pool created successfully: {0}'.format(name))
    return True


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
    current_apppools = list_apppools()
    apppool_path = r'IIS:\AppPools\{0}'.format(name)

    if name not in current_apppools:
        log.debug('Application pool already absent: {0}'.format(name))
        return True

    ps_cmd = ['Remove-Item', '-Path', r"'{0}'".format(apppool_path), '-Recurse']

    cmd_ret = _srvmgr(ps_cmd)

    if cmd_ret['retcode'] != 0:
        msg = 'Unable to remove application pool: {0}\nError: {1}' \
              ''.format(name, cmd_ret['stderr'])
        raise CommandExecutionError(msg)

    log.debug('Application pool removed successfully: {0}'.format(name))
    return True


def restart_apppool(name):
    '''
    Restart an IIS application pool.

    :param str name: The name of the IIS application pool.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.restart_apppool name='MyTestPool'
    '''
    ps_cmd = ['Restart-WebAppPool', r"'{0}'".format(name)]

    cmd_ret = _srvmgr(ps_cmd)

    return cmd_ret['retcode'] == 0


def get_container_setting(name, container, settings):
    '''
    Get the value of the setting for the IIS container.

    :param str name: The name of the IIS container.
    :param str container: The type of IIS container. The container types are:
        AppPools, Sites, SslBindings
    :param str settings: A dictionary of the setting names and their values.

    :return: A dictionary of the provided settings and their values.
    :rtype: dict

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.get_container_setting name='MyTestPool' container='AppPools'
            settings="['processModel.identityType']"
    '''
    ret = dict()
    ps_cmd = list()
    ps_cmd_validate = list()
    container_path = r"IIS:\{0}\{1}".format(container, name)

    if not settings:
        log.warning('No settings provided')
        return ret

    ps_cmd.append(r'$Settings = @{};')

    for setting in settings:
        # Build the commands to verify that the property names are valid.
        ps_cmd_validate.extend(['Get-ItemProperty',
                                '-Path', "'{0}'".format(container_path),
                                '-Name', "'{0}'".format(setting),
                                '-ErrorAction', 'Stop',
                                '|', 'Out-Null;'])

        # Some ItemProperties are Strings and others are ConfigurationAttributes.
        # Since the former doesn't have a Value property, we need to account
        # for this.
        ps_cmd.append("$Property = Get-ItemProperty -Path '{0}'".format(container_path))
        ps_cmd.append("-Name '{0}' -ErrorAction Stop;".format(setting))
        ps_cmd.append(r'if (([String]::IsNullOrEmpty($Property) -eq $False) -and')
        ps_cmd.append(r"($Property.GetType()).Name -eq 'ConfigurationAttribute') {")
        ps_cmd.append(r'$Property = $Property | Select-Object')
        ps_cmd.append(r'-ExpandProperty Value };')
        ps_cmd.append("$Settings['{0}'] = [String] $Property;".format(setting))
        ps_cmd.append(r'$Property = $Null;')

    # Validate the setting names that were passed in.
    cmd_ret = _srvmgr(cmd=ps_cmd_validate, return_json=True)

    if cmd_ret['retcode'] != 0:
        message = 'One or more invalid property names were specified for the provided container.'
        raise SaltInvocationError(message)

    ps_cmd.append('$Settings')
    cmd_ret = _srvmgr(cmd=ps_cmd, return_json=True)

    try:
        items = json.loads(cmd_ret['stdout'], strict=False)

        if isinstance(items, list):
            ret.update(items[0])
        else:
            ret.update(items)

    except ValueError:
        raise CommandExecutionError('Unable to parse return data as Json.')

    return ret


def set_container_setting(name, container, settings):
    '''
    Set the value of the setting for an IIS container.

    :param str name: The name of the IIS container.
    :param str container: The type of IIS container. The container types are:
        AppPools, Sites, SslBindings
    :param str settings: A dictionary of the setting names and their values.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' win_iis.set_container_setting name='MyTestPool' container='AppPools'
            settings="{'managedPipeLineMode': 'Integrated'}"
    '''
    ps_cmd = list()
    container_path = r"IIS:\{0}\{1}".format(container, name)

    if not settings:
        log.warning('No settings provided')
        return False

    # Treat all values as strings for the purpose of comparing them to existing values.
    for setting in settings:
        settings[setting] = str(settings[setting])

    current_settings = get_container_setting(
        name=name, container=container, settings=settings.keys())

    if settings == current_settings:
        log.debug('Settings already contain the provided values.')
        return True

    for setting in settings:
        # If the value is numeric, don't treat it as a string in PowerShell.
        try:
            complex(settings[setting])
            value = settings[setting]
        except ValueError:
            value = "'{0}'".format(settings[setting])

        ps_cmd.extend(['Set-ItemProperty',
                       '-Path', "'{0}'".format(container_path),
                       '-Name', "'{0}'".format(setting),
                       '-Value', '{0};'.format(value)])

    cmd_ret = _srvmgr(ps_cmd)

    if cmd_ret['retcode'] != 0:
        msg = 'Unable to set settings for {0}: {1}'.format(container, name)
        raise CommandExecutionError(msg)

    # Get the fields post-change so that we can verify tht all values
    # were modified successfully. Track the ones that weren't.
    new_settings = get_container_setting(
        name=name, container=container, settings=settings.keys())

    failed_settings = dict()

    for setting in settings:
        if str(settings[setting]) != str(new_settings[setting]):
            failed_settings[setting] = settings[setting]

    if failed_settings:
        log.error('Failed to change settings: {0}'.format(failed_settings))
        return False

    log.debug('Settings configured successfully: {0}'.format(settings.keys()))
    return True


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
    ps_cmd = list()
    ps_cmd.append("Get-WebApplication -Site '{0}'".format(site))
    ps_cmd.append(r"| Select-Object applicationPool, path, PhysicalPath, preloadEnabled,")
    ps_cmd.append(r"@{ Name='name'; Expression={ $_.path.Split('/', 2)[-1] } },")
    ps_cmd.append(r"@{ Name='protocols'; Expression={ @( $_.enabledProtocols.Split(',')")
    ps_cmd.append(r"| Foreach-Object { $_.Trim() } ) } }")

    cmd_ret = _srvmgr(cmd=ps_cmd, return_json=True)

    try:
        items = json.loads(cmd_ret['stdout'], strict=False)
    except ValueError:
        raise CommandExecutionError('Unable to parse return data as Json.')

    for item in items:
        protocols = list()

        # If there are no associated protocols, protocols will be an empty dict,
        # if there is one protocol, it will be a string, and if there are
        # multiple, it will be a dict with 'Count' and 'value' as the keys.

        if isinstance(item['protocols'], dict):
            if 'value' in item['protocols']:
                protocols += item['protocols']['value']
        else:
            protocols.append(item['protocols'])

        ret[item['name']] = {'apppool': item['applicationPool'],
                             'path': item['path'],
                             'preload': item['preloadEnabled'],
                             'protocols': protocols,
                             'sourcepath': item['PhysicalPath']}

    if not ret:
        log.warning('No apps found in output: {0}'.format(cmd_ret))

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
    current_apps = list_apps(site)

    if name in current_apps:
        log.debug('Application already present: {0}'.format(name))
        return True

    # The target physical path must exist.
    if not os.path.isdir(sourcepath):
        log.error('Path is not present: {0}'.format(sourcepath))
        return False

    ps_cmd = ['New-WebApplication',
              '-Name', "'{0}'".format(name),
              '-Site', "'{0}'".format(site),
              '-PhysicalPath', "'{0}'".format(sourcepath)]

    if apppool:
        ps_cmd.extend(['-ApplicationPool', "'{0}'".format(apppool)])

    cmd_ret = _srvmgr(ps_cmd)

    if cmd_ret['retcode'] != 0:
        msg = 'Unable to create application: {0}\nError: {1}' \
              ''.format(name, cmd_ret['stderr'])
        raise CommandExecutionError(msg)

    new_apps = list_apps(site)

    if name in new_apps:
        log.debug('Application created successfully: {0}'.format(name))
        return True

    log.error('Unable to create application: {0}'.format(name))
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
    current_apps = list_apps(site)

    if name not in current_apps:
        log.debug('Application already absent: {0}'.format(name))
        return True

    ps_cmd = ['Remove-WebApplication',
              '-Name', "'{0}'".format(name),
              '-Site', "'{0}'".format(site)]

    cmd_ret = _srvmgr(ps_cmd)

    if cmd_ret['retcode'] != 0:
        msg = 'Unable to remove application: {0}\nError: {1}' \
              ''.format(name, cmd_ret['stderr'])
        raise CommandExecutionError(msg)

    new_apps = list_apps(site)

    if name not in new_apps:
        log.debug('Application removed successfully: {0}'.format(name))
        return True

    log.error('Unable to remove application: {0}'.format(name))
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

    ps_cmd = ['Get-WebVirtualDirectory',
              '-Site', r"'{0}'".format(site),
              '-Application', r"'{0}'".format(app),
              '|', "Select-Object PhysicalPath, @{ Name = 'name';",
              r"Expression = { $_.path.Split('/')[-1] } }"]

    cmd_ret = _srvmgr(cmd=ps_cmd, return_json=True)

    try:
        items = json.loads(cmd_ret['stdout'], strict=False)
    except ValueError:
        raise CommandExecutionError('Unable to parse return data as Json.')

    for item in items:
        ret[item['name']] = {'sourcepath': item['physicalPath']}

    if not ret:
        log.warning('No vdirs found in output: {0}'.format(cmd_ret))

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
    current_vdirs = list_vdirs(site, app)

    if name in current_vdirs:
        log.debug('Virtual directory already present: {0}'.format(name))
        return True

    # The target physical path must exist.
    if not os.path.isdir(sourcepath):
        log.error('Path is not present: {0}'.format(sourcepath))
        return False

    ps_cmd = ['New-WebVirtualDirectory',
              '-Name', r"'{0}'".format(name),
              '-Site', r"'{0}'".format(site),
              '-PhysicalPath', r"'{0}'".format(sourcepath)]

    if app != _DEFAULT_APP:
        ps_cmd.extend(['-Application', r"'{0}'".format(app)])

    cmd_ret = _srvmgr(ps_cmd)

    if cmd_ret['retcode'] != 0:
        msg = 'Unable to create virtual directory: {0}\nError: {1}' \
              ''.format(name, cmd_ret['stderr'])
        raise CommandExecutionError(msg)

    new_vdirs = list_vdirs(site, app)

    if name in new_vdirs:
        log.debug('Virtual directory created successfully: {0}'.format(name))
        return True

    log.error('Unable to create virtual directory: {0}'.format(name))
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
    current_vdirs = list_vdirs(site, app)
    app_path = os.path.join(*app.rstrip('/').split('/'))

    if app_path:
        app_path = '{0}\\'.format(app_path)
    vdir_path = r'IIS:\Sites\{0}\{1}{2}'.format(site, app_path, name)

    if name not in current_vdirs:
        log.debug('Virtual directory already absent: {0}'.format(name))
        return True

    # We use Remove-Item here instead of Remove-WebVirtualDirectory, since the
    # latter has a bug that causes it to always prompt for user input.

    ps_cmd = ['Remove-Item',
              '-Path', r"'{0}'".format(vdir_path),
              '-Recurse']

    cmd_ret = _srvmgr(ps_cmd)

    if cmd_ret['retcode'] != 0:
        msg = 'Unable to remove virtual directory: {0}\nError: {1}' \
              ''.format(name, cmd_ret['stderr'])
        raise CommandExecutionError(msg)

    new_vdirs = list_vdirs(site, app)

    if name not in new_vdirs:
        log.debug('Virtual directory removed successfully: {0}'.format(name))
        return True

    log.error('Unable to remove virtual directory: {0}'.format(name))
    return False
