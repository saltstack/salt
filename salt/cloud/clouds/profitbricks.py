# -*- coding: utf-8 -*-
'''
ProfitBricks Cloud Module
=========================

The ProfitBricks SaltStack cloud module allows a ProfitBricks server to
be automatically deployed and bootstraped with Salt.

:depends: profitbrick >= 3.0.0

The module requires ProfitBricks credentials to be supplied along with
an existing virtual datacenter UUID where the server resources will
reside. The server should also be assigned a public LAN, a private LAN,
or both along with SSH key pairs.
...

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/profitbricks.conf``:

.. code-block:: yaml

    my-profitbricks-config:
      driver: profitbricks
      # The ProfitBricks login username
      username: user@example.com
      # The ProfitBricks login password
      password: secretpassword
      # The ProfitBricks virtual datacenter UUID
      datacenter_id: <UUID>
      # SSH private key filename
      ssh_private_key: /path/to/private.key
      # SSH public key filename
      ssh_public_key: /path/to/public.key

.. code-block:: yaml

    my-profitbricks-profile:
      provider: my-profitbricks-config
      # Name of a predefined server size.
      size: Micro Instance
      # Assign CPU family to server.
      cpu_family: INTEL_XEON
      # Number of CPU cores to allocate to node (overrides server size).
      cores: 4
      # Amount of RAM in multiples of 256 MB (overrides server size).
      ram: 4096
      # The server availability zone.
      availability_zone: ZONE_1
      # Name or UUID of the HDD image to use.
      image: <UUID>
      # Size of the node disk in GB (overrides server size).
      disk_size: 40
      # Type of disk (HDD or SSD).
      disk_type: SSD
      # Storage availability zone to use.
      disk_availability_zone: ZONE_2
      # Assign the server to the specified public LAN.
      public_lan: <ID>
      # Assign firewall rules to the network interface.
      public_firewall_rules:
        SSH:
          protocol: TCP
          port_range_start: 22
          port_range_end: 22
      # Assign the server to the specified private LAN.
      private_lan: <ID>
      # Enable NAT on the private NIC.
      nat: true
      # Assign additional volumes to the server.
      volumes:
        data-volume:
          disk_size: 500
          disk_availability_zone: ZONE_3
        log-volume:
          disk_size: 50
          disk_type: SSD

To use a private IP for connecting and bootstrapping node:

.. code-block:: yaml

    my-profitbricks-profile:
      ssh_interface: private_lan

Set ``deploy`` to False if Salt should not be installed on the node.

.. code-block:: yaml

    my-profitbricks-profile:
      deploy: False
'''

# Import python libs
from __future__ import absolute_import
import logging
import os
import pprint
import time

# Import salt libs
import salt.utils
import salt.config as config
from salt.exceptions import (
    SaltCloudConfigError,
    SaltCloudNotFound,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout,
    SaltCloudSystemExit
)

# Import salt.cloud libs
import salt.utils.cloud

# Import 3rd-party libs
import salt.ext.six as six
try:
    from profitbricks.client import (
        ProfitBricksService, Server,
        NIC, Volume, FirewallRule,
        Datacenter, LoadBalancer, LAN
    )
    HAS_PROFITBRICKS = True
except ImportError:
    HAS_PROFITBRICKS = False

# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = 'profitbricks'


# Only load in this module if the ProfitBricks configurations are in place
def __virtual__():
    '''
    Check for ProfitBricks configurations.
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
        ('username', 'password', 'datacenter_id')
    )


def get_dependencies():
    '''
    Warn if dependencies are not met.
    '''
    return config.check_driver_dependencies(
        __virtualname__,
        {'profitbricks': HAS_PROFITBRICKS}
    )


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    return ProfitBricksService(
        username=config.get_cloud_config_value(
            'username',
            get_configured_provider(),
            __opts__,
            search_global=False
        ),
        password=config.get_cloud_config_value(
            'password',
            get_configured_provider(),
            __opts__,
            search_global=False
        )
    )


def avail_images(call=None):
    '''
    Return a list of the images that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    ret = {}
    conn = get_conn()
    datacenter = get_datacenter(conn)

    for item in conn.list_images()['items']:
        if (item['properties']['location'] ==
           datacenter['properties']['location']):
            image = {'id': item['id']}
            image.update(item['properties'])
            ret[image['name']] = image

    return ret


