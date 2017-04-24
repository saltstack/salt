# -*- coding: utf-8 -*-
'''
Apache Libcloud Storage State
=============================

Manage cloud storage using libcloud

    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`

Apache Libcloud Storage (object/blob) management for a full list
of supported clouds, see http://libcloud.readthedocs.io/en/latest/storage/supported_providers.html

Clouds include Amazon S3, Google Storage, Aliyun, Azure Blobs, Ceph, OpenStack swift

.. versionadded:: Oxygen

:configuration:
    This module uses a configuration profile for one or multiple Storage providers

    .. code-block:: yaml

        libcloud_storage:
            profile_test1:
              driver: google_storage
              key: GOOG0123456789ABCXYZ
              secret: mysecret
            profile_test2:
              driver: s3
              key: 12345
              secret: mysecret

Examples
--------

Creating a container and uploading a file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    web_things:
      libcloud_storage.container_present:
        name: my_container_name  
        profile: profile1
      libcloud_storage.object_present:
        name: my_file.jpg
        container: my_container_name
        path: /path/to/local/file.jpg
        profile: profile1

Downloading a file
~~~~~~~~~~~~~~~~~~

This example will download the file from the remote cloud and keep it locally

.. code-block:: yaml

    web_things:
      libcloud_storage.file_present:
        object_name: my_file.jpg
        container: my_container_name
        path: /path/to/local/file.jpg
        profile: profile1

:depends: apache-libcloud
'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)


def state_result(result, message):
    return {'result': result, 'comment': message}


def container_present(name, profile):
    '''
    Ensures a record is present.

    :param domain: Zone name, i.e. the domain name
    :type  domain: ``str``

    :param type: Zone type (master / slave), defaults to master
    :type  type: ``str``

    :param profile: The profile key
    :type  profile: ``str``
    '''
    zones = __salt__['libcloud_dns.list_containers'](profile)
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
