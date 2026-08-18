"""
Dynamic DNS Runner
==================

.. versionadded:: 2015.8.0

Runner to interact with DNS server and create/delete/update DNS records

:codeauthor: Nitin Madhok <nmadhok@g.clemson.edu>

"""

import logging
import os

import salt.utils.files
import salt.utils.json

HAS_LIBS = False
try:
    import dns.query
    import dns.tsigkeyring  # pylint: disable=no-name-in-module
    import dns.update  # pylint: disable=no-name-in-module

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False


log = logging.getLogger(__name__)


def __virtual__():
    """
    Check if required libs (python-dns) is installed and load runner
    only if they are present
    """
    if not HAS_LIBS:
        return False

    return True


def _get_keyring(keyfile):
    keyring = None
    if keyfile and os.path.isfile(os.path.expanduser(keyfile)):
        with salt.utils.files.fopen(keyfile) as _f:
            keyring = dns.tsigkeyring.from_text(salt.utils.json.load(_f))

    return keyring


def create(
    zone,
    name,
    ttl,
    rdtype,
    data,
    keyname,
    keyfile,
    nameserver,
    timeout,
    port=53,
    keyalgorithm="hmac-md5",
):
    """
    Create a DNS record. The nameserver must be an IP address and the master running
    this runner must have create privileges on that server.

    CLI Example:

    .. code-block:: bash

        salt-run ddns.create domain.com my-test-vm 3600 A 10.20.30.40 my-tsig-key /etc/salt/tsig.keyring 10.0.0.1 5
    """
    if zone in name:
        name = name.replace(zone, "").rstrip(".")
    fqdn = f"{name}.{zone}"
    request = dns.message.make_query(fqdn, rdtype)
    answer = dns.query.udp(request, nameserver, timeout, port)

    rdata_value = dns.rdatatype.from_text(rdtype)
    rdata = dns.rdata.from_text(dns.rdataclass.IN, rdata_value, data)

    for rrset in answer.answer:
        if rdata in rrset.items:
            return {
                fqdn: "Record of type '{}' already exists with ttl of {}".format(
                    rdtype, rrset.ttl
                )
            }

    keyring = _get_keyring(keyfile)

    dns_update = dns.update.Update(
        zone, keyring=keyring, keyname=keyname, keyalgorithm=keyalgorithm
    )
    dns_update.add(name, ttl, rdata)

    answer = dns.query.udp(dns_update, nameserver, timeout, port)
    if answer.rcode() > 0:
        return {fqdn: f"Failed to create record of type '{rdtype}'"}

    return {fqdn: f"Created record of type '{rdtype}': {fqdn} -> {data}"}


def update(
    zone,
    name,
    ttl,
    rdtype,
    data,
    keyname,
    keyfile,
    nameserver,
    timeout,
    replace=False,
    port=53,
    keyalgorithm="hmac-md5",
):
    """
    Replace, or update a DNS record. The nameserver must be an IP address and the master running
    this runner must have update privileges on that server.

    .. note::

        If ``replace`` is set to True, all records for this name and type will first be deleted and
        then recreated. Default is ``replace=False``.

    CLI Example:

    .. code-block:: bash

        salt-run ddns.update domain.com my-test-vm 3600 A 10.20.30.40 my-tsig-key /etc/salt/tsig.keyring 10.0.0.1 5
    """
    if zone in name:
        name = name.replace(zone, "").rstrip(".")
    fqdn = f"{name}.{zone}"
    request = dns.message.make_query(fqdn, rdtype)
    answer = dns.query.udp(request, nameserver, timeout, port)
    if not answer.answer:
        return {fqdn: "No matching DNS record(s) found"}

    rdata_value = dns.rdatatype.from_text(rdtype)
    rdata = dns.rdata.from_text(dns.rdataclass.IN, rdata_value, data)

    for rrset in answer.answer:
        if rdata in rrset.items:
            rr = rrset.items
            if ttl == rrset.ttl:
                if replace and (len(answer.answer) > 1 or len(rrset.items) > 1):
                    break
                return {
                    fqdn: "Record of type '{}' already present with ttl of {}".format(
                        rdtype, ttl
                    )
                }
            break

    keyring = _get_keyring(keyfile)

    dns_update = dns.update.Update(
        zone, keyring=keyring, keyname=keyname, keyalgorithm=keyalgorithm
    )
    dns_update.replace(name, ttl, rdata)

    answer = dns.query.udp(dns_update, nameserver, timeout, port)
    if answer.rcode() > 0:
        return {fqdn: f"Failed to update record of type '{rdtype}'"}

    return {fqdn: f"Updated record of type '{rdtype}'"}


