# -*- coding: utf-8 -*-
'''
Boto3 Common Utils
=================

Note: This module depends on the dicts packed by the loader and,
therefore, must be accessed via the loader or from the __utils__ dict.

The __utils__ dict will not be automatically available to execution modules
until 2015.8.0. The `salt.utils.compat.pack_dunder` helper function
provides backwards compatibility.

This module provides common functionality for the boto3 execution modules.
The expected usage is to call `apply_funcs` from the `__virtual__` function
of the module. This will bring properly initilized partials of  `_get_conn`
and `_cache_id` into the module's namespace.

Example Usage:

    .. code-block:: python

        import salt.utils.boto3

        def __virtual__():
            # only required in 2015.2
            salt.utils.compat.pack_dunder(__name__)

            __utils__['boto3.apply_funcs'](__name__, 'vpc')

        def test():
            conn = _get_conn()
            vpc_id = _cache_id('test-vpc')

.. versionadded:: 2015.8.0
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import hashlib
import logging
import sys
from functools import partial

# Import salt libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin
from salt.exceptions import SaltInvocationError, CommandExecutionError
from salt.utils.versions import LooseVersion as _LooseVersion
from salt.ext import six
import salt.utils.stringutils
import salt.utils.versions

# Import third party libs
# pylint: disable=import-error
try:
    # pylint: disable=import-error
    import botocore
    import boto3

    # pylint: enable=import-error
    logging.getLogger('boto3').setLevel(logging.CRITICAL)
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
# pylint: enable=import-error


log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto3 libraries exist and if boto3 libraries are greater than
    a given version.
    '''
    # boto_s3_bucket module requires boto3 1.2.6 and botocore 1.3.23 for
    # idempotent ACL operations via the fix in  https://github.com/boto/boto3/issues/390
    required_boto3_version = '1.2.6'
    required_botocore_version = '1.3.23'
    if not HAS_BOTO3:
        return False
    elif _LooseVersion(boto3.__version__) < _LooseVersion(required_boto3_version):
        return False
    elif _LooseVersion(botocore.__version__) < _LooseVersion(required_botocore_version):
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


def _get_profile(service, region=None, key=None, keyid=None, profile=None,
                 aws_session_token=None, aws_profile=None):
    if profile:
        if isinstance(profile, six.string_types):
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
        log.info('Assuming default region %s', region)

    if not key and _option(service + '.key'):
        key = _option(service + '.key')
    if not keyid and _option(service + '.keyid'):
        keyid = _option(service + '.keyid')

    label = 'boto_{0}:'.format(service)
    if keyid and key:
        hash_string = region + keyid + key
        if six.PY3:
            hash_string = salt.utils.stringutils.to_bytes(hash_string)
        cxkey = label + hashlib.md5(hash_string).hexdigest()
    elif aws_session_token:
        hash_string = region + aws_session_key
        if six.PY3:
            hash_string = salt.utils.to_bytes(hash_string)
        cxkey = label + hashlib.md5(hash_string).hexdigest()
    elif aws_profile:
        cxkey = label + aws_profile
    else:  # Fall back to IAM, hopefully...
        cxkey = label + region

    return {'cxkey': cxkey, 'region': region, 'key': key, 'keyid': keyid,
            'aws_session_token': aws_session_token, 'aws_profile': aws_profile}


