# -*- coding: utf-8 -*-
'''
Microsoft certificate management via the Pki PowerShell module.

:platform:      Windows

.. versionadded:: Carbon
'''

# Import python libs
from __future__ import absolute_import
import json
import logging

# Import salt libs
from salt.exceptions import SaltInvocationError
import ast
import os
import salt.utils

_DEFAULT_CONTEXT = 'LocalMachine'
_DEFAULT_FORMAT = 'cer'
_DEFAULT_STORE = 'My'
_LOG = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'win_pki'


def __virtual__():
    '''
    Only works on Windows systems with the PKI PowerShell module installed.
    '''

    def _module_present():
        '''
        Check for the presence of the PKI module.
        '''
        cmd = r"[Bool] (Get-Module -ListAvailable | Where-Object { $_.Name -eq 'PKI' })"
        cmd_ret = __salt__['cmd.run_all'](cmd, shell='powershell', python_shell=True)

        if cmd_ret['retcode'] == 0:
            return ast.literal_eval(cmd_ret['stdout'])
        return False

    if salt.utils.is_windows():
        if _module_present():
            return __virtualname__
        else:
            _LOG.debug('PowerShell PKI module not available.')
    return False


def _cmd_run(cmd, as_json=False):
    '''
    Ensure that the Pki module is loaded, and convert to and extract data from Json as needed.
    '''
    cmd_full = ['Import-Module -Name PKI; ']

    if as_json:
        cmd_full.append(r'ConvertTo-Json -Compress -Depth 4 -InputObject @({0})'.format(cmd))
    else:
        cmd_full.append(cmd)
    cmd_ret = __salt__['cmd.run_all'](str().join(cmd_full), shell='powershell', python_shell=True)

    if cmd_ret['retcode'] != 0:
        _LOG.error('Unable to execute command: %s\nError: %s', cmd, cmd_ret['stderr'])

    if as_json:
        try:
            items = json.loads(cmd_ret['stdout'], strict=False)
        except ValueError:
            _LOG.error('Unable to parse return data as Json.')
        return items
    return cmd_ret['stdout']


def _validate_cert_path(name):
    '''
    Ensure that the certificate path, as determind from user input, is valid.
    '''
    cmd = r"Test-Path -Path '{0}'".format(name)

    if not ast.literal_eval(_cmd_run(cmd=cmd)):
        raise SaltInvocationError(r"Invalid path specified: {0}".format(name))


def _validate_cert_format(name):
    '''
    Ensure that the certificate format, as determind from user input, is valid.
    '''
    cert_formats = ['cer', 'pfx']

    if name not in cert_formats:
        message = ("Invalid certificate format '{0}' specified. Valid formats:"
                   ' {1}').format(name, cert_formats)
        raise SaltInvocationError(message)


def get_stores():
    '''
    Get the certificate location contexts and their corresponding stores.

    :return: A dictionary of the certificate location contexts and stores.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' win_pki.get_stores
    '''
    ret = dict()
    cmd = r"Get-ChildItem -Path 'Cert:\' | Select-Object LocationName, StoreNames"

    items = _cmd_run(cmd=cmd, as_json=True)

    for item in items:
        ret[item['LocationName']] = list()

        for store in item['StoreNames']:
            ret[item['LocationName']].append(store)
    return ret


def get_certs(context=_DEFAULT_CONTEXT, store=_DEFAULT_STORE):
    '''
    Get the available certificates in the given store.

    :param str context: The name of the certificate store location context.
    :param str store: The name of the certificate store.

    :return: A dictionary of the certificate thumbprints and properties.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' win_pki.get_certs
    '''
    ret = dict()
    cmd = list()
    blacklist_keys = ['DnsNameList']
    store_path = r'Cert:\{0}\{1}'.format(context, store)

    _validate_cert_path(name=store_path)

    cmd.append(r"Get-ChildItem -Path '{0}' | Select-Object".format(store_path))
    cmd.append(' DnsNameList, SerialNumber, Subject, Thumbprint, Version')

    items = _cmd_run(cmd=str().join(cmd), as_json=True)

    for item in items:
        cert_info = dict()
        for key in item:
            if key not in blacklist_keys:
                cert_info[key.lower()] = item[key]

        cert_info['dnsnames'] = [name['Unicode'] for name in item['DnsNameList']]
        ret[item['Thumbprint']] = cert_info
    return ret


