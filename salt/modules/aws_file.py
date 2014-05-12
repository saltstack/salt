'''
File Management through AWS S3.

This module is intended to replace the s3
module for performing file management operations against AWS.

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


def _error_occurred(ret):
    '''
    Return whether an error occurred in the return value.
    '''
    error_strings = (
        u'Invalid choice',
        u'A client error',
    )

    for error in error_strings:
        if error in ret:
            return True
    else:
        return False


def _get_region(region):
    return u'--region {0}'.format(region)


def _construct_path(bucket, path, isdir):
    '''
    Construct a path acceptable to S3.
    '''
    if path == '/':
        path = ''

    rtn = '/'.join(('s3:/', bucket, path))

    if isdir and rtn[-1] != '/':
        rtn = u'{0}/'.format(rtn)

    elif not isdir and rtn[-1] == '/':
        rtn = rtn[:-1]

    return rtn


def _construct_cmd(cmd, *args):
    full_cmd = ['aws', 's3', cmd]
    full_cmd.extend(args)
    return ' '.join(full_cmd)


def list_directory(path, bucket, region, opts=None, user=None):
    '''
    List the files and directories in a bucket with a path.

    path
        Full directory path to list. To list the root, use /

    bucket
        Bucket to list files against.

    region
        Region containing the bucket to search

    opts : None
        Any additional options to add to the command line

    user : None
        Run aws_file as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash
        salt '*' aws_file.list_directory testbucket eu-west-1 directory
    '''
    ls_path = _construct_path(bucket, path, True)

    cmd = _construct_cmd('ls', ls_path, _get_region(region))
    
    out = out = __salt__['cmd.run'](cmd, runas=user)

    out = '\n'.join(o.strip().replace('PRE ', '') for o in out.split('\n'))

    retcode = 0
    if not out.strip():
        if path == '/':
            retcode = 0
            out = ''
        else:
            retcode = 1
            out = u'Directory {0} is not in bucket {1}'.format(path, bucket)

    ret = {
        'retcode': retcode,
        'stdout': out,
    }
    return ret


def file_exists(path, bucket, region, opts=None, user=None):
    '''
    Return whether a file exists in the given bucket.

    path
        File to search for

    bucket
        Bucket to search for the file in

    region
        Region containing the bucket to search

    opts : None
        Any additional options to add to the command line

    user : None
        Run aws_file as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash
        salt '*' aws_file.file_exists test/file.txt testbucket eu-west-1
    '''
    find = _construct_path(bucket, path, False)

    cmd = _construct_cmd('ls', find, _get_region(region))

    out = __salt__['cmd.run'](cmd, runas=user)

    return len(out.strip()) > 0


def directory_exists(path, bucket, region, opts=None, user=None):
    '''
    Return whether a directory exists in the given bucket.

    path
        Directory to search for

    bucket
        Bucket to search in

    region
        Region containing the bucket to search

    opts : None
        Any additional options to add to the command line

    user : None
        Run aws_file as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash
        salt '*' aws_file.directory_exists test testbucket eu-west-1
    '''
    find = _construct_path(bucket, path, True)

    cmd = _construct_cmd('ls', find, _get_region(region))

    out = __salt__['cmd.run'](cmd, runas=user)

    return len(out.strip()) > 0


def copy(src, dst, bucket, region, force=False, opts=None, user=None):
    '''
    Copy a file to an S3 bucket.

    src
        File to copy

    dst
        Path of the file to copy to

    bucket
        Bucket to copy the file into

    force : False
        Forcibly overwrite the file if it already exists

    opts : None
        Any additional options to add to the command line

    user : None
        Run aws_file as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash
        salt '*' aws_file.copy source_file.txt test/destination_file.txt testbucket eu-west-1
    '''
    exists = file_exists(dst, bucket, region, opts, user)
    if exists and not force:
        retcode = 1
        ret = u'File {0} exists in bucket {1} and force is not set'.format(
            dst, bucket)
    else:
        destination_path = _construct_path(bucket, dst, False)

        cmd = _construct_cmd('cp', src, destination_path, _get_region(region))

        ret = __salt__['cmd.run'](cmd, runas=user)
        retcode = 0

        if _error_occurred(ret):
            retcode = 1

    return {
        'retcode': retcode,
        'stdout': ret,
    }


def remove(path, bucket, region, recursive=False, opts=None, user=None):
    '''
    Remove a file from S3.

    path
        Path to the file to remove

    bucket
        Bucket to remove the file from

    region
        Region to get the bucket from

    recursive : False
        If the path is a directory, recursively delete the contents as well

    opts : None
        Any additional options to add to the command line

    user : None
        Run aws_file as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash
        salt '*' aws_file.remove test_file.txt testbucket eu-west-1
    '''
    remove_path = _construct_path(bucket, path, False)

    args = []
    if recursive:
        args.append('--recursive')

    cmd = _construct_cmd('rm', remove_path, _get_region(region), *args)

    ret = __salt__['cmd.run'](cmd, runas=user)
    retcode = 0

    if _error_occurred(ret):
        retcode = 1

    return {
        'retcode': retcode,
        'stderr': ret if retcode else '',
        'stdout': ret if retcode == 0 else '',
    }
