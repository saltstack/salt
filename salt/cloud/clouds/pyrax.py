# -*- coding: utf-8 -*-
'''
Pyrax Cloud Module
===========================

PLEASE NOTE: This module is currently in early development, and considered to
be experimental and unstable. It is not recommended for production use. Unless
you are actively developing code in this module, you should use the OpenStack
module instead.
'''
# pylint: disable=E0102

# The import section is mostly libcloud boilerplate

# Import python libs
import os
import logging
import socket
import pprint

# Import generic libcloud functions
from salt.cloud.libcloudfuncs import *   # pylint: disable=W0614,W0401
import salt.utils.openstack.pyrax as suop

import salt.utils.cloud

# Import salt libs
import salt.utils
import salt.client

# Import salt.cloud libs
import salt.config as config
from salt.utils import namespaced_function
from salt.exceptions import (
    SaltCloudConfigError,
    SaltCloudNotFound,
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout
)

# Get logging started
log = logging.getLogger(__name__)

# namespace libcloudfuncs
get_salt_interface = namespaced_function(get_salt_interface, globals())


# Some of the libcloud functions need to be in the same namespace as the
# functions defined in the module, so we create new function objects inside
# this module namespace
script = namespaced_function(script, globals())
reboot = namespaced_function(reboot, globals())


# Only load in this module is the OPENSTACK configurations are in place
def __virtual__():
    '''
    Check for Nova configurations
    '''
    return suop.HAS_PYRAX


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'pyrax'
    )


def get_conn(conn_type):
    '''
    Return a conn object for the passed VM data
    '''
    vm_ = get_configured_provider()

    kwargs = vm_.copy()  # pylint: disable=E1103

    kwargs['username'] = vm_['username']
    kwargs['auth_endpoint'] = vm_.get('identity_url', None)
    kwargs['region'] = vm_['compute_region']

    conn = getattr(suop, conn_type)

    return conn(**kwargs)

def queues_exists(call, kwargs):
    conn = get_conn('RackspaceQueues')
    return conn.exists(kwargs['name'])

def queues_create(call, kwargs):
    conn = get_conn('RackspaceQueues')
    if conn.create(kwargs['name']):
        return conn.exists(kwargs['name']).__dict__
    else:
        return {}

def queues_delete(call, kwargs):
    conn = get_conn('RackspaceQueues')
    ret = conn.exists(kwargs['name']).__dict__
    if conn.delete(kwargs['name']):
        return {}
    else:
        return ret
