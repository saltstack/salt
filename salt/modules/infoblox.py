# -*- coding: utf-8 -*-
'''
This moduile have been tested on infoblox API v1.2.1,
other versions of the API are likly workable.

:depends: libinfoblox, https://github.com/steverweber/libinfoblox

    libinfoblox can be installed using `pip install libinfoblox`

API documents can be found on your infoblox server at:

    https://INFOBLOX/wapidoc

:configuration: The following configuration defaults can be
    define (pillar or config files '/etc/salt/master.d/infoblox.conf'):

    .. code-block:: python

        infoblox.config:
            api_sslverify: True
            api_url: 'https://INFOBLOX/wapi/v1.2.1'
            api_user: 'username'
            api_key: 'password'

    Many of the functions accept `kwargs` to override the API config.

    .. code-block:: bash

        salt-call infoblox.get_host name=my.host.com \
            api_url: 'https://INFOBLOX/wapi/v1.2.1' \
            api_user=admin \
            api_key=passs

'''
from __future__ import absolute_import


import time
IMPORT_ERR = None
try:
    import libinfoblox
except Exception as ex:
    IMPORT_ERR = str(ex)
__virtualname__ = 'infoblox'


def __virtual__():
    return (IMPORT_ERR is None, IMPORT_ERR)


cache = {}


def _get_config(**kwargs):
    '''
    Return configuration
    user passed kwargs override salt config.get vars
    '''
    config = {
        'api_sslverify': True,
        'api_url': 'https://INFOBLOX/wapi/v1.2.1',
        'api_user': '',
        'api_key': '',
    }
    if '__salt__' in globals():
        config_key = '{0}.config'.format(__virtualname__)
        config.update(__salt__['config.get'](config_key, {}))
    # pylint: disable=C0201
    for k in set(config.keys()) & set(kwargs.keys()):
        config[k] = kwargs[k]
    return config


def _get_infoblox(**kwargs):
    config = _get_config(**kwargs)
    # TODO: perhaps cache in __opts__
    cache_key = 'infoblox_session_{0},{1},{2}'.format(
        config['api_url'], config['api_user'], config['api_key'])
    if cache_key in cache:
        timedelta = int(time.time()) - cache[cache_key]['time']
        if cache[cache_key]['obj'] and timedelta < 60:
            return cache[cache_key]['obj']
    c = {}
    c['time'] = int(time.time())
    c['obj'] = libinfoblox.Session(api_sslverify=config['api_sslverify'], api_url=config['api_url'],
                                   api_user=config['api_user'], api_key=config['api_key'])
    cache[cache_key] = c
    return c['obj']


def diff_objects(obja, objb):
    '''
    Diff two complex infoblox objects.
    This is used from salt states to detect changes in objects.

    Using `func:nextavailableip` will not cause a diff if the ipaddres is in range
    '''
    return libinfoblox.diff_obj(obja, objb)


def is_ipaddr_in_ipfunc_range(ipaddr, ipfunc):
    '''
    Return true if the ipaddress is in the range of the nextavailableip function

    CLI Example:

        salt-call infoblox.is_ipaddr_in_ipfunc_range \
            ipaddr="10.0.2.2" ipfunc="func:nextavailableip:10.0.0.0/8"
    '''
    return libinfoblox.is_ipaddr_in_ipfunc_range(ipaddr, ipfunc)


def update_host(name, data, **kwargs):
    '''
    Update host record. This is a helper call to update_object.

    Find a hosts `_ref` then call update_object with the record data.

    CLI Example:

        salt-call infoblox.update_host name=fqdn data={}
    '''
    o = get_host(name=name, **kwargs)
    return update_object(objref=o['_ref'], data=data, **kwargs)


def update_object(objref, data, **kwargs):
    '''
    Update raw infoblox object.
    This is a low level api call.

    CLI Example:

    .. code-block:: bash

        salt-call infoblox.update_object objref=[ref_of_object] data={}
    '''
    if '__opts__' in globals() and __opts__['test']:
        return {'Test': 'Would attempt to update object: {0}'.format(objref)}
    infoblox = _get_infoblox(**kwargs)
    return infoblox.update_object(objref, data)


def delete_object(objref, **kwargs):
    '''
    Delete infoblox object.
    This is a low level api call.

    CLI Example:

        salt-call infoblox.delete_object objref=[ref_of_object]
    '''
    if '__opts__' in globals() and __opts__['test']:
        return {'Test': 'Would attempt to delete object: {0}'.format(objref)}
    infoblox = _get_infoblox(**kwargs)
    return infoblox.delete_object(objref)


