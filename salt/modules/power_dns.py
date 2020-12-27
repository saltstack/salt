# -*- coding: utf-8 -*-
'''
Create, modify and delete PowerDNS zone
'''

# Import Python libs
import logging
import requests
import socket

# Import salt libs
from salt.exceptions import CommandExecutionError

# Constant section

DEFAULT_TTL = 300  # In Seconds
DEFAULT_NS_TTL = 3600  # In Seconds

REPLACE_CHANGETYPE = "REPLACE"
DELETE_CHANGETYPE = "DELETE"

DNS_RECORD_NS = "NS"
DNS_RECORD_SOA = "SOA"
DNS_RECORD_TXT = "TXT"
DNS_RECORD_A = "A"
DNS_RECORD_CNAME = "CNAME"

HTTP_RESPONSE_CODE_UNPROCESSABLE_ENTITY = 422
HTTP_RESPONSE_CODE_CREATED = 201
HTTP_RESPONSE_CODE_NO_CONTENT = 204

POWERDNS_URL_ZONES_TEMPLATE = "/api/v1/servers/localhost/zones"
POWERDNS_AUTH_HEADER = "X-API-Key"

logger = logging.getLogger(__name__)


def _get_zone(name, headers, server):
    '''
    Returns info about zone or none if zone doesn't exist
    '''

    url = requests.compat.urljoin(requests.compat.urljoin(server, POWERDNS_URL_ZONES_TEMPLATE + "/"), name)

    resp = requests.get(url, headers=headers)

    if resp.status_code == HTTP_RESPONSE_CODE_UNPROCESSABLE_ENTITY:
        return None

    return resp.json()


def _check_records_equality(old_record, new_record):
    if old_record["name"] == new_record["name"] and \
        (old_record["type"] == new_record["type"] or
         ((old_record["type"] == DNS_RECORD_A or new_record["type"] == DNS_RECORD_A) and \
          (old_record["type"] == DNS_RECORD_CNAME or new_record["type"] == DNS_RECORD_CNAME))):
        return True
    return False


def _check_is_zone_changed(old_zone, new_zone):
    '''
    Compare the basic parameters of zones. Returns list of changes.
    '''

    changes = []

    if old_zone["dnssec"] != new_zone["dnssec"]:
        changes.append({
            "dnssec": {"old": old_zone["dnssec"], "new": new_zone["dnssec"]}
        })

    return changes


def _check_are_records_changed(old_records, new_records):
    '''
    Compare content parameters of rrsets and returns True is record is changed.
    Otherwise returns False.
    '''

    old_content = _extract_content_from_records(old_records)
    new_content = _extract_content_from_records(new_records)

    old_content.sort()
    new_content.sort()

    return old_content != new_content


def _check_are_rrsets_changed(old_rrsets, new_rrsets):
    '''
    Compare the basic parameters of rrsets. Returns list of changes rrsets.
    '''

    changes = []

    for new_rrset in new_rrsets:
        is_new = True
        for old_rrset in old_rrsets:
            if new_rrset["name"] == old_rrset["name"] and new_rrset["type"] == old_rrset["type"]:
                is_new = False
                if _check_are_records_changed(old_rrset["records"], new_rrset["records"]):
                    changes.append({
                        new_rrset["name"]:
                            {
                                "type": new_rrset["type"],
                                "old": {
                                    "ttl": old_rrset["ttl"],
                                    "content": _extract_content_from_records(old_rrset["records"])
                                },
                                "new": {
                                    "ttl": new_rrset["ttl"],
                                    "content": _extract_content_from_records(new_rrset["records"])
                                }
                            }
                    })
        if is_new:
            changes.append({
                new_rrset["name"]:
                    {
                        "type": new_rrset["type"],
                        "new": {
                            "ttl": new_rrset["ttl"],
                            "content": _extract_content_from_records(new_rrset["records"])
                        }
                    }
            })

    return changes


def _check_are_rrsets_deleted(rrsets):
    '''
    Check is rrset list has records to delete. Return list of deleted rrsets.
    '''

    deletions = []

    for rrset in rrsets:
        if rrset.get("changetype", "") == DELETE_CHANGETYPE:
            content_list = []
            for record in rrset["records"]:
                content_list.append(record["content"])
            deletions.append({rrset["name"]: {"type": rrset["type"], "ttl": rrset["ttl"], "content": content_list}})

    return deletions


def _check_are_rrsets_have_ns(rrsets):
    '''
    Check is a rrset list has NS records.
    '''

    for rrset in rrsets:
        if rrset["type"].upper() == DNS_RECORD_NS:
            return True

    return False


def _filter_incorrect_soa_records(rrsets):
    '''
    Remove incorrect SOA records from RRSets which is returned by API.
    Probably a temporary method, need for test purposes.
    '''

    for rrset in rrsets:
        if rrset["type"].upper() == DNS_RECORD_SOA:
            rrsets.remove(rrset)
            # for record in rrset["records"]:
            #     if "misconfigured" in record["content"]:
            #         rrsets.remove(rrset)
            #         break

    return rrsets


