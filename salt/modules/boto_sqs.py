# -*- coding: utf-8 -*-
'''
Connection module for Amazon SQS

:configuration: This module accepts explicit sqs credentials but can also utilize
    IAM roles assigned to the instance trough Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at::

       http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file::

        sqs.keyid: GKTADJGHEIQSXMKKRBJ08H
        sqs.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration::

        sqs.region: us-east-1

    If a region is not specified, the default is us-east-1.

:depends: boto
'''

# Import Python libs
import logging

log = logging.getLogger(__name__)

# Import third party libs
try:
    import boto
    import boto.sqs
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        return False
    return True


def exists(name, region=None, key=None, keyid=None):
    '''
    Check to see if a queue exists.

    CLI example::

        salt myminion sqs.exists myqueue region=us-east-1
    '''
    conn = _get_conn(region, key, keyid)
    if not conn:
        return False
    if conn.get_queue(name):
        return True
    else:
        return False


def create(name, region=None, key=None, keyid=None):
    '''
    Create an SQS queue.

    CLI example to create a queue::

        salt myminion sqs.create myqueue region=us-east-1
    '''
    conn = _get_conn(region, key, keyid)
    if not conn:
        return False
    if not conn.get_queue(name):
        try:
            conn.create_queue(name)
        except boto.exception.SQSError:
            msg = 'Failed to create queue {0}'.format(name)
            log.error(msg)
            return False
    log.info('Created queue {0}'.format(name))
    return True


def delete(name, region=None, key=None, keyid=None):
    '''
    Delete an SQS queue.

    CLI example to delete a queue::

        salt myminion sqs.delete myqueue region=us-east-1
    '''
    conn = _get_conn(region, key, keyid)
    if not conn:
        return False
    queue_obj = conn.get_queue(name)
    if queue_obj:
        deleted_queue = conn.delete_queue(queue_obj)
        if not deleted_queue:
            msg = 'Failed to delete queue {0}'.format(name)
            log.error(msg)
            return False
    return True


def get_attributes(name, region=None, key=None, keyid=None):
    '''
    Check to see if attributes are set on an SQS queue.

    CLI example::

        salt myminion sqs.get_attributes myqueue
    '''
    conn = _get_conn(region, key, keyid)
    if not conn:
        return {}
    queue_obj = conn.get_queue(name)
    if not queue_obj:
        log.error('Queue {0} does not exist.'.format(name))
        return {}
    return conn.get_queue_attributes(queue_obj)


def set_attributes(name, attributes, region=None, key=None, keyid=None):
    '''
    Set attributes on an SQS queue.

    CLI example to set attributes on a queue::

        salt myminion sqs.set_attributes myqueue '{ReceiveMessageWaitTimeSeconds: 20}' region=us-east-1
    '''
    ret = True
    conn = _get_conn(region, key, keyid)
    if not conn:
        return False
    queue_obj = conn.get_queue(name)
    if not queue_obj:
        log.error('Queue {0} does not exist.'.format(name))
        ret = False
    for attr, val in attributes.iteritems():
        attr_set = queue_obj.set_attribute(attr, val)
        if not attr_set:
            msg = 'Failed to set attribute {0} = {1} on queue {2}'
            log.error(msg.format(attr, val, name))
            ret = False
        else:
            msg = 'Set attribute {0} = {1} on queue {2}'
            log.info(msg.format(attr, val, name))
    return ret


def _get_conn(region, key, keyid):
    '''
    Get a boto connection to SQS.
    '''
    if not region and __salt__['config.option']('sqs.region'):
        region = __salt__['config.option']('sqs.region')

    if not region:
        region = 'us-east-1'

    if not key and __salt__['config.option']('sqs.key'):
        key = __salt__['config.option']('sqs.key')
    if not keyid and __salt__['config.option']('sqs.keyid'):
        keyid = __salt__['config.option']('sqs.keyid')

    try:
        conn = boto.sqs.connect_to_region(region, aws_access_key_id=keyid,
                                          aws_secret_access_key=key)
    except boto.exception.NoAuthHandlerFound:
        log.error('No authentication credentials found when attempting to'
                  ' make boto sqs connection.')
        return None
    return conn