def delete(
    zone,
    name,
    keyname,
    keyfile,
    nameserver,
    timeout,
    rdtype=None,
    data=None,
    port=53,
    keyalgorithm="hmac-md5",
):
    """
    Delete a DNS record.

    CLI Example:

    .. code-block:: bash

        salt-run ddns.delete domain.com my-test-vm my-tsig-key /etc/salt/tsig.keyring 10.0.0.1 5 A
    """
    if zone in name:
        name = name.replace(zone, "").rstrip(".")
    fqdn = f"{name}.{zone}"
    request = dns.message.make_query(fqdn, (rdtype or "ANY"))

    answer = dns.query.udp(request, nameserver, timeout, port)
    if not answer.answer:
        return {fqdn: "No matching DNS record(s) found"}

    keyring = _get_keyring(keyfile)

    dns_update = dns.update.Update(
        zone, keyring=keyring, keyname=keyname, keyalgorithm=keyalgorithm
    )

    if rdtype:
        rdata_value = dns.rdatatype.from_text(rdtype)
        if data:
            rdata = dns.rdata.from_text(dns.rdataclass.IN, rdata_value, data)
            dns_update.delete(name, rdata)
        else:
            dns_update.delete(name, rdata_value)
    else:
        dns_update.delete(name)

    answer = dns.query.udp(dns_update, nameserver, timeout, port)
    if answer.rcode() > 0:
        return {fqdn: "Failed to delete DNS record(s)"}

    return {fqdn: "Deleted DNS record(s)"}


def add_host(
    zone,
    name,
    ttl,
    ip,
    keyname,
    keyfile,
    nameserver,
    timeout,
    port=53,
    keyalgorithm="hmac-md5",
):
    """
    Create both A and PTR (reverse) records for a host.

    CLI Example:

    .. code-block:: bash

        salt-run ddns.add_host domain.com my-test-vm 3600 10.20.30.40 my-tsig-key /etc/salt/tsig.keyring 10.0.0.1 5
    """
    res = []
    if zone in name:
        name = name.replace(zone, "").rstrip(".")
    fqdn = f"{name}.{zone}"

    ret = create(
        zone,
        name,
        ttl,
        "A",
        ip,
        keyname,
        keyfile,
        nameserver,
        timeout,
        port,
        keyalgorithm,
    )
    res.append(ret[fqdn])

    parts = ip.split(".")[::-1]
    i = len(parts)
    popped = []

    # Iterate over possible reverse zones
    while i > 1:
        p = parts.pop(0)
        i -= 1
        popped.append(p)

        zone = "{}.{}".format(".".join(parts), "in-addr.arpa.")
        name = ".".join(popped)
        rev_fqdn = f"{name}.{zone}"
        ret = create(
            zone,
            name,
            ttl,
            "PTR",
            f"{fqdn}.",
            keyname,
            keyfile,
            nameserver,
            timeout,
            port,
            keyalgorithm,
        )

        if "Created" in ret[rev_fqdn]:
            res.append(ret[rev_fqdn])
            return {fqdn: res}

    res.append(ret[rev_fqdn])

    return {fqdn: res}


def delete_host(
    zone, name, keyname, keyfile, nameserver, timeout, port=53, keyalgorithm="hmac-md5"
):
    """
    Delete both forward (A) and reverse (PTR) records for a host only if the
    forward (A) record exists.

    CLI Example:

    .. code-block:: bash

        salt-run ddns.delete_host domain.com my-test-vm my-tsig-key /etc/salt/tsig.keyring 10.0.0.1 5
    """
    res = []
    if zone in name:
        name = name.replace(zone, "").rstrip(".")
    fqdn = f"{name}.{zone}"
    request = dns.message.make_query(fqdn, "A")
    answer = dns.query.udp(request, nameserver, timeout, port)

    try:
        ips = [i.address for i in answer.answer[0].items]
    except IndexError:
        ips = []

    ret = delete(
        zone,
        name,
        keyname,
        keyfile,
        nameserver,
        timeout,
        port=port,
        keyalgorithm=keyalgorithm,
    )
    res.append(f"{ret[fqdn]} of type 'A'")

    for ip in ips:
        parts = ip.split(".")[::-1]
        i = len(parts)
        popped = []

        # Iterate over possible reverse zones
        while i > 1:
            p = parts.pop(0)
            i -= 1
            popped.append(p)
            zone = "{}.{}".format(".".join(parts), "in-addr.arpa.")
            name = ".".join(popped)
            rev_fqdn = f"{name}.{zone}"
            ret = delete(
                zone,
                name,
                keyname,
                keyfile,
                nameserver,
                timeout,
                "PTR",
                f"{fqdn}.",
                port,
                keyalgorithm,
            )

            if "Deleted" in ret[rev_fqdn]:
                res.append(f"{ret[rev_fqdn]} of type 'PTR'")
                return {fqdn: res}

        res.append(ret[rev_fqdn])

    return {fqdn: res}
