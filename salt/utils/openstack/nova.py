# -*- coding: utf-8 -*-
'''
Nova class
'''

# Import Python libs
from __future__ import absolute_import, with_statement
from distutils.version import LooseVersion
import time
import inspect
import logging

# Import third party libs
import salt.ext.six as six
HAS_SHADE = False
# pylint: disable=import-error
try:
    import shade
    import novaclient
    from novaclient import client
    import novaclient.auth_plugin
    from novaclient.shell import OpenStackComputeShell
    HAS_SHADE = True
except ImportError:
    pass
# pylint: enable=import-error

# Import salt libs
import salt.utils
from salt.exceptions import SaltCloudSystemExit

# Get logging started
log = logging.getLogger(__name__)
# dict for block_device_mapping_v2
CLIENT_BDM2_KEYS = {
    'id': 'uuid',
    'source': 'source_type',
    'dest': 'destination_type',
    'bus': 'disk_bus',
    'device': 'device_name',
    'size': 'volume_size',
    'format': 'guest_format',
    'bootindex': 'boot_index',
    'type': 'device_type',
    'shutdown': 'delete_on_termination',
}


def check_nova():
    return HAS_SHADE


# kwargs has to be an object instead of a dictionary for the __post_parse_arg__
class KwargsStruct(object):
    def __init__(self, **entries):
        self.__dict__.update(entries)


def _parse_block_device_mapping_v2(block_device=None, boot_volume=None, snapshot=None, ephemeral=None, swap=None):
    bdm = []
    if block_device is None:
        block_device = []
    if ephemeral is None:
        ephemeral = []

    if boot_volume is not None:
        bdm_dict = {'uuid': boot_volume, 'source_type': 'volume',
                    'destination_type': 'volume', 'boot_index': 0,
                    'delete_on_termination': False}
        bdm.append(bdm_dict)

    if snapshot is not None:
        bdm_dict = {'uuid': snapshot, 'source_type': 'snapshot',
                    'destination_type': 'volume', 'boot_index': 0,
                    'delete_on_termination': False}
        bdm.append(bdm_dict)

    for device_spec in block_device:
        bdm_dict = {}

        for key, value in six.iteritems(device_spec):
            bdm_dict[CLIENT_BDM2_KEYS[key]] = value

        # Convert the delete_on_termination to a boolean or set it to true by
        # default for local block devices when not specified.
        if 'delete_on_termination' in bdm_dict:
            action = bdm_dict['delete_on_termination']
            bdm_dict['delete_on_termination'] = (action == 'remove')
        elif bdm_dict.get('destination_type') == 'local':
            bdm_dict['delete_on_termination'] = True

        bdm.append(bdm_dict)

    for ephemeral_spec in ephemeral:
        bdm_dict = {'source_type': 'blank', 'destination_type': 'local',
                    'boot_index': -1, 'delete_on_termination': True}
        if 'size' in ephemeral_spec:
            bdm_dict['volume_size'] = ephemeral_spec['size']
        if 'format' in ephemeral_spec:
            bdm_dict['guest_format'] = ephemeral_spec['format']

        bdm.append(bdm_dict)

    if swap is not None:
        bdm_dict = {'source_type': 'blank', 'destination_type': 'local',
                    'boot_index': -1, 'delete_on_termination': True,
                    'guest_format': 'swap', 'volume_size': swap}
        bdm.append(bdm_dict)


class NovaServer(object):
    def __init__(self, server, password=None):
        '''
        Make output look like libcloud output for consistency
        '''
        self.name = server.name
        self.id = server.id
        self.image = getattr(server, 'image', {}).get('id', 'Boot From Volume')
        self.size = server.flavor['id']
        self.state = server.status
        self._uuid = None
        self.extra = {
            'metadata': server.metadata,
            'access_ip': server.accessIPv4,
        }

        if hasattr(server, 'addresses'):
            if 'public' in server.addresses:
                self.public_ips = [
                    ip['addr'] for ip in server.addresses['public']
                ]
            else:
                self.public_ips = []

            if 'private' in server.addresses:
                self.private_ips = [
                    ip['addr'] for ip in server.addresses['private']
                ]
            else:
                self.private_ips = []

            self.addresses = server.addresses

        if password:
            self.extra['password'] = password

    def __str__(self):
        return self.__dict__


def get_entry(dict_, key, value, raise_error=True):
    for entry in dict_:
        if entry[key] == value:
            return entry
    if raise_error is True:
        raise SaltCloudSystemExit('Unable to find {0} in {1}.'.format(key, dict_))
    return {}


