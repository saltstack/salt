# -*- coding: utf-8 -*-
'''
Connection module for Amazon CloudFront

.. versionadded:: 2018.3.0

:depends: boto3

:configuration: This module accepts explicit AWS credentials but can also
    utilize IAM roles assigned to the instance through Instance Profiles or
    it can read them from the ~/.aws/credentials file or from these
    environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/
            iam-roles-for-amazon-ec2.html

        http://boto3.readthedocs.io/en/latest/guide/
            configuration.html#guide-configuration

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        cloudfront.keyid: GKTADJGHEIQSXMKKRBJ08H
        cloudfront.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        cloudfront.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1
'''
# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt libs
import salt.ext.six as six
from salt.utils.odict import OrderedDict
from salt.exceptions import SaltInvocationError
import salt.utils.versions

# Import third party libs
try:
    # pylint: disable=unused-import
    import boto3
    import botocore
    # pylint: enable=unused-import
    logging.getLogger('boto3').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto3 libraries exist.
    '''
    has_boto_reqs = salt.utils.versions.check_boto_reqs()
    if has_boto_reqs is True:
        __utils__['boto3.assign_funcs'](__name__, 'cloudfront')
    return has_boto_reqs


def _list_distributions(
    conn,
    name=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    '''
    Private function that returns an iterator over all CloudFront distributions.
    The caller is responsible for all boto-related error handling.

    name
        (Optional) Only yield the distribution with the given name
    '''
    for dl_ in conn.get_paginator('list_distributions').paginate():
        distribution_list = dl_['DistributionList']
        if 'Items' not in distribution_list:
            # If there are no items, AWS omits the `Items` key for some reason
            continue
        for partial_dist in distribution_list['Items']:
            tags = conn.list_tags_for_resource(Resource=partial_dist['ARN'])
            tags = dict(
                (kv['Key'], kv['Value']) for kv in tags['Tags']['Items']
            )

            id_ = partial_dist['Id']
            if 'Name' not in tags:
                log.warning('CloudFront distribution %s has no Name tag.', id_)
                continue
            distribution_name = tags.pop('Name', None)
            if name is not None and distribution_name != name:
                continue

            # NOTE: list_distributions() returns a DistributionList,
            # which nominally contains a list of Distribution objects.
            # However, they are mangled in that they are missing values
            # (`Logging`, `ActiveTrustedSigners`, and `ETag` keys)
            # and moreover flatten the normally nested DistributionConfig
            # attributes to the top level.
            # Hence, we must call get_distribution() to get the full object,
            # and we cache these objects to help lessen API calls.
            distribution = _cache_id(
                'cloudfront',
                sub_resource=distribution_name,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
            if distribution:
                yield (distribution_name, distribution)
                continue

            dist_with_etag = conn.get_distribution(Id=id_)
            distribution = {
                'distribution': dist_with_etag['Distribution'],
                'etag': dist_with_etag['ETag'],
                'tags': tags,
            }
            _cache_id(
                'cloudfront',
                sub_resource=distribution_name,
                resource_id=distribution,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
            yield (distribution_name, distribution)


def get_distribution(name, region=None, key=None, keyid=None, profile=None):
    '''
    Get information about a CloudFront distribution (configuration, tags) with a given name.

    name
        Name of the CloudFront distribution

    region
        Region to connect to

    key
        Secret key to use

    keyid
        Access key to use

    profile
        A dict with region, key, and keyid,
        or a pillar key (string) that contains such a dict.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.get_distribution name=mydistribution profile=awsprofile

    '''
    distribution = _cache_id(
        'cloudfront',
        sub_resource=name,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if distribution:
        return {'result': distribution}

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        for _, dist in _list_distributions(
            conn,
            name=name,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        ):
            # _list_distributions should only return the one distribution
            # that we want (with the given name).
            # In case of multiple distributions with the same name tag,
            # our use of caching means list_distributions will just
            # return the first one over and over again,
            # so only the first result is useful.
            if distribution is not None:
                msg = 'More than one distribution found with name {0}'
                return {'error': msg.format(name)}
            distribution = dist
    except botocore.exceptions.ClientError as err:
        return {'error': __utils__['boto3.get_error'](err)}
    if not distribution:
        return {'result': None}

    _cache_id(
        'cloudfront',
        sub_resource=name,
        resource_id=distribution,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    return {'result': distribution}


def export_distributions(region=None, key=None, keyid=None, profile=None):
    '''
    Get details of all CloudFront distributions.
    Produces results that can be used to create an SLS file.

    CLI Example:

    .. code-block:: bash

        salt-call boto_cloudfront.export_distributions --out=txt |\
            sed "s/local: //" > cloudfront_distributions.sls

    '''
    results = OrderedDict()
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        for name, distribution in _list_distributions(
            conn,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        ):
            config = distribution['distribution']['DistributionConfig']
            tags = distribution['tags']

            distribution_sls_data = [
                {'name': name},
                {'config': config},
                {'tags': tags},
            ]
            results['Manage CloudFront distribution {0}'.format(name)] = {
                'boto_cloudfront.present': distribution_sls_data,
            }
    except botocore.exceptions.ClientError as err:
        # Raise an exception, as this is meant to be user-invoked at the CLI
        # as opposed to being called from execution or state modules
        six.reraise(*sys.exc_info())

    dumper = __utils__['yaml.get_dumper']('IndentedSafeOrderedDumper')
    return __utils__['yaml.dump'](
        results,
        default_flow_style=False,
        Dumper=dumper,
    )


def create_distribution(
    name,
    config,
    tags=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    '''
    Create a CloudFront distribution with the given name, config, and (optionally) tags.

    name
        Name for the CloudFront distribution

    config
        Configuration for the distribution

    tags
        Tags to associate with the distribution

    region
        Region to connect to

    key
        Secret key to use

    keyid
        Access key to use

    profile
        A dict with region, key, and keyid,
        or a pillar key (string) that contains such a dict.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.create_distribution name=mydistribution profile=awsprofile \
            config='{"Comment":"partial configuration","Enabled":true}'
    '''
    if tags is None:
        tags = {}
    if 'Name' in tags:
        # Be lenient and silently accept if names match, else error
        if tags['Name'] != name:
            return {'error': 'Must not pass `Name` in `tags` but as `name`'}
    tags['Name'] = name
    tags = {
        'Items': [{'Key': k, 'Value': v} for k, v in six.iteritems(tags)]
    }

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        conn.create_distribution_with_tags(
            DistributionConfigWithTags={
                'DistributionConfig': config,
                'Tags': tags,
            },
        )
        _cache_id(
            'cloudfront',
            sub_resource=name,
            invalidate=True,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
    except botocore.exceptions.ClientError as err:
        return {'error': __utils__['boto3.get_error'](err)}

    return {'result': True}


def update_distribution(
    name,
    config,
    tags=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    '''
    Update the config (and optionally tags) for the CloudFront distribution with the given name.

    name
        Name of the CloudFront distribution

    config
        Configuration for the distribution

    tags
        Tags to associate with the distribution

    region
        Region to connect to

    key
        Secret key to use

    keyid
        Access key to use

    profile
        A dict with region, key, and keyid,
        or a pillar key (string) that contains such a dict.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.update_distribution name=mydistribution profile=awsprofile \
            config='{"Comment":"partial configuration","Enabled":true}'
    '''
    ### FIXME - BUG.  This function can NEVER work as written...
    ### Obviously it was never actually tested.
    distribution_ret = get_distribution(
        name,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile
    )
    if 'error' in distribution_ret:
        return distribution_ret
    dist_with_tags = distribution_ret['result']

    current_distribution = dist_with_tags['distribution']
    current_config = current_distribution['DistributionConfig']
    current_tags = dist_with_tags['tags']
    etag = dist_with_tags['etag']

    config_diff = __utils__['dictdiffer.deep_diff'](current_config, config)
    if tags:
        tags_diff = __utils__['dictdiffer.deep_diff'](current_tags, tags)

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        if 'old' in config_diff or 'new' in config_diff:
            conn.update_distribution(
                DistributionConfig=config,
                Id=current_distribution['Id'],
                IfMatch=etag,
            )
        if tags:
            arn = current_distribution['ARN']
            if 'new' in tags_diff:
                tags_to_add = {
                    'Items': [
                        {'Key': k, 'Value': v}
                        for k, v in six.iteritems(tags_diff['new'])
                    ],
                }
                conn.tag_resource(
                    Resource=arn,
                    Tags=tags_to_add,
                )
            if 'old' in tags_diff:
                tags_to_remove = {
                    'Items': list(tags_diff['old'].keys()),
                }
                conn.untag_resource(
                    Resource=arn,
                    TagKeys=tags_to_remove,
                )
    except botocore.exceptions.ClientError as err:
        return {'error': __utils__['boto3.get_error'](err)}
    finally:
        _cache_id(
            'cloudfront',
            sub_resource=name,
            invalidate=True,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )

    return {'result': True}


def get_distribution_v2(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Get information about a CloudFront distribution given its Resource ID.

    Id
        Resource ID of the CloudFront distribution.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.get_distribution_v2 Id=E24RBTSABCDEF0

    '''
    retries = 10
    sleep = 6
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith('_')}
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    Id = kwargs.get('Id')
    while retries:
        try:
            log.debug('Getting details for CloudFront distribution `%s`.', Id)
            ret = conn.get_distribution(**kwargs)
            ret.pop('ResponseMetadata', '')
            return ret
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get('Error', {}).get('Code') == 'Throttling':
                retries -= 1
                log.debug('Throttled by AWS API, retrying in %s seconds...', sleep)
                time.sleep(sleep)
                continue
            log.error('Failed to garner details for CloudFront distribution with Id `%s`:  %s',
                      Id, err.message)
            return None


