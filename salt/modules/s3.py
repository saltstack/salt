# -*- coding: utf-8 -*-
'''
Connection module for Amazon S3

:configuration: This module accepts explicit s3 credentials but can also utilize
    IAM roles assigned to the instance through Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at::

       http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file::

        s3.keyid: GKTADJGHEIQSXMKKRBJ08H
        s3.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A service_url may also be specified in the configuration::

        s3.service_url: s3.amazonaws.com

    A role_arn may also be specified in the configuration::

        s3.role_arn: arn:aws:iam::111111111111:role/my-role-to-assume

    If a service_url is not specified, the default is s3.amazonaws.com. This
    may appear in various documentation as an "endpoint". A comprehensive list
    for Amazon S3 may be found at::

        http://docs.aws.amazon.com/general/latest/gr/rande.html#s3_region

    The service_url will form the basis for the final endpoint that is used to
    query the service.

    SSL verification may also be turned off in the configuration:

        s3.verify_ssl: False

    This is required if using S3 bucket names that contain a period, as
    these will not match Amazon's S3 wildcard certificates. Certificate
    verification is enabled by default.

    AWS region may be specified in the configuration:

        s3.location: eu-central-1

    Default is us-east-1.

    This module should be usable to query other S3-like services, such as
    Eucalyptus.

:depends: requests
'''
from __future__ import absolute_import

# Import Python libs
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Should work on any modern Python installation
    '''
    return True


def delete(bucket, path=None, action=None, key=None, keyid=None,
           service_url=None, verify_ssl=None, kms_keyid=None, location=None,
           role_arn=None):
    '''
    Delete a bucket, or delete an object from a bucket.

    CLI Example to delete a bucket::

        salt myminion s3.delete mybucket

    CLI Example to delete an object from a bucket::

        salt myminion s3.delete mybucket remoteobject
    '''
    key, keyid, service_url, verify_ssl, kms_keyid, location, role_arn = _get_key(
        key,
        keyid,
        service_url,
        verify_ssl,
        kms_keyid,
        location,
        role_arn,
    )

    return __utils__['s3.query'](method='DELETE',
                                 bucket=bucket,
                                 path=path,
                                 action=action,
                                 key=key,
                                 keyid=keyid,
                                 kms_keyid=kms_keyid,
                                 service_url=service_url,
                                 verify_ssl=verify_ssl,
                                 location=location,
                                 role_arn=role_arn)


def get(bucket='', path='', return_bin=False, action=None,
        local_file=None, key=None, keyid=None, service_url=None,
        verify_ssl=None, kms_keyid=None, location=None, role_arn=None):
    '''
    List the contents of a bucket, or return an object from a bucket. Set
    return_bin to True in order to retrieve an object wholesale. Otherwise,
    Salt will attempt to parse an XML response.

    CLI Example to list buckets:

    .. code-block:: bash

        salt myminion s3.get

    CLI Example to list the contents of a bucket:

    .. code-block:: bash

        salt myminion s3.get mybucket

    CLI Example to return the binary contents of an object:

    .. code-block:: bash

        salt myminion s3.get mybucket myfile.png return_bin=True

    CLI Example to save the binary contents of an object to a local file:

    .. code-block:: bash

        salt myminion s3.get mybucket myfile.png local_file=/tmp/myfile.png

    It is also possible to perform an action on a bucket. Currently, S3
    supports the following actions::

        acl
        cors
        lifecycle
        policy
        location
        logging
        notification
        tagging
        versions
        requestPayment
        versioning
        website

    To perform an action on a bucket:

    .. code-block:: bash

        salt myminion s3.get mybucket myfile.png action=acl
    '''
    key, keyid, service_url, verify_ssl, kms_keyid, location, role_arn = _get_key(
        key,
        keyid,
        service_url,
        verify_ssl,
        kms_keyid,
        location,
        role_arn,
    )

    return __utils__['s3.query'](method='GET',
                                 bucket=bucket,
                                 path=path,
                                 return_bin=return_bin,
                                 local_file=local_file,
                                 action=action,
                                 key=key,
                                 keyid=keyid,
                                 kms_keyid=kms_keyid,
                                 service_url=service_url,
                                 verify_ssl=verify_ssl,
                                 location=location,
                                 role_arn=role_arn)


def head(bucket, path=None, key=None, keyid=None, service_url=None,
         verify_ssl=None, kms_keyid=None, location=None, role_arn=None):
    '''
    Return the metadata for a bucket, or an object in a bucket.

    CLI Examples:

    .. code-block:: bash

        salt myminion s3.head mybucket
        salt myminion s3.head mybucket myfile.png
    '''
    key, keyid, service_url, verify_ssl, kms_keyid, location, role_arn = _get_key(
        key,
        keyid,
        service_url,
        verify_ssl,
        kms_keyid,
        location,
        role_arn,
    )

    return __utils__['s3.query'](method='HEAD',
                                 bucket=bucket,
                                 path=path,
                                 key=key,
                                 keyid=keyid,
                                 kms_keyid=kms_keyid,
                                 service_url=service_url,
                                 verify_ssl=verify_ssl,
                                 location=location,
                                 full_headers=True,
                                 role_arn=role_arn)


def put(bucket, path=None, return_bin=False, action=None, local_file=None,
        key=None, keyid=None, service_url=None, verify_ssl=None,
        kms_keyid=None, location=None, role_arn=None):
    '''
    Create a new bucket, or upload an object to a bucket.

    CLI Example to create a bucket:

    .. code-block:: bash

        salt myminion s3.put mybucket

    CLI Example to upload an object to a bucket:

    .. code-block:: bash

        salt myminion s3.put mybucket remotepath local_file=/path/to/file
    '''
    key, keyid, service_url, verify_ssl, kms_keyid, location, role_arn = _get_key(
        key,
        keyid,
        service_url,
        verify_ssl,
        kms_keyid,
        location,
        role_arn,
    )

    return __utils__['s3.query'](method='PUT',
                                 bucket=bucket,
                                 path=path,
                                 return_bin=return_bin,
                                 local_file=local_file,
                                 action=action,
                                 key=key,
                                 keyid=keyid,
                                 kms_keyid=kms_keyid,
                                 service_url=service_url,
                                 verify_ssl=verify_ssl,
                                 location=location,
                                 role_arn=role_arn)


def _get_key(key, keyid, service_url, verify_ssl, kms_keyid, location, role_arn):
    '''
    Examine the keys, and populate as necessary
    '''
    if not key and __salt__['config.option']('s3.key'):
        key = __salt__['config.option']('s3.key')

    if not keyid and __salt__['config.option']('s3.keyid'):
        keyid = __salt__['config.option']('s3.keyid')

    if not kms_keyid and __salt__['config.option']('aws.kms.keyid'):
        kms_keyid = __salt__['config.option']('aws.kms.keyid')

    if not service_url and __salt__['config.option']('s3.service_url'):
        service_url = __salt__['config.option']('s3.service_url')

    if not service_url:
        service_url = 's3.amazonaws.com'

    if verify_ssl is None and __salt__['config.option']('s3.verify_ssl') is not None:
        verify_ssl = __salt__['config.option']('s3.verify_ssl')

    if verify_ssl is None:
        verify_ssl = True

    if location is None and __salt__['config.option']('s3.location') is not None:
        location = __salt__['config.option']('s3.location')

    if role_arn is None and __salt__['config.option']('s3.role_arn'):
        role_arn = __salt__['config.option']('s3.role_arn')

    return key, keyid, service_url, verify_ssl, kms_keyid, location, role_arn
