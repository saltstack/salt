# -*- coding: utf-8 -*-
'''
Manage S3 Buckets
=================

.. versionadded:: 2016.3.0

Create and destroy S3 buckets. Be aware that this interacts with Amazon's services,
and so may incur charges.

This module uses ``boto3``, which can be installed via package, or pip.

This module accepts explicit vpc credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    vpc.keyid: GKTADJGHEIQSXMKKRBJ08H
    vpc.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile,
either passed in as a dict, or as a string to pull from pillars or minion
config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. code-block:: yaml

    Ensure bucket exists:
        boto_s3_bucket.present:
            - Bucket: mybucket
            - LocationConstraint: EU
            - ACL:
              - GrantRead: "uri=http://acs.amazonaws.com/groups/global/AllUsers"
            - CORSRules:
              - AllowedHeaders: []
                AllowedMethods: ["GET"]
                AllowedOrigins: ["*"]
                ExposeHeaders: []
                MaxAgeSeconds: 123
            - LifecycleConfiguration:
              - Expiration:
                  Days: 123
                ID: "idstring"
                Prefix: "prefixstring"
                Status: "enabled",
                ID: "lc1"
                Transitions:
                  - Days: 123
                    StorageClass: "GLACIER"
                NoncurrentVersionTransitions:
                  - NoncurrentDays: 123
                    StorageClass: "GLACIER"
                NoncurrentVersionExpiration:
                  NoncurrentDays: 123
            - Logging:
                TargetBucket: log_bucket
                TargetPrefix: prefix
                TargetGrants:
                  - Grantee:
                      DisplayName: "string"
                      EmailAddress: "string"
                      ID: "string"
                      Type: "AmazonCustomerByEmail"
                      URI: "string"
                    Permission: "READ"
            - NotificationConfiguration:
                LambdaFunctionConfiguration:
                  - Id: "string"
                    LambdaFunctionArn: "string"
                    Events:
                      - "s3:ObjectCreated:*"
                    Filter:
                      Key:
                        FilterRules:
                          - Name: "prefix"
                            Value: "string"
            - Policy:
                Version: "2012-10-17"
                Statement:
                  - Sid: "String"
                    Effect: "Allow"
                    Principal:
                      AWS: "arn:aws:iam::133434421342:root"
                    Action: "s3:PutObject"
                    Resource: "arn:aws:s3:::my-bucket/*"
            - Replication:
                Role: myrole
                Rules:
                  - ID: "string"
                    Prefix: "string"
                    Status: "Enabled"
                    Destination:
                      Bucket: "arn:aws:s3:::my-bucket"
            - RequestPayment:
                Payer: Requester
            - Tagging:
                tag_name: tag_value
                tag_name_2: tag_value
            - Versioning:
                Status: "Enabled"
            - Website:
                ErrorDocument:
                  Key: "error.html"
                IndexDocument:
                  Suffix: "index.html"
                RedirectAllRequestsTo:
                  Hostname: "string"
                  Protocol: "http"
                RoutingRules:
                  - Condition:
                      HttpErrorCodeReturnedEquals: "string"
                      KeyPrefixEquals: "string"
                    Redirect:
                      HostName: "string"
                      HttpRedirectCode: "string"
                      Protocol: "http"
                      ReplaceKeyPrefixWith: "string"
                      ReplaceKeyWith: "string"
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

'''

# Import Python Libs
from __future__ import absolute_import
import logging
import os
import os.path
from copy import deepcopy
import json

# Import Salt Libs
from salt.ext.six import string_types  # pylint: disable=import-error
from salt.utils.boto3 import json_objs_equal

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_s3_bucket' if 'boto_s3_bucket.exists' in __salt__ else False


def _get_canonical_id(region, key, keyid, profile):
    return __salt__['boto_s3_bucket.list'](
        region=region, key=key, keyid=keyid, profile=profile
    ).get('Owner')