# Function alias to not shadow built-ins
class SaltNova(object):
    '''
    Class for all novaclient functions
    '''
    def __init__(self, **kwargs):
        '''
        Set up nova credentials
        '''
        self.kwargs = kwargs.copy()
        import pprint
        log.debug('KWARGS: %s', pprint.pformat(self.kwargs))

        if not novaclient.base.Manager._hooks_map:
            if hasattr(OpenStackComputeShell, '_discover_extensions'):
                self.extensions = OpenStackComputeShell()._discover_extensions('2.0')
            else:
                self.extensions = client.discover_extensions('2.0')
            for extension in self.extensions:
                extension.run_hooks('__pre_parse_args__')
            self.kwargs['extensions'] = self.extensions

        # needs an object, not a dictionary
        if hasattr(self, 'extensions'):
            self.kwargstruct = KwargsStruct(**self.kwargs)
            for extension in self.kwargs['extensions']:
                extension.run_hooks('__post_parse_args__', self.kwargstruct)
            self.kwargs = self.kwargstruct.__dict__

        if 'os_auth_plugin' in kwargs:
            kwargs['auth_type'] = kwargs['os_auth_plugin']
            del kwargs['os_auth_plugin']

        self.conn = shade.openstack_cloud(**self.kwargs)
        self.catalog = self.conn.service_catalog
        self.expand_extensions()

    def expand_extensions(self):
        for extension in self.extensions:
            for attr in extension.module.__dict__:
                if not inspect.isclass(getattr(extension.module, attr)):
                    continue
                for key, value in six.iteritems(self.conn.nova_client.__dict__):
                    if not isinstance(value, novaclient.base.Manager):
                        continue
                    if value.__class__.__name__ == attr:
                        setattr(self.conn.nova_client, key, extension.manager_class(self.conn.nova_client))

    def get_catalog(self):
        '''
        Return service catalog
        '''
        return self.catalog

    def server_show_libcloud(self, uuid):
        '''
        Make output look like libcloud output for consistency
        '''
        server = self.conn.get_server_by_id(uuid)
        if not hasattr(self, 'password'):
            self.password = None
        ret = NovaServer(server, self.password)

        return ret

    def _sanatize_boot_args(self, old_kwargs):
        allowed_boot_args = [
            'name', 'image', 'flavor', 'auto_ip', 'ips', 'ip_pool', 'root_volume', 'terminate_volume', 'wait',
            'timeout', 'reuse_ips', 'network', 'boot_from_volume', 'volume_size', 'boot_volume', 'volumes',
            'meta', 'files', 'userdata', 'reservation_id', 'return_raw', 'min_count', 'max_count', 'security_groups',
            'key_name', 'availability_zone', 'block_device_mapping', 'block_device_mapping_v2', 'nics',
            'scheduler_hints', 'config_drive', 'admin_pass', 'disk_config',
        ]
        kwargs = copy.deepcopy(old_kwargs)
        for key in six.iterkeys(old_kwargs.copy()):  # iterate over a copy, we might delete some
            if key not in allowed_boot_args:
                del kwargs[key]
        return kwargs

    def boot(self, name, flavor_id=0, image_id=0, timeout=300, **kwargs):
        '''
        Boot a cloud server.
        '''
        kwargs = kwargs.copy()
        kwargs['name'] = name
        kwargs['flavor'] = flavor_id
        kwargs['image'] = image_id or None
        kwargs['wait'] = True
        ephemeral = kwargs.pop('ephemeral', [])
        block_device = kwargs.pop('block_device', [])
        boot_volume = kwargs.pop('boot_volume', None)
        snapshot = kwargs.pop('snapshot', None)
        swap = kwargs.pop('swap', None)
        kwargs['block_device_mapping_v2'] = _parse_block_device_mapping_v2(
            block_device=block_device, boot_volume=boot_volume, snapshot=snapshot,
            ephemeral=ephemeral, swap=swap
        )
        kwargs = self._sanatize_boot_args(kwargs)
        return NovaServer(self.conn.create_server(**kwargs))

    def show_instance(self, name):
        '''
        Find a server by its name (libcloud)
        '''
        server = self.conn.get_server(name)
        if not server:
            return {'name': name, 'status': 'DELETED'}
        return NovaServer(server)

    def root_password(self, server_id, password):
        '''
        Change server(uuid's) root password
        '''
        self.conn.change_password(server_id, password, wait=True)

    def server_by_name(self, name):
        '''
        Find a server by its name
        '''
        servers = self.conn.get_server(name)
        if not servers:
            return {'name': name, 'status': 'DELETED'}
        return NovaServer(servers[0])

    def _get_volume(self, name):
        if not self.conn.volume_exists(name):
            return {'name': name, 'status': 'deleted'}
        return self.conn.get_volume(name)

    def _volume(self, volume):
        '''
        Organize information about a volume from the volume_id
        '''
        response = {'name': volume.display_name,
                    'size': volume.size,
                    'id': volume.id,
                    'description': volume.display_description,
                    'attachments': volume.attachments,
                    'status': volume.status
                    }
        return response

    def volume_list(self, search_opts=None):
        '''
        List all block volumes

        search_opts is depreacted.
        shade can do a search_volumes instead
        '''
        volumes = self.conn.list_volumes()
        response = {}
        for volume in volumes:
            response[volume.display_name] = self._volume(volume)
        return response

    def volume_show(self, name):
        '''
        Show one volume
        '''
        volume = self._get_volume(name)
        if volume['status'] == 'deleted':
            return volume
        return self._volume(volume)

    def volume_create(self, name, size=100, snapshot=None, voltype=None,
                      availability_zone=None):
        '''
        Create a block device
        '''
        volume = self.conn.create_volume(
            size=size,
            display_name=name,
            volume_type=voltype,
            snapshot_id=snapshot,
            availability_zone=availability_zone,
            wait=True,
        )

        return self._volume(volume)

    def volume_delete(self, name):
        '''
        Delete a block device
        '''
        if not self.conn.volume_exists(name):
            return {'name': name, 'status': 'deleted'}
        if not self.conn.delete_volume(name, wait=True):
            raise SaltCloudSystemExit('Failed to delete {0} volume: {1}'.format(name, exc))
        return {'name': name, 'status': 'deleted'}

    def volume_detach(self,
                      name,
                      timeout=300):
        '''
        Detach a block device
        '''
        if not self.conn.volume_exists(name):
            return True
        volume = self.conn.get_volume(name)
        volume_id = volume.attachments[0]['volume_id']
        server_id = volume.attachments[0]['server_id']
        if not self.conn.detach_volume(server_id, volume_id, wait=True, timeout=timeout):
            raise SaltCloudSystemExit('Failed to detach {0} volume: {1}'.format(name, exc))
        return True

    def volume_attach(self, name, server_name, device='/dev/xvdb', timeout=300):
        '''
        Attach a block device
        '''
        if not self.conn.volume_exists(name):
            raise SaltCloudSystemExit('Unable to find {0} volume: {1}'.format(name, exc))
        volume = self.conn.get_volume(name)
        servers = self.conn.get_server(server_name)

        return self.conn.attach_volume(server.id, volume.id, device=device, wait=True, timeout=timeout)

    def suspend(self, instance_id):
        '''
        Suspend a server
        '''
        self.conn.nova_client.servers.suspend(instance_id)
        return True

    def resume(self, instance_id):
        '''
        Resume a server
        '''
        self.conn.nova_client.servers.resume(instance_id)
        return True

    def lock(self, instance_id):
        '''
        Lock an instance
        '''
        self.conn.nova_client.servers.lock(instance_id)
        return True

    def delete(self, instance_id):
        '''
        Delete a server
        '''
        return self.conn.delete_server(instance_id)

    def flavor_list(self):
        '''
        Return a list of available flavors (nova flavor-list)
        '''
        ret = {}
        for flavor in self.conn.list_flavors():
            links = {}
            for link in flavor.links:
                links[link['rel']] = link['href']
            ret[flavor.name] = {
                'disk': flavor.disk,
                'id': flavor.id,
                'name': flavor.name,
                'ram': flavor.ram,
                'swap': flavor.swap,
                'vcpus': flavor.vcpus,
                'links': links,
            }
            if hasattr(flavor, 'rxtx_factor'):
                ret[flavor.name]['rxtx_factor'] = flavor.rxtx_factor
        return ret

    list_sizes = flavor_list

    def flavor_create(self,
                      name,             # pylint: disable=C0103
                      flavor_id=0,      # pylint: disable=C0103
                      ram=0,
                      disk=0,
                      vcpus=1):
        '''
        Create a flavor
        '''
        self.conn.nova_client.flavors.create(
            name=name, flavorid=flavor_id, ram=ram, disk=disk, vcpus=vcpus
        )
        return {'name': name,
                'id': flavor_id,
                'ram': ram,
                'disk': disk,
                'vcpus': vcpus}

    def flavor_delete(self, flavor_id):  # pylint: disable=C0103
        '''
        Delete a flavor
        '''
        nt_ks = self.conn.nova_client
        nt_ks.flavors.delete(flavor_id)
        return 'Flavor deleted: {0}'.format(flavor_id)

    def keypair_list(self):
        '''
        List keypairs
        '''
        ret = {}
        for keypair in self.conn.list_keypairs():
            ret[keypair.name] = {
                'name': keypair.name,
                'fingerprint': keypair.fingerprint,
                'public_key': keypair.public_key,
            }
        return ret

    def keypair_add(self, name, pubfile=None, pubkey=None):
        '''
        Add a keypair
        '''
        nt_ks = self.compute_conn
        if pubfile:
            ifile = salt.utils.fopen(pubfile, 'r')
            pubkey = ifile.read()
        if not pubkey:
            return False
        self.conn.create_keypair(name, pubkey)
        ret = {'name': name, 'pubkey': pubkey}
        return ret

    def keypair_delete(self, name):
        '''
        Delete a keypair
        '''
        self.conn.delete_keypair(name)
        return 'Keypair deleted: {0}'.format(name)

    def image_show(self, image_id):
        '''
        Show image details and metadata
        '''
        image = self.conn.get_image(image_id)
        if image is None:
            return {}
        ret = {
            'name': image.name,
            'id': image.id,
            'status': image.status,
            'created': image.created_at,
            'updated': image.updated_at,
        }
        if hasattr(image, 'minDisk'):
            ret['minDisk'] = image.minDisk
        if hasattr(image, 'minRam'):
            ret['minRam'] = image.minRam

        return ret

    def image_list(self, name=None):
        '''
        List server images
        '''
        ret = {}
        for image in self.conn.list_images():
            links = {}
            ret[image.name] = {
                'name': image.name,
                'id': image.id,
                'status': image.status,
                'created': image.created_at,
                'updated': image.updated_at,
            }
            if hasattr(image, 'min_disk'):
                ret[image.name]['minDisk'] = image.min_disk
            if hasattr(image, 'min_ram'):
                ret[image.name]['minRam'] = image.min_ram
        if name:
            return {name: ret[name]}
        return ret

    list_images = image_list

    def image_meta_set(self,
                       image_id=None,
                       name=None,
                       **kwargs):  # pylint: disable=C0103
        '''
        Set image metadata
        '''
        image_id = self.conn.get_image(image_id or name).id
        if not image_id:
            return {'Error': 'A valid image name or id was not specified'}
        self.conn.glance_client.images.set_meta(image_id, kwargs)
        return {image_id: kwargs}

    def image_meta_delete(self,
                          image_id=None,     # pylint: disable=C0103
                          name=None,
                          keys=None):
        '''
        Delete image metadata
        '''
        image_id = self.conn.get_image(image_id or name).id # pylint: disable=C0103
        pairs = keys.split(',')
        if not image_id:
            return {'Error': 'A valid image name or id was not specified'}
        self.conn.glance_client.images.delete_meta(image_id, pairs)
        return {image_id: 'Deleted: {0}'.format(pairs)}

    def server_list(self):
        '''
        List servers
        '''
        ret = {}
        for item in self.conn.list_servers():
            try:
                ret[item.name] = {
                    'id': item.id,
                    'name': item.name,
                    'state': item.status,
                    'accessIPv4': item.accessIPv4,
                    'accessIPv6': item.accessIPv6,
                    'flavor': {'id': item.flavor['id']},
                    'image': {'id': item.image['id'] if item.image else 'Boot From Volume'},
	        }
            except TypeError:
                pass
        return ret

    def _detail_server(self, item):
        ret[item.name] = {
            'OS-EXT-SRV-ATTR': {},
            'OS-EXT-STS': {},
            'accessIPv4': item.accessIPv4,
            'accessIPv6': item.accessIPv6,
            'addresses': item.addresses,
            'created': item.created,
            'flavor': {'id': item.flavor['id'],
                       'links': item.flavor['links']},
            'hostId': item.hostId,
            'id': item.id,
            'image': {'id': item.image['id'] if item.image else 'Boot From Volume',
                      'links': item.image['links'] if item.image else ''},
            'key_name': item.key_name,
            'links': item.links,
            'metadata': item.metadata,
            'name': item.name,
            'state': item.status,
            'tenant_id': item.tenant_id,
            'updated': item.updated,
            'user_id': item.user_id,
        }

        ret[item.name]['progress'] = getattr(item, 'progress', '0')

        if hasattr(item.__dict__, 'OS-DCF:diskConfig'):
            ret[item.name]['OS-DCF'] = {
                'diskConfig': item.__dict__['OS-DCF:diskConfig']
            }
        if hasattr(item.__dict__, 'OS-EXT-SRV-ATTR:host'):
            ret[item.name]['OS-EXT-SRV-ATTR']['host'] = \
                item.__dict__['OS-EXT-SRV-ATTR:host']
        if hasattr(item.__dict__, 'OS-EXT-SRV-ATTR:hypervisor_hostname'):
            ret[item.name]['OS-EXT-SRV-ATTR']['hypervisor_hostname'] = \
                item.__dict__['OS-EXT-SRV-ATTR:hypervisor_hostname']
        if hasattr(item.__dict__, 'OS-EXT-SRV-ATTR:instance_name'):
            ret[item.name]['OS-EXT-SRV-ATTR']['instance_name'] = \
                item.__dict__['OS-EXT-SRV-ATTR:instance_name']
        if hasattr(item.__dict__, 'OS-EXT-STS:power_state'):
            ret[item.name]['OS-EXT-STS']['power_state'] = \
                item.__dict__['OS-EXT-STS:power_state']
        if hasattr(item.__dict__, 'OS-EXT-STS:task_state'):
            ret[item.name]['OS-EXT-STS']['task_state'] = \
                item.__dict__['OS-EXT-STS:task_state']
        if hasattr(item.__dict__, 'OS-EXT-STS:vm_state'):
            ret[item.name]['OS-EXT-STS']['vm_state'] = \
                item.__dict__['OS-EXT-STS:vm_state']
        if hasattr(item.__dict__, 'security_groups'):
            ret[item.name]['security_groups'] = \
                item.__dict__['security_groups']

    def server_list_detailed(self):
        '''
        Detailed list of servers
        '''
        ret = {}
        for item in self.conn.list_servers(detailed=true):
            try:
                self._detail_server(item)
            except TypeError:
                continue
        return ret

    def server_show(self, server_id):
        '''
        Show details of one server
        '''
        server = self.conn.get_server(server_id, detailed=True)
        return {server.name: server}

    def secgroup_create(self, name, description):
        '''
        Create a security group
        '''
        return self.conn.create_security_group(name, description)

    def secgroup_delete(self, name):
        '''
        Delete a security group
        '''
        secgroups = self.conn.search_security_groups(name)
        if not secgroups:
            return 'Security group not found: {0}'.format(name)
        return self.delete_security_group(name)

    def secgroup_list(self):
        '''
        List security groups
        '''
        ret = {}
        for item in self.conn.list_security_groups():
            ret[item.name] = {
                'name': item.name,
                'description': item.description,
                'id': item.id,
                'tenant_id': item.tenant_id,
                'rules': item.rules,
            }
        return ret

    def _item_list(self):
        '''
        List items
        '''
        nt_ks = self.compute_conn
        ret = []
        for item in nt_ks.items.list():
            ret.append(item.__dict__)
        return ret

    def _network_show(self, name, network_lst):
        '''
        Parse the returned network list
        '''
        for net in network_lst:
            if net.label == name:
                return net.__dict__
        return {}

    def network_show(self, name):
        '''
        Show network information
        '''
        return self.conn.get_network(name)

    def network_list(self):
        '''
        List extra private networks
        '''
        return self.conn.list_networks()

    def _sanatize_network_params(self, kwargs):
        '''
        Sanatize novaclient network parameters
        '''
        params = [
            'label', 'bridge', 'bridge_interface', 'cidr', 'cidr_v6', 'dns1',
            'dns2', 'fixed_cidr', 'gateway', 'gateway_v6', 'multi_host',
            'priority', 'project_id', 'vlan_start', 'vpn_start'
        ]

        for variable in six.iterkeys(kwargs):  # iterate over a copy, we might delete some
            if variable not in params:
                del kwargs[variable]
        return kwargs

    def network_create(self, name, cidr, shared=False, admin_state_up=True, external=False, **kwargs):
        '''
        Create extra private network
        kwargs:
            :param int ip_version:
               The IP version, which is 4 or 6.
            :param bool enable_dhcp:
               Set to ``True`` if DHCP is enabled and ``False`` if disabled.
               Default is ``False``.
            :param string subnet_name:
               The name of the subnet.
            :param string tenant_id:
               The ID of the tenant who owns the network. Only administrative users
               can specify a tenant ID other than their own.
            :param list allocation_pools:
               A list of dictionaries of the start and end addresses for the
               allocation pools. For example::

                 [
                   {
                     "start": "192.168.199.2",
                     "end": "192.168.199.254"
                   }
                 ]

            :param string gateway_ip:
               The gateway IP address. When you specify both allocation_pools and
               gateway_ip, you must ensure that the gateway IP does not overlap
               with the specified allocation pools.
            :param list dns_nameservers:
               A list of DNS name servers for the subnet. For example::

                 [ "8.8.8.7", "8.8.8.8" ]

            :param list host_routes:
               A list of host route dictionaries for the subnet. For example::

                 [
                   {
                     "destination": "0.0.0.0/0",
                     "nexthop": "123.456.78.9"
                   },
                   {
                     "destination": "192.168.0.0/24",
                     "nexthop": "192.168.0.1"
                   }
                 ]

            :param string ipv6_ra_mode:
               IPv6 Router Advertisement mode. Valid values are: 'dhcpv6-stateful',
               'dhcpv6-stateless', or 'slaac'.
            :param string ipv6_address_mode:
               IPv6 address mode. Valid values are: 'dhcpv6-stateful',
               'dhcpv6-stateless', or 'slaac'.
        '''
        network = self.conn.create_network(name, shared, admin_state_up, external)
        subnet = self.conn.create_subnet(network.id, cidr, **kwargs)
        return self.conn.get_network(network.id)

    def virtual_interface_list(self, name):
        '''
        Get virtual interfaces on slice
        '''
        nets = self.conn.nova_client.virtual_interfaces.list(self.conn.get_server(name).id)
        return [network.__dict__ for network in nets]

    def virtual_interface_create(self, name, net_name):
        '''
        Add an interfaces to a slice
        '''
        serverid = self.conn.get_server(name).id
        networkid = getattr(self.get_network(net_name), 'id', None)
        if networkid is None:
            return {net_name: False}
        nets = self.conn.nova_client.virtual_interfaces.create(networkid, serverid)
        return nets

    def floating_ip_pool_list(self):
        '''
        List all floating IP pools

        .. versionadded:: Boron
        '''
        pools = nt_ks.floating_ip_pools.list()
        response = {}
        for pool in self.conn.list_floating_ip_pools():
            response[pool.name] = {
                'name': pool.name,
            }
        return response

    def floating_ip_list(self):
        '''
        List floating IPs

        .. versionadded:: Boron
        '''
        response = {}
        for floating_ip in self.conn.list_floating_ips():
            response[floating_ip.ip] = {
                'ip': floating_ip.ip,
                'fixed_ip': floating_ip.fixed_ip,
                'id': floating_ip.id,
                'instance_id': floating_ip.instance_id,
                'pool': floating_ip.pool
            }
        return response

    def floating_ip_show(self, ip):
        '''
        Show info on specific floating IP

        .. versionadded:: Boron
        '''
        return self.floating_ip_list().get(ip, {})

    def floating_ip_create(self, pool=None):
        '''
        Allocate a floating IP

        .. versionadded:: Boron
        '''
        floating_ip = self.conn.floating_ip_create(pool)
        response = {
            'ip': floating_ip.ip,
            'fixed_ip': floating_ip.fixed_ip,
            'id': floating_ip.id,
            'instance_id': floating_ip.instance_id,
            'pool': floating_ip.pool
        }
        return response

    def floating_ip_delete(self, floating_ip):
        '''
        De-allocate a floating IP

        .. versionadded:: Boron
        '''
        ip = self.floating_ip_show(floating_ip)
        return self.delete_floating_ip(ip['id'])

    def floating_ip_associate(self, server_name, floating_ip):
        '''
        Associate floating IP address to server

        .. versionadded:: Boron
        '''
        serverid = self.conn.get_server(server_name).id
        server = self.conn.nova_client.servers.get(serverid)
        server.add_floating_ip(floating_ip)
        return self.floating_ip_list()[floating_ip]

    def floating_ip_disassociate(self, server_name, floating_ip):
        '''
        Disassociate a floating IP from server

        .. versionadded:: Boron
        '''
        server = self.conn.nova_client.servers.get(self.conn.get_server(server_name).id)
        server.remove_floating_ip(floating_ip)
        return self.floating_ip_list()[floating_ip]
