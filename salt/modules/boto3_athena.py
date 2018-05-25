# -*- coding: utf-8 -*-
'''
Execution module for Amazon Athena using boto3
==============================================

.. versionadded:: 2017.7.0

:configuration: This module accepts explicit athena credentials but can
    also utilize IAM roles assigned to the instance through Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        athena.keyid: GKTADJGHEIQSXMKKRBJ08H
        athena.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        athena.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto3
'''

# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import time
import sys
import hashlib

# Import Salt libs
import salt.utils.boto3
import salt.utils.compat
import salt.utils.versions
from salt.exceptions import SaltInvocationError, CommandExecutionError
log = logging.getLogger(__name__)   # pylint: disable=W1699

# Import third party libs
try:
    import boto3  #pylint: disable=unused-import
    from botocore.exceptions import ClientError, ParamValidationError
    logging.getLogger('boto3').setLevel(logging.CRITICAL)
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def __virtual__():
    '''
    Only load if boto libraries exist and if boto libraries are greater than a given version.
    '''
    return salt.utils.versions.check_boto_reqs()


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)
    if HAS_BOTO3:
        __utils__['boto3.assign_funcs'](__name__, 'athena', exactly_one_funcname=None)


def _update_extend(dest, src):
    '''
    Very simplistic "deep merge with update" - designed for merging the JSON info returned from
    AWS API calls, and thus only handles JSON supported data types.
    '''
    ret = copy.deepcopy(dest)
    for k, v in src.items():
        if isinstance(v, list):
            ret[k] = copy.deepcopy(v) if k not in ret else (ret[k] + v)
        elif isinstance(v, dict):
            ret[k] = copy.deepcopy(v) if k not in ret else _update_extend(ret[k], v)
        else:  # Hope you're a string, int, or other scalar type, buddy...
            ret[k] = copy.copy(v)
    return ret


def _call_with_retries(func, kwargs, wait=10, retries=30):
    try:
        wait = int(wait)
    except:
        raise SaltInvocationError('Bad value `%s` passed for `wait` - must be an int.' % wait)
    while retries:
        try:
            return func(**kwargs)
        except ClientError as err:
            if err.response.get('Error', {}).get('Code') == 'Throttling':
                log.debug('Throttled by AWS API.  Sleeping %s seconds for retry...' % wait)
                time.sleep(wait)
                continue
            raise err
        except ParamValidationError as err:
            raise SaltInvocationError(err)
    raise CommandExecutionError('Failed %s retries over %s seconds' % (retries, retries * wait))


def _do_generic_thing(region=None, key=None, keyid=None, profile=None, fname='', kwargs=None):
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    func = getattr(conn, fname, None)
    kwargs = {key: val for key, val in kwargs.items() if not key.startswith('_')} if kwargs else {}
    if func is None:
        raise SaltInvocationError('Function `%s()` not available.' % fname)
    try:
        res = _call_with_retries(func=func, kwargs=kwargs)
        res.pop('ResponseMetadata', None)
        return res
    except (ClientError, CommandExecutionError) as err:
        log.error('Failed calling `%s()`:  %s' % (fname, err))
        return None


