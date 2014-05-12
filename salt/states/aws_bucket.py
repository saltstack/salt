# -*- coding: utf-8 -*-
'''
Manage S3 Buckets
=================

Create, manage and destroy S3 buckets. This interacts with Amazon's services,
and so may incur charges.

This module uses the awscli tool provided by Amazon. This can be downloaded
from pip. Also check the documentation for awscli for configuration information

To manage files/directories inside S3 buckets, use the file state, with s3://
as the protocol.

.. code-block: yaml

    saltbucket:
        aws_bucket.exists:
            - region: eu-west-1
'''

def __virtual__():
    '''
    Only load if aws is available.
    '''
    if __salt__['cmd.has_exec']('aws'):
        return 'aws_bucket'
    return False


def exists(
        name,
        region,
        user=None,
        opts=False):
    '''
    Create a bucket on Amazon's S3 service.

    name
        Name of the S3 Bucket

    region
        Region to create the bucket in.

    user : None
        Name of the user performing the S3 operations.

    opts : None
        Include additonal arguments and options to the aws command line.
    '''
    exists = __salt__['aws_bucket.bucket_exists'](
        name=name,
        region=region,
        opts=opts,
        user=user)

    ret = {
        'changes': {},
        'comment': '',
        'name': name,
        'result': True,
    }

    if exists:
        ret['comment'] = u'{Bucket {bucket} in {region} already exists'.format(
            bucket=name,
            region=region)
        return ret

    created = __salt__['aws_bucket.create_bucket'](
        name=name,
        region=region,
        opts=opts,
        user=user)

    if created['retcode'] == 0:
        ret['changes'][name] = created['stdout']
    else:
        ret['result'] = False
        ret['comment'] = created['stderr']

    return ret


def absent(
        name,
        region,
        force=False,
        user=None,
        opts=False):
    '''
    Remove a bucket, and all objects it contains. If the bucket contains any
    object, this operation will fail, unless force is set.

    name
        Name of the bucket to remove.

    region
        Region to remove the bucket from.

    force
        If the bucket is not empty, setting force removes it anyway.

    user : None
        Name of the user performing the S3 operations.

    opts : None
        Include additional arguments and options to the aws command line.
    '''
    ret = {
        'changes': {},
        'comment': '',
        'name': name,
        'result': True,
    }

    exists = __salt__['aws_bucket.bucket_exists'](
        name=name,
        region=region,
        opts=opts,
        user=user)

    if not exists:
        ret['comment'] = u'Bucket {name} exists in {region}'.format(
            name=name,
            region=region)
        return ret

    deleted = __salt__['aws_bucket.delete_bucket'](
        name=name,
        region=region,
        force=force,
        user=user,
        opts=opts)

    if deleted['retcode'] == 0:
        ret['changes'][name] = deleted['stdout']
        ret['comment'] = u'Bucket deleted'
    else:
        ret['result'] = False
        ret['comment'] = deleted['stderr']

    return ret