def get_distribution_config(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Get config information about a CloudFront distribution given its Resource ID.

    Id
        Resource ID of the CloudFront distribution.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.get_distribution_config Id=E24RBTSABCDEF0

    '''
    retries = 10
    sleep = 6
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith('_')}
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    Id = kwargs.get('Id')
    while retries:
        try:
            log.debug('Getting CloudFront distribution `%s` config.', Id)
            ret = conn.get_distribution_config(**kwargs)
            ret.pop('ResponseMetadata', '')
            return ret
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get('Error', {}).get('Code') == 'Throttling':
                retries -= 1
                log.debug('Throttled by AWS API, retrying in %s seconds...', sleep)
                time.sleep(sleep)
                continue
            log.error('Failed to garner config for CloudFront distribution with Id `%s`:  %s',
                      Id, err.message)
            return None


def list_distributions(region=None, key=None, keyid=None, profile=None):
    '''
    List, with moderate information, all CloudFront distributions in the bound account.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.list_distributions

    '''
    retries = 10
    sleep = 6
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    Items = []
    while retries:
        try:
            log.debug('Garnering list of CloudFront distributions')
            Marker = ''
            while Marker is not None:
                ret = conn.list_distributions(Marker=Marker)
                Items += ret.get('DistributionList', {}).get('Items', [])
                Marker = ret.get('DistributionList', {}).get('NextMarker')
            return Items
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get('Error', {}).get('Code') == 'Throttling':
                retries -= 1
                log.debug('Throttled by AWS API, retrying in %s seconds...', sleep)
                time.sleep(sleep)
                continue
            log.error('Failed to list CloudFront distributions: %s', err.message)
            return None


def distribution_exists(Id, region=None, key=None, keyid=None, profile=None):
    '''
    Return True if a CloudFront distribution exists with the given Resource ID or False otherwise.

    Id
        Resource ID of the CloudFront distribution.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.distribution_exists Id=E24RBTSABCDEF0

    '''
    authargs = {'region': region, 'key': key, 'keyid': keyid, 'profile': profile}
    dists = list_distributions(**authargs) or []
    return bool([i['Id'] for i in dists if i['Id'] == Id])


def get_distributions_by_comment(Comment, region=None, key=None, keyid=None, profile=None):
    '''
    Find and return any CloudFront distributions which happen to have a Comment sub-field
    either exactly matching the given Comment, or beginning with it AND with the remainder
    separated by a colon.

    Comment
        The string to be matched when searching for the given Distribution.  Note that this
        will be matched against both the exact value of the Comment sub-field, AND as a
        colon-separated initial value for the same Comment sub-field.  E.g. given a passed
        `Comment` value of `foobar`, this would match a distribution with EITHER a
        Comment sub-field of exactly `foobar`, OR a Comment sub-field beginning with
        `foobar:`.  The intention here is to permit using the Comment field for storing
        actual comments, in addition to overloading it to store Salt's `Name` attribute.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.get_distributions_by_comment 'Comment=foobar'
        salt myminion boto_cloudfront.get_distributions_by_comment 'Comment=foobar:Plus a real comment'

    '''
    log.debug('Dereferincing CloudFront distribution(s) by Comment `%s`.', Comment)
    ret = list_distributions(region=region, key=key, keyid=keyid, profile=profile)
    if ret is None:
        return ret
    items = []
    for item in ret:
        comment = item.get('Comment')
        # Comment field is never None, so it can only match if both exist...
        if comment == Comment or comment.startswith('{0}:'.format(Comment)):
            items += [item]
    return items


def create_distribution_v2(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Create a CloudFront distribution with the provided configuration details.  A LOT of fields are
    required in DistributionConfig to make up a valid creation request.  Details can be found at
    __: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/distribution-overview-required-fields.html
    and
    __: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudfront.html#CloudFront.Client.create_distribution

    DistributionConfig
        The distribution's configuration information.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        # Note that, minus the Aliases section, this is pretty close to the minimal config I've
        # found which AWS will accept for a create_distribution() call...
        salt myminion boto_cloudfront.create_distribution_v2 DistributionConfig='{
            "CallerReference": "28deef17-cc47-4169-b1a2-eff30c997bf0",
            "Aliases": {
                "Items": [
                    "spa-dev.saltstack.org"
                ],
                "Quantity": 1
            },
            "Comment": "CloudFront distribution for SPA",
            "DefaultCacheBehavior": {
                "AllowedMethods": {
                    "CachedMethods": {
                        "Items": [
                            "HEAD",
                            "GET"
                        ],
                        "Quantity": 2
                    },
                    "Items": [
                        "HEAD",
                        "GET"
                    ],
                    "Quantity": 2
                },
                "Compress": false,
                "DefaultTTL": 86400,
                "FieldLevelEncryptionId": "",
                "ForwardedValues": {
                    "Cookies": {
                        "Forward": "none"
                    },
                    "Headers": {
                        "Quantity": 0
                    },
                    "QueryString": false,
                    "QueryStringCacheKeys": {
                        "Quantity": 0
                    }
                },
                "LambdaFunctionAssociations": {
                    "Quantity": 0
                },
                "MaxTTL": 31536000,
                "MinTTL": 0,
                "SmoothStreaming": false,
                "TargetOriginId": "saltstack-spa-cf-dist",
                "TrustedSigners": {
                    "Enabled": false,
                    "Quantity": 0
                },
                "ViewerProtocolPolicy": "allow-all"
            },
            "DefaultRootObject": "",
            "Enabled": true,
            "HttpVersion": "http2",
            "IsIPV6Enabled": true,
            "Logging": {
                "Bucket": "",
                "Enabled": false,
                "IncludeCookies": false,
                "Prefix": ""
            },
            "Origins": {
                "Items": [
                    {
                        "CustomHeaders": {
                            "Quantity": 0
                        },
                        "DomainName": "saltstack-spa-dist.s3.amazonaws.com",
                        "Id": "saltstack-spa-dist",
                        "OriginPath": "",
                        "S3OriginConfig": {
                            "OriginAccessIdentity": "origin-access-identity/cloudfront/EABCDEF1234567"
                        }
                    }
                ],
                "Quantity": 1
            },
            "PriceClass": "PriceClass_All",
            "ViewerCertificate": {
                "CertificateSource": "cloudfront",
                "CloudFrontDefaultCertificate": true,
                "MinimumProtocolVersion": "TLSv1"
            },
            "WebACLId": ""
        }'

    '''
    retries = 10
    sleep = 6
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith('_')}
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    Comment = kwargs.get('DistributionConfig', {}).get('Comment')
    while retries:
        try:
            log.debug('Creating CloudFront distribution `%s`.', Comment)
            ret = conn.create_distribution(**kwargs)
            return ret
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get('Error', {}).get('Code') == 'Throttling':
                retries -= 1
                log.debug('Throttled by AWS API, retrying in %s seconds...', sleep)
                time.sleep(sleep)
                continue
            log.error('Failed to create CloudFront distribution `%s`:  %s', Comment, err.message)
            return None