def avail_sizes(call=None):
    '''
    Return a dict of all available VM sizes on the cloud provider with
    relevant data. Latest version can be found at:
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-sizes option'
        )

    sizes = {
        'Micro Instance': {
            'id': '1',
            'ram': 1024,
            'disk': 50,
            'cores': 1
        },
        'Small Instance': {
            'id': '2',
            'ram': 2048,
            'disk': 50,
            'cores': 1
        },
        'Medium Instance': {
            'id': '3',
            'ram': 4096,
            'disk': 50,
            'cores': 2
        },
        'Large Instance': {
            'id': '4',
            'ram': 7168,
            'disk': 50,
            'cores': 4
        },
        'Extra Large Instance': {
            'id': '5',
            'ram': 14336,
            'disk': 50,
            'cores': 8
        },
        'Memory Intensive Instance Medium': {
            'id': '6',
            'ram': 28672,
            'disk': 50,
            'cores': 4
        },
        'Memory Intensive Instance Large': {
            'id': '7',
            'ram': 57344,
            'disk': 50,
            'cores': 8
        }
    }

    return sizes


def get_size(vm_):
    '''
    Return the VM's size object
    '''
    vm_size = config.get_cloud_config_value('size', vm_, __opts__)
    sizes = avail_sizes()

    if not vm_size:
        return sizes['Small Instance']

    for size in sizes:
        if vm_size and str(vm_size) in (str(sizes[size]['id']), str(size)):
            return sizes[size]
    raise SaltCloudNotFound(
        'The specified size, \'{0}\', could not be found.'.format(vm_size)
    )


def get_datacenter_id():
    '''
    Return datacenter ID from provider configuration
    '''
    return config.get_cloud_config_value(
        'datacenter_id',
        get_configured_provider(),
        __opts__,
        search_global=False
    )


def list_loadbalancers(call=None):
    '''
    Return a list of the loadbalancers that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-loadbalancers option'
        )

    ret = {}
    conn = get_conn()
    datacenter = get_datacenter(conn)

    for item in conn.list_loadbalancers(datacenter['id'])['items']:
        lb = {'id': item['id']}
        lb.update(item['properties'])
        ret[lb['name']] = lb

    return ret


def create_loadbalancer(call=None, kwargs=None):
    '''
    Creates a loadbalancer within the datacenter from the provider config.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f create_loadbalancer profitbricks name=mylb
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The create_address function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    conn = get_conn()
    datacenter_id = get_datacenter_id()
    loadbalancer = LoadBalancer(name=kwargs.get('name'),
                                ip=kwargs.get('ip'),
                                dhcp=kwargs.get('dhcp'))

    response = conn.create_loadbalancer(datacenter_id, loadbalancer)
    _wait_for_completion(conn, response, 60, 'loadbalancer')

    return response


def get_datacenter(conn):
    '''
    Return the datacenter from the config provider datacenter ID
    '''
    datacenter_id = get_datacenter_id()

    for item in conn.list_datacenters()['items']:
        if item['id'] == datacenter_id:
            return item

    raise SaltCloudNotFound(
        'The specified datacenter \'{0}\' could not be found.'.format(
            datacenter_id
        )
    )


def create_datacenter(call=None, kwargs=None):
    '''
    Creates a virtual datacenter based on supplied parameters.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f create_datacenter profitbricks name=mydatacenter location=us/las description="my description"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The create_address function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    if kwargs.get('name') is None:
        raise SaltCloudExecutionFailure('The "name" parameter is required')

    if kwargs.get('location') is None:
        raise SaltCloudExecutionFailure('The "location" parameter is required')

    conn = get_conn()
    datacenter = Datacenter(name=kwargs['name'],
                            location=kwargs['location'],
                            description=kwargs.get('description'))

    response = conn.create_datacenter(datacenter)
    _wait_for_completion(conn, response, 60, 'create_datacenter')

    return response


