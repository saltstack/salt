# -*- coding: utf-8 -*-
'''
Module for managing Infoblox

Will look for pillar data infoblox:server, infoblox:user, infoblox:password if not passed to functions

.. versionadded:: 2016.3.0

:depends:
        - requests
'''
from __future__ import absolute_import

# Import salt libs
from salt.exceptions import CommandExecutionError
from salt.exceptions import SaltInvocationError
import logging

log = logging.getLogger(__name__)

try:
    import json
    import requests
    HAS_IMPORTS = True
except ImportError:
    HAS_IMPORTS = False


def __virtual__():
    if HAS_IMPORTS:
        return True
    return (False, 'The infoblox execution module cannot be loaded: '
            'python requests and/or json libraries are not available.')


def _conn_info_check(infoblox_server=None,
                     infoblox_user=None,
                     infoblox_password=None):
    '''
    get infoblox stuff from pillar if not passed
    '''

    if infoblox_server is None:
        infoblox_server = __salt__['pillar.get']('infoblox:server', None)
    if infoblox_user is None:
        infoblox_user = __salt__['pillar.get']('infoblox:user', None)
        log.debug('Infoblox username is "{0}"'.format(infoblox_user))
    if infoblox_password is None:
        infoblox_password = __salt__['pillar.get']('infoblox:password', None)

    return infoblox_server, infoblox_user, infoblox_password


def _process_return_data(retData):
    '''
    generic return processing
    '''
    if retData.status_code == 200:
        if retData.json():
            return retData
        else:
            log.debug('no data returned from infoblox')
            return None
    else:
        msg = 'Unsuccessful error code {0} returned'.format(retData.status_code)
        raise CommandExecutionError(msg)
    return None


def delete_record(name,
                  dns_view,
                  record_type,
                  infoblox_server=None,
                  infoblox_user=None,
                  infoblox_password=None,
                  infoblox_api_version='v1.4.2',
                  sslVerify=True):
    '''
    delete a record

    name
        name of the record

    dns_view
        the DNS view to remove the record from

    record_type
        the record type (a, cname, host, etc)

    infoblox_server
        the infoblox server hostname (can also use the infoblox:server pillar)

    infoblox_user
        the infoblox user to connect with (can also use the infoblox:user pillar)

    infoblox_password
        the infoblox user's password (can also use the infolblox:password pillar)

    infoblox_api_version
        the infoblox api verison to use

    sslVerify
        should ssl verification be done on the connection to the Infoblox REST API

    CLI Example:

    .. code-block:: bash

        salt my-minion infoblox.delete_record some.dns.record MyInfobloxView A sslVerify=False
    '''
    infoblox_server, infoblox_user, infoblox_password = _conn_info_check(infoblox_server,
                                                                         infoblox_user,
                                                                         infoblox_password)
    if infoblox_server is None and infoblox_user is None and infoblox_password is None:
        _throw_no_creds()
        return None

    record_type = record_type.lower()
    currentRecords = get_record(name,
                                record_type,
                                infoblox_server,
                                infoblox_user,
                                infoblox_password,
                                dns_view,
                                infoblox_api_version,
                                sslVerify)
    if currentRecords:
        for currentRecord in currentRecords:
            url = 'https://{0}/wapi/{1}/{2}'.format(infoblox_server,
                                                    infoblox_api_version,
                                                    currentRecord['Record ID'])
            ret = requests.delete(url,
                                  auth=(infoblox_user, infoblox_password),
                                  headers={'Content-Type': 'application/json'},
                                  verify=sslVerify)
            if ret.status_code == 200:
                return True
            else:
                msg = 'Unsuccessful error code {0} returned -- full json dump {1}'.format(ret.status_code, ret.json())
                raise CommandExecutionError(msg)
    return False