def update_distribution_v2(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Update a CloudFront distribution with the provided configuration details.  A LOT of fields are
    required in DistributionConfig to make up a valid update request.  Details can be found at
    __: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/distribution-overview-required-fields.html
    and
    __: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudfront.html#CloudFront.Client.update_distribution

    DistributionConfig
        The distribution's configuration information.

    Id
        Id of the distribution to update.

    IfMatch
        The value of the ETag header from a previous get_distribution_v2() call.  Optional, but
        highly recommended to use this, to avoid update conflicts.  If this value doesn't match
        the current ETag of the resource (in other words, if the resource was changed since you
        last fetched its config), the update will be refused.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        # Note that, minus the Aliases section, this is pretty close to the minimal config I've
        # found which AWS will accept for a update_distribution() call...
        salt myminion boto_cloudfront.update_distribution_v2 Id=ET123456789AB IfMatch=E2QWRUHABCDEF0 DistributionConfig='{
            "CallerReference": "28deef17-cc47-4169-b1a2-eff30c997bf0",
            "Aliases": {
                "Items": [
                    "spa-dev.saltstack.org"
                ],
                "Quantity": 1
            },
            "Comment": "CloudFront distribution for SPA",
            "DefaultCacheBehavior": {
                "AllowedMethods": {
                    "CachedMethods": {
                        "Items": [
                            "HEAD",
                            "GET"
                        ],
                        "Quantity": 2
                    },
                    "Items": [
                        "HEAD",
                        "GET"
                    ],
                    "Quantity": 2
                },
                "Compress": false,
                "DefaultTTL": 86400,
                "FieldLevelEncryptionId": "",
                "ForwardedValues": {
                    "Cookies": {
                        "Forward": "none"
                    },
                    "Headers": {
                        "Quantity": 0
                    },
                    "QueryString": false,
                    "QueryStringCacheKeys": {
                        "Quantity": 0
                    }
                },
                "LambdaFunctionAssociations": {
                    "Quantity": 0
                },
                "MaxTTL": 31536000,
                "MinTTL": 0,
                "SmoothStreaming": false,
                "TargetOriginId": "saltstack-spa-cf-dist",
                "TrustedSigners": {
                    "Enabled": false,
                    "Quantity": 0
                },
                "ViewerProtocolPolicy": "allow-all"
            },
            "DefaultRootObject": "",
            "Enabled": true,
            "HttpVersion": "http2",
            "IsIPV6Enabled": true,
            "Logging": {
                "Bucket": "",
                "Enabled": false,
                "IncludeCookies": false,
                "Prefix": ""
            },
            "Origins": {
                "Items": [
                    {
                        "CustomHeaders": {
                            "Quantity": 0
                        },
                        "DomainName": "saltstack-spa-dist.s3.amazonaws.com",
                        "Id": "saltstack-spa-dist",
                        "OriginPath": "",
                        "S3OriginConfig": {
                            "OriginAccessIdentity": "origin-access-identity/cloudfront/EABCDEF1234567"
                        }
                    }
                ],
                "Quantity": 1
            },
            "PriceClass": "PriceClass_All",
            "ViewerCertificate": {
                "CertificateSource": "cloudfront",
                "CloudFrontDefaultCertificate": true,
                "MinimumProtocolVersion": "TLSv1"
            },
            "WebACLId": ""
        }'

    '''
    retries = 10
    sleep = 6
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith('_')}
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    Comment = kwargs.get('DistributionConfig', {}).get('Comment')
    while retries:
        try:
            log.debug('Updating CloudFront distribution `%s`.', Comment)
            ret = conn.update_distribution(**kwargs)
            return ret
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get('Error', {}).get('Code') == 'Throttling':
                retries -= 1
                log.debug('Throttled by AWS API, retrying in %s seconds...', sleep)
                time.sleep(sleep)
                continue
            log.error('Failed to update CloudFront distribution `%s`:  %s', Comment, err.message)
            return None


def disable_distribution(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Set a CloudFront distribution to be disabled.

    Id
        Id of the distribution to update.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.disable_distribution Id=E24RBTSABCDEF0

    '''
    retries = 10
    sleep = 6
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith('_')}
    authargs = {'region': region, 'key': key, 'keyid': keyid, 'profile': profile}
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    Id = kwargs.get('Id')
    current = get_distribution_v2(Id=Id, **authargs)
    if current is None:
        log.error('Failed to get current config of CloudFront distribution `%s`.', Id)
        return None
    if not current['Distribution']['DistributionConfig']['Enabled']:
        return current

    ETag = current['ETag']
    DistributionConfig = current['Distribution']['DistributionConfig']
    DistributionConfig['Enabled'] = False
    kwargs = {'DistributionConfig': DistributionConfig, 'Id': Id, 'IfMatch': ETag}
    kwargs.update(authargs)
    while retries:
        try:
            log.debug('Disabling CloudFront distribution `%s`.', Id)
            ret = conn.update_distribution(**kwargs)
            return ret
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get('Error', {}).get('Code') == 'Throttling':
                retries -= 1
                log.debug('Throttled by AWS API, retrying in %s seconds...', sleep)
                time.sleep(sleep)
                continue
            log.error('Failed to disable CloudFront distribution `%s`:  %s', Comment, err.message)
            return None


