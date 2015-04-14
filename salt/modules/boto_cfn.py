# -*- coding: utf-8 -*-
'''
    Connection module for Amazon Cloud Formation

    .. versionadded:: Beryllium

    :configuration: This module accepts explicit AWS credentials but can also utilize
    IAM roles assigned to the instance trough Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at::

       http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file::

        cfn.keyid: GKTADJGHEIQSXMKKRBJ08H
        cfn.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration::

        cfn.region: us-east-1

:depends: boto
'''
# keep lint from choking on _get_conn and _cache_id
#pylint disable=E0602

from __future__ import absolute_import

# Import Python libs
import logging

log = logging.getLogger(__name__)

# Import third party libs
try:
    import boto
    import boto.cloudformation
    import boto.cloudformation.connection
    import boto.cloudformation.stack
    import boto.cloudformation.template
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
    __utils__['boto.assign_funcs'](__name__, 'cfn', module='cloudformation')
    return True


def exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if a stack exists.

    .. versionadded:: Beryllium

    CLI example::

        salt myminion boto_cfn.exists mystack region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        # Returns an object if stack exists else an exception
        exists = conn.describe_stacks(name)
        log.debug('Stack {0} exists.'.format(name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug('Exists returned an excpetion.\n{0}'.format(str(e)))
        return False


def create(name, template_body=None, template_url=None, parameters=None, notification_arns=None, disable_rollback=None,
           timeout_in_minutes=None, capabilities=None, tags=None, on_failure=None, stack_policy_body=None,
           stack_policy_url=None, region=None, key=None, keyid=None, profile=None):
    '''
    Create a CFN stack.

    .. versionadded:: Beryllium

    CLI example to create a stack::

        salt myminion boto_cfn.create mystack template_url='https://s3.amazonaws.com/bucket/template.cft' \
        region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        return conn.create_stack(name, template_body, template_url, parameters, notification_arns, disable_rollback,
                                 timeout_in_minutes, capabilities, tags, on_failure, stack_policy_body, stack_policy_url)
    except boto.exception.BotoServerError as e:
        msg = 'Failed to create stack {0}.'.format(name)
        log.error(msg)
        log.debug(e)
        return False


def update_stack(name, template_body=None, template_url=None, parameters=None, notification_arns=None,
                 disable_rollback=False, timeout_in_minutes=None, capabilities=None, tags=None,
                 use_previous_template=None, stack_policy_during_update_body=None, stack_policy_during_update_url=None,
                 stack_policy_body=None, stack_policy_url=None, region=None, key=None, keyid=None, profile=None):
    '''
    Update a CFN stack.

    .. versionadded:: Beryllium

    CLI example to update a stack::

        salt myminion boto_cfn.update_stack mystack template_url='https://s3.amazonaws.com/bucket/template.cft' \
        region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        update = conn.update_stack(name, template_body, template_url, parameters, notification_arns,
                                   disable_rollback, timeout_in_minutes, capabilities, tags, use_previous_template,
                                   stack_policy_during_update_body, stack_policy_during_update_url,
                                   stack_policy_body, stack_policy_url)
        log.debug('Updated result is : {0}.'.format(update))
        return update
    except boto.exception.BotoServerError as e:
        msg = 'Failed to update stack {0}.'.format(name)
        log.debug(e)
        log.error(msg)
        return str(e)


def delete(name, region=None, key=None, keyid=None, profile=None):
    '''
    Delete a CFN stack.

    .. versionadded:: Beryllium

    CLI example to delete a stack::

        salt myminion boto_cfn.delete mystack region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        return conn.delete_stack(name)
    except boto.exception.BotoServerError as e:
        msg = 'Failed to create stack {0}.'.format(name)
        log.error(msg)
        log.debug(e)
        return str(e)


def get_template(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if attributes are set on a CFN stack.

    .. versionadded:: Beryllium

    CLI example::

        salt myminion boto_cfn.get_template mystack
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        template = conn.get_template(name)
        log.info('Retrieved template for stack {0}'.format(name))
        return template
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Template {0} does not exist'.format(name)
        log.error(msg)
        return str(e)


def validate_template(template_body=None, template_url=None, region=None, key=None, keyid=None, profile=None):
    '''
    Validate cloudformation template

    .. versionadded:: Beryllium

    CLI example::

        salt myminion boto_cfn.validate_template mystack-template
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        # Returns an object if json is validated and an exception if its not
        return conn.validate_template(template_body, template_url)
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Error while trying to validate template {0}.'.format(template_body)
        log.error(msg)
        return str(e)
