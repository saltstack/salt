# -*- coding: utf-8 -*-
'''
Boto Common Utils
=================

Note: This module depends on the dicts packed by the loader and,
therefore, must be accessed via the loader or from the __utils__ dict.

.. versionadded:: Beryllium
'''

# NOTE: The functionality for passing in ctx, opts, and pillar is temporary
#       and will be removed in a future version. It is not needed when using
#       this module via the loader.

# Import Python libs
from __future__ import absolute_import
import hashlib
import logging
import sys
from distutils.version import LooseVersion as _LooseVersion  # pylint: disable=import-error,no-name-in-module
from functools import partial

# Import salt libs
import salt.ext.six as six
from salt.exceptions import SaltInvocationError
from salt._compat import ElementTree as ET

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


def _option(value, opts, pillar):
    '''
    Look up the value for an option.
    '''

    if opts is None:
        opts = __opts__

    if pillar is None:
        pillar = __pillar__

    if value in opts:
        return opts[value]
    master_opts = pillar.get('master', {})
    if value in master_opts:
        return master_opts[value]
    if value in pillar:
        return pillar[value]


def _get_profile(service, opts, pillar, region, key, keyid, profile):
    if profile:
        if isinstance(profile, six.string_types):
            _profile = _option(profile, opts, pillar)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and _option(service + '.region', opts, pillar):
        region = _option(service + '.region', opts, pillar)

    if not region:
        region = 'us-east-1'

    if not key and _option(service + '.key', opts, pillar):
        key = _option(service + '.key', opts, pillar)
    if not keyid and _option(service + '.keyid', opts, pillar):
        keyid = _option(service + '.keyid', opts, pillar)

    label = 'boto_{0}:'.format(service)
    if keyid:
        cxkey = label + hashlib.md5(region + keyid + key).hexdigest()
    else:
        cxkey = label + region

    return (cxkey, region, key, keyid)


def cache_id(service, name, sub_resource=None, resource_id=None,
             invalidate=False, region=None, key=None, keyid=None,
             profile=None, ctx=None, opts=None, pillar=None):
    '''
    Cache, invalidate, or retrieve an AWS resource id keyed by name.

    .. code-block:: python

        __utils__['boto.cache_id']('ec2', 'myinstance',
                                   'i-a1b2c3',
                                   profile='custom_profile')
    '''

    if ctx is None:
        ctx = __context__

    cxkey, _, _, _ = _get_profile(service, opts, pillar, region, key,
                                  keyid, profile)
    if sub_resource:
        cxkey = '{0}:{1}:{2}:id'.format(cxkey, sub_resource, name)
    else:
        cxkey = '{0}:{1}:id'.format(cxkey, name)

    if invalidate:
        if cxkey in ctx:
            del ctx[cxkey]
            return True
        else:
            return False
    if resource_id:
        ctx[cxkey] = resource_id
        return True

    return ctx.get(cxkey)


def cache_id_func(service, ctx=None, opts=None, pillar=None):
    '''
    Returns a partial `cache_id` function for the provided service.

    ... code-block:: python

        cache_id = __utils__['boto.cache_id_func']('ec2')
        cache_id('myinstance', 'i-a1b2c3')
        instance_id = cache_id('myinstance')
    '''
    return partial(cache_id, service, ctx=ctx, opts=opts, pillar=pillar)


def get_connection(service, module=None, region=None, key=None, keyid=None,
                   profile=None, ctx=None, opts=None, pillar=None):
    '''
    Return a boto connection for the service.

    .. code-block:: python

        conn = __utils__['boto.get_connection']('ec2', profile='custom_profile')
    '''

    module = module or service

    if ctx is None:
        ctx = __context__

    svc_mod = __import__('boto.' + module, fromlist=[module])

    cxkey, region, key, keyid = _get_profile(service, opts, pillar, region, key,
                                             keyid, profile)
    cxkey = cxkey + ':conn'

    if cxkey in ctx:
        return ctx[cxkey]

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
    ctx[cxkey] = conn
    return conn


def get_connection_func(service, module=None, ctx=None,
                        opts=None, pillar=None):
    '''
    Returns a partial `get_connection` function for the provided service.

    ... code-block:: python

        get_conn = __utils__['boto.get_connection_func']('ec2')
        conn = get_conn()
    '''
    return partial(get_connection, service, module=module, ctx=ctx,
                   opts=opts, pillar=pillar)


def get_error(e):
    aws = {}
    if e.status:
        aws['status'] = e.status
    if e.reason:
        aws['reason'] = e.reason

    try:
        body = e.body or ''
        error = ET.fromstring(body).find('Errors').find('Error')
        error = {'code': error.find('Code').text,
                 'message': error.find('Message').text}
    except (AttributeError, ET.ParseError):
        error = None

    if error:
        aws.update(error)
        message = '{0}: {1}'.format(aws.get('reason', ''),
                                    error['message'])
    else:
        message = aws.get('reason')
    r = {'message': message}
    if aws:
        r['aws'] = aws
    return r


def assign_funcs(modname, service, module=None):
    '''
    Assign _get_conn and _cache_id functions to the named module.

    .. code-block:: python

        __utils__['boto.assign_funcs'](__name__, 'ec2')
    '''
    mod = sys.modules[modname]
    ctx = mod.__context__
    opts = mod.__opts__
    pillar = mod.__pillar__
    setattr(mod, '_get_conn', get_connection_func(service, module=module,
                                                  ctx=ctx, opts=opts,
                                                  pillar=pillar))
    setattr(mod, '_cache_id', cache_id_func(service, ctx=ctx,
                                            opts=opts, pillar=pillar))
