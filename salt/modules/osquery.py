# -*- coding: utf-8 -*-
'''
Support for OSQuery - https://osquery.io
'''
from __future__ import absolute_import

# Import python libs
import json

# Import Salt libs
import salt.utils

import logging
log = logging.getLogger(__name__)


__func_alias__ = {
    'file_': 'file',
    'hash_': 'hash',
    'last_': 'last',
    'time_': 'time',
}


def __virtual__():
    if salt.utils.which('osqueryi'):
        return 'osquery'
    return False


def _table_attrs(table):
    '''
    Helper function to find valid table attributes
    '''
    cmd = 'osqueryi --json "pragma table_info({0})"'.format(table)
    res = __salt__['cmd.run_all'](cmd)
    if res['retcode'] == 0:
        attrs = []
        text = json.loads(res['stdout'])
        for item in text:
            attrs.append(item['name'])
        return attrs
    return False


def _osquery(sql, format='json'):
    '''
    Helper function to run raw osquery queries
    '''
    cmd = 'osqueryi --json "{0}"'.format(sql)
    res = __salt__['cmd.run_all'](cmd)
    if res['retcode'] == 0:
        text = json.loads(res['stdout'])
        return text
    return False


def _osquery_cmd(table, attrs=None, where=None, format='json'):
    '''
    Helper function to run osquery queries
    '''
    if attrs:
        if isinstance(attrs, list):
            valid_attrs = _table_attrs(table)
            if valid_attrs:
                for a in attrs:
                    if a not in valid_attrs:
                        log.error('{0} is not a valid attribute for table {1}'.format(a, table))
                        return False
                _attrs = ','.join(attrs)
            else:
                log.error('Invalid table {0}.'.format(table))
                return False
        else:
            log.error('attrs must be specified as a list.')
            return False
    else:
        _attrs = '*'

    sql = 'select {0} from {1}'.format(_attrs, table)

    if where:
        sql = '{0} where {1}'.format(sql, where)

    sql = '{0};'.format(sql)

    res = _osquery(sql)
    if res:
        return res
    return False


def version():
    '''
    Return version of osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.version
    '''
    res = _osquery_cmd(table='osquery_info', attrs=['version'])
    if res:
        return res[0]['version']
    return False


