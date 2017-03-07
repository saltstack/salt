# -*- coding: utf-8 -*-
'''
Packet Cloud Module Using Packet's Python API Client
===========================================

The Packet cloud module is used to control access to the Packet VPS system.

Use of this module only requires the ``token`` parameter.

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/packet.conf``:

The Packet profile requires ``size``, ``image``, ``location``,  ``project_id``

Optional profile parameters:

 - ``storage_size`` -  min value is 10, defines Gigabytes of storage that will be attached to device.
 - ``storage_tier`` - storage_1 - Standard Plan, storage_2 - Performance Plan
 - ``snapshot_count`` - int
 - ``snapshot_frequency`` - string - possible values:
    - 1min
    - 15min
    - 1hour
    - 1day
    - 1week
    - 1month
    - 1year

This driver requires Packet's client library: https://pypi.python.org/pypi/packet-python

.. code-block:: yaml

    packet-provider:
        minion:
            master: 192.168.50.10
        driver: packet
        token: ewr23rdf35wC8oNjJrhmHa87rjSXzJyi
        private_key: /root/.ssh/id_rsa

    packet-profile:
        provider: packet-provider
        size: baremetal_0
        image: ubuntu_16_04_image
        location: ewr1
        project_id: a64d000b-d47c-4d26-9870-46aac43010a6
        storage_size: 10
        storage_tier: storage_1
        storage_snapshot_count: 1
        storage_snapshot_frequency: 15min
'''

# Import Python Libs
from __future__ import absolute_import
import logging
import pprint
import time

# Import 3rd-party libs
try:
    import packet
    HAS_PACKET = True
except ImportError:
    HAS_PACKET = False

# Import Salt Libs
import salt.config as config

from salt.ext.six.moves import range

from salt.exceptions import (
    SaltCloudException,
    SaltCloudSystemExit
)

# Import Salt-Cloud Libs
import salt.utils.cloud

from salt.cloud.libcloudfuncs import get_size, get_image, script, show_instance
from salt.utils import namespaced_function

get_size = namespaced_function(get_size, globals())
get_image = namespaced_function(get_image, globals())

script = namespaced_function(script, globals())

show_instance = namespaced_function(show_instance, globals())

# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = 'packet'


# Only load this module if the Packet configuration is in place.
def __virtual__():
    '''
    Check for Packet configs.
    '''
    if HAS_PACKET is False:
        return False, 'The packet python library is not installed'
    if get_configured_provider() is False:
        return False

    return __virtualname__


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ('token',)
    )


def avail_images(call=None):
    '''
    Return available Packet os images.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-images packet-provider
        salt-cloud -f avail_images packet-provider
    '''
    if call == 'action':
        raise SaltCloudException(
            'The avail_images function must be called with -f or --function.'
        )

    ret = {}

    vm_ = get_configured_provider()
    manager = packet.Manager(auth_token=vm_['token'])

    ret = {}

    for os_system in manager.list_operating_systems():
        ret[os_system.name] = os_system.__dict__

    return ret


def avail_locations(call=None):
    '''
    Return available Packet datacenter locations.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-locations packet-provider
        salt-cloud -f avail_locations packet-provider
    '''
    if call == 'action':
        raise SaltCloudException(
            'The avail_locations function must be called with -f or --function.'
        )

    vm_ = get_configured_provider()
    manager = packet.Manager(auth_token=vm_['token'])

    ret = {}

    for facility in manager.list_facilities():
        ret[facility.name] = facility.__dict__

    return ret


def avail_sizes(call=None):
    '''
    Return available Packet sizes.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-sizes packet-provider
        salt-cloud -f avail_sizes packet-provider
    '''
    if call == 'action':
        raise SaltCloudException(
            'The avail_locations function must be called with -f or --function.'
        )

    vm_ = get_configured_provider()

    manager = packet.Manager(auth_token=vm_['token'])

    ret = {}

    for plan in manager.list_plans():
        ret[plan.name] = plan.__dict__

    return ret


