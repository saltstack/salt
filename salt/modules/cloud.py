# -*- coding: utf-8 -*-
'''
Salt-specific interface for calling Salt Cloud directly
'''

# Import python libs
import os
import logging

# Import salt libs
import salt.cloud
import salt.utils

log = logging.getLogger(__name__)

__func_alias__ = {
    'profile_': 'profile'
}


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    if salt.utils.is_windows():
        return False
    return True


def _get_client():
    '''
    Return a cloud client
    '''
    client = salt.cloud.CloudClient(
            os.path.join(os.path.dirname(__opts__['conf_file']), 'cloud')
            )
    return client


def list_sizes(provider='all'):
    '''
    List cloud provider sizes for the given providers

    CLI Example:

    .. code-block:: bash

        salt '*' cloud.list_sizes my-gce-config
    '''
    client = _get_client()
    sizes = client.list_sizes(provider)
    return sizes


def list_images(provider='all'):
    '''
    List cloud provider images for the given providers

    CLI Example:

    .. code-block:: bash

        salt '*' cloud.list_images my-gce-config
    '''
    client = _get_client()
    images = client.list_images(provider)
    return images


def list_locations(provider='all'):
    '''
    List cloud provider locations for the given providers

    CLI Example:

    .. code-block:: bash

        salt '*' cloud.list_locations my-gce-config
    '''
    client = _get_client()
    locations = client.list_locations(provider)
    return locations


def query(query_type='list_nodes'):
    '''
    List cloud provider data for all providers

    CLI Examples:

    .. code-block:: bash

        salt '*' cloud.query
        salt '*' cloud.query list_nodes_full
        salt '*' cloud.query list_nodes_select
    '''
    client = _get_client()
    info = client.query(query_type)
    return info


def full_query(query_type='list_nodes_full'):
    '''
    List all available cloud provider data

    CLI Example:

    .. code-block:: bash

        salt '*' cloud.full_query
    '''
    return query(query_type='list_nodes_full')


def select_query(query_type='list_nodes_select'):
    '''
    List selected nodes

    CLI Example:

    .. code-block:: bash

        salt '*' cloud.select_query
    '''
    return query(query_type='list_nodes_select')


def profile_(profile, names, **kwargs):
    '''
    Spin up an instance using Salt Cloud

    CLI Example:

    .. code-block:: bash

        salt '*' cloud.profile my-gce-config myinstance
    '''
    client = _get_client()
    info = client.profile(profile, names, **kwargs)
    return info


def destroy(names):
    '''
    Destroy the named VM(s)

    CLI Example:

    .. code-block:: bash

        salt '*' cloud.destroy myinstance
    '''
    client = _get_client()
    info = client.destroy(names)
    return info


def action(
        fun=None,
        cloudmap=None,
        names=None,
        provider=None,
        instance=None,
        **kwargs):
    '''
    Execute a single action on the given provider/instance

    CLI Example:

    .. code-block:: bash

        salt '*' cloud.action start instance=myinstance
        salt '*' cloud.action stop instance=myinstance
        salt '*' cloud.action show_image provider=my-ec2-config \
            image=ami-1624987f
    '''
    client = _get_client()
    info = client.action(fun, cloudmap, names, provider, instance, kwargs)
    return info


def create(provider, names, **kwargs):
    '''
    Create an instance using Salt Cloud

    CLI Example:

    .. code-block:: bash

        salt minionname cloud.create my-ec2-config myinstance \
            image=ami-1624987f size='Micro Instance' ssh_username=ec2-user \
            securitygroup=default delvol_on_destroy=True
    '''
    client = _get_client()
    info = client.create(provider, names, **kwargs)
    return info