def get_cert_file(name, cert_format=_DEFAULT_FORMAT):
    '''
    Get the details of the certificate file.

    :param str name: The filesystem path of the certificate file.
    :param str cert_format: The certificate format. Specify 'cer' for X.509, or 'pfx' for PKCS #12.

    :return: A dictionary of the certificate thumbprints and properties.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' win_pki.get_cert_file name='C:\\certs\\example.cer'
    '''
    ret = dict()
    cmd = list()
    blacklist_keys = ['DnsNameList']
    cert_format = cert_format.lower()

    _validate_cert_format(name=cert_format)

    if not name or not os.path.isfile(name):
        _LOG.error('Path is not present: %s', name)
        return ret

    if cert_format == 'pfx':
        cmd.append(r"Get-PfxCertificate -FilePath '{0}'".format(name))
        cmd.append(' | Select-Object DnsNameList, SerialNumber, Subject, Thumbprint, Version')
    else:
        cmd.append('$CertObject = New-Object')
        cmd.append(' System.Security.Cryptography.X509Certificates.X509Certificate2;')
        cmd.append(r" $CertObject.Import('{0}'); $CertObject".format(name))
        cmd.append(' | Select-Object DnsNameList, SerialNumber, Subject, Thumbprint, Version')

    items = _cmd_run(cmd=str().join(cmd), as_json=True)

    for item in items:
        for key in item:
            if key not in blacklist_keys:
                ret[key.lower()] = item[key]

        ret['dnsnames'] = [name['Unicode'] for name in item['DnsNameList']]

    if ret:
        _LOG.debug('Certificate thumbprint obtained successfully: %s', name)
    else:
        _LOG.error('Unable to obtain certificate thumbprint: %s', name)
    return ret


def import_cert(name, cert_format=_DEFAULT_FORMAT, context=_DEFAULT_CONTEXT, store=_DEFAULT_STORE,
                exportable=True, password='', saltenv='base'):
    '''
    Import the certificate file into the given certificate store.

    :param str name: The path of the certificate file to import.
    :param str cert_format: The certificate format. Specify 'cer' for X.509, or 'pfx' for PKCS #12.
    :param str context: The name of the certificate store location context.
    :param str store: The name of the certificate store.
    :param bool exportable: Mark the certificate as exportable. Only applicable to pfx format.
    :param str password: The password of the certificate. Only applicable to pfx format.
    :param str saltenv: The environment the file resides in.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_pki.import_cert name='salt://cert.cer'
    '''
    cmd = list()
    thumbprint = None
    store_path = r'Cert:\{0}\{1}'.format(context, store)
    cert_format = cert_format.lower()

    _validate_cert_format(name=cert_format)

    cached_source_path = __salt__['cp.cache_file'](name, saltenv)

    if not cached_source_path:
        _LOG.error('Unable to get cached copy of file: %s', name)
        return False

    cert_props = get_cert_file(name=cached_source_path)

    current_certs = get_certs(context=context, store=store)

    if cert_props['thumbprint'] in current_certs:
        _LOG.debug("Certificate thumbprint '%s' already present in store: %s",
                   cert_props['thumbprint'], store_path)
        return True

    if cert_format == 'pfx':
        # In instances where an empty password is needed, we use a System.Security.SecureString
        # object since ConvertTo-SecureString will not convert an empty string.
        if password:
            cmd.append(r"$Password = ConvertTo-SecureString -String '{0}'".format(password))
            cmd.append(' -AsPlainText -Force; ')
        else:
            cmd.append('$Password = New-Object System.Security.SecureString; ')

        cmd.append(r"Import-PfxCertificate -FilePath '{0}'".format(cached_source_path))
        cmd.append(r" -CertStoreLocation '{0}' -Password $Password".format(store_path))

        if exportable:
            cmd.append(' -Exportable')
    else:
        cmd.append(r"Import-Certificate -FilePath '{0}'".format(cached_source_path))
        cmd.append(r" -CertStoreLocation '{0}'".format(store_path))

    _cmd_run(cmd=str().join(cmd))

    new_certs = get_certs(context=context, store=store)

    for new_cert in new_certs:
        if new_cert not in current_certs:
            thumbprint = new_cert

    if thumbprint:
        _LOG.debug('Certificate imported successfully: %s', name)
        return True
    _LOG.error('Unable to import certificate: %s', name)
    return False