def get_disk_type(vm_):
    '''
    Return the type of disk to use. Either 'HDD' (default) or 'SSD'.
    '''
    return config.get_cloud_config_value(
        'disk_type', vm_, __opts__, default='HDD',
        search_global=False
    )


def get_wait_timeout(vm_):
    '''
    Return the wait_for_timeout for resource provisioning.
    '''
    return config.get_cloud_config_value(
        'wait_for_timeout', vm_, __opts__, default=15 * 60,
        search_global=False
    )


def get_image(vm_):
    '''
    Return the image object to use
    '''
    vm_image = config.get_cloud_config_value('image', vm_, __opts__).encode(
        'ascii', 'salt-cloud-force-ascii'
    )

    images = avail_images()
    for key in six.iterkeys(images):
        if vm_image and vm_image in (images[key]['id'], images[key]['name']):
            return images[key]

    raise SaltCloudNotFound(
        'The specified image, \'{0}\', could not be found.'.format(vm_image)
    )


def list_datacenters(conn=None, call=None):
    '''
    List all the data centers

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_datacenters my-profitbricks-config
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_datacenters function must be called with '
            '-f or --function.'
        )

    datacenters = []

    if not conn:
        conn = get_conn()

    for item in conn.list_datacenters()['items']:
        datacenter = {'id': item['id']}
        datacenter.update(item['properties'])
        datacenters.append({item['properties']['name']: datacenter})

    return {'Datacenters': datacenters}


def list_nodes(conn=None, call=None):
    '''
    Return a list of VMs that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    ret = {}
    datacenter_id = get_datacenter_id()
    nodes = conn.list_servers(datacenter_id=datacenter_id)

    for item in nodes['items']:
        node = {'id': item['id']}
        node.update(item['properties'])
        ret[node['name']] = node

    return ret


def list_nodes_full(conn=None, call=None):
    '''
    Return a list of the VMs that are on the provider, with all fields
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or '
            '--function.'
        )

    if not conn:
        conn = get_conn()   # pylint: disable=E0602

    ret = {}
    datacenter_id = get_datacenter_id()
    nodes = conn.list_servers(datacenter_id=datacenter_id, depth=3)

    for item in nodes['items']:
        node = {'id': item['id']}
        node.update(item['properties'])
        node['public_ips'] = []
        node['private_ips'] = []
        if item['entities']['nics']['items'] > 0:
            for nic in item['entities']['nics']['items']:
                ip_address = nic['properties']['ips'][0]
                if salt.utils.cloud.is_public_ip(ip_address):
                    node['public_ips'].append(ip_address)
                else:
                    node['private_ips'].append(ip_address)

        ret[node['name']] = node

    __utils__['cloud.cache_node_list'](
        ret,
        __active_provider_name__.split(':')[0],
        __opts__
    )

    return ret


def show_instance(name, call=None):
    '''
    Show the details from the provider concerning an instance
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

    nodes = list_nodes_full()
    __utils__['cloud.cache_node'](
        nodes[name],
        __active_provider_name__,
        __opts__
    )
    return nodes[name]


def get_node(conn, name):
    '''
    Return a node for the named VM
    '''
    datacenter_id = get_datacenter_id()

    for item in conn.list_servers(datacenter_id)['items']:
        if item['properties']['name'] == name:
            node = {'id': item['id']}
            node.update(item['properties'])
            return node


def ssh_interface(vm_):
    '''
    Return the ssh_interface type to connect to. Either 'public_ips' (default)
    or 'private_ips'.
    '''
    return config.get_cloud_config_value(
        'ssh_interface', vm_, __opts__, default='public_ips',
        search_global=False
    )


def _get_nics(vm_):
    '''
    Create network interfaces on appropriate LANs as defined in cloud profile.
    '''
    nics = []
    if 'public_lan' in vm_:
        firewall_rules = []
        # Set LAN to public if it already exists, otherwise create a new
        # public LAN.
        lan_id = set_public_lan(int(vm_['public_lan']))
        if 'public_firewall_rules' in vm_:
            firewall_rules = _get_firewall_rules(vm_['public_firewall_rules'])
        nics.append(NIC(lan=lan_id,
                        name='public',
                        firewall_rules=firewall_rules))

    if 'private_lan' in vm_:
        firewall_rules = []
        if 'private_firewall_rules' in vm_:
            firewall_rules = _get_firewall_rules(vm_['private_firewall_rules'])
        nic = NIC(lan=int(vm_['private_lan']),
                  name='private',
                  firewall_rules=firewall_rules)
        if 'nat' in vm_:
            nic.nat = vm_['nat']
        nics.append(nic)
    return nics