def update_record(name,
                  value,
                  dns_view,
                  record_type,
                  infoblox_server=None,
                  infoblox_user=None,
                  infoblox_password=None,
                  infoblox_api_version='v1.4.2',
                  sslVerify=True):
    '''
    update an entry to an infoblox dns view

    name
        the dns name

    value
        the value for the record

    record_type
        the record type (a, cname, etc)

    dns_view
        the DNS view to add the record to

    infoblox_server
        the infoblox server hostname (can also use the infoblox:server pillar)

    infoblox_user
        the infoblox user to connect with (can also use the infoblox:user pillar)

    infoblox_password
        the infoblox user's password (can also use the infolblox:password pillar)

    infoblox_api_version
        the infoblox api verison to use

    sslVerify
        should ssl verification be done on the connection to the Infoblox REST API

    CLI Example:

    .. code-block:: bash

        salt '*' infoblox.update_record alias.network.name canonical.network.name MyInfobloxView cname sslVerify=False
    '''

    infoblox_server, infoblox_user, infoblox_password = _conn_info_check(infoblox_server,
                                                                         infoblox_user,
                                                                         infoblox_password)
    if infoblox_server is None and infoblox_user is None and infoblox_password is None:
        _throw_no_creds()
        return None

    record_type = record_type.lower()
    currentRecords = get_record(name,
                                record_type,
                                infoblox_server,
                                infoblox_user,
                                infoblox_password,
                                dns_view,
                                infoblox_api_version,
                                sslVerify)
    if currentRecords:
        for currentRecord in currentRecords:
            url = 'https://{0}/wapi/{1}/{2}'.format(
                infoblox_server,
                infoblox_api_version,
                currentRecord['Record ID'])
            data = None
            if record_type == 'cname':
                data = json.dumps({'canonical': value})
            elif record_type == 'a':
                data = json.dumps({'ipv4addr': value})
            elif record_type == 'host':
                data = {'ipv4addrs': []}
                for i in value:
                    data['ipv4addrs'].append({'ipv4addr': i})
                data = json.dumps(data)
            ret = requests.put(url,
                               data,
                               auth=(infoblox_user, infoblox_password),
                               headers={'Content-Type': 'application/json'},
                               verify=sslVerify)
            if ret.status_code == 200:
                return True
            else:
                msg = 'Unsuccessful status code {0} returned.'.format(ret.status_code)
                raise CommandExecutionError(msg)
    else:
        msg = 'Record {0} of type {1} was not found'.format(name, record_type)
        log.error(msg)
        return False


def add_record(name,
               value,
               record_type,
               dns_view,
               infoblox_server=None,
               infoblox_user=None,
               infoblox_password=None,
               infoblox_api_version='v1.4.2',
               sslVerify=True):
    '''
    add a record to an infoblox dns view

    name
        the record name

    value
        the value for the entry
            can make use of infoblox functions for next available IP, like 'func:nextavailableip:10.1.0.0/24'

    record_type
        the record type (cname, a, host, etc)

    dns_view
        the DNS view to add the record to

    infoblox_server
        the infoblox server hostname (can also use the infoblox:server pillar)

    infoblox_user
        the infoblox user to connect with (can also use the infoblox:user pillar)

    infoblox_password
        the infoblox user's password (can also use the infolblox:password pillar)

    infoblox_api_version
        the infoblox api verison to use

    sslVerify
        should ssl verification be done on the connection to the Infoblox REST API

    CLI Example:

    .. code-block:: bash

        salt 'myminion' infoblox.add_record alias.network.name canonical.network.name MyView
    '''

    infoblox_server, infoblox_user, infoblox_password = _conn_info_check(infoblox_server,
                                                                         infoblox_user,
                                                                         infoblox_password)
    if infoblox_server is None and infoblox_user is None and infoblox_password is None:
        _throw_no_creds()
        return None

    record_type = record_type.lower()

    data = None
    url = None
    if record_type == 'cname':
        data = json.dumps({'name': name, 'canonical': value, 'view': dns_view})
        log.debug('cname data {0}'.format(data))
    elif record_type == 'host':
        data = json.dumps({'name': name, 'ipv4addrs': [{'ipv4addr': value}], 'view': dns_view})
        log.debug('host record data {0}'.format(data))
    elif record_type == 'a':
        data = json.dumps({'name': name, 'ipv4addr': value, 'view': dns_view})
        log.debug('a record data {0}'.format(data))

    url = 'https://{0}/wapi/{1}/record:{2}'.format(infoblox_server,
                                                   infoblox_api_version,
                                                   record_type)

    ret = requests.post(url,
                        data,
                        auth=(infoblox_user, infoblox_password),
                        headers={'Content-Type': 'application/json'},
                        verify=sslVerify)
    if ret.status_code == 201:
        return True
    else:
        msg = 'Unsuccessful error code {0} returned -- full json dump {1}'.format(ret.status_code, ret.json())
        raise CommandExecutionError(msg)


def _throw_no_creds():
    '''
    helper function to log no credentials found error
    '''
    msg = 'An infoblox server, username, and password must be specified or configured via pillar'
    raise SaltInvocationError(msg)


