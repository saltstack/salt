# -*- coding: utf-8 -*-
'''
Apache Libcloud DNS Management
==============================

Connection module for Apache Libcloud DNS management

.. versionadded:: 2016.11.0

:configuration:
    This module uses a configuration profile for one or multiple DNS providers

    .. code-block:: yaml

        libcloud_dns:
            profile_test1:
              driver: cloudflare
              key: 12345
              secret: mysecret
            profile_test2:
              driver: godaddy
              key: 12345
              secret: mysecret
              shopper_id: 12345

:depends: apache-libcloud
'''
# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602

from __future__ import absolute_import

# Import Python libs
import logging

# Import salt libs
import salt.utils.compat
from salt.utils.versions import LooseVersion as _LooseVersion

log = logging.getLogger(__name__)

# Import third party libs
REQUIRED_LIBCLOUD_VERSION = '0.21.0'
try:
    #pylint: disable=unused-import
    import libcloud
    from libcloud.dns.providers import get_driver
    from libcloud.dns.types import RecordType
    #pylint: enable=unused-import
    if hasattr(libcloud, '__version__') and _LooseVersion(libcloud.__version__) < _LooseVersion(REQUIRED_LIBCLOUD_VERSION):
        raise ImportError()
    logging.getLogger('libcloud').setLevel(logging.CRITICAL)
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False


def __virtual__():
    '''
    Only load if libcloud libraries exist.
    '''
    if not HAS_LIBCLOUD:
        msg = ('A apache-libcloud library with version at least {0} was not '
               'found').format(REQUIRED_LIBCLOUD_VERSION)
        return (False, msg)
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)


def _get_driver(profile):
    config = __salt__['config.option']('libcloud_dns')[profile]
    cls = get_driver(config['driver'])
    args = config
    del args['driver']
    args['key'] = config.get('key')
    args['secret'] = config.get('secret', None)
    args['secure'] = config.get('secure', True)
    args['host'] = config.get('host', None)
    args['port'] = config.get('port', None)
    return cls(**args)


def list_record_types(profile):
    '''
    List available record types for the given profile, e.g. A, AAAA

    :param profile: The profile key
    :type  profile: ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_dns.list_record_types profile1
    '''
    conn = _get_driver(profile=profile)
    return conn.list_record_types()


def list_zones(profile):
    '''
    List zones for the given profile

    :param profile: The profile key
    :type  profile: ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_dns.list_zones profile1
    '''
    conn = _get_driver(profile=profile)
    return conn.list_zones()


def list_records(zone_id, profile):
    '''
    List records for the given zone_id on the given profile

    :param zone_id: Zone to export.
    :type  zone_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_dns.list_records google.com profile1
    '''
    conn = _get_driver(profile=profile)
    zone = conn.get_zone(zone_id)
    return conn.list_records(zone)


def get_zone(zone_id, profile):
    '''
    Get zone information for the given zone_id on the given profile

    :param zone_id: Zone to export.
    :type  zone_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_dns.get_zone google.com profile1
    '''
    conn = _get_driver(profile=profile)
    return conn.get_zone(zone_id)


def get_record(zone_id, record_id, profile):
    '''
    Get record information for the given zone_id on the given profile

    :param zone_id: Zone to export.
    :type  zone_id: ``str``

    :param record_id: Record to delete.
    :type  record_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_dns.get_record google.com www profile1
    '''
    conn = _get_driver(profile=profile)
    return conn.get_record(zone_id, record_id)


def create_zone(domain, profile, type='master', ttl=None):
    '''
    Create a new zone.

    :param domain: Zone domain name (e.g. example.com)
    :type domain: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param type: Zone type (master / slave).
    :type  type: ``str``

    :param ttl: TTL for new records. (optional)
    :type  ttl: ``int``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_dns.create_zone google.com profile1
    '''
    conn = _get_driver(profile=profile)
    return conn.create_record(domain, type=type, ttl=ttl)


def update_zone(zone_id, domain, profile, type='master', ttl=None):
    '''
    Update an existing zone.

    :param zone_id: Zone ID to update.
    :type  zone_id: ``str``

    :param domain: Zone domain name (e.g. example.com)
    :type  domain: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param type: Zone type (master / slave).
    :type  type: ``str``

    :param ttl: TTL for new records. (optional)
    :type  ttl: ``int``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_dns.update_zone google.com google.com profile1 type=slave
    '''
    conn = _get_driver(profile=profile)
    zone = conn.get_zone(zone_id)
    return conn.update_zone(zone=zone, domain=domain, type=type, ttl=ttl)


def create_record(name, zone_id, type, data, profile):
    '''
    Create a new record.

    :param name: Record name without the domain name (e.g. www).
                 Note: If you want to create a record for a base domain
                 name, you should specify empty string ('') for this
                 argument.
    :type  name: ``str``

    :param zone_id: Zone where the requested record is created.
    :type  zone_id: ``str``

    :param type: DNS record type (A, AAAA, ...).
    :type  type: ``str``

    :param data: Data for the record (depends on the record type).
    :type  data: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_dns.create_record www google.com A 12.32.12.2 profile1
    '''
    conn = _get_driver(profile=profile)
    record_type = _string_to_record_type(type)
    zone = conn.get_zone(zone_id)
    return conn.create_record(name, zone, record_type, data)


def delete_zone(zone_id, profile):
    '''
    Delete a zone.

    :param zone_id: Zone to delete.
    :type  zone_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :rtype: ``bool``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_dns.delete_zone google.com profile1
    '''
    conn = _get_driver(profile=profile)
    zone = conn.get_zone(zone_id=zone_id)
    return conn.delete_zone(zone)


def delete_record(zone_id, record_id, profile):
    '''
    Delete a record.

    :param zone_id: Zone to delete.
    :type  zone_id: ``str``

    :param record_id: Record to delete.
    :type  record_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :rtype: ``bool``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_dns.delete_record google.com www profile1
    '''
    conn = _get_driver(profile=profile)
    record = conn.get_record(zone_id=zone_id, record_id=record_id)
    return conn.delete_record(record)


def get_bind_data(zone_id, profile):
    '''
    Export Zone to the BIND compatible format.

    :param zone_id: Zone to export.
    :type  zone_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :return: Zone data in BIND compatible format.
    :rtype: ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_dns.get_bind_data google.com profile1
    '''
    conn = _get_driver(profile=profile)
    zone = conn.get_zone(zone_id)
    return conn.export_zone_to_bind_format(zone)


def _string_to_record_type(string):
    '''
    Return a string representation of a DNS record type to a
    libcloud RecordType ENUM.

    :param string: A record type, e.g. A, TXT, NS
    :type  string: ``str``

    :rtype: :class:`RecordType`
    '''
    string = string.upper()
    record_type = getattr(RecordType, string)
    return record_type