def _prepare_nameservers_rrsets(name, nameservers):
    '''
    Prepare and return a list of RRSet object for nameservers.
    '''

    result = []

    if nameservers:

        records_result = []

        for nameserver in nameservers:
            records_object = {
                "content": _add_trailing_dot(nameserver),
                "disabled": False
            }
            records_result.append(records_object)

        result_object = {
            "name": _add_trailing_dot(name),
            "type": DNS_RECORD_NS,
            "changetype": REPLACE_CHANGETYPE,
            "ttl": DEFAULT_NS_TTL,
            "records": records_result
        }

        result.append(result_object)

    return result


def _prepare_rrset(rrset):
    '''
    Convert and return RRSet API object from the request object.
    '''

    result_records = []
    contents = []

    result = {
        "name": _add_trailing_dot(rrset["name"]),
        "type": rrset["type"].upper(),
        "changetype": rrset.get("changetype", REPLACE_CHANGETYPE)
    }

    if rrset.get("ttl", None):
        result["ttl"] = rrset["ttl"]
    else:
        result["ttl"] = DEFAULT_TTL

    # Universal method for API rrsets objects and for Salt objects.
    # Use "records" field for API rrsets objects.
    if rrset.get("records", None):
        records = rrset["records"]
        for record in records:
            contents.append(record["content"])
    else:
        # Adn "content" field for Salt objects.
        # Could use lists or just string values.
        if rrset["content"]:
            if isinstance(rrset["content"], list):
                contents += rrset["content"]
            else:
                contents.append(rrset["content"])
        else:
            # If field "content" is empty then record will be deleted.
            result["changetype"] = DELETE_CHANGETYPE

    for content in contents:
        result_record = {
            "disabled": False
        }

        if result["type"] == DNS_RECORD_TXT:
            result_record["content"] = "\"" + content + "\""
        else:
            result_record["content"] = _add_trailing_dot(content)

        result_records.append(result_record)

    result["records"] = result_records

    return result


def _prepare_rrsets(name, drop_existing, nameservers, new_rrsets, old_rrsets=None):
    '''
    Prepare and returns new RRSet list depends on existing RRSet list, new RRSet list,
    nameservers list and Drop existing parameter.
    '''

    result = []

    if old_rrsets:

        for old_rrset in old_rrsets:
            if drop_existing:
                old_rrset["changetype"] = DELETE_CHANGETYPE
            result.append(_prepare_rrset(old_rrset))

        # If not add nameservers from nameservers parameter or defaults
        if not _check_are_rrsets_have_ns(new_rrsets):
            new_rrsets += _prepare_nameservers_rrsets(name, nameservers)

        for new_rrset in new_rrsets:
            is_new = True
            is_conflicting = False
            new_rrset = _prepare_rrset(new_rrset)
            for idx, current in enumerate(result):
                # Check if old and new records is
                if _check_records_equality(current, new_rrset):
                    is_new = False
                    result[idx] = new_rrset
                    # Prevent conflicts with pre-existing A or CNAME RRset
                    if (current["type"] == DNS_RECORD_CNAME or new_rrset["type"] == DNS_RECORD_CNAME) and \
                        (current["type"] == DNS_RECORD_A or new_rrset["type"] == DNS_RECORD_A):
                        is_conflicting = True
                        conflicting_record = current
                        conflicting_record["changetype"] = DELETE_CHANGETYPE
                    break
            if is_new:
                result.append(new_rrset)
            if is_conflicting:
                result.append(conflicting_record)
    else:
        for new_rrset in new_rrsets:
            result.append(_prepare_rrset(new_rrset))

        if not _check_are_rrsets_have_ns(new_rrsets):
            result += _prepare_nameservers_rrsets(name, nameservers)

    return _filter_incorrect_soa_records(result)


def _prepare_new_zone_result_object(request):
    records = []
    rrsets = request.get("rrsets", [])
    for rrset in rrsets:
        record_object = {
            rrset["name"]:
                {
                    "content": _extract_content_from_records(rrset["records"]),
                    "type": rrset["type"],
                    "ttl": rrset["ttl"]
                }
        }
        records.append(record_object)

    return {
        "name": request["name"],
        "dnssec": request["dnssec"],
        "nameservers": request["nameservers"],
        "records": records
    }


def _validate_rrsets(rrsets, nameservers):
    '''
    Validate a list of RRSets and raise an exception if something is wrong.
    '''

    if rrsets:
        for rrset in rrsets:
            if not rrset.get("name", None):
                raise CommandExecutionError(
                    "One of Resource Record Set doesn't have a name")
            if not rrset.get("type", None):
                raise CommandExecutionError(
                    "Resource Record Set %s dosn't have a type" % (rrset["name"]))
            if not rrset.get("content", None) and not rrset.get("records", None) \
                and rrset.get("changetype", "") != DELETE_CHANGETYPE:
                raise CommandExecutionError(
                    "Resource Record Set %s doesn't have a records list" % (rrset["name"]))

        if not _check_are_rrsets_have_ns(rrsets) and not nameservers:
            raise CommandExecutionError(
                "Resource Record Set doesn't have any NS records")


