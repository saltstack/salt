# -*- coding: utf-8 -*-
'''
Pyrax Cloud Module
==================

PLEASE NOTE: This module is currently in early development, and considered to
be experimental and unstable. It is not recommended for production use. Unless
you are actively developing code in this module, you should use the OpenStack
module instead.
'''

# Import Python Libs
from __future__ import absolute_import

# Import salt libs
import salt.utils
import salt.config as config
import salt.utils.boto3
import salt.utils.compat
import salt.utils.odict as odict


import yaml
import salt.ext.six as six
try:
    import boto3  # pylint: disable=unused-import
    from botocore.exceptions import ClientError
    logging.getLogger('boto3').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False



__virtualname__ = 'lightsail'


# Only load in this module is the PYRAX configurations are in place
def __virtual__():
    '''
    Check for Pyrax configurations
    '''
    if get_configured_provider() is False:
        return False

    if get_dependencies() is False:
        return False

    return __virtualname__

def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ('id', 'key')
    )


def get_dependencies():
    '''
    Warn if dependencies aren't met.
    '''
    return config.check_driver_dependencies(
        __virtualname__,
        {'boto3': HAS_BOTO}
    )



def queues_exists(call, kwargs):
    conn = salt.utils.boto3.get_connection('lightsail', 'lightsail')
    return conn.exists(kwargs['name'])


def queues_show(call, kwargs):
    conn = salt.utils.boto3.get_connection('lightsail', 'lightsail')
    return salt.utils.simple_types_filter(conn.show(kwargs['name']).__dict__)


def queues_create(call, kwargs):
    conn = salt.utils.boto3.get_connection('lightsail', 'lightsail')
    if conn.create(kwargs['name']):
        return salt.utils.simple_types_filter(conn.show(kwargs['name']).__dict__)
    else:
        return {}


def queues_delete(call, kwargs):
    conn = salt.utils.boto3.get_connection('lightsail', 'lightsail')
    if conn.delete(kwargs['name']):
        return {}
    else:
        return salt.utils.simple_types_filter(conn.show(kwargs['name'].__dict__))
