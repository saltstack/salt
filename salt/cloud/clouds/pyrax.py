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

from __future__ import absolute_import

# Import salt libs
import salt.utils.cloud
import salt.config as config

# Import pyrax libraries
# This is typically against SaltStack coding styles,
# it should be 'import salt.utils.openstack.pyrax as suop'.  Something
# in the loader is creating a name clash and making that form fail
from salt.utils.openstack import pyrax as suop


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


def queues_show(call, kwargs):
    conn = get_conn('RackspaceQueues')
    return salt.utils.cloud.simple_types_filter(conn.show(kwargs['name']).__dict__)


def queues_create(call, kwargs):
    conn = get_conn('RackspaceQueues')
    if conn.create(kwargs['name']):
        return salt.utils.cloud.simple_types_filter(conn.show(kwargs['name']).__dict__)
    else:
        return {}


def queues_delete(call, kwargs):
    conn = get_conn('RackspaceQueues')
    if conn.delete(kwargs['name']):
        return {}
    else:
        return salt.utils.cloud.simple_types_filter(conn.show(kwargs['name'].__dict__))