def set_public_lan(lan_id):
    '''
    Enables public Internet access for the specified public_lan. If no public
    LAN is available, then a new public LAN is created.
    '''
    conn = get_conn()
    datacenter_id = get_datacenter_id()

    try:
        lan = conn.get_lan(datacenter_id=datacenter_id, lan_id=lan_id)
        if not lan['properties']['public']:
            conn.update_lan(datacenter_id=datacenter_id,
                            lan_id=lan_id,
                            public=True)
        return lan['id']
    except Exception:
        lan = conn.create_lan(datacenter_id,
                              LAN(public=True,
                                  name='Public LAN'))
        return lan['id']


def get_public_keys(vm_):
    '''
    Retrieve list of SSH public keys.
    '''
    key_filename = config.get_cloud_config_value(
        'ssh_public_key', vm_, __opts__, search_global=False, default=None
    )
    if key_filename is not None:
        key_filename = os.path.expanduser(key_filename)
        if not os.path.isfile(key_filename):
            raise SaltCloudConfigError(
                'The defined ssh_public_key \'{0}\' does not exist'.format(
                    key_filename
                )
            )
        ssh_keys = []
        with salt.utils.fopen(key_filename) as rfh:
            for key in rfh.readlines():
                ssh_keys.append(key)

        return ssh_keys