def _check_is_valid_ip_address(address):
    '''
    Check if argument is valid IPv4 address
    '''
    try:
        socket.inet_pton(socket.AF_INET, address)
    except AttributeError:  # no inet_pton here, sorry
        try:
            socket.inet_aton(address)
        except socket.error:
            return False
        return address.count('.') == 3
    except socket.error:  # not a valid address
        return False
    return True


def _add_trailing_dot(zone):
    '''
    Check and add a trailing dot for zone names and content (API requirement).
    '''

    if not _check_is_valid_ip_address(zone):
        if not zone.endswith(".") and zone not in ["*", "@"]:
            zone = zone + "."

    return zone


def _extract_content_from_records(records):
    result = []

    for record in records:
        if record.get("content", None):
            result.append(record["content"])

    return result


def manage_zone(name, key, server, rrsets=[], nameservers=[], drop_existing=False, dnssec=False):
    '''
    Create zone and/or return zone id
    '''

    url = requests.compat.urljoin(server, POWERDNS_URL_ZONES_TEMPLATE)

    headers = {
        POWERDNS_AUTH_HEADER: key
    }

    result = {
        "name": name,
        "changes": {},
        "result": True,
    }

    request = {
        "name": _add_trailing_dot(name),
        "dnssec": dnssec,
        "type": "Zone",
        "kind": "Native",
        "nameservers": []
    }

    zone = _get_zone(name, headers, server)

    # Create new zone with new records
    if zone is None:

        _validate_rrsets(rrsets, nameservers)

        request["rrsets"] = _prepare_rrsets(name, drop_existing, nameservers, rrsets)

        resp = requests.post(url, headers=headers, json=request)

        logger.info("Create new zone {0}".format(name))
        logger.info("Starting request to {0} for zone {1}".format(url, name))
        logger.info(request)

        if resp.status_code == HTTP_RESPONSE_CODE_CREATED:
            result["changes"]["created"] = _prepare_new_zone_result_object(request)
        else:
            logger.info(resp)
            raise CommandExecutionError(resp)

        logger.info(result)

    # Update zone
    else:

        # Check is zone is changing

        update_url = requests.compat.urljoin(url + "/", request["name"])

        zone_changes = _check_is_zone_changed(zone, request)

        if zone_changes:
            resp = requests.put(update_url, headers=headers, json=request)

            logger.info("Update zone {0}".format(name))
            logger.info("Starting request to {0} for zone {1}".format(update_url, name))
            logger.info(request)

            if resp.status_code == HTTP_RESPONSE_CODE_NO_CONTENT:
                result["changes"]["zone"] = zone_changes
            else:
                logger.error(resp.json())
                raise CommandExecutionError(resp.json())

        prepared_rrsets = _prepare_rrsets(name, drop_existing, nameservers, rrsets, zone["rrsets"])

        _validate_rrsets(prepared_rrsets, nameservers)

        request["rrsets"] = prepared_rrsets

        old_rrsets = zone["rrsets"]
        new_rrsets = request["rrsets"]

        rrsets_changes = _check_are_rrsets_changed(old_rrsets, new_rrsets)
        rrsets_deletions = _check_are_rrsets_deleted(new_rrsets)

        if rrsets_changes or rrsets_deletions:

            resp = requests.patch(update_url, headers=headers, json=request)

            logger.info("Update rrsets {0}".format(name))
            logger.info("Starting request to {0} for zone {1}".format(update_url, name))
            logger.info(request)

            if resp.status_code == HTTP_RESPONSE_CODE_NO_CONTENT:
                result["changes"]["records"] = {}
                result["changes"]["records"]["modified"] = rrsets_changes
                result["changes"]["records"]["deleted"] = rrsets_deletions
            else:
                logger.error(resp.json())
                raise CommandExecutionError(resp.json())

    return result


def delete_zone(name, key, server):
    '''
    Remove zone
    '''

    headers = {
        POWERDNS_AUTH_HEADER: key
    }

    result = {
        "name": name,
        "changes": {},
        "result": True,
    }

    zone = _get_zone(name, headers, server)

    if zone:

        url = requests.compat.urljoin(requests.compat.urljoin(server, POWERDNS_URL_ZONES_TEMPLATE + "/"), name)

        resp = requests.delete(url, headers=headers)

        if resp.status_code == HTTP_RESPONSE_CODE_NO_CONTENT:
            result["changes"]["deleted"] = name
        else:
            raise CommandExecutionError(resp.json())

    return result