def delete_distribution(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Delete a CloudFront distribution.

    Id
        Id of the distribution to delete.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.delete_distribution Id=E24RBTSABCDEF0

    '''
    retries = 10
    sleep = 6
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith('_')}
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    Id = kwargs.get('Id')
    while retries:
        try:
            log.debug('Deleting CloudFront distribution `%s`.', Id)
            conn.delete_distribution(**kwargs)
            return True
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get('Error', {}).get('Code') == 'Throttling':
                retries -= 1
                log.debug('Throttled by AWS API, retrying in %s seconds...', sleep)
                time.sleep(sleep)
                continue
            log.error('Failed to delete CloudFront distribution `%s`:  %s', Id, err.message)
            return False


def list_cloud_front_origin_access_identities(region=None, key=None, keyid=None, profile=None):
    '''
    List, with moderate information, all CloudFront origin access identities in the bound account.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.list_cloud_front_origin_access_identities

    '''
    retries = 10
    sleep = 6
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    Items = []
    while retries:
        try:
            log.debug('Garnering list of CloudFront origin access identities')
            Marker = ''
            while Marker is not None:
                ret = conn.list_cloud_front_origin_access_identities(Marker=Marker)
                Items += ret.get('CloudFrontOriginAccessIdentityList', {}).get('Items', [])
                Marker = ret.get('CloudFrontOriginAccessIdentityList', {}).get('NextMarker')
            return Items
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get('Error', {}).get('Code') == 'Throttling':
                retries -= 1
                log.debug('Throttled by AWS API, retrying in %s seconds...', sleep)
                time.sleep(sleep)
                continue
            log.error('Failed to list CloudFront origin access identities: %s', err.message)
            return None


def get_cloud_front_origin_access_identity(region=None, key=None, keyid=None, profile=None,
                                           **kwargs):
    '''
    Get information about a CloudFront origin access identity given its Resource ID.

    Id
        Resource ID of the CloudFront origin access identity.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.get_origin_access_identity Id=E30ABCDEF12345

    '''
    retries = 10
    sleep = 6
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith('_')}
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    Id = kwargs.get('Id')
    while retries:
        try:
            log.debug('Getting CloudFront origin access identity `%s` details.', Id)
            ret = conn.get_cloud_front_origin_access_identity(**kwargs)
            ret.pop('ResponseMetadata', '')
            return ret
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get('Error', {}).get('Code') == 'Throttling':
                retries -= 1
                log.debug('Throttled by AWS API, retrying in %s seconds...', sleep)
                time.sleep(sleep)
                continue
            log.error('Failed to garner details for CloudFront origin access identity '
                      'with Id `%s`:  %s', Id, err.message)
            return None


def get_cloud_front_origin_access_identity_config(region=None, key=None, keyid=None, profile=None,
                                                  **kwargs):
    '''
    Get config information about a CloudFront origin access identity given its Resource ID.

    Id
        Resource ID of the CloudFront origin access identity.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.get_cloud_front_origin_access_identity_config Id=E30ABCDEF12345

    '''
    retries = 10
    sleep = 6
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith('_')}
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    Id = kwargs.get('Id')
    while retries:
        try:
            log.debug('Getting CloudFront origin access identity `%s` config.', Id)
            ret = conn.get_cloud_front_origin_access_identity_config(**kwargs)
            ret.pop('ResponseMetadata', '')
            return ret
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get('Error', {}).get('Code') == 'Throttling':
                retries -= 1
                log.debug('Throttled by AWS API, retrying in %s seconds...', sleep)
                time.sleep(sleep)
                continue
            log.error('Failed to garner config for CloudFront origin access identity '
                      'with Id `%s`:  %s', Id, err.message)
            return None


def get_cloud_front_origin_access_identities_by_comment(Comment, region=None, key=None, keyid=None,
                                                        profile=None):
    '''
    Find and return any CloudFront Origin Access Identities which happen to have a Comment
    sub-field either exactly matching the given Comment, or beginning with it AND with the
    remainder separate by a colon.

    Comment
        The string to be matched when searching for the given Origin Access Identity.  Note
        that this will be matched against both the exact value of the Comment sub-field, AND as
        a colon-separated initial value for the same Comment sub-field.  E.g. given a passed
        `Comment` value of `foobar`, this would match a Origin Access Identity with EITHER a
        Comment sub-field of exactly `foobar`, OR a Comment sub-field beginning with
        `foobar:`.  The intention here is to permit using the Comment field for storing
        actual comments, in addition to overloading it to store Salt's `Name` attribute.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.get_cloud_front_origin_access_identities_by_comment 'Comment=foobar'
        salt myminion boto_cloudfront.get_cloud_front_origin_access_identities_by_comment 'Comment=foobar:Plus a real comment'

    '''
    log.debug('Dereferincing CloudFront origin access identity `%s` by Comment.', Comment)
    ret = list_cloud_front_origin_access_identities(region=region, key=key, keyid=keyid,
                                                    profile=profile)
    if ret is None:
        return ret
    items = []
    for item in ret:
        comment = item.get('Comment', '')
        if comment == Comment or comment.startswith('{0}:'.format(Comment)):
            items += [item]
    return items


def create_cloud_front_origin_access_identity(region=None, key=None, keyid=None, profile=None,
                                              **kwargs):
    '''
    Create a CloudFront origin access identity with the provided configuration details.

    CloudFrontOriginAccessIdentityConfig
        The origin access identity's configuration information.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.create_cloud_front_origin_access_identity \
                CloudFrontOriginAccessIdentityConfig='{
                    "CallerReference": "28deef17-cc47-4169-b1a2-eff30c997bf0",
                    "Comment": "CloudFront origin access identity for SPA"
                }'

    '''
    retries = 10
    sleep = 6
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith('_')}
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    Comment = kwargs.get('CloudFrontOriginAccessIdentityConfig', {}).get('Comment')
    while retries:
        try:
            log.debug('Creating CloudFront origin access identity `%s`.', Comment)
            ret = conn.create_cloud_front_origin_access_identity(**kwargs)
            ret.pop('ResponseMetadata', '')
            return ret
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get('Error', {}).get('Code') == 'Throttling':
                retries -= 1
                log.debug('Throttled by AWS API, retrying in %s seconds...', sleep)
                time.sleep(sleep)
                continue
            log.error('Failed to create CloudFront origin access identity '
                      'with Comment `%s`:  %s', Comment, err.message)
            return None


def update_cloud_front_origin_access_identity(region=None, key=None, keyid=None, profile=None,
                                              **kwargs):
    '''
    Update a CloudFront origin access identity with the provided configuration details.

    CloudFrontOriginAccessIdentityConfig
        The origin access identity's configuration information.

    Id
        Id of the origin access identity to update.

    IfMatch
        The value of the ETag header from a previous get_cloud_front_origin_access_identity() call.
        Optional, but highly recommended to use this, to avoid update conflicts.  If this value
        doesn't match the current ETag of the resource (in other words, if the resource was changed
        since you last fetched its config), the update will be refused.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.update_cloud_front_origin_access_identity Id=ET123456789AB \\
                IfMatch=E2QWRUHABCDEF0 CloudFrontOriginAccessIdentityConfig='{
                    "CallerReference": "28deef17-cc47-4169-b1a2-eff30c997bf0",
                    "Comment": "CloudFront origin access identity for SPA"
                }'

    '''
    retries = 10
    sleep = 6
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith('_')}
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    Id = kwargs.get('Id')
    while retries:
        try:
            log.debug('Updating CloudFront origin access identity `%s`.', Id)
            ret = conn.update_cloud_front_origin_access_identity(**kwargs)
            ret.pop('ResponseMetadata', '')
            return ret
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get('Error', {}).get('Code') == 'Throttling':
                retries -= 1
                log.debug('Throttled by AWS API, retrying in %s seconds...', sleep)
                time.sleep(sleep)
                continue
            log.error('Failed to update CloudFront origin access identity '
                      'with Id `%s`:  %s', Id, err.message)
            return None


def delete_cloud_front_origin_access_identity(region=None, key=None, keyid=None, profile=None,
                                              **kwargs):
    '''
    Delete a CloudFront origin access identity.

    Id
        Id of the origin access identity to delete.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.delete_origin_access_identity Id=E30RBTSABCDEF0

    '''
    retries = 10
    sleep = 6
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith('_')}
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    Id = kwargs.get('Id')
    while retries:
        try:
            log.debug('Deleting CloudFront origin access identity `%s`.', Id)
            conn.delete_cloud_front_origin_access_identity(**kwargs)
            return True
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get('Error', {}).get('Code') == 'Throttling':
                retries -= 1
                log.debug('Throttled by AWS API, retrying in %s seconds...', sleep)
                time.sleep(sleep)
                continue
            log.error('Failed to delete CloudFront origin access identity '
                      'with Id `%s`:  %s', Id, err.message)
            return False


def cloud_front_origin_access_identity_exists(Id, region=None, key=None, keyid=None, profile=None):
    '''
    Return True if a CloudFront origin access identity exists with the given Resource ID or False
    otherwise.

    Id
        Resource ID of the CloudFront origin access identity.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.cloud_front_origin_access_identity_exists Id=E30RBTSABCDEF0

    '''
    authargs = {'region': region, 'key': key, 'keyid': keyid, 'profile': profile}
    oais = list_cloud_front_origin_access_identities(**authargs) or []
    return bool([i['Id'] for i in oais if i['Id'] == Id])


def list_tags_for_resource(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    List tags attached to a CloudFront resource.

    Resource
        The ARN of the affected CloudFront resource.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.list_tags_for_resource Resource='arn:aws:cloudfront::012345678012:distribution/ETLNABCDEF123'

    '''
    retries = 10
    sleep = 6
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith('_')}
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    Id = kwargs.get('Id')
    while retries:
        try:
            log.debug('Listing tags for CloudFront resource `%s`.', kwargs.get('Resource'))
            ret = conn.list_tags_for_resource(**kwargs)
            tags = {t['Key']: t['Value'] for t in ret.get('Tags', {}).get('Items', [])}
            return tags
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get('Error', {}).get('Code') == 'Throttling':
                retries -= 1
                log.debug('Throttled by AWS API, retrying in %s seconds...', sleep)
                time.sleep(sleep)
                continue
            log.error('Failed to list tags for resource `%s`:  %s', kwargs.get('Resource'),
                    err.message)
            return None


