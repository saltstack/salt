'''
Support for the Amazon Simple Queue Service.
Currently, this module cannot select which user to run the commands. Your
boto config must be in /etc/boto.cfg with your AWS credentials.
'''

# Import salt libs
from salt import utils
from salt.exceptions import CommandExecutionError

_OUTPUT = '-output json'


def _check_aws():
    '''
    Make sure boto is installed
    '''
    utils.check_or_die('aws')
    return 'amazon_sqs'


def _region(region):
    '''
    Return the region argument.
    '''
    return ' --region {r}'.format(r=region)


def _run_aws(cmd, region, opts, user, **kwargs):
    '''
    Runs the given command against AWS.
    cmd
        Command to run
    region
        Region to execute cmd in
    opts
        Pass in from salt
    user
        Pass in from salt
    kwargs
        Key-value arguments to pass to the command
    '''
    _formatted_args = [
        '--{0} {1}'.format(k, v) for k, v in kwargs.iteritems()]

    cmd = 'aws sqs {cmd} {args} {region}'.format(
        cmd=cmd,
        args=' '.join(_formatted_args),
        region=_region(region))

    rtn = __salt__['cmd.run'](cmd, runas=user)


def list_queues(region, opts=None, user=None):
    '''
    List the queues in the selected region.

    region
        Region to list SQS queues for

    opts : None
        Any additional options to add to the command line

    user : None
        Run hg as a user other than what the minion runs as
    '''
    return _run_aws('list-queues', region, opts, user)


def create_queue(name, region, opts=None, user=None):
    '''
    Creates a queue with the correct name.
    
    name
        Name of the SQS queue to create

    region
        Region to create the SQS queue in

    opts : None
        Any additional options to add to the command line

    user : None
        Run hg as a user other than what the minion runs as
    '''
    _check_aws()

    return _run_aws(
        'create-queue', name=name, region=region, opts=opts,
        user=user)
    
    create = True

    out = ''
    err = ''
    rtn = 0

    if queue_exists(name, region):
        err = (
            u'Queue {0} in region {1} exists'.format(name, region))
        create = False
        rtn = 1

    if create:
        # Create the queue
        sqs_region = _connect_to_region(region)
        sqs_region.create_queue(name, default_timeout)
        if not out:
            out = u'Creating queue {0} in region {1}'.format(
                name, region)

    return {
        'stdout': out,
        'stderr': err,
        'retcode': rtn,
    }


def delete_queue(name, region, opts=None, user=None):
    '''
    Deletes a queue in the region.

    name
        Name of the SQS queue to deletes
    region
        Name of the region to delete the queue from

    opts : None
        Any additional options to add to the command line

    user : None
        Run hg as a user other than what the minion runs as
    '''
    out = ''
    err = ''
    rtn = 0

    if queue_exists(name, region):
        sqs_region = _connect_to_region(region)
        out = u'Deleting {0} from {1}'.format(name, region)
        sqs_region.delete_queue(name)
    else:
        err = u'Queue {0} does not exist in {1}'.format(name, region)
        rtn = 1

    return {
        'stdout': out,
        'stderr': err,
        'retcode': rtn,
    }

def queue_exists(name, region, opts=None, user=None):
    '''
    Returns True or False on whether the queue exists in the region

    name
        Name of the SQS queue to search for

    region
        Name of the region to search for the queue in

    opts : None
        Any additional options to add to the command line

    user : None
        Run hg as a user other than what the minion runs as
    '''
    sqs_region = _connect_to_region(region)
    return sqs_region.get_queue(name) != None