def avail_projects(call=None):
    '''
    Return available Packet projects.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f avail_projects packet-provider
    '''
    if call == 'action':
        raise SaltCloudException(
            'The avail_projects function must be called with -f or --function.'
        )

    vm_ = get_configured_provider()
    manager = packet.Manager(auth_token=vm_['token'])

    ret = {}

    for project in manager.list_projects():
        ret[project.name] = project.__dict__

    return ret


def _wait_for_status(status_type, object_id, status=None, timeout=500, quiet=True):
    '''
    Wait for a certain status from Packet.
    status_type
        device or volume
    object_id
        The ID of the Packet device or volume to wait on. Required.
    status
        The status to wait for.
    timeout
        The amount of time to wait for a status to update.
    quiet
        Log status updates to debug logs when False. Otherwise, logs to info.
    '''
    if status is None:
        status = "ok"

    interval = 5
    iterations = int(timeout / interval)

    vm_ = get_configured_provider()
    manager = packet.Manager(auth_token=vm_['token'])

    for i in range(0, iterations):
        get_object = getattr(manager, "get_{status_type}".format(status_type=status_type))
        obj = get_object(object_id)

        if obj.state == status:
            return obj

        time.sleep(interval)
        if quiet:
            log.info('Status for Packet {0} is \'{1}\', waiting for \'{2}\'.'.format(
                object_id,
                obj.state,
                status)
            )
        else:
            log.debug('Status for Packet {0} is \'{1}\', waiting for \'{2}\'.'.format(
                object_id,
                obj.state,
                status)
            )

    return obj


def is_profile_configured(vm_):
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or __virtualname__,
                                                           vm_['profile'],
                                                           vm_=vm_) is False:
            return False

        alias, driver = __active_provider_name__.split(':')

        profile_data = __opts__['providers'][alias][driver]['profiles'][vm_['profile']]

        if profile_data.get('storage_size') or profile_data.get('storage_tier'):
            required_keys = ['storage_size', 'storage_tier']

            for key in required_keys:
                if profile_data.get(key) is None:
                    log.error(
                        'both storage_size and storage_tier required for profile {profile}. '
                        'Please check your profile configuration'.format(profile=vm_['profile'])
                    )
                    return False

            locations = avail_locations()

            for location in locations.values():
                if location['code'] == profile_data['location']:
                    if 'storage' not in location['features']:
                        log.error(
                            'Choosen location {location} for profile {profile} does not support storage feature. '
                            'Please check your profile configuration'.format(
                                location=location['code'], profile=vm_['profile']
                            )
                        )
                        return False

        if profile_data.get('storage_snapshot_count') or profile_data.get('storage_snapshot_frequency'):
            required_keys = ['storage_size', 'storage_tier']

            for key in required_keys:
                if profile_data.get(key) is None:
                    log.error(
                        'both storage_snapshot_count and storage_snapshot_frequency required for profile {profile}. '
                        'Please check your profile configuration'.format(profile=vm_['profile'])
                    )
                    return False

    except AttributeError:
        pass

    return True