def get_key_filename(vm_):
    '''
    Check SSH private key file and return absolute path if exists.
    '''
    key_filename = config.get_cloud_config_value(
        'ssh_private_key', vm_, __opts__, search_global=False, default=None
    )
    if key_filename is not None:
        key_filename = os.path.expanduser(key_filename)
        if not os.path.isfile(key_filename):
            raise SaltCloudConfigError(
                'The defined ssh_private_key \'{0}\' does not exist'.format(
                    key_filename
                )
            )

        return key_filename


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if (vm_['profile'] and
           config.is_profile_configured(__opts__,
                                        (__active_provider_name__ or
                                         'profitbricks'),
                                        vm_['profile']) is False):
            return False
    except AttributeError:
        pass

    __utils__['cloud.fire_event'](
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        args=__utils__['cloud.filter_event']('creating', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    data = None
    datacenter_id = get_datacenter_id()
    conn = get_conn()

    # Assemble list of network interfaces from the cloud profile config.
    nics = _get_nics(vm_)

    # Assemble list of volumes from the cloud profile config.
    volumes = [_get_system_volume(vm_)]
    if 'volumes' in vm_:
        volumes.extend(_get_data_volumes(vm_))

    # Assembla the composite server object.
    server = _get_server(vm_, volumes, nics)

    __utils__['cloud.fire_event'](
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        args=__utils__['cloud.filter_event']('requesting', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    try:
        data = conn.create_server(datacenter_id=datacenter_id, server=server)
        log.info('Create server request ID: {0}'.format(data['requestId']),
                 exc_info_on_loglevel=logging.DEBUG)

        _wait_for_completion(conn, data, get_wait_timeout(vm_),
                             'create_server')
    except Exception as exc:  # pylint: disable=W0703
        log.error(
            'Error creating {0} on ProfitBricks\n\n'
            'The following exception was thrown by the profitbricks library '
            'when trying to run the initial deployment: \n{1}'.format(
                vm_['name'], exc
            ),
            exc_info_on_loglevel=logging.DEBUG
        )
        return False

    vm_['server_id'] = data['id']

    def __query_node_data(vm_, data):
        '''
        Query node data until node becomes available.
        '''
        running = False
        try:
            data = show_instance(vm_['name'], 'action')
            if not data:
                return False
            log.debug(
                'Loaded node data for {0}:\nname: {1}\nstate: {2}'.format(
                    vm_['name'],
                    pprint.pformat(data['name']),
                    data['vmState']
                )
            )
        except Exception as err:
            log.error(
                'Failed to get nodes list: {0}'.format(
                    err
                ),
                # Show the trackback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
            # Trigger a failure in the wait for IP function
            return False

        running = data['vmState'] == 'RUNNING'
        if not running:
            # Still not running, trigger another iteration
            return

        if ssh_interface(vm_) == 'private_lan' and data['private_ips']:
            vm_['ssh_host'] = data['private_ips'][0]

        if ssh_interface(vm_) != 'private_lan' and data['public_ips']:
            vm_['ssh_host'] = data['public_ips'][0]

        return data

    try:
        data = salt.utils.cloud.wait_for_ip(
            __query_node_data,
            update_args=(vm_, data),
            timeout=config.get_cloud_config_value(
                'wait_for_ip_timeout', vm_, __opts__, default=10 * 60),
            interval=config.get_cloud_config_value(
                'wait_for_ip_interval', vm_, __opts__, default=10),
        )
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
        try:
            # It might be already up, let's destroy it!
            destroy(vm_['name'])
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(str(exc.message))

    log.debug('VM is now running')
    log.info('Created Cloud VM {0}'.format(vm_))
    log.debug(
        '{0} VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data)
        )
    )

    __utils__['cloud.fire_event'](
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        args=__utils__['cloud.filter_event']('created', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    if 'ssh_host' in vm_:
        vm_['key_filename'] = get_key_filename(vm_)
        ret = __utils__['cloud.bootstrap'](vm_, __opts__)
        ret.update(data)
        return ret
    else:
        raise SaltCloudSystemExit('A valid IP address was not found.')


def destroy(name, call=None):
    '''
    destroy a machine by name

    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: array of booleans , true if successfully stopped and true if
             successfully removed

    CLI Example:

    .. code-block:: bash

        salt-cloud -d vm_name

    '''
    if call == 'function':
        raise SaltCloudSystemExit(
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

    datacenter_id = get_datacenter_id()
    conn = get_conn()
    node = get_node(conn, name)

    conn.delete_server(datacenter_id=datacenter_id, server_id=node['id'])

    __utils__['cloud.fire_event'](
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    if __opts__.get('update_cachedir', False) is True:
        __utils__['cloud.delete_minion_cachedir'](
            name,
            __active_provider_name__.split(':')[0],
            __opts__
        )

    return True


def reboot(name, call=None):
    '''
    reboot a machine by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reboot vm_name
    '''
    datacenter_id = get_datacenter_id()
    conn = get_conn()
    node = get_node(conn, name)

    conn.reboot_server(datacenter_id=datacenter_id, server_id=node['id'])

    return True


def stop(name, call=None):
    '''
    stop a machine by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop vm_name
    '''
    datacenter_id = get_datacenter_id()
    conn = get_conn()
    node = get_node(conn, name)

    conn.stop_server(datacenter_id=datacenter_id, server_id=node['id'])

    return True


def start(name, call=None):
    '''
    start a machine by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful


    CLI Example:

    .. code-block:: bash

        salt-cloud -a start vm_name
    '''
    datacenter_id = get_datacenter_id()
    conn = get_conn()
    node = get_node(conn, name)

    conn.start_server(datacenter_id=datacenter_id, server_id=node['id'])

    return True


def _override_size(vm_):
    '''
    Apply any extra component overrides to VM from the cloud profile.
    '''
    vm_size = get_size(vm_)

    if 'cores' in vm_:
        vm_size['cores'] = vm_['cores']

    if 'ram' in vm_:
        vm_size['ram'] = vm_['ram']

    return vm_size


def _get_server(vm_, volumes, nics):
    '''
    Construct server instance from cloud profile config
    '''
    # Apply component overrides to the size from the cloud profile config
    vm_size = _override_size(vm_)

    # Set the server availability zone from the cloud profile config
    availability_zone = config.get_cloud_config_value(
        'availability_zone', vm_, __opts__, default=None,
        search_global=False
    )

    # Assign CPU family from the cloud profile config
    cpu_family = config.get_cloud_config_value(
        'cpu_family', vm_, __opts__, default=None,
        search_global=False
    )

    # Contruct server object
    return Server(
        name=vm_['name'],
        ram=vm_size['ram'],
        availability_zone=availability_zone,
        cores=vm_size['cores'],
        cpu_family=cpu_family,
        create_volumes=volumes,
        nics=nics
    )


def _get_system_volume(vm_):
    '''
    Construct VM system volume list from cloud profile config
    '''
    # Retrieve list of SSH public keys
    ssh_keys = get_public_keys(vm_)

    # Override system volume size if 'disk_size' is defined in cloud profile
    disk_size = get_size(vm_)['disk']
    if 'disk_size' in vm_:
        disk_size = vm_['disk_size']

    # Construct the system volume
    volume = Volume(
        name='{0} Storage'.format(vm_['name']),
        size=disk_size,
        image=get_image(vm_)['id'],
        disk_type=get_disk_type(vm_),
        ssh_keys=ssh_keys
    )

    # Set volume availability zone if defined in the cloud profile
    if 'disk_availability_zone' in vm_:
        volume.availability_zone = vm_['disk_availability_zone']

    return volume


def _get_data_volumes(vm_):
    '''
    Construct a list of optional data volumes from the cloud profile
    '''
    ret = []
    volumes = vm_['volumes']
    for key, value in six.iteritems(volumes):
        # Verify the required 'disk_size' property is present in the cloud
        # profile config
        if 'disk_size' not in volumes[key].keys():
            raise SaltCloudConfigError(
                'The volume \'{0}\' is missing \'disk_size\''.format(key)
            )
        # Use 'HDD' if no 'disk_type' property is present in cloud profile
        if 'disk_type' not in volumes[key].keys():
            volumes[key]['disk_type'] = 'HDD'

        # Construct volume object and assign to a list.
        volume = Volume(
            name=key,
            size=volumes[key]['disk_size'],
            disk_type=volumes[key]['disk_type'],
            licence_type='OTHER'
        )

        # Set volume availability zone if defined in the cloud profile
        if 'disk_availability_zone' in volumes[key].keys():
            volume.availability_zone = volumes[key]['disk_availability_zone']

        ret.append(volume)

    return ret


def _get_firewall_rules(firewall_rules):
    '''
    Construct a list of optional firewall rules from the cloud profile.
    '''
    ret = []
    for key, value in six.iteritems(firewall_rules):
        # Verify the required 'protocol' property is present in the cloud
        # profile config
        if 'protocol' not in firewall_rules[key].keys():
            raise SaltCloudConfigError(
                'The firewall rule \'{0}\' is missing \'protocol\''.format(key)
            )
        ret.append(FirewallRule(
            name=key,
            protocol=firewall_rules[key].get('protocol', None),
            source_mac=firewall_rules[key].get('source_mac', None),
            source_ip=firewall_rules[key].get('source_ip', None),
            target_ip=firewall_rules[key].get('target_ip', None),
            port_range_start=firewall_rules[key].get('port_range_start', None),
            port_range_end=firewall_rules[key].get('port_range_end', None),
            icmp_type=firewall_rules[key].get('icmp_type', None),
            icmp_code=firewall_rules[key].get('icmp_code', None)
        ))

    return ret


def _wait_for_completion(conn, promise, wait_timeout, msg):
    '''
    Poll request status until resource is provisioned.
    '''
    if not promise:
        return
    wait_timeout = time.time() + wait_timeout
    while wait_timeout > time.time():
        time.sleep(5)
        operation_result = conn.get_request(
            request_id=promise['requestId'],
            status=True)

        if operation_result['metadata']['status'] == "DONE":
            return
        elif operation_result['metadata']['status'] == "FAILED":
            raise Exception(
                "Request: {0}, requestId: {1} failed to complete:\n{2}".format(
                    msg, str(promise['requestId']),
                    operation_result['metadata']['message']
                )
            )

    raise Exception(
        'Timed out waiting for async operation ' + msg + ' "' + str(
            promise['requestId']
            ) + '" to complete.')
