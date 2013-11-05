# -*- coding: utf-8 -*-
'''
Connection module for Amazon S3

:configuration: This module is not usable until the following are specified
    either in a pillar or in the minion's config file::

        s3.keyid: GKTADJGHEIQSXMKKRBJ08H
        s3.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A service_url may also be specified in the configuration::

        s3.service_url: s3.amazonaws.com

    If a service_url is not specified, the default is s3.amazonaws.com. This
    may appear in various documentation as an "endpoint". A comprehensive list
    for Amazon S3 may be found at::

        http://docs.aws.amazon.com/general/latest/gr/rande.html#s3_region

    The service_url will form the basis for the final endpoint that is used to
    query the service.

    This module should be usable to query other S3-like services, such as
    Eucalyptus.
'''

# Import Python libs
import logging

# Import Salt libs
import salt.utils
import salt.utils.s3

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Should work on any modern Python installation
    '''
    return 's3'


def delete(bucket, path=None, action=None, key=None, keyid=None,
           service_url=None):
    '''
    Delete a bucket, or delete an object from a bucket.

    CLI Example to delete a bucket::

        salt myminion s3.delete mybucket

    CLI Example to delete an object from a bucket::

        salt myminion s3.delete mybucket remoteobject
    '''
    key, keyid, service_url = _get_key(key, keyid, service_url)

    return salt.utils.s3.query(method='DELETE',
                               bucket=bucket,
                               path=path,
                               action=action,
                               key=key,
                               keyid=keyid,
                               service_url=service_url)


def get(bucket=None, path=None, return_bin=False, action=None,
        local_file=None, key=None, keyid=None, service_url=None):
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
    key, keyid, service_url = _get_key(key, keyid, service_url)

    return salt.utils.s3.query(method='GET',
                               bucket=bucket,
                               path=path,
                               return_bin=return_bin,
                               local_file=local_file,
                               action=action,
                               key=key,
                               keyid=keyid,
                               service_url=service_url)


def head(bucket, path=None, key=None, keyid=None, service_url=None):
    '''
    Return the metadata for a bucket, or an object in a bucket.

    CLI Examples:

    .. code-block:: bash

        salt myminion s3.head mybucket
        salt myminion s3.head mybucket myfile.png
    '''
    key, keyid, service_url = _get_key(key, keyid, service_url)

    return salt.utils.s3.query(method='HEAD',
                               bucket=bucket,
                               path=path,
                               key=key,
                               keyid=keyid,
                               service_url=service_url)


def put(bucket, path=None, return_bin=False, action=None, local_file=None,
        key=None, keyid=None, service_url=None):
    '''
    Create a new bucket, or upload an object to a bucket.

    CLI Example to create a bucket:

    .. code-block:: bash

        salt myminion s3.put mybucket

    CLI Example to upload an object to a bucket:

    .. code-block:: bash

        salt myminion s3.put mybucket remotepath local_path=/path/to/file
    '''
    key, keyid, service_url = _get_key(key, keyid, service_url)

    return salt.utils.s3.query(method='PUT',
                               bucket=bucket,
                               path=path,
                               return_bin=return_bin,
                               local_file=local_file,
                               action=action,
                               key=key,
                               keyid=keyid,
                               service_url=service_url)


def _get_key(key, keyid, service_url):
    '''
    Examine the keys, and populate as necessary
    '''
    if not key and __salt__['config.option']('s3.key'):
        key = __salt__['config.option']('s3.key')
    if not keyid and __salt__['config.option']('s3.keyid'):
        keyid = __salt__['config.option']('s3.keyid')

    if not service_url and __salt__['config.option']('s3.service_url'):
        service_url = __salt__['config.option']('s3.service_url')

    if not service_url:
        service_url = 's3.amazonaws.com'

    return key, keyid, service_url