def batch_get_named_query(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Returns the details of a single named query or a list of up to 50 queries, which you provide
    as an array of query ID strings.  Use `list_named_queries()` to get the list of named query
    IDs.  If information could not be retrieved for a submitted query ID, information about the
    query ID submitted is listed under UnprocessedNamedQueryId.  Named queries are different from
    executed queries.  Use `batch_get_query_execution()` to get details about each unique query
    execution, and `list_query_executions()` to get a list of query execution IDs.

    NamedQueryIds
        A [python list] of named query IDs.  A max of 50 may be passed in one call.

    '''
    return _do_generic_thing(region=region, key=key, keyid=keyid, profile=profile,
                             fname=sys._getframe().f_code.co_name, kwargs=kwargs)


def batch_get_query_execution(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Returns the details of a single query execution or a list of up to 50 query executions, which
    you provide as an array of query execution ID strings.  To get a list of query execution IDs,
    use `list_query_executions()`.  Query executions are different from named (saved) queries.
    Use `batch_get_named_query()` to get details about named queries.

    QueryExecutionIds
        A [python list] of query execution IDs.  A max of 50 may be passed in one call.

    '''
    return _do_generic_thing(region=region, key=key, keyid=keyid, profile=profile,
                             fname=sys._getframe().f_code.co_name, kwargs=kwargs)


def create_named_query(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Creates a named query.

    Name
        The plain language name for the query.
    Description
        A brief explanation of the query.
    Database
        The database to which the query belongs.
    QueryString
        The text of the query itself.  In other words, all query statements.
    ClientRequestToken
        A unique case-sensitive string used to ensure the request to create the query is
        idempotent.  If another create_named_query() request with the same ClientRequestToken
        and otherwise identical parameters is received, the original response is returned and a
        new query is not created.  If a parameter is different - for example the QueryString -
        an error is returned.  Minimum length is 32 characters.
        Notes:
        - BY DEFAULT, if this param is not provided, salt will use an md5 hash of the value of
          `Name` for this parameter.  This ensures that only one query at a time exists with the
          given Name.  This is generally the desired behaviour, but can lead to issues when
          rapidly deleting and re-creating the same Named query (since the ClientRequestToken
          can be cached by Athena for up to 24 hours after the query has been deleted).
        - Overriding this default behaviour by passing in a value of 'dynamic' will cause a
          dynamically generated value to be used at each invocation.  This avoids the wait when
          deleting/recreating named queries, but can easily lead to multiple identically named
          queries, which is a BAD THING, so it is almost never desirable to do this.
        - A third option is to pass in a valid 32+ character string for this parameter, which will
          then prevent multiple queries with the same ClientRequestToken, but not otherwise limit
          or prevent queries with duplicate Names.

    '''
    if not kwargs.get('ClientRequestToken'):
        kwargs.update({'ClientRequestToken': hashlib.md5(kwargs.get('Name', '')).hexdigest()})
    elif kwargs['ClientRequestToken'] == 'dynamic':
        kwargs.pop('ClientRequestToken')
    return _do_generic_thing(region=region, key=key, keyid=keyid, profile=profile,
                             fname=sys._getframe().f_code.co_name, kwargs=kwargs)


def delete_named_query(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Delete a named query.

    NamedQueryId
        The unique ID of the query to delete.

    '''
    return _do_generic_thing(region=region, key=key, keyid=keyid, profile=profile,
                             fname=sys._getframe().f_code.co_name, kwargs=kwargs)


def generate_presigned_url(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Generate a presigned url given a client, its method, and arguments.

    ClientMethod
        The client method to presign for.
    Params
        A dictionary of the parameters normally passed to ClientMethod.
    ExpiresIn
        The number of seconds the presigned url is valid for.  By default it expires in an
        hour (3600 seconds)
    HttpMethod
        The http method to use on the generated url.  By default, the http method is whatever
        is used in the method's model.

    '''
    return _do_generic_thing(region=region, key=key, keyid=keyid, profile=profile,
                             fname=sys._getframe().f_code.co_name, kwargs=kwargs)


def get_named_query(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Returns information about a single named query, by NamedQueryId.

    NamedQueryId
        The unique ID of the query.

    '''
    return _do_generic_thing(region=region, key=key, keyid=keyid, profile=profile,
                             fname=sys._getframe().f_code.co_name, kwargs=kwargs)


def get_named_query_by_name(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Returns information about a single named query, by Name.

    Name
        The Name of the named query.

    '''
    if 'Name' not in kwargs:
        raise SaltInvocationError('`Name` is a required param for `%s()`.' %
                                  sys._getframe().f_code.co_name)
    res = list_named_queries(region=region, key=key, keyid=keyid, profile=profile)
    if res is None:
        return None
    for qid in res:
        query = get_named_query(region=region, key=key, keyid=keyid, profile=profile,
                                NamedQueryId=qid)
        if query is None:
            return None
        name = query.get('NamedQuery', {}).get('Name')
        if name == kwargs['Name']:
            return query
    return {}


def get_query_execution(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Returns information about a single execution of a query.  Each time a query executes,
    information about the query execution is saved with a unique ID.

    QueryExecutionId
        The unique ID of the query execution.

    '''
    return _do_generic_thing(region=region, key=key, keyid=keyid, profile=profile,
                             fname=sys._getframe().f_code.co_name, kwargs=kwargs)


def get_query_results(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Returns the results of a single query execution specified by QueryExecutionId.  This request
    does NOT execute the query - it merely returns results from a previously executed query.

    QueryExecutionId
        The unique ID of the query execution.

    '''
    ret = {}
    page = ''
    fname = sys._getframe().f_code.co_name
    kwargs.update({'MaxResults': 50})
    while page is not None:
        res = _do_generic_thing(region=region, key=key, keyid=keyid, profile=profile,
                                fname=fname, kwargs=kwargs)
        if res is None:  # Error condition of some kind
            return res
        ret = _update_extend(ret, res['ResultSet'])
        page = res.get('NextToken', None)
        kwargs.update({'NextToken': page})
    return ret


def list_named_queries(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Provides a list of all available query IDs.

    '''
    ret = []
    page = ''
    fname = sys._getframe().f_code.co_name
    kwargs.update({'MaxResults': 50})
    while page is not None:
        res = _do_generic_thing(region=region, key=key, keyid=keyid, profile=profile,
                                fname=fname, kwargs=kwargs)
        if res is None:  # Error condition of some kind
            return res
        ret += res['NamedQueryIds']
        page = res.get('NextToken', None)
        kwargs.update({'NextToken': page})
    return ret


def list_query_executions(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Provides a list of all available query IDs.

    '''
    ret = []
    page = ''
    fname = sys._getframe().f_code.co_name
    kwargs.update({'MaxResults': 50})
    while page is not None:
        res = _do_generic_thing(region=region, key=key, keyid=keyid, profile=profile,
                                fname=fname, kwargs=kwargs)
        if res is None:  # Error condition of some kind
            return res
        ret += res['QueryExecutionIds']
        page = res.get('NextToken', None)
        kwargs.update({'NextToken': page})
    return ret


def start_query_execution(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Executes the SQL query statements contained in the provided Query string.

    QueryString
        The SQL query statements to be executed.

    ClientRequestToken
        A unique case-sensitive string used to ensure the request to create the query is
        idempotent.  If another start_query_execution() request with the same ClientRequestToken
        and otherwise identical parameters is received, the original response is returned and a
        new query is not created.  If a parameter is different - for example the QueryString -
        an error is returned.
        Notes:
        - This field is autopopulated if not provided.  Note that this autopopulation prevents
          idempotency, since the same query can be created essentially ad infinitum with no
          way for AWS or salt to know they are redundant.  This is PROBABLY a bad thing to do...

        XXX TODO: think about whether some hash of some combination of
                   QueryString+QueryExecutionContext+ResultConfiguration might be useful here.

    QueryExecutionContext
        The database within which the query should be executed.
        Complex argument with sub-fields.  Should be passed as YAML.
        Sub-fields:
            Database
                The name of the database.

        ..code-block yaml
            QueryExecutionContext:
              Database: MyDatabase

        See the CLI example below for more clarity.

    ResultConfiguration
        Specifies information about where and how to save the results of the query execution.
        Complex argument with sub-fields.  Should be passed as YAML.
        Sub-fields:
            OutputLocation
                The location in S3 where query results are stored.
            EncryptionConfiguration
                If query results are encrypted in S3, indicates the S3 encryption option used
                (for example, SSE-KMS or CSE-KMS) and key information.
            EncryptionOption
                Indicates whether Amazon S3 server-side encryption with Amazon S3-managed keys
                (SSE-S3), server-side encryption with KMS-managed keys (SSE-KMS), or client-side
                encryption with KMS-managed keys (CSE-KMS) is used.
            KmsKey
                For SSE-KMS and CSE-KMS, this is the KMS key ARN or ID.

        ..code-block yaml
            ResultConfiguration:
                OutputLocation: myS3Bucket
                EncryptionConfiguration:
                    EncryptionOption: SSE_KMS
                    KmsKey: arn:aws:some:kms:key

        See the CLI example below for more clarity.

    '''
    return _do_generic_thing(region=region, key=key, keyid=keyid, profile=profile,
                             fname=sys._getframe().f_code.co_name, kwargs=kwargs)


def stop_query_execution(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Stops a query execution.

    QueryExecutionId
        The unique ID of the query execution.

    '''
    return _do_generic_thing(region=region, key=key, keyid=keyid, profile=profile,
                             fname=sys._getframe().f_code.co_name, kwargs=kwargs)
