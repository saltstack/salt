# -*- coding: utf-8 -*-
'''
Connection module for Amazon Cloud Formation

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

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto
'''
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

from salt.ext.six import string_types


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
	log.error("The boto libraries are not installed on this server")
        return False
    log.trace("The boto libraries were successfully imported")
    return True


def exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if a stack exists.

    CLI example::

        salt myminion boto_cfn.exists mystack region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        log.error((("Failed to connect to amazon aws in region {0}").format(region)))
        return False
    try:
        stack = conn.describe_stacks(name)
    except boto.exception.BotoServerError as e:
	#log.error(e)
        return False
    return True


def create(name, template_url=None, region=None, key=None, keyid=None, profile=None, parameters=None, capabilities=None):
    '''
    Create a CFN stack.

    CLI example to create a stack::

        salt myminion boto_cfn.create mystack template_url='https://s3.amazonaws.com/bucket/template.cft' region=us-east-1
	salt myminion boto_cfn.create mystack template_url='https://s3.amazonaws.com/bucket/template.cft' region=us-east-1 parameters='{"Key" : "Value", "Key2" : "Value2"}'
	salt myminion boto_cfn.create mystack template_url='https://s3.amazonaws.com/bucket/template.cft' region=us-east-1 parameters='{"Key" : "Value", "Key2" : "Value2"}' capabilities="['CAPABILITY_IAM']"
	salt myminion boto_cfn.create mystack template_url='https://s3.amazonaws.com/bucket/template.cft' region=us-east-1 capabilities="['CAPABILITY_IAM']"

    	Currently, the only implemented capability is the CAPABILITY_IAM.

    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
	log.error((("Failed to connect to amazon aws in region {0}").format(region)))
        return False
    if not exists(name):
        try:
	    #TODO: What is the right way to deal with a dict argument being passed.  Python does not do 'argument' fingerprinting.
	    if not parameters:
		log.debug("Calling create_stack with capabilities passed in")
            	conn.create_stack(name, template_url=template_url, capabilities=capabilities)
    	    else:
		log.debug("Calling create_stack with capabilities and parameters passed in")
            	conn.create_stack(name, template_url=template_url, parameters=parameters.items(), capabilities=capabilities)
        except boto.exception.BotoServerError as e:
            msg = 'Failed to create stack {0}'.format(name)
            log.error(msg)
	    log.debug(e)
            return False
    if not exists(name):
        msg = 'Failed to create stack {0}'.format(name)
        log.error(msg)
        return False
    log.info('Created stack {0}'.format(name))
    return True


def delete(name, region=None, key=None, keyid=None, profile=None):
    '''
    Delete a CFN stack.

    CLI example to delete a stack::

        salt myminion boto_cfn.delete mystack region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
	log.error((("Failed to connect to amazon aws in region {0}").format(region)))
        return False
    if not exists(name):
	log.error((("Stack ID {0} did not exist and should have").format(name)))
        return False
    deleted_stack = conn.delete_stack(name)
    if not deleted_stack:
        msg = 'Failed to delete stack {0}'.format(name)
        log.error(msg)
        return False
    return True


def get_template(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if attributes are set on a CFN stack.

    CLI example::

        salt myminion boto_cfn.get_template mystack
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
	log.error((("Failed to connect to amazon aws in region {0}").format(region)))
        return {}
    try:
        template = conn.get_template(name)
    except boto.exception.BotoServerError as e:
        msg = 'Template {0} does not exist'.format(name)
        log.error(msg)
	log.debug(e)
        return {}
    log.info('Retrieved template for stack {0}'.format(name))
    return template


def _get_conn(region, key, keyid, profile):
    '''
    Get a boto connection to CFN.
    '''
    if profile:
        if isinstance(profile, string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and __salt__['config.option']('cfn.region'):
        region = __salt__['config.option']('cfn.region')

    if not region:
        region = 'us-east-1'

    if not key and __salt__['config.option']('cfn.key'):
        key = __salt__['config.option']('cfn.key')
    if not keyid and __salt__['config.option']('cfn.keyid'):
        keyid = __salt__['config.option']('cfn.keyid')

    try:
        conn = boto.cloudformation.connect_to_region(region, aws_access_key_id=keyid,
                                          aws_secret_access_key=key)
    except boto.exception.NoAuthHandlerFound:
        log.error('No authentication credentials found when attempting to'
                  ' make boto cfn connection.')
        return None
    return conn
