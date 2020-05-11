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
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
import salt.utils.data
import salt.config as config

# Import pyrax libraries
# This is typically against SaltStack coding styles,
# it should be 'import salt.utils.openstack.pyrax as suop'.  Something
# in the loader is creating a name clash and making that form fail
from salt.utils.openstack import pyrax as suop

__virtualname__ = 'pyrax'


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
        ('username', 'identity_url', 'compute_region',)
    )


def get_dependencies():
    '''
    Warn if dependencies aren't met.
    '''
    return config.check_driver_dependencies(
        __virtualname__,
        {'pyrax': suop.HAS_PYRAX}
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
    return salt.utils.data.simple_types_filter(conn.show(kwargs['name']).__dict__)


def queues_create(call, kwargs):
    conn = get_conn('RackspaceQueues')
    if conn.create(kwargs['name']):
        return salt.utils.data.simple_types_filter(conn.show(kwargs['name']).__dict__)
    else:
        return {}


def queues_delete(call, kwargs):
    conn = get_conn('RackspaceQueues')
    if conn.delete(kwargs['name']):
        return {}
    else:
        return salt.utils.data.simple_types_filter(conn.show(kwargs['name'].__dict__))
