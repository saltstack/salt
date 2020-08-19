"""
Boto3 Common Utils
=================

Note: This module depends on the dicts packed by the loader and,
therefore, must be accessed via the loader or from the __utils__ dict.

The __utils__ dict will not be automatically available to execution modules
until 2015.8.0. The `salt.utils.compat.pack_dunder` helper function
provides backwards compatibility.

This module provides common functionality for the boto execution modules.
The expected usage is to call `apply_funcs` from the `__virtual__` function
of the module. This will bring properly initilized partials of  `_get_conn`
and `_cache_id` into the module's namespace.

Example Usage:

    .. code-block:: python

        def __virtual__():
            # only required in 2015.2
            salt.utils.compat.pack_dunder(__name__)

            __utils__['boto.apply_funcs'](__name__, 'vpc')

        def test():
            conn = _get_conn()
            vpc_id = _cache_id('test-vpc')

.. versionadded:: 2015.8.0
"""

# Import Python libs

import hashlib
import logging
import sys
from functools import partial

import salt.utils.data
import salt.utils.stringutils
import salt.utils.versions
from salt.exceptions import SaltInvocationError

# Import salt libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

# Import third party libs
# pylint: disable=import-error
try:
    # pylint: disable=import-error
    import boto3
    import boto3.session
    import botocore  # pylint: disable=W0611
    import botocore.exceptions

    # pylint: enable=import-error
    logging.getLogger("boto3").setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False
# pylint: enable=import-error


log = logging.getLogger(__name__)

__virtualname__ = "boto3"

# Minimum required version of botocore to use tags in the _create call
SUPPORT_CREATE_TAGGING = {
    "create_vpc": "1.17.14",
    "create_subnet": "1.17.14",
    "create_dhcp_options": "1.17.14",
    "copy_snapshot": "1.17.14",  # TODO: Verify version number
}
# Describing these resources will return an XSet instead of _plural(X).
DESCRIBE_RESOURCES_RETURN_AS_SET = [
    "stale_security_group",
    "security_group_reference",
    "elastic_gpu",
    "offering",
    "host_reservation",
    "scheduled_instance_availability",
    "scheduled_instance",
    "connection_notification",
]
DESCRIBE_RESOURCES_ALT_IDS = {
    "address": "AllocationIds",
}


def __virtual__():
    """
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    """
    has_boto = salt.utils.versions.check_boto_reqs(check_boto=False)
    if has_boto is True:
        return __virtualname__
    return has_boto


def _option(value):
    """
    Look up the value for an option.
    """
    if value in __opts__:
        return __opts__[value]
    master_opts = __pillar__.get("master", {})
    if value in master_opts:
        return master_opts[value]
    if value in __pillar__:
        return __pillar__[value]


