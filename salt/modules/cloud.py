# -*- coding: utf-8 -*-
'''
Salt-specific interface for calling Salt Cloud directly
'''

# Import python libs
from __future__ import absolute_import
import os
import logging
import copy

# Import salt libs
try:
    import salt.cloud
    HAS_SALTCLOUD = True
except ImportError:
    HAS_SALTCLOUD = False

import salt.utils

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)

__func_alias__ = {
    'profile_': 'profile'
}


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    if HAS_SALTCLOUD:
        return True
    return False


def _get_client():
    '''
    Return a cloud client
    '''
    client = salt.cloud.CloudClient(
        os.path.join(os.path.dirname(__opts__['conf_file']), 'cloud'),
        pillars=copy.deepcopy(__pillar__.get('cloud', {}))
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
    return query(query_type=query_type)


def select_query(query_type='list_nodes_select'):
    '''
    List selected nodes

    CLI Example:

    .. code-block:: bash

        salt '*' cloud.select_query
    '''
    return query(query_type=query_type)


def has_instance(name, provider=None):
    '''
    Return true if the instance is found on a provider

    CLI Example:

    .. code-block:: bash

        salt '*' cloud.has_instance myinstance
    '''
    data = get_instance(name, provider)
    if data is None:
        return False
    return True


def get_instance(name, provider=None):
    '''
    Return details on an instance.

    Similar to the cloud action show_instance
    but returns only the instance details.

    CLI Example:

    .. code-block:: bash

        salt '*' cloud.get_instance myinstance

    SLS Example:

    .. code-block:: bash

        {{ salt['cloud.get_instance']('myinstance')['mac_address'] }}

    '''
    data = action(fun='show_instance', names=[name], provider=provider)
    info = salt.utils.cloud.simple_types_filter(data)
    try:
        # get the first: [alias][driver][vm_name]
        info = next(six.itervalues(next(six.itervalues(next(six.itervalues(info))))))
    except AttributeError:
        return None
    return info


def profile_(profile, names, vm_overrides=None, **kwargs):
    '''
    Spin up an instance using Salt Cloud

    CLI Example:

    .. code-block:: bash

        salt '*' cloud.profile my-gce-config myinstance
    '''
    client = _get_client()
    info = client.profile(profile, names, vm_overrides=vm_overrides, **kwargs)
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
        salt '*' cloud.action show_image provider=my-ec2-config image=ami-1624987f
    '''
    client = _get_client()
    info = client.action(fun, cloudmap, names, provider, instance, kwargs)
    return info


def create(provider, names, **kwargs):
    '''
    Create an instance using Salt Cloud

    CLI Example:

    .. code-block:: bash

        salt minionname cloud.create my-ec2-config myinstance image=ami-1624987f size='t1.micro' ssh_username=ec2-user securitygroup=default delvol_on_destroy=True
    '''
    client = _get_client()
    info = client.create(provider, names, **kwargs)
    return info


def volume_list(provider):
    '''
    List block storage volumes

    CLI Example:

    .. code-block:: bash

        salt minionname cloud.volume_list my-nova

    '''
    client = _get_client()
    info = client.extra_action(action='volume_list', provider=provider, names='name')
    return info['name']


def volume_delete(provider, names, **kwargs):
    '''
    Delete volume

    CLI Example:

    .. code-block:: bash

        salt minionname cloud.volume_delete my-nova myblock

    '''
    client = _get_client()
    info = client.extra_action(provider=provider, names=names, action='volume_delete', **kwargs)
    return info


def volume_create(provider, names, **kwargs):
    '''
    Create volume

    CLI Example:

    .. code-block:: bash

        salt minionname cloud.volume_create my-nova myblock size=100 voltype=SSD

    '''
    client = _get_client()
    info = client.extra_action(action='volume_create', names=names, provider=provider, **kwargs)
    return info


def volume_attach(provider, names, **kwargs):
    '''
    Attach volume to a server

    CLI Example:

    .. code-block:: bash

        salt minionname cloud.volume_attach my-nova myblock server_name=myserver device='/dev/xvdf'

    '''
    client = _get_client()
    info = client.extra_action(provider=provider, names=names, action='volume_attach', **kwargs)
    return info


def volume_detach(provider, names, **kwargs):
    '''
    Detach volume from a server

    CLI Example:

    .. code-block:: bash

        salt minionname cloud.volume_detach my-nova myblock server_name=myserver

    '''
    client = _get_client()
    info = client.extra_action(provider=provider, names=names, action='volume_detach', **kwargs)
    return info


def network_list(provider):
    '''
    List private networks

    CLI Example:

    .. code-block:: bash

        salt minionname cloud.network_list my-nova

    '''
    client = _get_client()
    return client.extra_action(action='network_list', provider=provider, names='names')


def network_create(provider, names, **kwargs):
    '''
    Create private network

    CLI Example:

    .. code-block:: bash

        salt minionname cloud.network_create my-nova names=['salt'] cidr='192.168.100.0/24'

    '''
    client = _get_client()
    return client.extra_action(provider=provider, names=names, action='network_create', **kwargs)


def virtual_interface_list(provider, names, **kwargs):
    '''
    List virtual interfaces on a server

    CLI Example:

    .. code-block:: bash

        salt minionname cloud.virtual_interface_list my-nova names=['salt-master']

    '''
    client = _get_client()
    return client.extra_action(provider=provider, names=names, action='virtual_interface_list', **kwargs)


def virtual_interface_create(provider, names, **kwargs):
    '''
    Attach private interfaces to a server

    CLI Example:

    .. code-block:: bash

        salt minionname cloud.virtual_interface_create my-nova names=['salt-master'] net_name='salt'

    '''
    client = _get_client()
    return client.extra_action(provider=provider, names=names, action='virtual_interface_create', **kwargs)
