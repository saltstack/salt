# -*- coding: utf-8 -*-
'''
Manage S3 buckets.

This module is intended to replace the s3 module for performing operations on
AWS S3 buckets.

:configuration: This module uses the awscli tool provided by Amazon. Install
    awscli on the minion executing these commands through pip. The awscli
    documentation contains the configuration instructions.
'''
import json

# import salt libs
import salt.utils
from salt.utils import aws


def __virtual__():
    return aws.installed()


def list_buckets(region, opts=None, user=None):
    '''
    List the buckets in the selected region.

    region
        Region to list the S3 buckets for

    opts : None
        Any additional options to add to the command line

    user : None
        Run as a different user. This user must have access permissions to AWS
        configured.

    CLI Example:

    .. code-block:: bash
        salt '*' aws_bucket.list_buckets eu-west-1
    '''
    out = aws.cli(
        's3api', 'list-buckets', region, __salt__, opts=opts, user=user)

    ret = {
        'retcode': 0,
        'stdout': [bucket['Name'] for bucket in out['Buckets']],
    }
    return ret


def create_bucket(name, region, opts=None, user=None):
    '''
    Creates a bucket with the given name. This name needs to be globally
    unique across S3.

    name
        Name of bucket to create

    region
        Region to create the S3 bucket in

    opts : None
        Any additional options to add to the command line

    user : None
        Run awscli as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash
        salt '*' aws_bucket.create_bucket saltbucket eu-west-1
    '''
    create = {'bucket': name}

    out = aws.cli(
        's3api', 'create-bucket', region, __salt__, opts=opts, user=user,
        **create)

    retcode = 0

    if isinstance(out, basestring):
        retcode = 1
        stdout = ''
        stderr = out
    else:
        retcode = 0
        stdout = out['Location'].replace('/', '')
        stderr = ''

    # Remove the leading / so we just see the bucket's name
    return {
        'retcode': retcode,
        'stdout': stdout,
        'stderr': stderr,
    }


def delete_bucket(name, region, force=False, user=None, opts=None):
    '''
    Deletes the named bucket. The named bucket must be in the region
    specified.

    name
        Name of bucket to delete

    region
        Region the bucket resides in

    force : False
        If the bucket is not empty, you must set this flag to delete it

    opts : None
        Any additional options to add to the command line

    user : None
        Run awscli as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash
        salt '*' aws_bucket.delete_bucket saltbucket eu-west-1
    '''
    delete = {'bucket': name}

    bucket_contents = __salt__['aws_file.list_directory'](
        path='/',
        bucket=name,
        region=region,
        opts=opts,
        user=user)

    if bucket_contents['retcode'] != 0:
        return {
            'retcode': bucket_contents['retcode'],
            'stdout': '',
            'stderr': bucket_contents['stdout'],
        }

    if bucket_contents['stdout']:
        if not force:
            return {
                'retcode': 1,
                'stdout': '',
                'stderr': u'Bucket {bucket} in {region} is not empty'.format(
                    bucket=name,
                    region=region),
            }

        for filename in bucket_contents['stdout'].split('\n'):
            removed_file = __salt__['aws_file.remove'](
                path=filename,
                recursive=True,
                bucket=name,
                region=region,
                user=user,
                opts=opts)
            if removed_file['retcode'] != 0: # Something went wrong, stop
                return {
                    'retcode': removed_file['retcode'],
                    'stdout': '',
                    'stderr': removed_file['stderr'],
                }

    rtn = aws.cli(
        's3api', 'delete-bucket', region, __salt__, opts=opts, user=user,
        **delete)

    if rtn:
        retcode = 1
        stdout = ''
        stderr = rtn
    else:
        retcode = 0
        stdout = name
        stderr = ''

    return {
        'retcode': retcode,
        'stdout': stdout,
        'stderr': stderr,
    }


def bucket_exists(name, region, opts=None, user=None):
    '''
    Returns True or False on whether the bucket exists in the region

    name
        Name of the S3 bucket to search for

    region
        Name of the region to search in

    opts : None
        Any additional options to add to the command line

    user : None
        Run awscli as a different user

    CLI Example:

    .. code-block:: bash
        salt '*' aws_bucket.bucket_exists saltbucket eu-west-1
    '''
    buckets = list_buckets(region, opts, user)
    return name in buckets['stdout']