def create_object(object_type, data, **kwargs):
    '''
    Create raw infoblox object
    This is a low level api call.

    CLI Example:

        salt-call infoblox.update_object object_type=record:host  data={}
    '''
    if '__opts__' in globals() and __opts__['test']:
        return {'Test': 'Would attempt to create object: {0}'.format(object_type)}
    infoblox = _get_infoblox(**kwargs)
    return infoblox.create_object(object_type, data)


def get_object(objref, data=None, return_fields=None, max_results=None,
               ensure_none_or_one_result=False, **kwargs):
    '''
    Get raw infoblox object.
    This is a low level api call.

    CLI Example:

        salt-call infoblox.get_object objref=[_ref of object]
    '''
    if not data:
        data = {}
    infoblox = _get_infoblox(**kwargs)
    return infoblox.get_object(objref, data, return_fields,
                               max_results, ensure_none_or_one_result)


def create_cname(data, **kwargs):
    '''
    Create a cname record.

    CLI Example:

        salt-call infoblox.create_cname data={ \
            "comment": "cname to example server", \
            "name": "example.example.com", \
            "zone": "example.com", \
            "view": "Internal", \
            "canonical": "example-ha-0.example.com" \
        }
    '''
    infoblox = _get_infoblox(**kwargs)
    host = infoblox.create_cname(data=data)
    return host


def get_cname(name=None, canonical=None, return_fields=None, **kwargs):
    '''
    Get cname information.

    CLI Example:

        salt-call infoblox.get_cname name=example.example.com
        salt-call infoblox.get_cname canonical=example-ha-0.example.com
    '''
    infoblox = _get_infoblox(**kwargs)
    o = infoblox.get_cname(name=name, canonical=canonical, return_fields=return_fields)
    return o


def update_cname(name, data, **kwargs):
    '''
    Update cname. This is a helper call to update_object.

    Find a cname `_ref` then call update_object with the record data.

    CLI Example:

        salt-call infoblox.update_cname name=example.example.com data="{
                'canonical':'example-ha-0.example.com',
                'use_ttl':true,
                'ttl':200,
                'comment':'Salt managed cname'}"
    '''
    o = get_cname(name=name, **kwargs)
    if not o:
        raise Exception('Cname record not found')
    return update_object(objref=o['_ref'], data=data, **kwargs)


def delete_cname(name=None, canonical=None, **kwargs):
    '''
    Delete cname. This is a helper call to delete_object.

    If record is not found, return True

    CLI Example:

        salt-call infoblox.delete_cname name=example.example.com
        salt-call infoblox.delete_cname canonical=example-ha-0.example.com
    '''
    cname = get_cname(name=name, canonical=canonical, **kwargs)
    if cname:
        return delete_object(cname['_ref'], **kwargs)
    return True


def get_host(name=None, ipv4addr=None, mac=None, return_fields=None, **kwargs):
    '''
    Get host information

    CLI Example:

        salt-call infoblox.get_host hostname.domain.ca
        salt-call infoblox.get_host ipv4addr=123.123.122.12
        salt-call infoblox.get_host mac=00:50:56:84:6e:ae

        return_fields=
        https://INFOBLOX/wapidoc/objects/record.host.html#fields-list

        return_fields='ipv4addrs,aliases,name,configure_for_dns,extattrs,disable,view,comment,zone'
    '''
    infoblox = _get_infoblox(**kwargs)
    host = infoblox.get_host(name=name, mac=mac, ipv4addr=ipv4addr, return_fields=return_fields)
    return host


def get_host_advanced(name=None, ipv4addr=None, mac=None, **kwargs):
    '''
    Get all host information

    CLI Example:

        salt-call infoblox.get_host_advanced hostname.domain.ca
    '''
    infoblox = _get_infoblox(**kwargs)
    host = infoblox.get_host_advanced(name=name, mac=mac, ipv4addr=ipv4addr)
    return host


def get_host_domainname(name, domains=None, **kwargs):
    '''
    Get host domain name

    If no domains are passed, the hostname is checked for a zone in infoblox, if no zone split on first dot.

    If domains are provided, the best match out of the list is returned.

    If none are found the return is None

    dots at end of names are ignored.

    CLI Example:

        salt-call uwl.get_host_domainname name=localhost.t.domain.com \
            domains=['domain.com', 't.domain.com.']

        # returns: t.domain.com
    '''
    name = name.lower().rstrip('.')
    if not domains:
        data = get_host(name=name, **kwargs)
        if data and 'zone' in data:
            return data['zone'].lower()
        else:
            if name.count('.') > 1:
                return name[name.find('.')+1:]
            return name
    match = ''
    for d in domains:
        d = d.lower().rstrip('.')
        if name.endswith(d) and len(d) > len(match):
            match = d
    if len(match) > 0:
        return match
    return None


