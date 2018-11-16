# -*- coding: utf-8 -*-
'''
Manage DNS records and zones using libcloud

    :codeauthor: Anthony Shaw <anthonyshaw@apache.org>

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

    my-zone:
      libcloud_dns.zone_present:
        - domain: mywebsite.com
        - type: master
        - profile: profile1
    my-website:
      libcloud_dns.record_present:
        - name: www
        - zone: mywebsite.com
        - type: A
        - data: 12.34.32.3
        - profile: profile1
        - require:
          - libcloud_dns: my-zone


:depends: apache-libcloud
'''

# Import Python Libs
from __future__ import absolute_import

# Import salt libs
import salt.utils.compat


def __virtual__():
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)


def state_result(result, message, name, changes=None):
    if changes is None:
        changes = {}
    return {'result': result,
            'comment': message,
            'name': name,
            'changes': changes}


def zone_present(name, profile, domain=None, type=None, ttl=None, extra=None):
    '''
    Ensures a record is present.

    :param name: Name for this zone
    :type  name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param domain: The domain name (defaults to name if not provided)
    :type  domain: ``str``

    :param type: Zone type (master / slave), defaults to master
    :type  type: ``str``

    :param ttl: TTL for new records. (optional)
    :type  ttl: ``int``

    :param extra: Extra data (optional)
    :type  extra: ``dict``
    '''
    zones = __salt__['libcloud_dns.list_zones'](profile)
    type = type or 'master'
    domain = domain or name
    extra = extra or {}
    matching_zone = [z for z in zones if z['domain'] == domain]
    if len(matching_zone) > 0:
        has_changes = False
        if ttl and ttl != matching_zone[0]['ttl']:
            has_changes = True
        if extra:
            for key, value in list(extra.items()):
                if key in matching_zone[0]['extra'] and \
                 matching_zone[0]['extra'][key] != value:
                    has_changes = True
                else:
                    has_changes = True
        if has_changes:
            if __opts__['test']:
                _changes = {
                    'id': matching_zone[0]['id'],
                    'domain': domain,
                    'type': type,
                    'ttl': ttl,
                    'extra': extra
                }
                return state_result(True, 'Will update zone.', name, _changes)
            else:
                result = __salt__['libcloud_dns.update_zone'](
                    zone_id=matching_zone[0]['id'],
                    domain=domain, profile=profile, type=type, ttl=ttl, extra=extra)
                return state_result(True, 'Updated zone.', name, result)
        else:
            return state_result(True, 'Zone already exists.', name)
    else:
        if __opts__['test']:
            _changes = {
                'id': None,
                'domain': domain,
                'type': type,
                'ttl': ttl,
                'extra': extra
            }
            return state_result(None, 'Will create new zone.', name, _changes)
        else:
            result = __salt__['libcloud_dns.create_zone'](
                domain=domain, profile=profile, type=type, ttl=ttl, extra=extra)
            return state_result(True, 'Created new zone.', name, result)


def zone_absent(name, profile, domain=None):
    '''
    Ensures a record is absent.

    :param name: Name for this zone
    :type  name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param domain: The domain name (defaults to name if not provided)
    :type  domain: ``str``
    '''
    domain = domain or name
    zones = __salt__['libcloud_dns.list_zones'](profile)
    matching_zone = [z for z in zones if z['domain'] == domain]
    if len(matching_zone) == 0:
        return state_result(True, 'Zone already absent.', name)
    else:
        _changes = {
            'domain': domain
        }
        if __opts__['test']:
            return state_result(None, 'Will delete zone.', name, _changes)
        else:
            result = __salt__['libcloud_dns.delete_zone'](matching_zone[0]['id'], profile)
            return state_result(result, 'Deleted zone.', name, _changes)


def record_present(name, zone, type, data, profile, extra=None):
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

    :param extra: Extra data (optional)
    :type  extra: ``dict``
    '''
    if not extra:
        extra = {}
    zones = __salt__['libcloud_dns.list_zones'](profile)
    try:
        matching_zone = [z for z in zones if z['domain'] == zone][0]
    except IndexError:
        return state_result(False, 'Zone could not be found.', name)
    records = __salt__['libcloud_dns.list_records'](matching_zone['id'], profile)
    matching_records = [record for record in records
                        if record['name'] == name and
                        record['type'] == type and
                        record['data'] == data]
    if len(matching_records) == 0:
        if __opts__['test']:
            _changes = {
                'id': None,
                'name': name,
                'type': type,
                'data': data,
                'ttl': extra.get('ttl', None),
                'extra': extra,
                'zone': matching_zone
            }
            return state_result(None, 'Will create new record.', name, _changes)
        else:
            result = __salt__['libcloud_dns.create_record'](
                name, matching_zone['id'],
                type, data, profile, extra=extra)
            return state_result(True, 'Created new record.', name, result)
    else:
        return state_result(True, 'Record already exists.', name)


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
        matching_zone = [z for z in zones if z['domain'] == zone][0]
    except IndexError:
        return state_result(False, 'Zone could not be found.', name)
    records = __salt__['libcloud_dns.list_records'](matching_zone['id'], profile)
    matching_records = [record for record in records
                        if record['name'] == name and
                        record['type'] == type and
                        record['data'] == data]
    if len(matching_records) > 0:
        result = []
        if __opts__['test']:
            return state_result(None, 'Will remove {0} records.'.format(len(matching_records)), name, matching_records)
        else:
            for record in matching_records:
                result.append(__salt__['libcloud_dns.delete_record'](
                    matching_zone['id'],
                    record['id'],
                    profile))
            return state_result(all(result), 'Removed {0} records.'.format(len(result)), name, matching_records)
    else:
        return state_result(True, 'Records already absent.', name)
