# -*- coding: utf-8 -*-
'''
Manage DNS records and zones using libcloud

    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`

.. versionadded:: 2016.11.0

Create and delete DNS records or zones through Libcloud. Libcloud's DNS system supports over 20 DNS
providers including Amazon, Google, GoDaddy, Softlayer

This module uses ``libcloud``, which can be installed via package, or pip.

:configuration:
    This module uses a configuration profile for one or multiple DNS providers

    .. code-block:: yaml

        libcloud_dns:
          profile1:
            driver: godaddy
            key: 2orgk34kgk34g
          profile2:
            driver: route53
            key: blah
            secret: blah

Example:

.. code-block:: yaml

    webserver:
      libcloud_dns.zone_present:
        name: mywebsite.com
        profile: profile1
      libcloud_dns.record_present:
        name: www
        zone: mywebsite.com
        type: A
        data: 12.34.32.3
        profile: profile1


:depends: apache-libcloud
'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.utils
from salt.utils.versions import LooseVersion as _LooseVersion

log = logging.getLogger(__name__)


def __virtual__():
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)


def state_result(result, message):
    return {'result': result, 'comment': message}


def zone_present(domain, type, profile):
    '''
    Ensures a record is present.

    :param domain: Zone name, i.e. the domain name
    :type  domain: ``str``

    :param type: Zone type (master / slave), defaults to master
    :type  type: ``str``

    :param profile: The profile key
    :type  profile: ``str``
    '''
    zones = __salt__['libcloud_dns.list_zones'](profile)
    if not type:
        type = 'master'
    matching_zone = [z for z in zones if z.domain == domain]
    if len(matching_zone) > 0:
        return state_result(True, "Zone already exists")
    else:
        result = __salt__['libcloud_dns.create_zone'](domain, profile, type)
        return state_result(result, "Created new zone")


def zone_absent(domain, profile):
    '''
    Ensures a record is absent.

    :param domain: Zone name, i.e. the domain name
    :type  domain: ``str``

    :param profile: The profile key
    :type  profile: ``str``
    '''
    zones = __salt__['libcloud_dns.list_zones'](profile)
    matching_zone = [z for z in zones if z.domain == domain]
    if len(matching_zone) == 0:
        return state_result(True, "Zone already absent")
    else:
        result = __salt__['libcloud_dns.delete_zone'](matching_zone[0].id, profile)
        return state_result(result, "Deleted zone")


def record_present(name, zone, type, data, profile):
    '''
    Ensures a record is present.

    :param name: Record name without the domain name (e.g. www).
                 Note: If you want to create a record for a base domain
                 name, you should specify empty string ('') for this
                 argument.
    :type  name: ``str``

    :param zone: Zone where the requested record is created, the domain name
    :type  zone: ``str``

    :param type: DNS record type (A, AAAA, ...).
    :type  type: ``str``

    :param data: Data for the record (depends on the record type).
    :type  data: ``str``

    :param profile: The profile key
    :type  profile: ``str``
    '''
    zones = __salt__['libcloud_dns.list_zones'](profile)
    try:
        matching_zone = [z for z in zones if z.domain == zone][0]
    except IndexError:
        return state_result(False, "Could not locate zone")
    records = __salt__['libcloud_dns.list_records'](matching_zone.id, profile)
    matching_records = [record for record in records
                        if record.name == name and
                        record.type == type and
                        record.data == data]
    if len(matching_records) == 0:
        result = __salt__['libcloud_dns.create_record'](
            name, matching_zone.id,
            type, data, profile)
        return state_result(result, "Created new record")
    else:
        return state_result(True, "Record already exists")


def record_absent(name, zone, type, data, profile):
    '''
    Ensures a record is absent.

    :param name: Record name without the domain name (e.g. www).
                 Note: If you want to create a record for a base domain
                 name, you should specify empty string ('') for this
                 argument.
    :type  name: ``str``

    :param zone: Zone where the requested record is created, the domain name
    :type  zone: ``str``

    :param type: DNS record type (A, AAAA, ...).
    :type  type: ``str``

    :param data: Data for the record (depends on the record type).
    :type  data: ``str``

    :param profile: The profile key
    :type  profile: ``str``
    '''
    zones = __salt__['libcloud_dns.list_zones'](profile)
    try:
        matching_zone = [z for z in zones if z.domain == zone][0]
    except IndexError:
        return state_result(False, "Zone could not be found")
    records = __salt__['libcloud_dns.list_records'](matching_zone.id, profile)
    matching_records = [record for record in records
                        if record.name == name and
                        record.type == type and
                        record.data == data]
    if len(matching_records) > 0:
        result = []
        for record in matching_records:
            result.append(__salt__['libcloud_dns.delete_record'](
                matching_zone.id,
                record.id,
                profile))
        return state_result(all(result), "Removed {0} records".format(len(result)))
    else:
        return state_result(True, "Records already absent")
