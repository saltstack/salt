"""
Create, modify and delete PowerDNS zone
"""

import logging

from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


def __virtual__():
    return "powerdns.manage_zone" in __salt__ and "powerdns.delete_zone" in __salt__


def managed_zone(
    name,
    key,
    server,
    records=None,
    nameservers=None,
    remove_existing_records=False,
    dnssec=False,
):
    """
    Ensure that the PowerDNS zone is created and has correct DNS records.

    :param str name:
        The name of the zone to be created or updated. (e.g. example.com)

    :param str key:
        Static PowerDNS API key.

    :param str server:
        PowerDNS server URL.

    :param list records:
        A list of records objects in this zone.
        Default value for TTL is 300 seconds except NS records.
        Default NS records TTL is 3600 seconds.

        .. code-block:: yaml

            example.com:
              powerdns.manage_zone:
                - records:
                  - name: example.com
                    type: "A"
                    ttl: 300
                    content:
                      - 123.45.67.89
                  - name: www.example.com
                    type: "CNAME"
                    ttl: 3600
                    content:
                      - example.com

      :param list nameservers
          A list of nameservers for zone. Simple list of strings of nameserver names.
          List of nameservers could be passed as NS in records parameter.
          Otherwise, nameservers is required field.

      :param bool remove_existing_records
          If this parameter is enabled, module will be purge all records and add records only from
          records list. Default value is False.

      :param bool dnssec
          Whether or not this zone is DNSSEC signed.
          Default value is True.

    """

    result = {"name": name, "result": True, "changes": {}, "comment": ""}

    if not key or not server:
        raise SaltInvocationError('Arguments "key" and "server" must be specified')

    if not name:
        result["comment"] = "No name of zone provided"
        result["result"] = False
        return result

    state = __salt__["powerdns.manage_zone"](
        name, key, server, records, nameservers, remove_existing_records, dnssec
    )

    if state["changes"]:
        result["changes"] = state["changes"]

    return result


def absent_zone(name, key, server):
    """
    Ensure that the PowerDNS zone is created and has correct DNS records.

    :param str name:
        The name of the zone to be created or updated. (e.g. example.com)

    :param str key:
        Static PowerDNS API key.

    :param str server:
        PowerDNS server URL.
    """

    result = {"name": name, "result": True, "changes": {}, "comment": ""}

    if not key or not server:
        raise SaltInvocationError('Arguments "key" and "server" must be specified')

    if not name:
        result["comment"] = "No name of zone provided"
        result["result"] = False
        return result

    state = __salt__["powerdns.delete_zone"](name, key, server)

    if state["changes"]:
        result["changes"] = state["changes"]

    return result
