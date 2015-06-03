# -*- coding: utf-8 -*-
'''
Boto Common Utils
=================

Note: This module depends on the dicts packed by the loader and,
therefore, must be accessed via the loader or from the __utils__ dict.

The __utils__ dict will not be automatically available to execution modules
until Beryllium. The `salt.utils.compat.pack_dunder` helper function
provides backwards compatibility.

This module provides common functionality for the boto execution modules.
The expected usage is to call `apply_funcs` from the `__virtual__` function
of the module. This will bring properly initilized partials of  `_get_conn`
and `_cache_id` into the module's namespace.

Example Usage:

    .. code-block:: python

        import salt.utils.boto

        def __virtual__():
            # only required in 2015.2
            salt.utils.compat.pack_dunder(__name__)

            __utils__['boto.apply_funcs'](__name__, 'vpc')

        def test():
            conn = _get_conn()
            vpc_id = _cache_id('test-vpc')

.. versionadded:: Beryllium
'''

# Import Python libs
from __future__ import absolute_import
import hashlib
import logging
import sys
from distutils.version import LooseVersion as _LooseVersion  # pylint: disable=import-error,no-name-in-module
from functools import partial

# Import salt libs
from salt.ext.six import string_types  # pylint: disable=import-error
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin
from salt.exceptions import SaltInvocationError

# Import third party libs
# pylint: disable=import-error
try:
    # pylint: disable=import-error
    import boto
    import boto.exception
    # pylint: enable=import-error
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False
# pylint: enable=import-error


log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    '''
    # TODO: Determine minimal version we want to support. VPC requires > 2.8.0.
    required_boto_version = '2.0.0'
    if not HAS_BOTO:
        return False
    elif _LooseVersion(boto.__version__) < _LooseVersion(required_boto_version):
        return False
    else:
        return True


def _option(value):
    '''
    Look up the value for an option.
    '''
    if value in __opts__:
        return __opts__[value]
    master_opts = __pillar__.get('master', {})
    if value in master_opts:
        return master_opts[value]
    if value in __pillar__:
        return __pillar__[value]


def _get_profile(service, region, key, keyid, profile):
    if profile:
        if isinstance(profile, string_types):
            _profile = _option(profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and _option(service + '.region'):
        region = _option(service + '.region')

    if not region:
        region = 'us-east-1'

    if not key and _option(service + '.key'):
        key = _option(service + '.key')
    if not keyid and _option(service + '.keyid'):
        keyid = _option(service + '.keyid')

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

        __utils__['boto.cache_id']('ec2', 'myinstance',
                                   'i-a1b2c3',
                                   profile='custom_profile')
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
        elif resource_id in __context__.values():
            ctx = dict((k, v) for k, v in __context__.items() if v != resource_id)
            __context__.clear()
            __context__.update(ctx)
            return True
        else:
            return False
    if resource_id:
        __context__[cxkey] = resource_id
        return True

    return __context__.get(cxkey)


def cache_id_func(service):
    '''
    Returns a partial `cache_id` function for the provided service.

    ... code-block:: python

        cache_id = __utils__['boto.cache_id_func']('ec2')
        cache_id('myinstance', 'i-a1b2c3')
        instance_id = cache_id('myinstance')
    '''
    return partial(cache_id, service)


def get_connection(service, module=None, region=None, key=None, keyid=None,
                   profile=None):
    '''
    Return a boto connection for the service.

    .. code-block:: python

        conn = __utils__['boto.get_connection']('ec2', profile='custom_profile')
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
        if conn is None:
            raise SaltInvocationError('Region "{0}" is not '
                                      'valid.'.format(region))
    except boto.exception.NoAuthHandlerFound:
        raise SaltInvocationError('No authentication credentials found when '
                                  'attempting to make boto {0} connection to '
                                  'region "{1}".'.format(service, region))
    __context__[cxkey] = conn
    return conn


def get_connection_func(service, module=None):
    '''
    Returns a partial `get_connection` function for the provided service.

    ... code-block:: python

        get_conn = __utils__['boto.get_connection_func']('ec2')
        conn = get_conn()
    '''
    return partial(get_connection, service, module=module)


def get_error(e):
    # The returns from boto modules vary greatly between modules. We need to
    # assume that none of the data we're looking for exists.
    aws = {}
    if hasattr(e, 'status'):
        aws['status'] = e.status
    if hasattr(e, 'reason'):
        aws['reason'] = e.reason
    if hasattr(e, 'message') and e.message != '':
        aws['message'] = e.message
    if hasattr(e, 'error_code') and e.error_code is not None:
        aws['code'] = e.error_code

    if 'message' in aws and 'reason' in aws:
        message = '{0}: {1}'.format(aws['reason'], aws['message'])
    elif 'message' in aws:
        message = aws['message']
    elif 'reason' in aws:
        message = aws['reason']
    else:
        message = ''
    r = {'message': message}
    if aws:
        r['aws'] = aws
    return r


def exactly_n(l, n=1):
    '''
    Tests that exactly N items in an iterable are "truthy" (neither None,
    False, nor 0).
    '''
    i = iter(l)
    return all(any(i) for j in range(n)) and not any(i)


def exactly_one(l):
    return exactly_n(l)


def assign_funcs(modname, service, module=None):
    '''
    Assign _get_conn and _cache_id functions to the named module.

    .. code-block:: python

        _utils__['boto.assign_partials'](__name__, 'ec2')
    '''
    mod = sys.modules[modname]
    setattr(mod, '_get_conn', get_connection_func(service, module=module))
    setattr(mod, '_cache_id', cache_id_func(service))

    # TODO: Remove this and import salt.utils.exactly_one into boto_* modules instead
    # Leaving this way for now so boto modules can be back ported
    setattr(mod, '_exactly_one', exactly_one)