def _acl_to_grant(ACL, owner_canonical_id):
    if 'AccessControlPolicy' in ACL:
        ret = deepcopy(ACL['AccessControlPolicy'])
        # Type is required as input, but is not returned as output
        for item in ret.get('Grants'):
            if 'Type' in item.get('Grantee', ()):
                del item['Grantee']['Type']
        # If AccessControlPolicy is set, other options are not allowed
        return ret
    ret = {
        'Grants': [{
            'Grantee': owner_canonical_id,
            'Permission': 'FULL_CONTROL'
        }],
        'Owner': owner_canonical_id
    }
    if 'ACL' in ACL:
        # This is syntactic sugar; expand it out
        acl = ACL['ACL']
        if acl in ('public-read', 'public-read-write'):
            ret['Grants'].append({
                'Grantee': {
                    'URI': 'http://acs.amazonaws.com/groups/global/AllUsers'
                },
                'Permission': 'READ'
            })
        if acl == 'public-read-write':
            ret['Grants'].append({
                'Grantee': {
                    'URI': 'http://acs.amazonaws.com/groups/global/AllUsers'
                },
                'Permission': 'WRITE'
            })
        if acl == 'aws-exec-read':
            ret['Grants'].append({
                'Grantee': {
                    'DisplayName': 'za-team',
                    'ID': '6aa5a366c34c1cbe25dc49211496e913e0351eb0e8c37aa3477e40942ec6b97c'
                },
                'Permission': 'READ'
            })
        if acl == 'authenticated-read':
            ret['Grants'].append({
                'Grantee': {
                    'URI': 'http://acs.amazonaws.com/groups/global/AuthenticatedUsers'
                },
                'Permission': 'READ'
            })
        if acl == 'log-delivery-write':
            for permission in ('WRITE', 'READ_ACP'):
                ret['Grants'].append({
                    'Grantee': {
                        'URI': 'http://acs.amazonaws.com/groups/s3/LogDelivery'
                    },
                    'Permission': permission
                })
    for key, permission in (
        ('GrantFullControl', 'FULL_CONTROL'),
        ('GrantRead', 'READ'),
        ('GrantReadACP', 'READ_ACP'),
        ('GrantWrite', 'WRITE'),
        ('GrantWriteACP', 'WRITE_ACP'),
    ):
        if key in ACL:
            for item in ACL[key].split(','):
                kind, val = item.split('=')
                if kind == 'uri':
                    grantee = {
                        'URI': val,
                    }
                elif kind == 'id':
                    grantee = {
                        # No API provides this info, so the result will never
                        # match, and we will always update. Result is still
                        # idempotent
                        # 'DisplayName': ???,
                        'ID': val
                    }
                else:
                    grantee = {
                        # No API provides this info, so the result will never
                        # match, and we will always update. Result is still
                        # idempotent
                        # 'DisplayName': ???,
                        # 'ID': ???
                    }
                ret['Grants'].append({
                    'Grantee': grantee,
                    'Permission': permission
                })
    return ret


def _get_role_arn(name, region=None, key=None, keyid=None, profile=None):
    if name.startswith('arn:aws:iam:'):
        return name

    account_id = __salt__['boto_iam.get_account_id'](
        region=region, key=key, keyid=keyid, profile=profile
    )
    if profile and 'region' in profile:
        region = profile['region']
    if region is None:
        region = 'us-east-1'
    return 'arn:aws:iam::{0}:role/{1}'.format(account_id, name)


def _compare_json(current, desired, region, key, keyid, profile):
    return json_objs_equal(current, desired)


def _compare_acl(current, desired, region, key, keyid, profile):
    '''
    ACLs can be specified using macro-style names that get expanded to
    something more complex. There's no predictable way to reverse it.
    So expand all syntactic sugar in our input, and compare against that
    rather than the input itself.
    '''
    ocid = _get_canonical_id(region, key, keyid, profile)
    return json_objs_equal(current, _acl_to_grant(desired, ocid))


def _compare_policy(current, desired, region, key, keyid, profile):
    '''
    Policy discription is always returned as a JSON string. Comparison
    should be object-to-object, since order is not significant in JSON
    '''
    if isinstance(desired, string_types):
        desired = json.loads(desired)

    if current is not None:
        temp = current.get('Policy')
        if isinstance(temp, string_types):
            current = {'Policy': json.loads(temp)}
        else:
            current = None
    return json_objs_equal(current, desired)


def _compare_replication(current, desired, region, key, keyid, profile):
    '''
    Replication accepts a non-ARN role name, but always returns an ARN
    '''
    if desired is not None and desired.get('Role'):
        desired = deepcopy(desired)
        desired['Role'] = _get_role_arn(desired['Role'],
                                 region=region, key=key, keyid=keyid, profile=profile)
    return json_objs_equal(current, desired)


