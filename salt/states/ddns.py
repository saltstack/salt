"""
Dynamic DNS updates
===================

Ensure a DNS record is present or absent utilizing RFC 2136
type dynamic updates.

:depends: - `dnspython <http://www.dnspython.org/>`_

.. note::
    The ``dnspython`` module is required when managing DDNS using a TSIG key.
    If you are not using a TSIG key, DDNS is allowed by ACLs based on IP
    address and the ``dnspython`` module is not required.

Example:

.. code-block:: yaml

    webserver:
      ddns.present:
        - zone: example.com
        - ttl: 60
        - data: 111.222.333.444
        - nameserver: 123.234.345.456
        - keyfile: /srv/salt/dnspy_tsig_key.txt
"""


def __virtual__():
    if "ddns.update" in __salt__:
        return "ddns"
    return (False, "ddns module could not be loaded")


def present(name, zone, ttl, data, rdtype="A", **kwargs):
    """
    Ensures that the named DNS record is present with the given ttl.

    name
        The host portion of the DNS record, e.g., 'webserver'. Name and zone
        are concatenated when the entry is created unless name includes a
        trailing dot, so make sure that information is not duplicated in these
        two arguments.

    zone
        The zone to check/update

    ttl
        TTL for the record

    data
        Data for the DNS record. E.g., the IP address for an A record.

    rdtype
        DNS resource type. Default 'A'.

    ``**kwargs``
        Additional arguments the ddns.update function may need (e.g.
        nameserver, keyfile, keyname).  Note that the nsupdate key file can’t
        be reused by this function, the keyfile and other arguments must
        follow the `dnspython <http://www.dnspython.org/>`_ spec.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = '{} record "{}" will be updated'.format(rdtype, name)
        return ret

    status = __salt__["ddns.update"](zone, name, ttl, rdtype, data, **kwargs)

    if status is None:
        ret["result"] = True
        ret["comment"] = '{} record "{}" already present with ttl of {}'.format(
            rdtype, name, ttl
        )
    elif status:
        ret["result"] = True
        ret["comment"] = 'Updated {} record for "{}"'.format(rdtype, name)
        ret["changes"] = {
            "name": name,
            "zone": zone,
            "ttl": ttl,
            "rdtype": rdtype,
            "data": data,
        }
    else:
        ret["result"] = False
        ret["comment"] = 'Failed to create or update {} record for "{}"'.format(
            rdtype, name
        )
    return ret


def absent(name, zone, data=None, rdtype=None, **kwargs):
    """
    Ensures that the named DNS record is absent.

    name
        The host portion of the DNS record, e.g., 'webserver'. Name and zone
        are concatenated when the entry is created unless name includes a
        trailing dot, so make sure that information is not duplicated in these
        two arguments.

    zone
        The zone to check

    data
        Data for the DNS record. E.g., the IP address for an A record. If omitted,
        all records matching name (and rdtype, if provided) will be purged.

    rdtype
        DNS resource type. If omitted, all types will be purged.

    ``**kwargs``
        Additional arguments the ddns.update function may need (e.g.
        nameserver, keyfile, keyname).  Note that the nsupdate key file can’t
        be reused by this function, the keyfile and other arguments must
        follow the `dnspython <http://www.dnspython.org/>`_ spec.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = '{} record "{}" will be deleted'.format(rdtype, name)
        return ret

    status = __salt__["ddns.delete"](zone, name, rdtype, data, **kwargs)

    if status is None:
        ret["result"] = True
        ret["comment"] = "No matching DNS record(s) present"
    elif status:
        ret["result"] = True
        ret["comment"] = "Deleted DNS record(s)"
        ret["changes"] = {"Deleted": {"name": name, "zone": zone}}
    else:
        ret["result"] = False
        ret["comment"] = "Failed to delete DNS record(s)"
    return ret