def cache_id(service, name, sub_resource=None, resource_id=None,
             invalidate=False, region=None, key=None, keyid=None,
             profile=None, aws_session_token=None, aws_profile=None):
    '''
    Cache, invalidate, or retrieve an AWS resource id keyed by name.

    .. code-block:: python

        __utils__['boto3.cache_id']('ec2', 'myinstance', 'i-a1b2c3', profile='custom_profile')
    '''

    prof = _get_profile(service, region, key, keyid, profile,
                        aws_session_token, aws_profile)
    cxkey = prof['cxkey']
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

    .. code-block:: python

        cache_id = __utils__['boto3.cache_id_func']('ec2')
        cache_id('myinstance', 'i-a1b2c3')
        instance_id = cache_id('myinstance')
    '''
    return partial(cache_id, service)


def get_connection(service, module=None, region=None, key=None, keyid=None,
                   profile=None, aws_session_token=None, botocore_session=None,
                   aws_profile=None, test_func=None):
    '''
    Return a boto3 connection for the service.

    .. code-block:: python

        conn = __utils__['boto3.get_connection']('ec2', profile='custom_profile')
    '''

    service_name = module or service

    prof = _get_profile(service, region, key, keyid, profile,
                        aws_session_token, aws_profile)
    cxkey = prof['cxkey'] + ':conn3'

    if cxkey in __context__:
        return __context__[cxkey]

    # This try/excpet does absolutlely no good BTW, unless `test_func` is passed in.
    # Boto3 doesn't attempt a bind until the first client op is called, which means this will
    # never throw, while any auth errors will happen within the client function call itself.
    # This implies that any functions not trapping on auth errors will stacktrace...
    try:
        session = boto3.Session(aws_access_key_id=prof.get('keyid'),
                                aws_secret_access_key=prof.get('key'),
                                region_name=prof.get('region'),
                                aws_session_token=prof.get('aws_session_token'),
                                botocore_session=botocore_session,
                                profile_name=prof.get('aws_profile'))
        if session is None:
            raise CommandExecutionError("Failed to create Boto3 Session.  Verify the "
                                        "region '{0}' is valid.".format(prof.get('region')))
        conn = session.client(service_name)
        if conn is None:
            raise CommandExecutionError("Failed to create Boto3 client for {0}.  "
                                        "Verify the region '{1}' is valid.".format(
                                        service_name, prof.get('region')))
        # To module writers:
        # If you pass in a name of a test_func() of your boto3 resource which takes no args,
        # we can use it to validate your creds are good here, while setting up the connection
        # the first time.  Otherwise one has the joy of checking for auth success inside every
        # single function call :(  Note that the connection is cached once it's up, so this
        # will only be needed / reached once per "API endpoint + cred style".
        if test_func and getattr(conn, test_func, None):
            getattr(conn, test_func)()  # Call and discard, just to test creds work...
    except botocore.exceptions.ClientError as e:
        err = get_error(e)
        if err['code'] in ('NoCredentialsError', 'ProfileNotFound'):
            raise CommandExecutionError('Error authenticating for service `{0}`: {1}'.format(
                                        service_name, err['message']))
        raise CommandExecutionError('Error creating client for service `{0}`: {1}'.format(
                                    service_name, err['message']))
    __context__[cxkey] = conn

    return conn


def get_connection_func(service, module=None):
    '''
    Returns a partial `get_connection` function for the provided service.

    .. code-block:: python

        get_conn = __utils__['boto3.get_connection_func']('ec2')
        conn = get_conn()
    '''
    return partial(get_connection, service, module=module)


def get_region(service, region, profile):
    """
    Retrieve the region for a particular AWS service based on configured region and/or profile.
    """
    prof = _get_profile(service, region, None, None, profile)
    return prof.get('region')


def get_error(e):
    '''
    Parse a boto3 error object.  Return a hopefully useful description of what went wrong,
    along with the AWS error code, if available.
    '''
    ret = {'message': str(e)}
    if getattr(e, 'error_code', None):
        ec = getattr(e, 'error_code', None)
    else:
        ec = getattr(e, 'response', {}).get('Error', {}).get('Code')
    ret.update({'code': ec if ec else 'unknown'})
    return ret


def exactly_n(l, n=1):
    '''
    Tests that exactly N items in an iterable are "truthy" (neither None,
    False, nor 0).
    '''
    i = iter(l)
    return all(any(i) for j in range(n)) and not any(i)


def exactly_one(l):
    return exactly_n(l)


def assign_funcs(modname, service, module=None,
                get_conn_funcname='_get_conn', cache_id_funcname='_cache_id',
                exactly_one_funcname='_exactly_one'):
    '''
    Assign _get_conn and _cache_id functions to the named module.

    .. code-block:: python

        _utils__['boto3.assign_partials'](__name__, 'ec2')
    '''
    mod = sys.modules[modname]
    setattr(mod, get_conn_funcname, get_connection_func(service, module=module))
    setattr(mod, cache_id_funcname, cache_id_func(service))

    # TODO: Remove this and import salt.utils.exactly_one into boto_* modules instead
    # Leaving this way for now so boto3 modules can be back ported
    if exactly_one_funcname is not None:
        setattr(mod, exactly_one_funcname, exactly_one)


def paged_call(function, *args, **kwargs):
    """Retrieve full set of values from a boto3 API call that may truncate
    its results, yielding each page as it is obtained.
    """
    marker_flag = kwargs.pop('marker_flag', 'NextMarker')
    marker_arg = kwargs.pop('marker_arg', 'Marker')
    while True:
        ret = function(*args, **kwargs)
        marker = ret.get(marker_flag)
        yield ret
        if not marker:
            break
        kwargs[marker_arg] = marker


def ordered(obj):
    if isinstance(obj, (list, tuple)):
        return sorted(ordered(x) for x in obj)
    elif isinstance(obj, dict):
        return dict((six.text_type(k) if isinstance(k, six.string_types) else k, ordered(v)) for k, v in obj.items())
    elif isinstance(obj, six.string_types):
        return six.text_type(obj)
    return obj


def json_objs_equal(left, right):
    """ Compare two parsed JSON objects, given non-ordering in JSON objects
    """
    return ordered(left) == ordered(right)