def rpm_packages(attrs=None, where=None):
    '''
    Return cpuid information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.rpm_packages
    '''
    if __grains__['os_family'] == 'RedHat':
        res = _osquery_cmd(table='rpm_packages', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def kernel_integrity(attrs=None, where=None):
    '''
    Return kernel_integrity information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.kernel_integrity
    '''
    if __grains__['os_family'] == 'RedHat' or __grains__['os_family'] == 'Debian':
        res = _osquery_cmd(table='kernel_integrity', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def kernel_modules(attrs=None, where=None):
    '''
    Return kernel_modules information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.kernel_modules
    '''
    if __grains__['os_family'] == 'RedHat' or __grains__['os_family'] == 'Debian':
        res = _osquery_cmd(table='kernel_modules', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def memory_map(attrs=None, where=None):
    '''
    Return memory_map information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.memory_map
    '''
    if __grains__['os_family'] == 'RedHat' or __grains__['os_family'] == 'Debian':
        res = _osquery_cmd(table='memory_map', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def process_memory_map(attrs=None, where=None):
    '''
    Return process_memory_map information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.process_memory_map
    '''
    if __grains__['os_family'] == 'RedHat' or __grains__['os_family'] == 'Debian':
        res = _osquery_cmd(table='process_memory_map', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def shared_memory(attrs=None, where=None):
    '''
    Return shared_memory information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.shared_memory
    '''
    if __grains__['os_family'] == 'RedHat' or __grains__['os_family'] == 'Debian':
        res = _osquery_cmd(table='shared_memory', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def apt_sources(attrs=None, where=None):
    '''
    Return apt_sources information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.apt_sources
    '''
    if __grains__['os_family'] == 'Debian':
        res = _osquery_cmd(table='apt_sources', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def deb_packages(attrs=None, where=None):
    '''
    Return deb_packages information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.deb_packages
    '''
    if __grains__['os_family'] == 'Debian':
        res = _osquery_cmd(table='deb_packages', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def acpi_tables(attrs=None, where=None):
    '''
    Return acpi_tables information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.acpi_tables
    '''
    res = _osquery_cmd(table='acpi_tables', attrs=attrs, where=where)
    if res:
        return res
    return False


def arp_cache(attrs=None, where=None):
    '''
    Return arp_cache information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.arp_cache
    '''
    res = _osquery_cmd(table='arp_cache', attrs=attrs, where=where)
    if res:
        return res
    return False


def block_devices(attrs=None, where=None):
    '''
    Return block_devices information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.block_devices
    '''
    res = _osquery_cmd(table='block_devices', attrs=attrs, where=where)
    if res:
        return res
    return False


def cpuid(attrs=None, where=None):
    '''
    Return cpuid information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.cpuid
    '''
    res = _osquery_cmd(table='cpuid', attrs=attrs, where=where)
    if res:
        return res
    return False


def crontab(attrs=None, where=None):
    '''
    Return crontab information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.crontab
    '''
    res = _osquery_cmd(table='crontab', attrs=attrs, where=where)
    if res:
        return res
    return False


def etc_hosts(attrs=None, where=None):
    '''
    Return etc_hosts information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.etc_hosts
    '''
    res = _osquery_cmd(table='etc_hosts', attrs=attrs, where=where)
    if res:
        return res
    return False


def etc_services(attrs=None, where=None):
    '''
    Return etc_services information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.etc_services
    '''
    res = _osquery_cmd(table='etc_services', attrs=attrs, where=where)
    if res:
        return res
    return False


def file_changes(attrs=None, where=None):
    '''
    Return file_changes information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.file_changes
    '''
    res = _osquery_cmd(table='file_changes', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def groups(attrs=None, where=None):
    '''
    Return groups information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.groups
    '''
    res = _osquery_cmd(table='groups', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def hardware_events(attrs=None, where=None):
    '''
    Return hardware_events information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.hardware_events
    '''
    res = _osquery_cmd(table='hardware_events', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def interface_addresses(attrs=None, where=None):
    '''
    Return interface_addresses information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.interface_addresses
    '''
    res = _osquery_cmd(table='interface_addresses', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def interface_details(attrs=None, where=None):
    '''
    Return interface_details information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.interface_details
    '''
    res = _osquery_cmd(table='interface_details', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def kernel_info(attrs=None, where=None):
    '''
    Return kernel_info information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.kernel_info
    '''
    res = _osquery_cmd(table='kernel_info', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def last_(attrs=None, where=None):
    '''
    Return last_ information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.last
    '''
    res = _osquery_cmd(table='last', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def listening_ports(attrs=None, where=None):
    '''
    Return listening_ports_ information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.listening_ports
    '''
    res = _osquery_cmd(table='listening_ports', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def logged_in_users(attrs=None, where=None):
    '''
    Return logged_in_users_ information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.logged_in_users
    '''
    res = _osquery_cmd(table='logged_in_users', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def mounts(attrs=None, where=None):
    '''
    Return mounts_ information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.mounts
    '''
    res = _osquery_cmd(table='mounts', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def os_version(attrs=None, where=None):
    '''
    Return os_version information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.os_version
    '''
    res = _osquery_cmd(table='os_version', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def passwd_changes(attrs=None, where=None):
    '''
    Return passwd_changes information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.passwd_changes
    '''
    res = _osquery_cmd(table='passwd_changes', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def pci_devices(attrs=None, where=None):
    '''
    Return pci_devices information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.pci_devices
    '''
    res = _osquery_cmd(table='pci_devices', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def process_envs(attrs=None, where=None):
    '''
    Return process_envs information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.process_envs
    '''
    res = _osquery_cmd(table='process_envs', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def process_open_files(attrs=None, where=None):
    '''
    Return process_open_files information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.process_open_files
    '''
    res = _osquery_cmd(table='process_open_files', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def process_open_sockets(attrs=None, where=None):
    '''
    Return process_open_sockets information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.process_open_sockets
    '''
    res = _osquery_cmd(table='process_open_sockets', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def processes(attrs=None, where=None):
    '''
    Return processes information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.processes
    '''
    res = _osquery_cmd(table='processes', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def routes(attrs=None, where=None):
    '''
    Return routes information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.routes
    '''
    res = _osquery_cmd(table='routes', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def shell_history(attrs=None, where=None):
    '''
    Return shell_history information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.shell_history
    '''
    res = _osquery_cmd(table='shell_history', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def smbios_tables(attrs=None, where=None):
    '''
    Return smbios_tables information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.smbios_tables
    '''
    res = _osquery_cmd(table='smbios_tables', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def suid_bin(attrs=None, where=None):
    '''
    Return suid_bin information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.suid_bin
    '''
    res = _osquery_cmd(table='suid_bin', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def system_controls(attrs=None, where=None):
    '''
    Return system_controls information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.system_controls
    '''
    res = _osquery_cmd(table='system_controls', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def usb_devices(attrs=None, where=None):
    '''
    Return usb_devices information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.usb_devices
    '''
    res = _osquery_cmd(table='usb_devices', attrs=attrs, where=where)
    if res is not False:
        return res
    return False


def users(attrs=None, where=None):
    '''
    Return users information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.users
    '''
    res = _osquery_cmd(table='users', attrs=attrs, where=where)
    if res:
        return res
    return False


def alf(attrs=None, where=None):
    '''
    Return alf information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.alf
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='alf', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def alf_exceptions(attrs=None, where=None):
    '''
    Return alf_exceptions information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.alf_exceptions
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='alf_exceptions', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def alf_explicit_auths(attrs=None, where=None):
    '''
    Return alf_explicit_auths information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.alf_explicit_auths
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='alf_explicit_auths', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def alf_services(attrs=None, where=None):
    '''
    Return alf_services information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.alf_services
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='alf_services', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def apps(attrs=None, where=None):
    '''
    Return apps information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.apps
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='apps', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def certificates(attrs=None, where=None):
    '''
    Return certificates information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.certificates
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='certificates', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def chrome_extensions(attrs=None, where=None):
    '''
    Return chrome_extensions information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.chrome_extensions
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='chrome_extensions', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def firefox_addons(attrs=None, where=None):
    '''
    Return firefox_addons information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.firefox_addons
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='firefox_addons', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def homebrew_packages(attrs=None, where=None):
    '''
    Return homebrew_packages information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.homebrew_packages
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='homebrew_packages', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def iokit_devicetree(attrs=None, where=None):
    '''
    Return iokit_devicetree information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.iokit_devicetree
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='iokit_devicetree', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def iokit_registry(attrs=None, where=None):
    '''
    Return iokit_registry information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.iokit_registry
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='iokit_registry', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def kernel_extensions(attrs=None, where=None):
    '''
    Return kernel_extensions information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.kernel_extensions
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='kernel_extensions', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def keychain_items(attrs=None, where=None):
    '''
    Return keychain_items information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.keychain_items
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='keychain_items', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def launchd(attrs=None, where=None):
    '''
    Return launchd information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.launchd
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='launchd', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def nfs_shares(attrs=None, where=None):
    '''
    Return nfs_shares information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.nfs_shares
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='nfs_shares', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def nvram(attrs=None, where=None):
    '''
    Return nvram information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.nvram
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='nvram', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def preferences(attrs=None, where=None):
    '''
    Return preferences information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.preferences
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='preferences', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def quarantine(attrs=None, where=None):
    '''
    Return quarantine information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.quarantine
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='quarantine', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def safari_extensions(attrs=None, where=None):
    '''
    Return safari_extensions information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.safari_extensions
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='safari_extensions', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def startup_items(attrs=None, where=None):
    '''
    Return startup_items information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.startup_items
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='startup_items', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def xattr_where_from(attrs=None, where=None):
    '''
    Return xattr_where_from information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.xattr_where_from
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='xattr_where_from', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def xprotect_entries(attrs=None, where=None):
    '''
    Return xprotect_entries information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.xprotect_entries
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='xprotect_entries', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def xprotect_reports(attrs=None, where=None):
    '''
    Return xprotect_reports information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.xprotect_reports
    '''
    if salt.utils.is_darwin():
        res = _osquery_cmd(table='xprotect_reports', attrs=attrs, where=where)
        if res:
            return res
        return False
    return False


def file_(attrs=None, where=None):
    '''
    Return file information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.file
    '''
    res = _osquery_cmd(table='file', attrs=attrs, where=where)
    if res:
        return res
    return False


def hash_(attrs=None, where=None):
    '''
    Return hash information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.hash
    '''
    res = _osquery_cmd(table='hash', attrs=attrs, where=where)
    if res:
        return res
    return False


def osquery_extensions(attrs=None, where=None):
    '''
    Return osquery_extensions information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.osquery_extensions
    '''
    res = _osquery_cmd(table='osquery_extensions', attrs=attrs, where=where)
    if res:
        return res
    return False


def osquery_flags(attrs=None, where=None):
    '''
    Return osquery_flags information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.osquery_flags
    '''
    res = _osquery_cmd(table='osquery_flags', attrs=attrs, where=where)
    if res:
        return res
    return False


def osquery_info(attrs=None, where=None):
    '''
    Return osquery_info information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.osquery_info
    '''
    res = _osquery_cmd(table='osquery_info', attrs=attrs, where=where)
    if res:
        return res
    return False


def osquery_registry(attrs=None, where=None):
    '''
    Return osquery_registry information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.osquery_registry
    '''
    res = _osquery_cmd(table='osquery_registry', attrs=attrs, where=where)
    if res:
        return res
    return False


def time_(attrs=None):
    '''
    Return time information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.time
    '''
    res = _osquery_cmd(table='time', attrs=attrs)
    if res:
        return res
    return False


def query(sql=None):
    '''
    Return time information from osquery

    CLI Example:

    .. code-block:: bash

        salt '*' osquery.query "select * from users;"
    '''
    res = _osquery(sql)
    if res:
        return res
    return False