def _get_profile(service, region, key, keyid, profile):
    if profile:
        if isinstance(profile, str):
            _profile = _option(profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get("key", None)
        keyid = _profile.get("keyid", None)
        region = _profile.get("region", None)

    if not region and _option(service + ".region"):
        region = _option(service + ".region")

    if not region:
        region = "us-east-1"
        log.info("Assuming default region %s", region)

    if not key and _option(service + ".key"):
        key = _option(service + ".key")
    if not keyid and _option(service + ".keyid"):
        keyid = _option(service + ".keyid")

    label = "boto_{}:".format(service)
    if keyid:
        hash_string = region + keyid + key
        hash_string = salt.utils.stringutils.to_bytes(hash_string)
        cxkey = label + hashlib.md5(hash_string).hexdigest()
    else:
        cxkey = label + region

    return (cxkey, region, key, keyid)


def cache_id(
    service,
    name,
    sub_resource=None,
    resource_id=None,
    invalidate=False,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Cache, invalidate, or retrieve an AWS resource id keyed by name.

    .. code-block:: python

        __utils__['boto.cache_id']('ec2', 'myinstance',
                                   'i-a1b2c3',
                                   profile='custom_profile')
    """

    cxkey, _, _, _ = _get_profile(service, region, key, keyid, profile)
    if sub_resource:
        cxkey = "{}:{}:{}:id".format(cxkey, sub_resource, name)
    else:
        cxkey = "{}:{}:id".format(cxkey, name)

    if invalidate:
        if cxkey in __context__:
            del __context__[cxkey]
            return True
        elif resource_id in __context__.values():
            ctx = {k: v for k, v in __context__.items() if v != resource_id}
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
    """
    Returns a partial `cache_id` function for the provided service.

    .. code-block:: python

        cache_id = __utils__['boto.cache_id_func']('ec2')
        cache_id('myinstance', 'i-a1b2c3')
        instance_id = cache_id('myinstance')
    """
    return partial(cache_id, service)


def get_connection(
    service, module=None, region=None, key=None, keyid=None, profile=None
):
    """
    Return a boto3 connection for the service.

    .. code-block:: python

        conn = __utils__['boto3.get_connection']('ec2', profile='custom_profile')
    """

    module = module or service

    cxkey, region, key, keyid = _get_profile(service, region, key, keyid, profile)
    cxkey = cxkey + ":conn3"

    if cxkey in __context__:
        return __context__[cxkey]

    try:
        session = boto3.session.Session(
            aws_access_key_id=keyid, aws_secret_access_key=key, region_name=region
        )
        if session is None:
            raise SaltInvocationError('Region "{}" is not ' "valid.".format(region))
        conn = session.client(module)
        if conn is None:
            raise SaltInvocationError('Region "{}" is not ' "valid.".format(region))
    except botocore.exceptions.NoCredentialsError:
        raise SaltInvocationError(
            "No authentication credentials found when "
            "attempting to make boto {} connection to "
            'region "{}".'.format(service, region)
        )
    __context__[cxkey] = conn
    return conn


def get_connection_func(service, module=None):
    """
    Returns a partial `get_connection` function for the provided service.

    .. code-block:: python

        get_conn = __utils__['boto.get_connection_func']('ec2')
        conn = get_conn()
    """
    return partial(get_connection, service, module=module)


def get_region(service, region, profile):
    """
    Retrieve the region for a particular AWS service based on configured region and/or profile.
    """
    _, region, _, _ = _get_profile(service, region, None, None, profile)

    return region


def get_error(e):
    # The returns from boto modules vary greatly between modules. We need to
    # assume that none of the data we're looking for exists.
    aws = {}

    message = ""
    message = e.args[0]

    r = {"message": message}
    if aws:
        r["aws"] = aws
    return r


def exactly_n(l, n=1):
    """
    Tests that exactly N items in an iterable are "truthy" (neither None,
    False, nor 0).
    """
    i = iter(l)
    return all(any(i) for j in range(n)) and not any(i)


def exactly_one(l):
    return exactly_n(l)


def assign_funcs(
    modname,
    service,
    module=None,
    get_conn_funcname="_get_conn",
    cache_id_funcname="_cache_id",
    exactly_one_funcname="_exactly_one",
):
    """
    Assign _get_conn and _cache_id functions to the named module.

    .. code-block:: python

        _utils__['boto.assign_partials'](__name__, 'ec2')
    """
    mod = sys.modules[modname]
    setattr(mod, get_conn_funcname, get_connection_func(service, module=module))
    setattr(mod, cache_id_funcname, cache_id_func(service))

    # TODO: Remove this and import salt.utils.data.exactly_one into boto_* modules instead
    # Leaving this way for now so boto modules can be back ported
    if exactly_one_funcname is not None:
        setattr(mod, exactly_one_funcname, exactly_one)


def paged_call(function, *args, **kwargs):
    """Retrieve full set of values from a boto3 API call that may truncate
    its results, yielding each page as it is obtained.
    """
    marker_flag = kwargs.pop("marker_flag", "NextMarker")
    marker_arg = kwargs.pop("marker_arg", "Marker")
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
        return {str(k) if isinstance(k, str) else k: ordered(v) for k, v in obj.items()}
    elif isinstance(obj, str):
        return str(obj)
    return obj


def json_objs_equal(left, right):
    """ Compare two parsed JSON objects, given non-ordering in JSON objects
    """
    return ordered(left) == ordered(right)


def _plural(name):
    """
    Helper function that returns the plural form of a boto3 resource.

    :param str name: Name of the resource in snake_case
    """
    if name.endswith("ss"):
        ret = name + "es"
    elif name.endswith("s"):
        ret = name
    elif name in DESCRIBE_RESOURCES_RETURN_AS_SET:
        ret = name + "set"
    else:
        ret = name + "s"
    return ret


def describe_resource(
    resource_type, ids=None, filters=None, result_key=None, client=None, **kwargs,
):
    """
    Helper function to deduplicate common code in describe-functions.
    This is inteded as a backend-function to ``describe_x``-functions in various
    boto3-modules.

    :param str resource_type: The name of the resource type in snake_case.
    :param str/list ids: Zero or more resource_ids to describe.
    :param dict filters: Return only resources that match these filters.
    :param str result_key: Override result key of value returned.
        Default: _plural(UpperCamel(resource_type))
    :param * kwargs: Any additional kwargs to pass to the boto3 function.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with dict containing the result of the boto3 ``describe_{resource_type}``-call
        on succes.

    :raises: SaltInvocationError if there are errors regarding the provided arguments.
    """
    if not isinstance(ids, list):
        ids = [ids]
    resource_type_plural = _plural(resource_type)
    resource_type_uc = salt.utils.stringutils.snake_to_camel_case(
        resource_type, uppercamel=True
    )
    result_key = result_key or salt.utils.stringutils.snake_to_camel_case(
        resource_type_plural, uppercamel=True
    )
    boto_filters = [
        {"Name": k, "Values": v if isinstance(v, list) else [v]}
        for k, v in (filters or {}).items()
    ]
    params = salt.utils.data.filter_falsey(
        {
            "Filters": boto_filters,
            "{}Ids".format(
                DESCRIBE_RESOURCES_ALT_IDS.get(resource_type, resource_type_uc)
            ): ids,
        },
        recurse_depth=1,
    )
    boto_function_name = "describe_{}".format(resource_type_plural)
    if not hasattr(client, boto_function_name):
        raise SaltInvocationError(
            '{} does not have a "{}"-function.'.format(
                client.__class__, boto_function_name
            )
        )
    boto_function = getattr(client, boto_function_name)
    try:
        res = boto_function(**params, **kwargs)
        log.debug("_describe_resource(%s): res: %s", resource_type, res)
        return {"result": res.get(result_key)}
    except (
        botocore.exceptions.ParamValidationError,
        botocore.exceptions.ClientError,
    ) as exp:
        return {"error": get_error(exp)["message"]}


def lookup_resource(
    resource_type, filters=None, tags=None, result_key=None, only_one=True, client=None,
):
    """
    Helper function to deduplicate common code in lookup-functions.
    This is inteded as a backend-function to ``lookup_x``-functions in various
    boto3 modules.

    :param str resource_type: The name of the resource type in snake_case.
    :param dict filters: The filters to use in the lookup.
    :param dict tags: The tags to filter on in the lookup.
    :param str result_key: Overrides result_key whose value is returned by
        _desribe_resource. Default: Plural(UpperCamel(resource_type))
    :param bool only_one: Indicate whether only one result is expected. It will
        be an error if more than one resource is found using the specified filters
        and tags. Default: ``True``.
        Will return a list of results if this is set to ``False``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with dict containing the result of the boto ``describe_resource_type``-
        call on succes.
        If the call was succesful but returned nothing, both the 'error' and 'result'
        key will be set with the notice that nothing was found and an empty dict
        respectively (since it is assumed you're looking to find something).
    """
    ret = {}
    if filters is None:
        filters = {}
    if tags is not None:
        filters.update(
            {"tag:{}".format(tag_key): tag_value for tag_key, tag_value in tags.items()}
        )
    if not filters:
        raise SaltInvocationError(
            "No constraints where given when for lookup_{}.".format(resource_type)
        )
    res = describe_resource(
        resource_type, filters=filters, result_key=result_key, client=client,
    )
    log.debug("_lookup_resource(%s): res: %s", resource_type, res)
    if "error" in res:
        ret = res
    elif not res["result"]:
        ret["result"] = {}
        ret["error"] = "No {} found with the specified parameters".format(resource_type)
    elif len(res["result"]) > 1:
        if only_one:
            ret["error"] = (
                "There are multiple {} with the specified filters."
                " Please specify additional filters."
                "".format(_plural(resource_type))
            )
        else:
            ret["result"] = res["result"]
    else:
        ret["result"] = res["result"][0]
    log.debug("_lookup_resource(%s): ret: %s", resource_type, ret)
    return ret


def create_resource(
    resource_type,
    boto_function_name=None,
    params=None,
    tags=None,
    wait_until_state=None,
    client=None,
):
    """
    Helper function to deduplicate common code in create-functions. Some other
    functions also follow the same structure (copy_snapshot), so the function name
    to call has been made an argument.
    This is inteded as a backend-function to ``create_x``-functions (and a few
    others) in various boto3-modules.

    :param str resource_type: The name of the resource type in snake_case.
    :param str boto_function_name: Name of the boto function to call.
        Default: ``create_resource_type``.
    :param dict params: Params to pass to the boto3 create_X function.
    :param dict tags: The tags to assign to the created object.
    :param str wait_until_state: The resource state to wait for (if available).

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with dict containing the result of the boto ``create_dhcp_options``-call
        on succes.

    :raises: SaltInvocationError if there are errors regarding the provided arguments.
    """
    boto_function_name = boto_function_name or "create_{}".format(resource_type)
    # support_create_tagging = LooseVersion(botocore.__version__) >= LooseVersion(SUPPORT_CREATE_TAGGING.get(boto_function_name, '9000'))
    support_create_tagging = False
    resource_type_uc = salt.utils.stringutils.snake_to_camel_case(
        resource_type, uppercamel=True
    )
    if params is None:
        params = {}
    if tags:
        boto_tags = [{"Key": k, "Value": v} for k, v in tags.items()]
        if support_create_tagging:
            params.update(
                {
                    "TagSpecifications": [
                        {
                            "ResourceType": resource_type.replace("_", "-"),
                            "Tags": boto_tags,
                        }
                    ],
                }
            )
    if not hasattr(client, boto_function_name):
        raise SaltInvocationError(
            '{} does not have a "{}"-function.'.format(
                client.__class__, boto_function_name
            )
        )
    boto_function = getattr(client, boto_function_name)
    try:
        res = boto_function(**params)
        if tags and not support_create_tagging:
            tag_res = client.create_tags(
                Resources=[res[resource_type_uc]["{}Id".format(resource_type_uc)]],
                Tags=boto_tags,
            )
            if "error" in tag_res:
                return tag_res
        ret = res.get(resource_type_uc, False)
        if ret and tags and not support_create_tagging:
            # Add Tags to result description, just like when it _is_ supported.
            ret["Tags"] = boto_tags
        if ret and wait_until_state is not None:
            res = wait_resource(resource_type, ret, wait_until_state, client=client)
            if "error" in res:
                return res
    except (
        botocore.exceptions.ParamValidationError,
        botocore.exceptions.ClientError,
    ) as exp:
        return {"error": get_error(exp)["message"]}
    return {"result": ret}


def generic_action(
    primary, params, *args,
):
    """
    Helper function to deduplicate code when calling ``primary``.

    :param callable primary: Function to call. Can either be a boto3.client function,
        or a function from this module.
    :param dict params: Parameters to pass to the ``primary`` function.
    :param *args: Positional arguments to pass to the ``primary`` function.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with returned data if available, otherwise ``True`` on success.

    :raises: SaltInvocationError if there are errors regarding the provided arguments.
    """
    ret = {}
    try:
        log.debug("generic_action:\n" "\t\targs: %s\n" "\t\tparams: %s", args, params)
        res = primary(*args, **params)
        res.pop("ResponseMetadata", None)
    except (
        botocore.exceptions.ParamValidationError,
        botocore.exceptions.ClientError,
    ) as exp:
        return {"error": get_error(exp)["message"]}
    if "error" in res:
        return res
    if not res:
        ret["result"] = True
    elif isinstance(res, dict) and "result" in res:
        ret["result"] = res["result"]
    else:
        ret["result"] = res
    return ret


def wait_resource(resource_type, resource_description, desired_state, client=None):
    """
    Helper function to use waiters.
    Returns immediately on error, otherwise blocks until the desired state is reached.

    :param str resource_type: The name of the resource involved.
    :param dict resource_description: The output of a describe_X or lookup_X function.
    :param str desired_state: The resource state to wait for.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with returned data if available, otherwise ``True`` on success.
    """
    ret = {}
    resource_type_cc = salt.utils.stringutils.snake_to_camel_case(
        resource_type, uppercamel=True
    )
    resource_id = resource_description.get(resource_type_cc + "Id")
    if not resource_id:
        ret["error"] = "No ResourceId found in resource_description"
    else:
        try:
            waiter = client.get_waiter(resource_type + "_" + desired_state)
            waiter.wait(**{resource_type_cc + "Ids": resource_id})
        except (
            botocore.exceptions.ParamValidationError,
            botocore.exceptions.ClientError,
            botocore.exceptions.WaiterError,
        ) as exc:
            ret["error"] = exc
    ret["result"] = "error" not in ret
    return ret
