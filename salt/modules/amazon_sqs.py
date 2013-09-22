'''
Support for the Amazon Simple Queue Service.
Currently, this module cannot select which user to run the commands. Your
boto config must be in /etc/boto.cfg with your AWS credentials.
'''

# Import salt libs
from salt.exceptions import CommandNotFoundError

def _check_boto():
    '''
    Make sure boto is installed
    '''
    try:
        import boto
    except ImportError:
        raise CommandNotFoundError
    return 'amazon_sqs'

def _connect_to_region(region):
    '''
    Connect to the given region.
    '''
    from boto.sqs import connect_to_region
    return connect_to_region(region)

def create_queue(name, region, default_timeout=None):
    '''
    Creates a queue with the correct name.
    
    name
        Name of the SQS queue to create
    region
        Region to create the SQS queue in
    default_timeout
        The default message timeout to use
    '''
    _check_boto()

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

def delete_queue(name, region):
    '''
    Deletes a queue in the region.

    name
        Name of the SQS queue to deletes
    region
        Name of the region to delete the queue from
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

def queue_exists(name, region):
    '''
    Returns True or False on whether the queue exists in the region

    name
        Name of the SQS queue to search for
    region
        Name of the region to search for the queue in
    '''
    sqs_region = _connect_to_region(region)
    return sqs_region.get_queue(name) != None