def create(vm_):
    '''
    Create a single Packet VM.
    '''
    name = vm_['name']

    if not is_profile_configured(vm_):
        return False

    __utils__['cloud.fire_event'](
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(name),
        args={
            'name': name,
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    log.info('Creating Packet VM {0}'.format(name))

    manager = packet.Manager(auth_token=vm_['token'])

    device = manager.create_device(project_id=vm_['project_id'],
                                hostname=name,
                                plan=vm_['size'], facility=vm_['location'],
                                operating_system=vm_['image'])

    device = _wait_for_status('device', device.id, status="active")

    if device.state != "active":
        log.error(
            'Error creating {0} on PACKET\n\n'
            'while waiting for initial ready status'.format(name),
            exc_info_on_loglevel=logging.DEBUG
        )

    # Define which ssh_interface to use
    ssh_interface = _get_ssh_interface(vm_)

    # Pass the correct IP address to the bootstrap ssh_host key
    if ssh_interface == 'private_ips':
        for ip in device.ip_addresses:
            if ip['public'] is False:
                vm_['ssh_host'] = ip['address']
                break
    else:
        for ip in device.ip_addresses:
            if ip['public'] is True:
                vm_['ssh_host'] = ip['address']
                break

    key_filename = config.get_cloud_config_value(
        'private_key', vm_, __opts__, search_global=False, default=None
    )

    vm_['key_filename'] = key_filename

    vm_['private_key'] = key_filename

    # Bootstrap!
    ret = __utils__['cloud.bootstrap'](vm_, __opts__)

    ret.update({'device': device.__dict__})

    if vm_.get('storage_tier') and vm_.get('storage_size'):
        # create storage and attach it to device

        volume = manager.create_volume(
            vm_['project_id'], "{0}_storage".format(name), vm_.get('storage_tier'),
            vm_.get('storage_size'), vm_.get('location'), snapshot_count=vm_.get('storage_snapshot_count', 0),
            snapshot_frequency=vm_.get('storage_snapshot_frequency'))

        volume.attach(device.id)

        volume = _wait_for_status('volume', volume.id, status="active")

        if volume.state != "active":
            log.error(
                'Error creating {0} on PACKET\n\n'
                'while waiting for initial ready status'.format(name),
                exc_info_on_loglevel=logging.DEBUG
            )

        ret.update({'volume': volume.__dict__})

    log.info('Created Cloud VM \'{0}\''.format(name))

    log.debug(
        '\'{0}\' VM creation details:\n{1}'.format(
            name, pprint.pformat(device.__dict__)
        )
    )

    __utils__['cloud.fire_event'](
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(name),
        args={
            'name': name,
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    return ret


def list_nodes_full(call=None):
    '''
    List devices, with all available information.

    CLI Example:

    .. code-block:: bash

        salt-cloud -F
        salt-cloud --full-query
        salt-cloud -f list_nodes_full packet-provider

    ..
    '''
    if call == 'action':
        raise SaltCloudException(
            'The list_nodes_full function must be called with -f or --function.'
        )

    ret = {}

    for device in get_devices_by_token():
        ret[device.hostname] = device.__dict__

    return ret


def list_nodes_min(call=None):
    '''
    Return a list of the VMs that are on the provider. Only a list of VM names and
    their state is returned. This is the minimum amount of information needed to
    check for existing VMs.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_nodes_min packet-provider
        salt-cloud --function list_nodes_min packet-provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_min function must be called with -f or --function.'
        )

    ret = {}

    for device in get_devices_by_token():
        ret[device.hostname] = {'id': device.id, 'state': device.state}

    return ret


def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields.
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(), __opts__['query.selection'], call,
    )


def get_devices_by_token():
    vm_ = get_configured_provider()
    manager = packet.Manager(auth_token=vm_['token'])

    devices = []

    for profile_name in vm_['profiles'].keys():
        profile = vm_['profiles'][profile_name]

        devices.extend(manager.list_devices(profile['project_id']))

    return devices


def list_nodes(call=None):
    '''
    Returns a list of devices, keeping only a brief listing.
    CLI Example:
    .. code-block:: bash
        salt-cloud -Q
        salt-cloud --query
        salt-cloud -f list_nodes packet-provider
    ..
    '''

    if call == 'action':
        raise SaltCloudException(
            'The list_nodes function must be called with -f or --function.'
        )

    ret = {}

    for device in get_devices_by_token():
        ret[device.hostname] = device.__dict__

    return ret


def destroy(name, call=None):
    '''
    Destroys a Packet device by name.

    name
        The hostname of VM to be be destroyed.

    CLI Example:

    .. code-block:: bash

        salt-cloud -d name
    '''
    if call == 'function':
        raise SaltCloudException(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )

    __utils__['cloud.fire_event'](
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    vm_ = get_configured_provider()
    manager = packet.Manager(auth_token=vm_['token'])

    nodes = list_nodes_min()

    node = nodes[name]

    for project in manager.list_projects():

        for volume in manager.list_volumes(project.id):
            if volume.attached_to == node['id']:
                volume.detach()
                volume.delete()
                break

    manager.call_api("devices/{id}".format(id=node['id']), type='DELETE')

    __utils__['cloud.fire_event'](
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    return {}


def _get_ssh_interface(vm_):
    '''
    Return the ssh_interface type to connect to. Either 'public_ips' (default)
    or 'private_ips'.
    '''
    return config.get_cloud_config_value(
        'ssh_interface', vm_, __opts__, default='public_ips',
        search_global=False
    )
