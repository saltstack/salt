# -*- coding: utf-8 -*-
'''
Manage DNS records and zones using libcloud

    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`

.. versionadded:: Carbon

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
      libcloud_dns.present:
        name: www
        zone: mywebsite.com
        type: A
        data: 12.34.32.3
        profile: profile1


:depends: apache-libcloud
'''

# Import Python Libs
from __future__ import absolute_import

from distutils.version import LooseVersion as _LooseVersion  # pylint: disable=import-error,no-name-in-module

import salt.modules.libcloud_dns as libcloud_dns_module

# Import salt libs
import salt.utils
import logging
log = logging.getLogger(__name__)

# Import third party libs
REQUIRED_LIBCLOUD_VERSION = '0.21.0'
try:
    #pylint: disable=unused-import
    import libcloud
    from libcloud.dns.providers import get_driver
    #pylint: enable=unused-import
    if _LooseVersion(libcloud.__version__) < _LooseVersion(REQUIRED_LIBCLOUD_VERSION):
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
    key = config.get('key')
    secret = config.get('secret', None)
    secure = config.get('secure', True)
    host = config.get('host', None)
    port = config.get('port', None)
    return cls(key, secret, secure, host, port)


def state_result(result, message):
    return {'result': result, 'comment': message}


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
    zones = libcloud_dns_module.list_zones(profile)
    try:
        matching_zone = [z for z in zones if z.name == zone][0]
    except IndexError:
        return state_result(False, "Could not locate zone")
    records = libcloud_dns_module.list_records(matching_zone.id, profile)
    matching_records = [record for record in records
                        if record.name == name and
                        record.type == type and
                        record.data == data]
    if len(matching_records) == 0:
        result = libcloud_dns_module.create_record(
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
    zones = libcloud_dns_module.list_zones(profile)
    try:
        matching_zone = [z for z in zones if z.name == zone][0]
    except IndexError:
        return state_result(False, "Zone could not be found")
    records = libcloud_dns_module.list_records(matching_zone.id, profile)
    matching_records = [record for record in records
                        if record.name == name and
                        record.type == type and
                        record.data == data]
    if len(matching_records) > 0:
        result = []
        for record in matching_records:
            result.append(libcloud_dns_module.delete_record(
                matching_zone.id,
                record.id,
                profile))
        return state_result(all(result), "Removed {0} records".format(len(result)))
    else:
        return state_result(True, "Records already absent")
