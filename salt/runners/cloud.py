# -*- coding: utf-8 -*-
'''
The Salt Cloud Runner
=====================

This runner wraps the functionality of salt cloud making salt cloud routines
available to all internal apis via the runner system
'''
from __future__ import absolute_import

# Import python libs
import logging
import os

# Import Salt libs
import salt.cloud
from salt.exceptions import SaltCloudConfigError

# Get logging started
log = logging.getLogger(__name__)


def _filter_kwargs(k):
    return dict((x, k[x]) for x in k if not x.startswith('__'))


def _get_client():
    '''
    Return cloud client
    '''
    client = salt.cloud.CloudClient(
            os.path.join(os.path.dirname(__opts__['conf_file']), 'cloud')
            )
    return client


def list_sizes(provider='all'):
    '''
    List cloud provider sizes for the given providers
    '''
    client = _get_client()
    sizes = client.list_sizes(provider)
    return sizes


def list_images(provider='all'):
    '''
    List cloud provider images for the given providers
    '''
    client = _get_client()
    images = client.list_images(provider)
    return images


def list_locations(provider='all'):
    '''
    List cloud provider sizes for the given providers
    '''
    client = _get_client()
    locations = client.list_locations(provider)
    return locations


def query(query_type='list_nodes'):
    '''
    List cloud provider data for all providers
    '''
    client = _get_client()
    info = client.query(query_type)
    return info


def full_query(query_type='list_nodes_full'):
    '''
    List all available cloud provider data
    '''
    client = _get_client()
    info = client.full_query(query_type)
    return info


def select_query(query_type='list_nodes_select'):
    '''
    List selected nodes
    '''
    client = _get_client()
    info = client.select_query(query_type)
    return info


def profile(prof=None, instances=None, opts=None, **kwargs):
    '''
    Create a cloud vm with the given profile and instances, instances can be a
    list or comma-delimited string

    CLI Example:

    .. code-block:: bash

        salt-run cloud.profile prof=my-ec2 instances=node1,node2,node3
    '''
    if prof is None and 'profile' in kwargs:
        prof = kwargs['profile']

    if prof is None:
        return {'Error': 'A profile (or prof) must be defined'}

    if instances is None and 'names' in kwargs:
        instances = kwargs['names']

    if instances is None:
        return {'Error': 'One or more instances (comma-delimited) must be set'}

    client = _get_client()
    if isinstance(opts, dict):
        client.opts.update(opts)
    info = client.profile(prof, instances, **_filter_kwargs(kwargs))
    return info


def map_run(path=None, **kwargs):
    '''
    Execute a salt cloud map file
    '''
    client = _get_client()
    info = client.map_run(path, **_filter_kwargs(kwargs))
    return info


def destroy(instances):
    '''
    Destroy the named vm(s)
    '''
    client = _get_client()
    info = client.destroy(instances)
    return info


def action(func=None,
           cloudmap=None,
           instances=None,
           provider=None,
           instance=None,
           **kwargs):
    '''
    Execute a single action on the given map/provider/instance

    CLI Example:

    .. code-block:: bash

        salt-run cloud.action start my-salt-vm
    '''
    info = {}
    client = _get_client()
    try:
        info = client.action(func, cloudmap, instances, provider, instance, **_filter_kwargs(kwargs))
    except SaltCloudConfigError as err:
        log.error(err)
    return info


def create(provider, instances, opts=None, **kwargs):
    '''
    Create an instance using Salt Cloud

    CLI Example:

    .. code-block:: bash

        salt-run cloud.create my-ec2-config myinstance \
            image=ami-1624987f size='t1.micro' ssh_username=ec2-user \
            securitygroup=default delvol_on_destroy=True
    '''
    create_kwargs = {}
    for kwarg in kwargs:
        if not kwarg.startswith('__'):
            create_kwargs[kwarg] = kwargs[kwarg]
    client = _get_client()
    if isinstance(opts, dict):
        client.opts.update(opts)
    info = client.create(provider, instances, **create_kwargs)
    return info
