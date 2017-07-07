# -*- coding: utf-8 -*-
'''
Boto Common Utils
=================

Note: This module depends on the dicts packed by the loader and,
therefore, must be accessed via the loader or from the __utils__ dict.

The __utils__ dict will not be automatically available to execution modules
until 2015.8.0. The `salt.utils.compat.pack_dunder` helper function
provides backwards compatibility.

This module provides common functionality for the boto execution modules.
The expected usage is to call `assign_funcs` from the `__virtual__` function
of the module. This will bring properly initialized partials of  `_get_conn`
and `_cache_id` into the module's namespace.

Example Usage:

    .. code-block:: python

        import salt.utils.boto

        def __virtual__():
            # only required in 2015.2
            salt.utils.compat.pack_dunder(__name__)

            __utils__['boto.assign_funcs'](__name__, 'vpc')

        def test():
            conn = _get_conn()
            vpc_id = _cache_id('test-vpc')

.. versionadded:: 2015.8.0
'''

# Import Python libs
from __future__ import absolute_import
import hashlib
import logging
import sys
from functools import partial
from salt.loader import minion_mods

# Import salt libs
import salt.ext.six as six
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin
from salt.exceptions import SaltInvocationError
from salt.utils.versions import LooseVersion as _LooseVersion
import salt.utils

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

__salt__ = None


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
        global __salt__
        if not __salt__:
            __salt__ = minion_mods(__opts__)
        return True


def _get_profile(service, region, key, keyid, profile):
    if profile:
        if isinstance(profile, six.string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', region or None)
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
        hash_string = region + keyid + key
        if six.PY3:
            hash_string = salt.utils.to_bytes(hash_string)
        cxkey = label + hashlib.md5(hash_string).hexdigest()
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
    module, submodule = ('boto.' + module).rsplit('.', 1)

    svc_mod = getattr(__import__(module, fromlist=[submodule]), submodule)

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


def assign_funcs(modname, service, module=None, pack=None):
    '''
    Assign _get_conn and _cache_id functions to the named module.

    .. code-block:: python

        _utils__['boto.assign_partials'](__name__, 'ec2')
    '''
    if pack:
        global __salt__  # pylint: disable=W0601
        __salt__ = pack
    mod = sys.modules[modname]
    setattr(mod, '_get_conn', get_connection_func(service, module=module))
    setattr(mod, '_cache_id', cache_id_func(service))

    # TODO: Remove this and import salt.utils.exactly_one into boto_* modules instead
    # Leaving this way for now so boto modules can be back ported
    setattr(mod, '_exactly_one', exactly_one)


def paged_call(function, *args, **kwargs):
    """Retrieve full set of values from a boto API call that may truncate
    its results, yielding each page as it is obtained.
    """
    marker_flag = kwargs.pop('marker_flag', 'marker')
    marker_arg = kwargs.pop('marker_flag', 'marker')
    while True:
        ret = function(*args, **kwargs)
        marker = ret.get(marker_flag)
        yield ret
        if not marker:
            break
        kwargs[marker_arg] = marker