def get_host_hostname(name, domains=None, **kwargs):
    '''
    Get hostname

    If no domains are passed, the hostname is checked for a zone in infoblox, if no zone split on first dot.

    If domains are provided, the best match out of the list is truncated from the fqdn leaving the hostname.

    If no matching domains are found the fqdn is returned.

    dots at end of names are ignored.

    CLI Example:

        salt-call infoblox.get_host_hostname fqdn=localhost.xxx.t.domain.com \
            domains="['domain.com', 't.domain.com']"
        #returns: localhost.xxx

        salt-call infoblox.get_host_hostname fqdn=localhost.xxx.t.domain.com
        #returns: localhost
    '''
    name = name.lower().rstrip('.')
    if not domains:
        return name.split('.')[0]
    domain = get_host_domainname(name, domains, **kwargs)
    if domain and domain in name:
        return name.rsplit('.' + domain)[0]
    return name


def get_host_mac(name=None, allow_array=False, **kwargs):
    '''
    Get mac address from host record.

    Use `allow_array` to return possible mutiple values.

    CLI Example:

        salt-call infoblox.get_host_mac host=localhost.domain.com
    '''
    data = get_host(name=name, **kwargs)
    if data and 'ipv4addrs' in data:
        l = []
        for a in data['ipv4addrs']:
            if 'mac' in a:
                l.append(a['mac'])
        if allow_array:
            return l
        if l:
            return l[0]
    return None


def get_host_ipv4(name=None, mac=None, allow_array=False, **kwargs):
    '''
    Get ipv4 address from host record.

    Use `allow_array` to return possible mutiple values.

    CLI Example:

        salt-call infoblox.get_host_ipv4 host=localhost.domain.com
        salt-call infoblox.get_host_ipv4 mac=00:50:56:84:6e:ae
    '''
    data = get_host(name=name, mac=mac, **kwargs)
    if data and 'ipv4addrs' in data:
        l = []
        for a in data['ipv4addrs']:
            if 'ipv4addr' in a:
                l.append(a['ipv4addr'])
        if allow_array:
            return l
        if l:
            return l[0]
    return None


def get_host_ipv4addr_info(ipv4addr=None, mac=None,
                                        discovered_data=None,
                                        return_fields=None, **kwargs):
    '''
    Get host ipv4addr information

    return_fields='mac,host,configure_for_dhcp,ipv4addr'

    CLI Example:

        salt-call infoblox.get_ipv4addr ipv4addr=123.123.122.12
        salt-call infoblox.get_ipv4addr mac=00:50:56:84:6e:ae
        salt-call infoblox.get_ipv4addr mac=00:50:56:84:6e:ae return_fields=host
        return_fields='mac,host,configure_for_dhcp,ipv4addr'
    '''
    infoblox = _get_infoblox(**kwargs)
    return infoblox.get_host_ipv4addr_object(ipv4addr, mac, discovered_data, return_fields)


def get_host_ipv6addr_info(ipv6addr=None, mac=None,
                                        discovered_data=None,
                                        return_fields=None, **kwargs):
    '''
    Get host ipv6addr information

    CLI Example:

        salt-call infoblox.get_host_ipv6addr_info ipv6addr=2001:db8:85a3:8d3:1349:8a2e:370:7348
    '''
    infoblox = _get_infoblox(**kwargs)
    return infoblox.get_host_ipv6addr_object(ipv6addr, mac, discovered_data, return_fields)


def get_network(ipv4addr=None, network=None, return_fields=None, **kwargs):
    '''
    Get list of all networks.
    This is helpfull when looking up subnets to
    use with func:nextavailableip

    This call is offen slow and not cached!

    some return_fields
    comment,network,network_view,ddns_domainname,disable,enable_ddns

    CLI Example:

        salt-call infoblox.get_network
    '''
    infoblox = _get_infoblox(**kwargs)
    return infoblox.get_network(ipv4addr=ipv4addr, network=network, return_fields=return_fields)


