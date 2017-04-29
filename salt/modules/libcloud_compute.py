# -*- coding: utf-8 -*-
'''
Apache Libcloud Compute Management
==================================

Connection module for Apache Libcloud Compute management for a full list
of supported clouds, see http://libcloud.readthedocs.io/en/latest/compute/supported_providers.html

Clouds include Amazon EC2, Azure, Google GCE, VMware, OpenStack Nova

.. versionadded:: Oxygen

:configuration:
    This module uses a configuration profile for one or multiple cloud providers

    .. code-block:: yaml

        libcloud_compute:
            profile_test1:
              driver: google
              key: service-account@googlecloud.net
              secret: /path/to.key.json
            profile_test2:
              driver: arm
              key: 12345
              secret: mysecret

:depends: apache-libcloud
'''
# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602

from __future__ import absolute_import

# Import Python libs
import logging

# Import salt libs
import salt.utils.compat
import salt.ext.six as six
from salt.utils import clean_kwargs
from salt.utils.versions import LooseVersion as _LooseVersion

log = logging.getLogger(__name__)

# Import third party libs
REQUIRED_LIBCLOUD_VERSION = '2.0.0'
try:
    #pylint: disable=unused-import
    import libcloud
    from libcloud.compute.providers import get_driver
    from libcloud.compute.base import Node
    #pylint: enable=unused-import
    if hasattr(libcloud, '__version__') and _LooseVersion(libcloud.__version__) < _LooseVersion(REQUIRED_LIBCLOUD_VERSION):
        raise ImportError()
    logging.getLogger('libcloud').setLevel(logging.CRITICAL)
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False


def __virtual__():
    '''
    Only load if libcloud libraries exist.
    '''
    if not HAS_LIBCLOUD:
        msg = ('A apache-libcloud library with version at least {0} was not '
               'found').format(REQUIRED_LIBCLOUD_VERSION)
        return (False, msg)
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)


def _get_driver(profile):
    config = __salt__['config.option']('libcloud_compute')[profile]
    cls = get_driver(config['driver'])
    args = config.copy()
    del args['driver']
    args['key'] = config.get('key')
    args['secret'] = config.get('secret', None)
    if args['secret'] is None:
        del args['secret']
    args['secure'] = config.get('secure', True)
    args['host'] = config.get('host', None)
    args['port'] = config.get('port', None)
    return cls(**args)


def list_nodes(profile, **libcloud_kwargs):
    '''
    Return a list of nodes

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_nodes method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.list_nodes profile1
    '''
    conn = _get_driver(profile=profile)
    libcloud_kwargs = clean_kwargs(**libcloud_kwargs)
    nodes = conn.list_nodes(**libcloud_kwargs)
    ret = []
    for node in nodes:
        ret.append(_simple_node(node))
    return ret


def list_sizes(profile, location_id=None, **libcloud_kwargs):
    '''
    Return a list of node sizes

    :param profile: The profile key
    :type  profile: ``str``

    :param location_id: The location key, from list_locations
    :type  location_id: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_sizes method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.list_sizes profile1
        salt myminion libcloud_compute.list_sizes profile1 us-east1
    '''
    conn = _get_driver(profile=profile)
    libcloud_kwargs = clean_kwargs(**libcloud_kwargs)
    if location_id is not None:
        locations = [loc for loc in conn.list_locations() if loc.id == location_id]
        if len(locations) == 0:
            raise ValueError("Location not found")
        else:
            sizes = conn.list_sizes(location=locations[0], **libcloud_kwargs)
    else:
        sizes = conn.list_sizes(**libcloud_kwargs)
    
    ret = []
    for size in sizes:
        ret.append(_simple_size(size))
    return ret


def list_locations(profile, **libcloud_kwargs):
    '''
    Return a list of locations for this cloud

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_locations method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.list_locations profile1
    '''
    conn = _get_driver(profile=profile)
    libcloud_kwargs = clean_kwargs(**libcloud_kwargs)
    locations = conn.list_locations(**libcloud_kwargs)
    
    ret = []
    for loc in locations:
        ret.append(_simple_location(loc))
    return ret


def reboot_node(node_id, profile, **libcloud_kwargs):
    '''
    Reboot a node in the cloud

    :param node_id: Unique ID of the node to reboot
    :type  node_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's reboot_node method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.reboot_node as-2346 profile1
    '''
    conn = _get_driver(profile=profile)
    matches = [node for node in conn.list_nodes(**libcloud_kwargs) if node.id == node_id]
    if len(matches) == 0:
        raise ValueError('Could not find a matching node')
    elif len(matches) > 1:
        raise ValueError('The node_id matched {0} nodes, not 1'.format(len(matches)))
    return conn.reboot_node(matches[0], **libcloud_kwargs)


def destroy_node(node_id, profile, **libcloud_kwargs):
    '''
    Destroy a node in the cloud

    :param node_id: Unique ID of the node to destory
    :type  node_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's destroy_node method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.destry_node as-2346 profile1
    '''
    conn = _get_driver(profile=profile)
    matches = [node for node in conn.list_nodes(**libcloud_kwargs) if node.id == node_id]
    if len(matches) == 0:
        raise ValueError('Could not find a matching node')
    elif len(matches) > 1:
        raise ValueError('The node_id matched {0} nodes, not 1'.format(len(matches)))
    return conn.destroy_node(matches[0], **libcloud_kwargs)


def list_volumes(profile, **libcloud_kwargs):
    '''
    Return a list of storage volumes for this cloud

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_volumes method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.list_volumes profile1
    '''
    conn = _get_driver(profile=profile)
    libcloud_kwargs = clean_kwargs(**libcloud_kwargs)
    volumes = conn.list_volumes(**libcloud_kwargs)
    
    ret = []
    for volume in volumes:
        ret.append(_simple_volume(volume))
    return ret

'''
Remaining functions to implement:

    def create_node(self, **kwargs):
    def deploy_node(self, **kwargs):
    def list_volume_snapshots(self, volume):
    def create_volume(self, size, name, location=None, snapshot=None):
    def create_volume_snapshot(self, volume, name=None):
    def attach_volume(self, node, volume, device=None):
    def detach_volume(self, volume):
    def destroy_volume(self, volume):
    def destroy_volume_snapshot(self, snapshot):
    def list_images(self, location=None):
    def create_image(self, node, name, description=None):
    def delete_image(self, node_image):
    def get_image(self, image_id):
    def copy_image(self, source_region, node_image, name, description=None):
    def list_key_pairs(self):
    def get_key_pair(self, name):
    def create_key_pair(self, name):
    def import_key_pair_from_string(self, name, key_material):
    def import_key_pair_from_file(self, name, key_file_path):
    def delete_key_pair(self, key_pair):
'''

def _simple_volume(volume):
    return {
        'id': volume.id,
        'name': volume.name,
        'size': volume.size,
        'state': volume.state,
        'extra': volume.extra
    }


def _simple_location(location):
    return {
        'id': location.id,
        'name': location.name,
        'country': location.country
    }


def _simple_size(size):
    return {
        'id': size.id,
        'name': size.name,
        'ram': size.ram,
        'disk': size.disk,
        'bandwidth': size.bandwidth,
        'price': size.price,
        'extra': size.extra
    }


def _simple_node(node):
    return {
        'id': node.id,
        'name': node.name,
        'state': str(node.state),
        'public_ips': node.public_ips,
        'private_ips': node.private_ips,
        'size': _simple_size(node.size) if node.size else {},
        'extra': node.extra
    }
