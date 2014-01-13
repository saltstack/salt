# -*- coding: utf-8 -*-
'''
Create and destroy S3 Buckets
=============================

Create and destroy S3 buckets. This interacts with Amazon's services, and so
may incur charges.

This differs from the raw s3 module in that it uses the awscli tool provided by
Amazon.  This can be downloaded from pip. Check the documentation for awscli
for configuration information.
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
        Run hg as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash
        salt '*' aws_bucket.list_buckets eu-west-1
    '''
    out = aws.cli(
        's3api', 'list-buckets', region=region, opts=opts, user=user)

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
        's3api', 'create-bucket', region=region, opts=opts, user=user,
        **create)

    # Remove the leading / so we just see the bucket's name
    ret = {
        'retcode': 0,
        'stdout': out['Location'].replace('/', ''),
        'stderr': '',
    }


def delete_bucket(name, region, user=None, opts=None):
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
    rtn = aws.cli(
        's3api',
        'delete-bucket',
        region=region,
        opts=opts,
        user=user,
        **delete)

    return {
        'retcode': 0,
        'stdout': name,
        'stderr': '',
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
    return name in buckets