def tag_resource(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Add tags to a CloudFront resource.

    Resource
        The ARN of the affected CloudFront resource.

    Tags
        Dict of {'Tag': 'Value', ...} providing the tags to be set.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.tag_resource Tags='{Owner: Infra, Role: salt_master}' \\
                Resource='arn:aws:cloudfront::012345678012:distribution/ETLNABCDEF123'

    '''
    retries = 10
    sleep = 6
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith('_')}
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    kwargs['Tags'] = {'Items': [{'Key': k, 'Value': v} for k, v in kwargs.get('Tags', {}).items()]}
    while retries:
        try:
            log.debug('Adding tags (%s) to CloudFront resource `%s`.', kwargs['Tags'],
                    kwargs.get('Resource'))
            conn.tag_resource(**kwargs)
            return True
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get('Error', {}).get('Code') == 'Throttling':
                retries -= 1
                log.debug('Throttled by AWS API, retrying in %s seconds...', sleep)
                time.sleep(sleep)
                continue
            log.error('Failed to add tags to resource `%s`:  %s', kwargs.get('Resource'),
                    err.message)
            return False


def untag_resource(region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Remove tags from a CloudFront resource.

    Resource
        The ARN of the affected CloudFront resource.

    TagKeys
        List of Tag keys providing the tags to be removed.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.untag_resource TagKeys='[Owner, Role]' \\
                Resource='arn:aws:cloudfront::012345678012:distribution/ETLNABCDEF123'
    '''
    retries = 10
    sleep = 6
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith('_')}
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    kwargs['TagKeys'] = {'Items': kwargs.get('TagKeys', [])}
    while retries:
        try:
            log.debug('Removing tags (%s) from CloudFront resource `%s`.', kwargs['TagKeys'],
                    kwargs.get('Resource'))
            ret = conn.untag_resource(**kwargs)
            return True
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get('Error', {}).get('Code') == 'Throttling':
                retries -= 1
                log.debug('Throttled by AWS API, retrying in %s seconds...', sleep)
                time.sleep(sleep)
                continue
            log.error('Failed to remove tags from resource `%s`:  %s', kwargs.get('Resource'),
                    err.message)
            return False


