# -*- coding: utf-8 -*-
'''
The Salt Cloud Runner
=====================

This runner wraps the functionality of salt cloud making salt cloud routines
available to all internal apis via the runner system
'''

# Import python libs
import os

# Import Salt libs
import salt.cloud


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


def profile(prof, names, **kwargs):
    '''
    Create a cloud vm with the given profile and names, names can be a list
    or comma delimited string
    '''
    client = _get_client()
    info = client.profile(prof, names, **kwargs)
    return info


def destroy(names):
    '''
    Destroy the named vm(s)
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
    Execute a single action on the given map/provider/instance
    '''
    client = _get_client()
    info = client.action(fun, cloudmap, names, provider, instance, kwargs)
    return info
