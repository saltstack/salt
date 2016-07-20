# -*- coding: utf-8 -*-
'''
Support for RFC 2136 dynamic DNS updates.

:depends:   - dnspython Python module
:configuration: If you want to use TSIG authentication for the server, there
    are a couple of optional configuration parameters made available to
    support this (the keyname is only needed if the keyring contains more
    than one key)::

        keyring: keyring file (default=None)
        keyname: key name in file (default=None)

    The keyring file needs to be in json format and the key name needs to end
    with an extra period in the file, similar to this:

    .. code-block:: json

        {"keyname.": "keycontent"}
'''
from __future__ import absolute_import
# Import python libs
import logging
import json

log = logging.getLogger(__name__)

try:
    import dns.query
    import dns.update
    import dns.tsigkeyring
    dns_support = True
except ImportError as e:
    dns_support = False

import salt.utils


def __virtual__():
    '''
    Confirm dnspython is available.
    '''
    if dns_support:
        return 'ddns'
    return False


def _config(name, key=None, **kwargs):
    '''
    Return a value for 'name' from command line args then config file options.
    Specify 'key' if the config file option is not the same as 'name'.
    '''
    if key is None:
        key = name
    if name in kwargs:
        value = kwargs[name]
    else:
        value = __salt__['config.option']('ddns.{0}'.format(key))
        if not value:
            value = None
    return value


def _get_keyring(keyfile):
    keyring = None
    if keyfile and __salt__['file.file_exists'](keyfile):
        with salt.utils.fopen(keyfile) as _f:
            keyring = dns.tsigkeyring.from_text(json.load(_f))
    return keyring


def add_host(zone, name, ttl, ip, nameserver='127.0.0.1', replace=True, **kwargs):
    '''
    Add, replace, or update the A and PTR (reverse) records for a host.

    CLI Example:

    .. code-block:: bash

        salt ns1 ddns.add_host example.com host1 60 10.1.1.1
    '''
    res = update(zone, name, ttl, 'A', ip, nameserver, replace, **kwargs)
    if res is False:
        return False

    fqdn = '{0}.{1}.'.format(name, zone)
    parts = ip.split('.')[::-1]
    popped = []

    # Iterate over possible reverse zones
    while len(parts) > 1:
        p = parts.pop(0)
        popped.append(p)
        zone = '{0}.{1}'.format('.'.join(parts), 'in-addr.arpa.')
        name = '.'.join(popped)
        ptr = update(zone, name, ttl, 'PTR', fqdn, nameserver, replace, **kwargs)
        if ptr:
            return True
    return res


def delete_host(zone, name, nameserver='127.0.0.1', **kwargs):
    '''
    Delete the forward and reverse records for a host.

    Returns true if any records are deleted.

    CLI Example:

    .. code-block:: bash

        salt ns1 ddns.delete_host example.com host1
    '''
    fqdn = '{0}.{1}'.format(name, zone)
    request = dns.message.make_query(fqdn, 'A')
    answer = dns.query.udp(request, nameserver)
    try:
        ips = [i.address for i in answer.answer[0].items]
    except IndexError:
        ips = []

    res = delete(zone, name, nameserver=nameserver, **kwargs)

    fqdn = fqdn + '.'
    for ip in ips:
        parts = ip.split('.')[::-1]
        popped = []

        # Iterate over possible reverse zones
        while len(parts) > 1:
            p = parts.pop(0)
            popped.append(p)
            zone = '{0}.{1}'.format('.'.join(parts), 'in-addr.arpa.')
            name = '.'.join(popped)
            ptr = delete(zone, name, 'PTR', fqdn, nameserver=nameserver, **kwargs)
        if ptr:
            res = True
    return res


def update(zone, name, ttl, rdtype, data, nameserver='127.0.0.1', replace=False, **kwargs):
    '''
    Add, replace, or update a DNS record.
    nameserver must be an IP address and the minion running this module
    must have update privileges on that server.
    If replace is true, first deletes all records for this name and type.

    CLI Example:

    .. code-block:: bash

        salt ns1 ddns.update example.com host1 60 A 10.0.0.1
    '''
    name = str(name)
    fqdn = '{0}.{1}'.format(name, zone)
    request = dns.message.make_query(fqdn, rdtype)
    answer = dns.query.udp(request, nameserver)

    rdtype = dns.rdatatype.from_text(rdtype)
    rdata = dns.rdata.from_text(dns.rdataclass.IN, rdtype, data)

    is_update = False
    for rrset in answer.answer:
        if rdata in rrset.items:
            rr = rrset.items
            if ttl == rrset.ttl:
                if replace and (len(answer.answer) > 1
                        or len(rrset.items) > 1):
                    is_update = True
                    break
                return None
            is_update = True
            break

    keyring = _get_keyring(_config('keyfile', **kwargs))
    keyname = _config('keyname', **kwargs)
    keyalgorithm = _config('keyalgorithm', **kwargs) or 'HMAC-MD5.SIG-ALG.REG.INT'

    dns_update = dns.update.Update(zone, keyring=keyring, keyname=keyname, keyalgorithm=keyalgorithm)
    if is_update:
        dns_update.replace(name, ttl, rdata)
    else:
        dns_update.add(name, ttl, rdata)
    answer = dns.query.udp(dns_update, nameserver)
    if answer.rcode() > 0:
        return False
    return True


def delete(zone, name, rdtype=None, data=None, nameserver='127.0.0.1', **kwargs):
    '''
    Delete a DNS record.

    CLI Example:

    .. code-block:: bash

        salt ns1 ddns.delete example.com host1 A
    '''
    name = str(name)
    fqdn = '{0}.{1}'.format(name, zone)
    request = dns.message.make_query(fqdn, (rdtype or 'ANY'))

    answer = dns.query.udp(request, nameserver)
    if not answer.answer:
        return None

    keyring = _get_keyring(_config('keyfile', **kwargs))
    keyname = _config('keyname', **kwargs)
    keyalgorithm = _config('keyalgorithm', **kwargs) or 'HMAC-MD5.SIG-ALG.REG.INT'

    dns_update = dns.update.Update(zone, keyring=keyring, keyname=keyname, keyalgorithm=keyalgorithm)

    if rdtype:
        rdtype = dns.rdatatype.from_text(rdtype)
        if data:
            rdata = dns.rdata.from_text(dns.rdataclass.IN, rdtype, data)
            dns_update.delete(name, rdata)
        else:
            dns_update.delete(name, rdtype)
    else:
        dns_update.delete(name)

    answer = dns.query.udp(dns_update, nameserver)
    if answer.rcode() > 0:
        return False
    return True