def get_network(network_name,
                network_view=None,
                infoblox_server=None,
                infoblox_user=None,
                infoblox_password=None,
                infoblox_api_version='v1.4.2',
                sslVerify=True):
    '''
    get a network from infoblox

    network_name
        The name of the network in IPAM

    network_view
        The name of the network view the network belongs to

    infoblox_server
        the infoblox server hostname (can also use the infoblox:server pillar)

    infoblox_user
        the infoblox user to connect with (can also use the infoblox:user pillar)

    infoblox_password
        the infoblox user's password (can also use the infolblox:password pillar)

    infoblox_api_version
        the infoblox api verison to use

    sslVerify
        should ssl verification be done on the connection to the Infoblox REST API

    CLI Example:

    .. code-block:: bash

        salt myminion infoblox.get_network '10.0.0.0/8'
    '''

    records = []
    infoblox_server, infoblox_user, infoblox_password = _conn_info_check(infoblox_server,
                                                                         infoblox_user,
                                                                         infoblox_password)
    if infoblox_server is None and infoblox_user is None and infoblox_password is None:
        _throw_no_creds()
        return None

    url = 'https://{0}/wapi/{1}/network?network={2}{3}'.format(
        infoblox_server,
        infoblox_api_version,
        network_name,
        ('' if network_view is None else '&network_view=' + network_view))
    log.debug('Requst url is "{0}"'.format(url))
    ret = _process_return_data(requests.get(url,
                                            auth=(infoblox_user, infoblox_password),
                                            verify=sslVerify))
    if ret:
        for entry in ret.json():
            log.debug('Infoblox record returned: {0}'.format(entry))
            tEntry = {}
            data = _parse_record_data(entry)
            for key in data.keys():
                tEntry[key] = data[key]
            records.append(tEntry)
        return records
    else:
        return False
    return False


def get_record(record_name,
               record_type='host',
               infoblox_server=None,
               infoblox_user=None,
               infoblox_password=None,
               dns_view=None,
               infoblox_api_version='v1.4.2',
               sslVerify=True):
    '''
    get a record from infoblox

    record_name
        name of the record to search for

    record_type
        type of reacord to search for (host, cname, a, etc...defaults to host)

    infoblox_server
        the infoblox server hostname (can also use the infoblox:server pillar)

    infoblox_user
        the infoblox user to connect with (can also use the infoblox:user pillar)

    infoblox_password
        the infoblox user's password (can also use the infolblox:password pillar)

    dns_view
        the infoblox DNS view to search, if not specified all views are searched

    infoblox_api_version
        the infoblox api verison to use

    sslVerify
        should ssl verification be done on the connection to the Infoblox REST API

    CLI Example:

    .. code-block:: bash

        salt myminion infoblox.get_record some.host.com A sslVerify=False
    '''

    # TODO - verify record type (A, AAAA, CNAME< HOST, MX, PTR, SVR, TXT, host_ipv4addr, host_ipv6addr, naptr)
    records = []

    infoblox_server, infoblox_user, infoblox_password = _conn_info_check(infoblox_server,
                                                                         infoblox_user,
                                                                         infoblox_password)

    record_type = record_type.lower()
    if infoblox_server is None and infoblox_user is None and infoblox_password is None:
        _throw_no_creds()
        return None

    url = 'https://{0}/wapi/{1}/record:{3}?name:={2}{4}{5}'.format(
        infoblox_server,
        infoblox_api_version,
        record_name,
        record_type,
        ('' if dns_view is None else '&view=' + dns_view),
        ('&_return_fields%2B=aliases' if record_type == 'host' else '')
        )
    log.debug('Requst url is "{0}"'.format(url))
    ret = _process_return_data(requests.get(url,
                                            auth=(infoblox_user, infoblox_password),
                                            verify=sslVerify))
    if ret:
        for entry in ret.json():
            log.debug('Infoblox record returned: {0}'.format(entry))
            tEntry = {}
            data = _parse_record_data(entry)
            for key in data.keys():
                tEntry[key] = data[key]
            records.append(tEntry)
        return records
    else:
        return False
    return False


def _parse_record_data(entry_data):
    '''
    returns the right value data we'd be interested in for the specified record type
    '''

    ret = {}
    ipv4addrs = []
    aliases = []
    if 'canonical' in entry_data:
        ret['Canonical Name'] = entry_data['canonical']
    if 'ipv4addrs' in entry_data:
        for ipaddrs in entry_data['ipv4addrs']:
            ipv4addrs.append(ipaddrs['ipv4addr'])
        ret['IP Addresses'] = ipv4addrs
    if 'ipv4addr' in entry_data:
        ret['IP Address'] = entry_data['ipv4addr']
    if 'aliases' in entry_data:
        for alias in entry_data['aliases']:
            aliases.append(alias)
        ret['Aliases'] = aliases
    if 'name' in entry_data:
        ret['Name'] = entry_data['name']
    if 'view' in entry_data:
        ret['DNS View'] = entry_data['view']
    if 'network_view' in entry_data:
        ret['Network View'] = entry_data['network_view']
    if 'comment' in entry_data:
        ret['Comment'] = entry_data['comment']
    if 'network' in entry_data:
        ret['Network'] = entry_data['network']
    if '_ref' in entry_data:
        ret['Record ID'] = entry_data['_ref']
    return ret