def export_cert(name, thumbprint, cert_format=_DEFAULT_FORMAT, context=_DEFAULT_CONTEXT,
                store=_DEFAULT_STORE, password=''):
    '''
    Export the certificate to a file from the given certificate store.

    :param str name: The destination path for the exported certificate file.
    :param str thumbprint: The thumbprint value of the target certificate.
    :param str cert_format: The certificate format. Specify 'cer' for X.509, or 'pfx' for PKCS #12.
    :param str context: The name of the certificate store location context.
    :param str store: The name of the certificate store.
    :param str password: The password of the certificate. Only applicable to pfx format.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_pki.export_cert name='C:\\certs\\example.cer' thumbprint='AAA000'
    '''
    cmd = list()
    thumbprint = thumbprint.upper()
    cert_path = r'Cert:\{0}\{1}\{2}'.format(context, store, thumbprint)
    cert_format = cert_format.lower()

    _validate_cert_path(name=cert_path)
    _validate_cert_format(name=cert_format)

    if cert_format == 'pfx':
        # In instances where an empty password is needed, we use a System.Security.SecureString
        # object since ConvertTo-SecureString will not convert an empty string.
        if password:
            cmd.append(r"$Password = ConvertTo-SecureString -String '{0}'".format(password))
            cmd.append(' -AsPlainText -Force; ')
        else:
            cmd.append('$Password = New-Object System.Security.SecureString; ')

        cmd.append(r"Export-PfxCertificate -Cert '{0}' -FilePath '{1}'".format(cert_path, name))
        cmd.append(r" -Password $Password")
    else:
        cmd.append(r"Export-Certificate -Cert '{0}' -FilePath '{1}'".format(cert_path, name))

    cmd.append(r" | Out-Null; Test-Path -Path '{0}'".format(name))

    ret = ast.literal_eval(_cmd_run(cmd=str().join(cmd)))

    if ret:
        _LOG.debug('Certificate exported successfully: %s', name)
    else:
        _LOG.error('Unable to export certificate: %s', name)
    return ret


def test_cert(thumbprint, context=_DEFAULT_CONTEXT, store=_DEFAULT_STORE, untrusted_root=False,
              dns_name='', eku=''):
    '''
    Check the certificate for validity.

    :param str thumbprint: The thumbprint value of the target certificate.
    :param str context: The name of the certificate store location context.
    :param str store: The name of the certificate store.
    :param bool untrusted_root: Whether the root certificate is required to be trusted in chain building.
    :param str dns_name: The DNS name to verify as valid for the certificate.
    :param str eku: The enhanced key usage object identifiers to verify for the certificate chain.

    :return: A boolean representing whether the certificate was considered valid.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_pki.test_cert thumbprint='AAA000' dns_name='example.test'
    '''
    cmd = list()
    thumbprint = thumbprint.upper()
    cert_path = r'Cert:\{0}\{1}\{2}'.format(context, store, thumbprint)
    cmd.append(r"Test-Certificate -Cert '{0}'".format(cert_path))

    _validate_cert_path(name=cert_path)

    if untrusted_root:
        cmd.append(' -AllowUntrustedRoot')
    if dns_name:
        cmd.append(" -DnsName '{0}'".format(dns_name))
    if eku:
        cmd.append(" -EKU '{0}'".format(eku))

    cmd.append(' -ErrorAction SilentlyContinue')

    return ast.literal_eval(_cmd_run(cmd=str().join(cmd)))


def remove_cert(thumbprint, context=_DEFAULT_CONTEXT, store=_DEFAULT_STORE):
    '''
    Remove the certificate from the given certificate store.

    :param str thumbprint: The thumbprint value of the target certificate.
    :param str context: The name of the certificate store location context.
    :param str store: The name of the certificate store.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_pki.remove_cert thumbprint='AAA000'
    '''
    thumbprint = thumbprint.upper()
    store_path = r'Cert:\{0}\{1}'.format(context, store)
    cert_path = r'{0}\{1}'.format(store_path, thumbprint)
    cmd = r"Remove-Item -Path '{0}'".format(cert_path)

    current_certs = get_certs(context=context, store=store)

    if thumbprint not in current_certs:
        _LOG.debug("Certificate '%s' already absent in store: %s", thumbprint, store_path)
        return True

    _validate_cert_path(name=cert_path)
    _cmd_run(cmd=cmd)

    new_certs = get_certs(context=context, store=store)

    if thumbprint in new_certs:
        _LOG.error('Unable to remove certificate: %s', cert_path)
        return False
    _LOG.debug('Certificate removed successfully: %s', cert_path)
    return True