def delete_host(name=None, mac=None, ipv4addr=None, **kwargs):
    '''
    Delete host

    CLI Example:

        salt-call infoblox.delete_host name=example.domain.com
        salt-call infoblox.delete_host ipv4addr=123.123.122.12
        salt-call infoblox.delete_host ipv4addr=123.123.122.12 mac=00:50:56:84:6e:ae
    '''
    if '__opts__' in globals() and __opts__['test']:
        return {'Test': 'Would attempt to delete host'}
    infoblox = _get_infoblox(**kwargs)
    return infoblox.delete_host(name, mac, ipv4addr)


def create_host(data, **kwargs):
    '''
    Add host record

    Avoid race conditions, use func:nextavailableip for ipv[4,6]addrs:
        - func:nextavailableip:network/ZG54dfgsrDFEFfsfsLzA:10.0.0.0/8/default
        - func:nextavailableip:10.0.0.0/8
        - func:nextavailableip:10.0.0.0/8,external
        - func:nextavailableip:10.0.0.3-10.0.0.10

    See your infoblox API for full `data` format.

    CLI Example:

        salt-call infoblox.create_host \
            data =
                {'name': 'hostname.example.ca',
                'aliases': ['hostname.math.example.ca'],
            'extattrs': [{'Business Contact': {'value': 'example@example.ca'}},
                {'Pol8 Classification': {'value': 'Restricted'}},
                {'Primary OU': {'value': 'CS'}},
                {'Technical Contact': {'value': 'example@example.ca'}}],
            'ipv4addrs': [{'configure_for_dhcp': True,
                'ipv4addr': 'func:nextavailableip:129.97.139.0/24',
                'mac': '00:50:56:84:6e:ae'}],
            'ipv6addrs': [], }
    '''
    return create_object('record:host', data, **kwargs)


def get_ipv4_range(start_addr=None, end_addr=None, return_fields=None, **kwargs):
    '''
    Get ip range

    CLI Example:

        salt-call infoblox.get_ipv4_range start_addr=123.123.122.12
    '''
    infoblox = _get_infoblox(**kwargs)
    return infoblox.get_range(start_addr, end_addr, return_fields)


def delete_ipv4_range(start_addr=None, end_addr=None, **kwargs):
    '''
    Delete ip range.

    CLI Example:

            salt-call infoblox.delete_ipv4_range start_addr=123.123.122.12
    '''
    r = get_ipv4_range(start_addr, end_addr, **kwargs)
    if r:
        return delete_object(r['_ref'], **kwargs)
    else:
        return True


def create_ipv4_range(data, **kwargs):
    '''
    Create a ipv4 range

    This is a helper function to `create_object`
    See your infoblox API for full `data` format.

    CLI Example:

        salt-call infoblox.create_ipv4_range data={
            start_addr: '129.97.150.160',
            end_addr: '129.97.150.170'}
    '''
    return create_object('range', data, **kwargs)


def create_a(data, **kwargs):
    '''
    Create 'a' record.

    This is a helper function to `create_object`.
    See your infoblox API for full `data` format.

    CLI Example:

        salt-call infoblox.create_a \
                    data =
                    name: 'fastlinux.math.example.ca'
                    ipv4addr: '127.0.0.1'
                    view: External
    '''
    return create_object('record:a', data, **kwargs)


def get_a(name=None, ipv4addr=None, allow_array=True, **kwargs):
    '''
    Get 'a' record

    CLI Example:

        salt-call infoblox.get_a name=abc.example.com
        salt-call infoblox.get_a ipv4addr=192.168.3.5
    '''
    data = {}
    if name:
        data['name'] = name
    if ipv4addr:
        data['ipv4addr'] = ipv4addr
    r = get_object('record:a', data=data, **kwargs)
    if r and len(r) > 1 and not allow_array:
        raise Exception('More than one result, use allow_array to return the data')
    return r


def delete_a(name=None, ipv4addr=None, allow_array=False, **kwargs):
    '''
    Delete 'a' record

    If the 'a' record is used as a round robin you can set
    `allow_array=true to delete all records for the hostname.

    CLI Example:

        salt-call infoblox.delete_a name=abc.example.com
        salt-call infoblox.delete_a ipv4addr=192.168.3.5
        salt-call infoblox.delete_a name=acname.example.com allow_array=true
    '''
    r = get_a(name, ipv4addr, allow_array=False, **kwargs)
    if not r:
        return True
    if len(r) == 0:
        return True
    if len(r) > 1 and not allow_array:
        raise Exception('More than one result, use allow_array to override')
    ret = []
    for ri in r:
        ret.append(delete_object(ri['_ref'], **kwargs))
    return ret
