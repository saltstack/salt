# -*- coding: utf-8 -*-
'''
Module for handling OpenStack Swift calls
Author: Anthony Stanton <anthony.stanton@gmail.com>

Inspired by the S3 and Nova modules

:depends:   - swiftclient Python module
:configuration: This module is not usable until the user, password, tenant, and
    auth URL are specified either in a pillar or in the minion's config file.
    For example::

        keystone.user: admin
        keystone.password: verybadpass
        keystone.tenant: admin
        keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'
        # Optional
        keystone.region_name: 'regionOne'

    If configuration for multiple OpenStack accounts is required, they can be
    set up as different configuration profiles:
    For example::

        openstack1:
          keystone.user: admin
          keystone.password: verybadpass
          keystone.tenant: admin
          keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'

        openstack2:
          keystone.user: admin
          keystone.password: verybadpass
          keystone.tenant: admin
          keystone.auth_url: 'http://127.0.0.2:5000/v2.0/'

    With this configuration in place, any of the nova functions can make use of
    a configuration profile by declaring it explicitly.
    For example::

        salt '*' nova.flavor_list profile=openstack1
'''

# Import python libs
import logging

# Import salt libs
import salt.utils.openstack.swift as suos


# Get logging started
log = logging.getLogger(__name__)

# Function alias to not shadow built-ins
__func_alias__ = {
    'list_': 'list'
}


def __virtual__():
    '''
    Only load this module if swift
    is installed on this minion.
    '''
    if suos.check_swift():
        return 'swift'
    else:
        return False


__opts__ = {}


def _auth(profile=None):
    '''
    Set up openstack credentials
    '''
    if profile:
        credentials = __salt__['config.option'](profile)
        user = credentials['keystone.user']
        password = credentials['keystone.password']
        tenant = credentials['keystone.tenant']
        auth_url = credentials['keystone.auth_url']
        region_name = credentials.get('keystone.region_name', None)
        api_key = credentials.get('keystone.api_key', None)
        os_auth_system = credentials.get('keystone.os_auth_system', None)
    else:
        user = __salt__['config.option']('keystone.user')
        password = __salt__['config.option']('keystone.password')
        tenant = __salt__['config.option']('keystone.tenant')
        auth_url = __salt__['config.option']('keystone.auth_url')
        region_name = __salt__['config.option']('keystone.region_name')
        api_key = __salt__['config.option']('keystone.api_key')
        os_auth_system = __salt__['config.option']('keystone.os_auth_system')
    kwargs = {
        'user': user,
        'password': password,
        'api_key': api_key,
        'tenant_name': tenant,
        'auth_url': auth_url,
        'region_name': region_name
    }

    return suos.SaltSwift(**kwargs)

def delete(cont, path=None, profile=None):
    '''
    Delete a container, or delete an object from a container.

    CLI Example to delete a bucket::

        salt myminion swift.delete mycontainer

    CLI Example to delete an object from a bucket::

        salt myminion swift.delete mycontainer remoteobject
    '''
    swift_conn = _auth(profile)

    if path == None:
      return swift_conn.delete_container(cont)
    else:
      return swift_conn.delete_object(cont, path)

def get(cont=None, path=None, local_file=None, return_bin=False, profile=None):
    '''
    List the contents of a bucket, or return an object from a bucket. Set
    return_bin to True in order to retrieve an object wholesale. Otherwise,
    Salt will attempt to parse an XML response.

    CLI Example to list buckets:

    .. code-block:: bash

        salt myminion s3.get

    CLI Example to list the contents of a bucket:

    .. code-block:: bash

        salt myminion s3.get mybucket

    CLI Example to return the binary contents of an object:

    .. code-block:: bash

        salt myminion s3.get mybucket myfile.png return_bin=True

    CLI Example to save the binary contents of an object to a local file:

    .. code-block:: bash

        salt myminion s3.get mybucket myfile.png local_file=/tmp/myfile.png

    '''
    swift_conn = _auth(profile)

    if cont == None:
        return swift_conn.get_account()
        
    if path == None:
        return swift_conn.get_container(cont)

    if return_bin == True:
        return swift_conn.get_object(cont, path, return_bin)

    if local_file != None:
        return swift_conn.get_object(cont, path, local_file)

    return False

def head():
    pass

def put(cont, path=None, local_file=None, profile=None):
    '''
    Create a new bucket, or upload an object to a bucket.

    CLI Example to create a bucket:

    .. code-block:: bash

        salt myminion s3.put mybucket

    CLI Example to upload an object to a bucket:

    .. code-block:: bash

        salt myminion s3.put mybucket remotepath local_path=/path/to/file
    '''
    swift_conn = _auth(profile)

    if path == None:
        return swift_conn.put_container(cont)
    elif local_file != None:
        return swift_conn.put_object(cont, path, local_file)
    else:
        return False



#The following is a list of functions that need to be incorporated in the
#swift module. This list should be updated as functions are added.
#
#    delete               Delete a container or objects within a container.
#    download             Download objects from containers.
#    list                 Lists the containers for the account or the objects
#                         for a container.
#    post                 Updates meta information for the account, container,
#                         or object; creates containers if not present.
#    stat                 Displays information for the account, container,
#                         or object.
#    upload               Uploads files or directories to the given container
#    capabilities         List cluster capabilities.
