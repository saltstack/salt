# -*- coding: utf-8 -*-
'''
Common functionality for boto modules

.. versionadded:: Beryllium

:depends: boto
'''

# Import Python libs
from __future__ import absolute_import
import hashlib
import logging

# Import Salt libs
import salt.ext.six as six

# Import third party libs
try:
    # pylint: disable=import-error
    import boto
    # pylint: enable=import-error
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        return False
    return True


def _get_profile(service, region, key, keyid, profile):
    if profile:
        if isinstance(profile, six.string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and __salt__['config.option'](service + '.region'):
        region = __salt__['config.option'](service + '.region')

    if not region:
        region = 'us-east-1'

    if not key and __salt__['config.option'](service + '.key'):
        key = __salt__['config.option'](service + '.key')
    if not keyid and __salt__['config.option'](service + '.keyid'):
        keyid = __salt__['config.option'](service + '.keyid')

    label = 'boto_{0}:'.format(service)
    if keyid:
        cxkey = label + hashlib.md5(region + keyid + key).hexdigest()
    else:
        cxkey = label + region

    return (cxkey, region, key, keyid)


def cache_id(service, name, sub_resource=None, resource_id=None,
             invalidate=False, region=None, key=None, keyid=None,
             profile=None):
    '''
    Cache, invalidate, or retrieve an AWS resource id keyed by name.

    .. code-block:: python

        conn = __salt__['boto_common.cache_id']('ec2', 'myinstance', \
                    i-a1b2c3', profile='custom_profile')
    '''

    cxkey, _, _, _ = _get_profile(service, region, key,
                                  keyid, profile)
    if sub_resource:
        cxkey = '{0}:{1}:{2}:id'.format(cxkey, sub_resource, name)
    else:
        cxkey = '{0}:{1}:id'.format(cxkey, name)

    if invalidate:
        if cxkey in __context__:
            del __context__[cxkey]
            return True
        else:
            return False
    if resource_id:
        __context__[cxkey] = resource_id
        return True

    return __context__.get(cxkey)


def get_connection(service, module=None, region=None, key=None, keyid=None, profile=None):
    '''
    Return a boto connection for the service. Not intended for CLI usage.

    .. code-block:: python

        conn = __salt__['boto_common.get_connection']('ec2', profile='custom_profile')
    '''

    module = module or service
    svc_mod = __import__('boto.' + module, fromlist=[module])

    cxkey, region, key, keyid = _get_profile(service, region, key,
                                             keyid, profile)
    cxkey = cxkey + ':conn'

    if cxkey in __context__:
        return __context__[cxkey]

    try:
        conn = svc_mod.connect_to_region(region, aws_access_key_id=keyid,
                                         aws_secret_access_key=key)
    except boto.exception.NoAuthHandlerFound:
        log.error('No authentication credentials found when '
                  'attempting to make boto {0} connection to '
                  'region "{1}".'.format(service, region))
        return None
    __context__[cxkey] = conn
    return conn
