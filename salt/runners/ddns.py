# -*- coding: utf-8 -*-
'''
Dynamic DNS Runner
==================

.. versionadded:: Beryllium

Runner to interact with DNS server and create/delete/update DNS records

:codeauthor: Nitin Madhok <nmadhok@clemson.edu>


Configuration
-------------

To use this runner, default configuration to use for the nameserver such as ``keyname``,
``keyfile``, ``keyalgorithm``, ``nameserver``, ``timeout``, ``port`` can also be specified
in the master configuration at ``/etc/salt/master`` or ``/etc/salt/master.d/ddns.conf``:

.. code-block:: yaml

    ddns:
      nameserver1:
        keyname: 'my-tsig-key'
        keyfile: '/etc/salt/tsig.keyring'
        nameserver: '10.0.0.1'
      10.0.0.2:
        keyname: 'my-tsig-key'
        keyfile: '/etc/salt/tsig.keyring'
        keyalgorithm: 'HMAC-MD5.SIG-ALG.REG.INT'
        port: 53
        timeout: 10

'''
from __future__ import absolute_import

# Import python libs
import os
import logging
import json

# Import third party libs
HAS_LIBS = False
try:
    import dns.query
    import dns.update
    import dns.tsig
    import dns.tsigkeyring
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

# Import salt libs
import salt.utils
import salt.exceptions

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Check if required libs (python-dns) is installed and load runner
    only if they are present
    '''
    if not HAS_LIBS:
        return False

    return True


def _get_keyring(keyfile):
    keyring = None
    if keyfile and os.path.isfile(os.path.expanduser(keyfile)):
        with salt.utils.fopen(keyfile) as _f:
            keyring = dns.tsigkeyring.from_text(json.load(_f))

    return keyring


def _get_ddns_config(*args, **kwargs):
    '''
    Return the configuration read from the master configuration
    file or directory
    '''
    ddns_config = __opts__.get('ddns', {})
    nameservers = list(ddns_config.keys())
    nameserver = kwargs.get('nameserver', nameservers[0] if len(nameservers) == 1 else {})
    if not nameserver:
        message = 'Missing \'nameserver\' or multiple nameserver configurations ' \
                  'found in the master configuration.'
        log.error(message)
        raise salt.exceptions.SaltRunnerError(message)

    config = {
        'keyname': kwargs.get('keyname', ddns_config.get(nameserver, {}).get('keyname', None)),
        'keyfile': kwargs.get('keyfile', ddns_config.get(nameserver, {}).get('keyfile', None)),
        'nameserver': ddns_config.get(nameserver, {}).get('nameserver', nameserver),
        'timeout': kwargs.get('timeout', ddns_config.get(nameserver, {}).get('timeout', 5)),
        'port': kwargs.get('port', ddns_config.get(nameserver, {}).get('port', 53)),
        'keyalgorithm': kwargs.get('keyalgorithm', ddns_config.get(nameserver, {}).get('keyalgorithm', dns.tsig.default_algorithm))
    }

    log.debug("DDNS configuration: {0}".format(config))

    if not config['keyname'] or not config['keyfile']:
        message = 'Missing \'keyname\' and/or \'keyfile\' for the nameserver: {0}'.format(nameserver)
        log.error(message)
        raise salt.exceptions.SaltRunnerError(message)

    return config


def create(zone, name, ttl, rdtype, data, *args, **kwargs):
    '''
    Create a DNS record. The nameserver must be an IP address and the master running
    this runner must have create privileges on that server.

    zone
        The zone which is being updated

    name
        The host portion of the DNS record. Name and zone are concatenated together when
        the entry is created unless the name includes a trailing dot (``.``)

    ttl
        The TTL for the record

    rdtype
        The query type; can be set to ``A``, ``AAAA``, ``CNAME``, ``HINFO``, ``ISDN``, ``MX``,
        ``NS``, ``PTR``, ``SOA`` or ``TXT``

    data
        The data for the DNS record. E.g., the IP address for an A record

    keyname
        The name of the TSIG key to use

    keyfile
        The path to the file that contains the TSIG keyring

    nameserver
        The server that answers DNS queries

    timeout: ``5``
        The number of seconds to wait for each response message; defaults to ``5``

    port: ``53``
        The port on the nameserver that the BIND service uses to answer queries from clients;
        defaults to ``53``

    keyalgorithm: ``HMAC-MD5.SIG-ALG.REG.INT``
        The TSIG algorithm to use; can be set to ``HMAC_MD5``, ``HMAC_SHA1``, ``HMAC_SHA224``,
        ``HMAC_SHA256``, ``HMAC_SHA384``, or ``HMAC_SHA512``; defaults to ``HMAC-MD5.SIG-ALG.REG.INT``

    CLI Example:

    .. code-block:: bash

        salt-run ddns.create zone="domain.com" name="my-test-vm" data="10.20.30.40" ttl=3600 \\
        rdtype="A" nameserver="nameserver1"

        salt-run ddns.create zone="domain.com" name="my-test-vm" data="10.20.30.40" ttl=3600 \\
        rdtype="A" "keyname=my-tsig-key" keyfile="/etc/salt/tsig.keyring" nameserver="10.0.0.2"

    '''
    kwargs.update(dict(list(zip(
        ('keyname', 'keyfile', 'nameserver', 'timeout', 'port', 'keyalgorithm'),
        args
    ))))
    zone = kwargs.get('zone', zone)
    name = kwargs.get('name', name)
    ttl = kwargs.get('ttl', ttl)
    rdtype = kwargs.get('rdtype', rdtype)
    data = kwargs.get('data', data)

    config = _get_ddns_config(*args, **kwargs)

    if zone in name:
        name = name.replace(zone, '').rstrip('.')
    fqdn = '{0}.{1}'.format(name, zone)
    request = dns.message.make_query(fqdn, rdtype)
    answer = dns.query.udp(request, config['nameserver'], config['timeout'], config['port'])

    rdata_value = dns.rdatatype.from_text(rdtype)
    rdata = dns.rdata.from_text(dns.rdataclass.IN, rdata_value, data)

    for rrset in answer.answer:
        if rdata in rrset.items:
            return {fqdn: 'Record of type \'{0}\' already exists with ttl of {1}'.format(rdtype, rrset.ttl)}

    keyring = _get_keyring(config['keyfile'])
    dns_update = dns.update.Update(zone, keyring=keyring, keyname=config['keyname'],
                                   keyalgorithm=config['keyalgorithm'])
    dns_update.add(name, ttl, rdata)

    answer = dns.query.udp(dns_update, config['nameserver'], config['timeout'], config['port'])
    if answer.rcode() > 0:
        return {fqdn: 'Failed to create record of type \'{0}\''.format(rdtype)}

    return {fqdn: 'Created record of type \'{0}\': {1} -> {2}'.format(rdtype, fqdn, data)}


def update(zone, name, ttl, rdtype, data, *args, **kwargs):
    '''
    Replace, or update a DNS record. The nameserver must be an IP address and the master running
    this runner must have update privileges on that server.

    .. note::

        If ``replace`` is set to True, all records for this name and type will first be deleted and
        then recreated. Default is ``replace=False``.

    zone
        The zone which is being updated

    name
        The host portion of the DNS record. Name and zone are concatenated together when
        the entry is created/updated unless the name includes a trailing dot (``.``)

    ttl
        The TTL for the record

    rdtype
        The query type; can be set to ``A``, ``AAAA``, ``CNAME``, ``HINFO``, ``ISDN``, ``MX``,
        ``NS``, ``PTR``, ``SOA`` or ``TXT``

    data
        The data for the DNS record. E.g., the IP address for an A record

    keyname
        The name of the TSIG key to use

    keyfile
        The path to the file that contains the TSIG keyring

    nameserver
        The server that answers DNS queries

    timeout: ``5``
        The number of seconds to wait for each response message; defaults to ``5``

    replace: False
        Set to ``True`` to first delete all records for the ``name`` and ``rdtype`` specified
        and then create it; defaults to ``False``

    port: ``53``
        The port on the nameserver that the BIND service uses to answer queries from clients;
        defaults to ``53``

    keyalgorithm: ``HMAC-MD5.SIG-ALG.REG.INT``
        The TSIG algorithm to use; can be set to ``HMAC_MD5``, ``HMAC_SHA1``, ``HMAC_SHA224``,
        ``HMAC_SHA256``, ``HMAC_SHA384``, or ``HMAC_SHA512``; defaults to ``HMAC-MD5.SIG-ALG.REG.INT``

    CLI Example:

    .. code-block:: bash

        salt-run ddns.update zone="domain.com" name="my-test-vm" data="10.20.30.40" ttl=3600 \\
        rdtype="A" nameserver="nameserver1"

        salt-run ddns.update zone="domain.com" name="my-test-vm" data="10.20.30.40" ttl=3600 \\
        rdtype="A" keyname="my-tsig-key" keyfile="/etc/salt/tsig.keyring" nameserver="10.0.0.2"

    '''
    kwargs.update(dict(list(zip(
        ('keyname', 'keyfile', 'nameserver', 'timeout', 'replace', 'port', 'keyalgorithm'),
        args
    ))))
    zone = kwargs.get('zone', zone)
    name = kwargs.get('name', name)
    ttl = kwargs.get('ttl', ttl)
    rdtype = kwargs.get('rdtype', rdtype)
    data = kwargs.get('data', data)
    replace = kwargs.get('replace', False)

    config = _get_ddns_config(*args, **kwargs)

    if zone in name:
        name = name.replace(zone, '').rstrip('.')
    fqdn = '{0}.{1}'.format(name, zone)
    request = dns.message.make_query(fqdn, rdtype)
    answer = dns.query.udp(request, config['nameserver'], config['timeout'], config['port'])
    if not answer.answer:
        return {fqdn: 'No matching DNS record(s) found'}

    rdata_value = dns.rdatatype.from_text(rdtype)
    rdata = dns.rdata.from_text(dns.rdataclass.IN, rdata_value, data)

    for rrset in answer.answer:
        if rdata in rrset.items:
            rr = rrset.items
            if ttl == rrset.ttl:
                if replace and (len(answer.answer) > 1
                        or len(rrset.items) > 1):
                    break
                return {fqdn: 'Record of type \'{0}\' already present with ttl of {1}'.format(rdtype, ttl)}
            break

    keyring = _get_keyring(config['keyfile'])

    dns_update = dns.update.Update(zone, keyring=keyring, keyname=config['keyname'],
                                   keyalgorithm=config['keyalgorithm'])
    dns_update.replace(name, ttl, rdata)

    answer = dns.query.udp(dns_update, config['nameserver'], config['timeout'], config['port'])
    if answer.rcode() > 0:
        return {fqdn: 'Failed to update record of type \'{0}\''.format(rdtype)}

    return {fqdn: 'Updated record of type \'{0}\''.format(rdtype)}


def delete(zone, name, *args, **kwargs):
    '''
    Delete a DNS record.

    zone
        The zone which is being updated

    name
        The host portion of the DNS record. Name and zone are concatenated together when
        the entry is created unless the name includes a trailing dot (``.``)

    rdtype
        The query type; can be set to ``A``, ``AAAA``, ``CNAME``, ``HINFO``, ``ISDN``, ``MX``,
        ``NS``, ``PTR``, ``SOA`` or ``TXT``

    data
        The data for the DNS record. E.g., the IP address for an A record

    keyname
        The name of the TSIG key to use

    keyfile
        The path to the file that contains the TSIG keyring

    nameserver
        The server that answers DNS queries

    timeout: ``5``
        The number of seconds to wait for each response message; defaults to ``5``

    port: ``53``
        The port on the nameserver that the BIND service uses to answer queries from clients;
        defaults to ``53``

    keyalgorithm: ``HMAC-MD5.SIG-ALG.REG.INT``
        The TSIG algorithm to use; can be set to ``HMAC_MD5``, ``HMAC_SHA1``, ``HMAC_SHA224``,
        ``HMAC_SHA256``, ``HMAC_SHA384``, or ``HMAC_SHA512``; defaults to ``HMAC-MD5.SIG-ALG.REG.INT``

    CLI Example:

    .. code-block:: bash

        salt-run ddns.delete zone="domain.com" name="my-test-vm" rdtype="A" nameserver="nsmaster1"

        salt-run ddns.delete zone="domain.com" name="my-test-vm" rdtype="A" keyname="my-tsig-key" \\
        keyfile="/etc/salt/tsig.keyring" nameserver="10.0.0.2"

    '''
    kwargs.update(dict(list(zip(
        ('keyname', 'keyfile', 'nameserver', 'timeout', 'rdtype', 'data', 'port', 'keyalgorithm'),
        args
    ))))
    zone = kwargs.get('zone', zone)
    name = kwargs.get('name', name)
    rdtype = kwargs.get('rdtype', None)
    data = kwargs.get('data', None)

    config = _get_ddns_config(*args, **kwargs)

    if zone in name:
        name = name.replace(zone, '').rstrip('.')
    fqdn = '{0}.{1}'.format(name, zone)
    request = dns.message.make_query(fqdn, (rdtype or 'ANY'))

    answer = dns.query.udp(request, config['nameserver'], config['timeout'], config['port'])
    if not answer.answer:
        return {fqdn: 'No matching DNS record(s) found'}

    keyring = _get_keyring(config['keyfile'])

    dns_update = dns.update.Update(zone, keyring=keyring, keyname=config['keyname'],
                                   keyalgorithm=config['keyalgorithm'])

    if rdtype:
        rdata_value = dns.rdatatype.from_text(rdtype)
        if data:
            rdata = dns.rdata.from_text(dns.rdataclass.IN, rdata_value, data)
            dns_update.delete(name, rdata)
        else:
            dns_update.delete(name, rdata_value)
    else:
        dns_update.delete(name)

    answer = dns.query.udp(dns_update, config['nameserver'], config['timeout'], config['port'])
    if answer.rcode() > 0:
        return {fqdn: 'Failed to delete DNS record(s)'}

    return {fqdn: 'Deleted DNS record(s)'}


def add_host(zone, name, ttl, ip, *args, **kwargs):
    '''
    Create both A and PTR (reverse) records for a host.

    zone
        The zone which is being updated

    name
        The host portion of the DNS record. Name and zone are concatenated together when
        the entry is created unless the name includes a trailing dot (``.``)

    ttl
        The TTL for the record

    ip
        The IP for the DNS record

    keyname
        The name of the TSIG key to use

    keyfile
        The path to the file that contains the TSIG keyring

    nameserver
        The server that answers DNS queries

    timeout: ``5``
        The number of seconds to wait for each response message; defaults to ``5``

    port: ``53``
        The port on the nameserver that the BIND service uses to answer queries from clients;
        defaults to ``53``

    keyalgorithm: ``HMAC-MD5.SIG-ALG.REG.INT``
        The TSIG algorithm to use; can be set to ``HMAC_MD5``, ``HMAC_SHA1``, ``HMAC_SHA224``,
        ``HMAC_SHA256``, ``HMAC_SHA384``, or ``HMAC_SHA512``; defaults to ``HMAC-MD5.SIG-ALG.REG.INT``

    CLI Example:

    .. code-block:: bash

        salt-run ddns.add_host zone="domain.com" name="my-test-vm" ip="10.20.30.40" ttl="3600" \\
        nameserver="nsmaster1"

        salt-run ddns.add_host zone="domain.com" name="my-test-vm" ip="10.20.30.40" ttl="3600" \\
        keyname="my-tsig-key" keyfile="/etc/salt/tsig.keyring" nameserver="10.0.0.2"

    '''
    kwargs.update(dict(list(zip(
        ('keyname', 'keyfile', 'nameserver', 'timeout', 'port', 'keyalgorithm'),
        args
    ))))
    zone = kwargs.get('zone', zone)
    name = kwargs.get('name', name)
    ttl = kwargs.get('ttl', ttl)
    ip = kwargs.get('ip', ip)

    res = []
    if zone in name:
        name = name.replace(zone, '').rstrip('.')
    fqdn = '{0}.{1}'.format(name, zone)

    ret = create(zone, name, ttl, 'A', ip, *args, **kwargs)
    res.append(ret[fqdn])

    parts = ip.split('.')[::-1]
    i = len(parts)
    popped = []

    # Iterate over possible reverse zones
    while i > 1:
        p = parts.pop(0)
        i -= 1
        popped.append(p)

        zone = '{0}.{1}'.format('.'.join(parts), 'in-addr.arpa.')
        name = '.'.join(popped)
        rev_fqdn = '{0}.{1}'.format(name, zone)
        ret = create(zone, name, ttl, 'PTR', "{0}.".format(fqdn), *args, **kwargs)

        if "Created" in ret[rev_fqdn]:
            res.append(ret[rev_fqdn])
            return {fqdn: res}

    res.append(ret[rev_fqdn])

    return {fqdn: res}


def delete_host(zone, name, *args, **kwargs):
    '''
    Delete both forward (A) and reverse (PTR) records for a host only if the
    forward (A) record exists.

    zone
        The zone which is being updated

    name
        The host portion of the DNS record. Name and zone are concatenated together when
        the entry is created unless the name includes a trailing dot (``.``)

    keyname
        The name of the TSIG key to use

    keyfile
        The path to the file that contains the TSIG keyring

    nameserver
        The server that answers DNS queries

    timeout: ``5``
        The number of seconds to wait for each response message; defaults to ``5``

    port: ``53``
        The port on the nameserver that the BIND service uses to answer queries from clients;
        defaults to ``53``

    keyalgorithm: ``HMAC-MD5.SIG-ALG.REG.INT``
        The TSIG algorithm to use; can be set to ``HMAC_MD5``, ``HMAC_SHA1``, ``HMAC_SHA224``,
        ``HMAC_SHA256``, ``HMAC_SHA384``, or ``HMAC_SHA512``; defaults to ``HMAC-MD5.SIG-ALG.REG.INT``

    CLI Example:

    .. code-block:: bash

        salt-run ddns.delete_host zone="domain.com" name="my-test-vm" nameserver="nsmaster1"

        salt-run ddns.delete_host zone="domain.com" name="my-test-vm" keyname="my-tsig-key" \\
        keyfile="/etc/salt/tsig.keyring" nameserver="10.0.0.2"

    '''
    kwargs.update(dict(list(zip(
        ('keyname', 'keyfile', 'nameserver', 'timeout', 'port', 'keyalgorithm'),
        args
    ))))
    zone = kwargs.get('zone', zone)
    name = kwargs.get('name', name)

    config = _get_ddns_config(*args, **kwargs)

    res = []
    if zone in name:
        name = name.replace(zone, '').rstrip('.')
    fqdn = '{0}.{1}'.format(name, zone)
    request = dns.message.make_query(fqdn, 'A')
    answer = dns.query.udp(request, config['nameserver'], config['timeout'], config['port'])

    try:
        ips = [i.address for i in answer.answer[0].items]
    except IndexError:
        ips = []

    ret = delete(zone, name, *args, **kwargs)
    res.append("{0} of type \'A\'".format(ret[fqdn]))

    for ip in ips:
        parts = ip.split('.')[::-1]
        i = len(parts)
        popped = []

        # Iterate over possible reverse zones
        while i > 1:
            p = parts.pop(0)
            i -= 1
            popped.append(p)
            zone = '{0}.{1}'.format('.'.join(parts), 'in-addr.arpa.')
            name = '.'.join(popped)
            rev_fqdn = '{0}.{1}'.format(name, zone)
            ret = delete(zone, name, keyname=config['keyname'], keyfile=config['keyfile'],
                         nameserver=config['nameserver'], timeout=config['timeout'],
                         rdtype='PTR', data="{0}.".format(fqdn), port=config['port'],
                         keyalgorithm=config['keyalgorithm'])

            if "Deleted" in ret[rev_fqdn]:
                res.append("{0} of type \'PTR\'".format(ret[rev_fqdn]))
                return {fqdn: res}

        res.append(ret[rev_fqdn])

    return {fqdn: res}