def present(name, Bucket,
            LocationConstraint=None,
            ACL=None,
            CORSRules=None,
            LifecycleConfiguration=None,
            Logging=None,
            NotificationConfiguration=None,
            Policy=None,
            Replication=None,
            RequestPayment=None,
            Tagging=None,
            Versioning=None,
            Website=None,
            region=None, key=None, keyid=None, profile=None):
    '''
    Ensure bucket exists.

    name
        The name of the state definition

    Bucket
        Name of the bucket.

    LocationConstraint
        'EU'|'eu-west-1'|'us-west-1'|'us-west-2'|'ap-southeast-1'|'ap-southeast-2'|'ap-northeast-1'|'sa-east-1'|'cn-north-1'|'eu-central-1'

    ACL
        The permissions on a bucket using access control lists (ACL).

    CORSRules
        The cors configuration for a bucket.

    LifecycleConfiguration
        Lifecycle configuration for your bucket

    Logging
        The logging parameters for a bucket and to specify permissions for who
        can view and modify the logging parameters.

    NotificationConfiguration
        notifications of specified events for a bucket

    Policy
        Policy on the bucket

    Replication
        Replication rules. You can add as many as 1,000 rules.
        Total replication configuration size can be up to 2 MB

    RequestPayment
        The request payment configuration for a bucket. By default, the bucket
        owner pays for downloads from the bucket. This configuration parameter
        enables the bucket owner (only) to specify that the person requesting
        the download will be charged for the download

    Tagging
        A dictionary of tags that should be set on the bucket

    Versioning
        The versioning state of the bucket

    Website
        The website configuration of the bucket

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    '''
    ret = {'name': Bucket,
           'result': True,
           'comment': '',
           'changes': {}
           }

    if ACL is None:
        ACL = {'ACL': 'private'}
    if NotificationConfiguration is None:
        NotificationConfiguration = {}
    if RequestPayment is None:
        RequestPayment = {'Payer': 'BucketOwner'}

    r = __salt__['boto_s3_bucket.exists'](Bucket=Bucket,
           region=region, key=key, keyid=keyid, profile=profile)

    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to create bucket: {0}.'.format(r['error']['message'])
        return ret

    if not r.get('exists'):
        if __opts__['test']:
            ret['comment'] = 'S3 bucket {0} is set to be created.'.format(Bucket)
            ret['result'] = None
            return ret
        r = __salt__['boto_s3_bucket.create'](Bucket=Bucket,
                   LocationConstraint=LocationConstraint,
                   region=region, key=key, keyid=keyid, profile=profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create bucket: {0}.'.format(r['error']['message'])
            return ret

        for setter, testval, funcargs in (
                ('put_acl', ACL, ACL),
                ('put_cors', CORSRules, {"CORSRules": CORSRules}),
                ('put_lifecycle_configuration', LifecycleConfiguration, {"Rules": LifecycleConfiguration}),
                ('put_logging', Logging, Logging),
                ('put_notification_configuration', NotificationConfiguration, NotificationConfiguration),
                ('put_policy', Policy, {"Policy": Policy}),
                # versioning must be set before replication
                ('put_versioning', Versioning, Versioning),
                ('put_replication', Replication, Replication),
                ('put_request_payment', RequestPayment, RequestPayment),
                ('put_tagging', Tagging, Tagging),
                ('put_website', Website, Website),
        ):
            if testval is not None:
                r = __salt__['boto_s3_bucket.{0}'.format(setter)](Bucket=Bucket,
                                   region=region, key=key, keyid=keyid, profile=profile,
                                   **funcargs)
                if not r.get('updated'):
                    ret['result'] = False
                    ret['comment'] = 'Failed to create bucket: {0}.'.format(r['error']['message'])
                    return ret

        _describe = __salt__['boto_s3_bucket.describe'](Bucket,
                                   region=region, key=key, keyid=keyid, profile=profile)
        ret['changes']['old'] = {'bucket': None}
        ret['changes']['new'] = _describe
        ret['comment'] = 'S3 bucket {0} created.'.format(Bucket)

        return ret

    # bucket exists, ensure config matches
    ret['comment'] = os.linesep.join([ret['comment'], 'S3 bucket {0} is present.'.format(Bucket)])
    ret['changes'] = {}
    _describe = __salt__['boto_s3_bucket.describe'](Bucket=Bucket,
                                 region=region, key=key, keyid=keyid, profile=profile)
    if 'error' in _describe:
        ret['result'] = False
        ret['comment'] = 'Failed to update bucket: {0}.'.format(_describe['error']['message'])
        ret['changes'] = {}
        return ret
    _describe = _describe['bucket']

    # Once versioning has been enabled, it can't completely go away, it can
    # only be suspended
    if not bool(Versioning) and bool(_describe.get('Versioning')):
        Versioning = {'Status': 'Suspended'}

    config_items = [
            ('ACL', 'put_acl',
                    _describe.get('ACL'), _compare_acl, ACL,
                    None),
            ('CORS', 'put_cors',
                    _describe.get('CORS'), _compare_json, {"CORSRules": CORSRules} if CORSRules else None,
                   'delete_cors'),
            ('LifecycleConfiguration', 'put_lifecycle_configuration',
                    _describe.get('LifecycleConfiguration'), _compare_json, {"Rules": LifecycleConfiguration} if LifecycleConfiguration else None,
                    'delete_lifecycle_configuration'),
            ('Logging', 'put_logging',
                    _describe.get('Logging', {}).get('LoggingEnabled'), _compare_json, Logging,
                    None),
            ('NotificationConfiguration', 'put_notification_configuration',
                    _describe.get('NotificationConfiguration'), _compare_json, NotificationConfiguration,
                    None),
            ('Policy', 'put_policy',
                    _describe.get('Policy'), _compare_policy, {"Policy": Policy} if Policy else None,
                    'delete_policy'),
            ('RequestPayment', 'put_request_payment',
                    _describe.get('RequestPayment'), _compare_json, RequestPayment,
                    None),
            ('Tagging', 'put_tagging',
                    _describe.get('Tagging'), _compare_json, Tagging,
                    'delete_tagging'),
            ('Website', 'put_website',
                    _describe.get('Website'), _compare_json, Website,
                    'delete_website'),
    ]
    versioning_item = ('Versioning', 'put_versioning',
                    _describe.get('Versioning'), _compare_json, Versioning or {},
                    None)
    # Substitute full ARN into desired state for comparison
    replication_item = ('Replication', 'put_replication',
                    _describe.get('Replication', {}).get('ReplicationConfiguration'), _compare_replication, Replication,
                    'delete_replication')

    # versioning must be turned on before replication can be on, thus replication
    # must be turned off before versioning can be off
    if Replication is not None:
        # replication will be on, must deal with versioning first
        config_items.append(versioning_item)
        config_items.append(replication_item)
    else:
        # replication will be off, deal with it first
        config_items.append(replication_item)
        config_items.append(versioning_item)

    for varname, setter, current, comparator, desired, deleter in config_items:
        if not comparator(current, desired, region, key, keyid, profile):
            # current state and desired state differ
            if __opts__['test']:
                msg = 'S3 bucket {0} set to be modified.'.format(Bucket)
                ret['comment'] = msg
                ret['result'] = None
                return ret
            ret['changes'].setdefault('new', {})[varname] = desired
            ret['changes'].setdefault('old', {})[varname] = current

            if deleter and desired is None:
                # Setting can be deleted, so use that to unset it
                r = __salt__['boto_s3_bucket.{0}'.format(deleter)](Bucket=Bucket,
                   region=region, key=key, keyid=keyid, profile=profile)
                if not r.get('deleted'):
                    ret['result'] = False
                    ret['comment'] = 'Failed to update bucket: {0}.'.format(r['error']['message'])
                    ret['changes'] = {}
                    return ret
            else:
                r = __salt__['boto_s3_bucket.{0}'.format(setter)](Bucket=Bucket,
                   region=region, key=key, keyid=keyid, profile=profile,
                   **(desired or {}))
                if not r.get('updated'):
                    ret['result'] = False
                    ret['comment'] = 'Failed to update bucket: {0}.'.format(r['error']['message'])
                    ret['changes'] = {}
                    return ret

    # Since location can't be changed, try that last so at least the rest of
    # the things are correct by the time we fail here. Fail so the user will
    # notice something mismatches their desired state.
    if _describe.get('Location', {}).get('LocationConstraint') != LocationConstraint:
        msg = 'Bucket {0} location does not match desired configuration, but cannot be changed'.format(LocationConstraint)
        log.warning(msg)
        ret['result'] = False
        ret['comment'] = 'Failed to update bucket: {0}.'.format(msg)
        return ret

    return ret


def absent(name, Bucket,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Ensure bucket with passed properties is absent.

    name
        The name of the state definition.

    Bucket
        Name of the bucket.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    '''

    ret = {'name': Bucket,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_s3_bucket.exists'](Bucket,
                       region=region, key=key, keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete bucket: {0}.'.format(r['error']['message'])
        return ret

    if r and not r['exists']:
        ret['comment'] = 'S3 bucket {0} does not exist.'.format(Bucket)
        return ret

    if __opts__['test']:
        ret['comment'] = 'S3 bucket {0} is set to be removed.'.format(Bucket)
        ret['result'] = None
        return ret
    r = __salt__['boto_s3_bucket.delete'](Bucket,
                                    region=region, key=key,
                                    keyid=keyid, profile=profile)
    if not r['deleted']:
        ret['result'] = False
        ret['comment'] = 'Failed to delete bucket: {0}.'.format(r['error']['message'])
        return ret
    ret['changes']['old'] = {'bucket': Bucket}
    ret['changes']['new'] = {'bucket': None}
    ret['comment'] = 'S3 bucket {0} deleted.'.format(Bucket)
    return ret
