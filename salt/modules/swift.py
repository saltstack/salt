# -*- coding: utf-8 -*-
"""
Module for handling OpenStack Swift calls
Author: Anthony Stanton <anthony.stanton@gmail.com>

Inspired by the S3 and Nova modules

:depends:   - swiftclient Python module
:configuration: This module is not usable until the user, tenant, auth URL, and password or auth_key
    are specified either in a pillar or in the minion's config file.
    For example::

        keystone.user: admin
        keystone.tenant: admin
        keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'
        keystone.password: verybadpass
        # or
        keystone.auth_key: 203802934809284k2j34lkj2l3kj43k

    If configuration for multiple OpenStack accounts is required, they can be
    set up as different configuration profiles:
    For example::

        openstack1:
          keystone.user: admin
          keystone.tenant: admin
          keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'
          keystone.password: verybadpass
          # or
          keystone.auth_key: 203802934809284k2j34lkj2l3kj43k

        openstack2:
          keystone.user: admin
          keystone.tenant: admin
          keystone.auth_url: 'http://127.0.0.2:5000/v2.0/'
          keystone.password: verybadpass
          # or
          keystone.auth_key: 303802934809284k2j34lkj2l3kj43k

    With this configuration in place, any of the swift functions can make use of
    a configuration profile by declaring it explicitly.
    For example::

        salt '*' swift.get mycontainer myfile /tmp/file profile=openstack1

    NOTE: For Rackspace cloud files setting keystone.auth_version = 1 is recommended.
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

# Import salt libs
import salt.utils.openstack.swift as suos

# Get logging started
log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load this module if swift
    is installed on this minion.
    """
    return suos.check_swift()


__opts__ = {}


def _auth(profile=None):
    """
    Set up openstack credentials
    """
    if profile:
        credentials = __salt__["config.option"](profile)
        user = credentials["keystone.user"]
        password = credentials.get("keystone.password", None)
        tenant = credentials["keystone.tenant"]
        auth_url = credentials["keystone.auth_url"]
        auth_version = credentials.get("keystone.auth_version", 2)
        region_name = credentials.get("keystone.region_name", None)
        api_key = credentials.get("keystone.api_key", None)
        os_auth_system = credentials.get("keystone.os_auth_system", None)
    else:
        user = __salt__["config.option"]("keystone.user")
        password = __salt__["config.option"]("keystone.password", None)
        tenant = __salt__["config.option"]("keystone.tenant")
        auth_url = __salt__["config.option"]("keystone.auth_url")
        auth_version = __salt__["config.option"]("keystone.auth_version", 2)
        region_name = __salt__["config.option"]("keystone.region_name")
        api_key = __salt__["config.option"]("keystone.api_key")
        os_auth_system = __salt__["config.option"]("keystone.os_auth_system")
    kwargs = {
        "user": user,
        "password": password,
        "key": api_key,
        "tenant_name": tenant,
        "auth_url": auth_url,
        "auth_version": auth_version,
        "region_name": region_name,
    }

    return suos.SaltSwift(**kwargs)


def delete(cont, path=None, profile=None):
    """
    Delete a container, or delete an object from a container.

    CLI Example to delete a container::

        salt myminion swift.delete mycontainer

    CLI Example to delete an object from a container::

        salt myminion swift.delete mycontainer remoteobject
    """
    swift_conn = _auth(profile)

    if path is None:
        return swift_conn.delete_container(cont)
    else:
        return swift_conn.delete_object(cont, path)


def get(cont=None, path=None, local_file=None, return_bin=False, profile=None):
    """
    List the contents of a container, or return an object from a container. Set
    return_bin to True in order to retrieve an object wholesale. Otherwise,
    Salt will attempt to parse an XML response.

    CLI Example to list containers:

    .. code-block:: bash

        salt myminion swift.get

    CLI Example to list the contents of a container:

    .. code-block:: bash

        salt myminion swift.get mycontainer

    CLI Example to return the binary contents of an object:

    .. code-block:: bash

        salt myminion swift.get mycontainer myfile.png return_bin=True

    CLI Example to save the binary contents of an object to a local file:

    .. code-block:: bash

        salt myminion swift.get mycontainer myfile.png local_file=/tmp/myfile.png

    """
    swift_conn = _auth(profile)

    if cont is None:
        return swift_conn.get_account()

    if path is None:
        return swift_conn.get_container(cont)

    if return_bin is True:
        return swift_conn.get_object(cont, path, return_bin)

    if local_file is not None:
        return swift_conn.get_object(cont, path, local_file)

    return False


def head():
    pass


def put(cont, path=None, local_file=None, profile=None):
    """
    Create a new container, or upload an object to a container.

    CLI Example to create a container:

    .. code-block:: bash

        salt myminion swift.put mycontainer

    CLI Example to upload an object to a container:

    .. code-block:: bash

        salt myminion swift.put mycontainer remotepath local_file=/path/to/file
    """
    swift_conn = _auth(profile)

    if path is None:
        return swift_conn.put_container(cont)
    elif local_file is not None:
        return swift_conn.put_object(cont, path, local_file)
    else:
        return False