def enforce_tags(Resource, Tags, region=None, key=None, keyid=None, profile=None):
    '''
    Enforce a given set of tags on a CloudFront resource:  adding, removing, or changing them
    as necessary to ensure the resource's tags are exactly and only those specified.

    Resource
        The ARN of the affected CloudFront resource.

    Tags
        Dict of {'Tag': 'Value', ...} providing the tags to be enforced.

    region
        Region to connect to.

    key
        Secret key to use.

    keyid
        Access key to use.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.enforce_tags Tags='{Owner: Infra, Role: salt_master}' \\
                Resource='arn:aws:cloudfront::012345678012:distribution/ETLNABCDEF123'

    '''
    authargs = {'region': region, 'key': key, 'keyid': keyid, 'profile': profile}
    current = list_tags_for_resource(Resource=Resource, **authargs)
    if current is None:
        log.error('Failed to list tags for CloudFront resource `%s`.', Resource)
        return False
    if current == Tags:  # Short-ciruits save cycles!
        return True
    remove = [k for k in current if k not in Tags]
    removed = untag_resource(Resource=Resource, TagKeys=remove, **authargs)
    if removed is False:
        log.error('Failed to remove tags (%s) from CloudFront resource `%s`.', remove, Resource)
        return False
    add = {k: v for k, v in Tags.items() if current.get(k) != v}
    added = tag_resource(Resource=Resource, Tags=add, **authargs)
    if added is False:
        log.error('Failed to add tags (%s) to CloudFront resource `%s`.', add, Resource)
        return False
    return True
