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


def _construct_path(bucket, path, isdir):
    '''
    Construct a path acceptable to S3.
    '''
    rtn = '/'.join(('s3:/', bucket, path))
    if isdir and rtn[-1] != '/':
        rtn = u'{0}/'.format(rtn)
    elif not isdir and rtn[-1] == '/':
        rtn = rtn[:-1]

    return rtn


def _construct_cmd(cmd, *args):
    cmd = ['aws', 's3', 'ls']
    cmd.extend(args)
    return ' '.join(cmd)


def ls(bucket, region, path='', isdir=True, opts=None, user=None):
    '''
    Run the ls command against a bucket. To list buckets, use aws_bucket.list_buckets

    bucket
        Bucket to list files against.

    region
        Region containing the bucket to search

    path : ''
        File path to run ls against.

    isdir : True
        Treat path is if it's a directory. This is to handle a peculiarity in
            the way S3 takes its path argument.

    opts : None
        Any additional options to add to the command line

    user : None
        Run aws_bucket as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash
        salt '*' aws_file.ls testbucket eu-west-1
    '''
    ls_path = _construct_path(bucket, path, isdir)

    cmd = _construct_cmd('ls', ls_path)
    
    out = __salt__['cmd.run'](cmd, runas=user)

    out = '\n'.join([o.strip() for o in out.split('\n')])

    retcode = 0
    if not out.strip():
        retcode = 1
        out = u'No such {0}'.format('directory' if isdir else 'file')

    ret = {
        'retcode': retcode,
        'stdout': out,
    }
    return ret
