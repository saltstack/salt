# -*- coding: utf-8 -*-
'''
OpenStack Nova Cloud Module
===========================

PLEASE NOTE: This module is currently in early development, and considered to
be experimental and unstable. It is not recommended for production use. Unless
you are actively developing code in this module, you should use the OpenStack
module instead.

OpenStack is an open source project that is in use by a number a cloud
providers, each of which have their own ways of using it.

The OpenStack Nova module for Salt Cloud was bootstrapped from the OpenStack
module for Salt Cloud, which uses a libcloud-based connection. The Nova module
is designed to use the nova and glance modules already built into Salt.

These modules use the Python novaclient and glanceclient libraries,
respectively. In order to use this module, the proper salt configuration must
also be in place.  This can be specified in the master config, the minion
config, a set of grains or a set of pillars.

.. code-block:: yaml

    my_openstack_profile:
      keystone.user: admin
      keystone.password: verybadpass
      keystone.tenant: admin
      keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'

Note that there is currently a dependency upon netaddr. This can be installed
on Debian-based systems by means of the python-netaddr package.

This module currently requires the latest develop branch of Salt to be
installed.

This module has been tested to work with HP Cloud and Rackspace. See the
documentation for specific options for either of these providers. These
examples could be set up in the cloud configuration at
``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/openstack.conf``:

.. code-block:: yaml

    my-openstack-config:
      # The ID of the minion that will execute the salt nova functions
      auth_minion: myminion
      # The name of the configuration profile to use on said minion
      config_profile: my_openstack_profile

      ssh_key_name: mykey

      provider: nova
      userdata_file: /tmp/userdata.txt

For local installations that only use private IP address ranges, the
following option may be useful. Using the old syntax:

Note: For api use, you will need an auth plugin.  The base novaclient does not
support apikeys, but some providers such as rackspace have extended keystone to
accept them

.. code-block:: yaml

    my-openstack-config:
      # Ignore IP addresses on this network for bootstrap
      ignore_cidr: 192.168.50.0/24

    my-nova:
      identity_url: 'https://identity.api.rackspacecloud.com/v2.0/'
      compute_region: IAD
      user: myusername
      password: mypassword
      tenant: <userid>
      provider: nova

    my-api:
      identity_url: 'https://identity.api.rackspacecloud.com/v2.0/'
      compute_region: IAD
      user: myusername
      api_key: <api_key>
      os_auth_plugin: rackspace
      tenant: <userid>
      provider: nova
      networks:
        - net-id: 47a38ff2-fe21-4800-8604-42bd1848e743
        - net-id: 00000000-0000-0000-0000-000000000000
        - net-id: 11111111-1111-1111-1111-111111111111

Note: You must include the default net-ids when setting networks or the server
will be created without the rest of the interfaces

Note: For rackconnect v3, rackconnectv3 needs to be specified with the
rackconnect v3 cloud network as it's variable
'''
from __future__ import absolute_import
# pylint: disable=E0102

# The import section is mostly libcloud boilerplate

# Import python libs
import os
import logging
import socket
import pprint
import yaml

# Import generic libcloud functions
from salt.cloud.libcloudfuncs import *   # pylint: disable=W0614,W0401
import salt.ext.six as six
try:
    from salt.utils.openstack import nova
    HAS_NOVA = True
except NameError as exc:
    HAS_NOVA = False

import salt.utils.cloud

# Import nova libs
try:
    import novaclient.exceptions
except ImportError:
    pass

# Import salt libs
import salt.utils
import salt.client

# Import salt.cloud libs
import salt.utils.pycrypto as sup
import salt.config as config
from salt.utils import namespaced_function
from salt.exceptions import (
    SaltCloudConfigError,
    SaltCloudNotFound,
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout
)

# Import netaddr IP matching
try:
    from netaddr import all_matching_cidrs
    HAS_NETADDR = True
except ImportError:
    HAS_NETADDR = False

# Get logging started
log = logging.getLogger(__name__)
request_log = logging.getLogger('requests')

# namespace libcloudfuncs
get_salt_interface = namespaced_function(get_salt_interface, globals())


# Some of the libcloud functions need to be in the same namespace as the
# functions defined in the module, so we create new function objects inside
# this module namespace
script = namespaced_function(script, globals())
reboot = namespaced_function(reboot, globals())


# Only load in this module is the OPENSTACK configurations are in place
def __virtual__():
    '''
    Check for Nova configurations
    '''
    request_log.setLevel(getattr(logging, __opts__.get('requests_log_level', 'warning').upper()))
    return HAS_NOVA


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'nova'
    )


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    vm_ = get_configured_provider()

    kwargs = vm_.copy()  # pylint: disable=E1103

    kwargs['username'] = vm_['user']
    kwargs['project_id'] = vm_['tenant']
    kwargs['auth_url'] = vm_['identity_url']
    kwargs['region_name'] = vm_['compute_region']

    if 'password' in vm_:
        kwargs['password'] = vm_['password']

    conn = nova.SaltNova(**kwargs)

    return conn


def avail_locations(conn=None, call=None):
    '''
    Return a list of locations
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_locations function must be called with '
            '-f or --function, or with the --list-locations option'
        )

    if conn is None:
        conn = get_conn()

    endpoints = nova.get_entry(conn.get_catalog(), 'type', 'compute')['endpoints']
    ret = {}
    for endpoint in endpoints:
        ret[endpoint['region']] = endpoint

    return ret


def get_image(conn, vm_):
    '''
    Return the image object to use
    '''
    image_list = conn.image_list()

    vm_image = config.get_cloud_config_value('image', vm_, __opts__).encode(
        'ascii', 'salt-cloud-force-ascii'
    )

    for img in image_list:
        if vm_image in (image_list[img]['id'], img):
            return image_list[img]['id']

    try:
        image = conn.image_show(vm_image)
        return image['id']
    except novaclient.exceptions.NotFound as exc:
        raise SaltCloudNotFound(
            'The specified image, {0!r}, could not be found: {1}'.format(
                vm_image,
                str(exc)
            )
        )


def show_instance(name, call=None):
    '''
    Show the details from the provider concerning an instance
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

    conn = get_conn()
    node = conn.show_instance(name).__dict__
    salt.utils.cloud.cache_node(node, __active_provider_name__, __opts__)
    return node


def get_size(conn, vm_):
    '''
    Return the VM's size object
    '''
    sizes = conn.list_sizes()
    vm_size = config.get_cloud_config_value('size', vm_, __opts__)
    if not vm_size:
        return sizes[0]

    for size in sizes:
        if vm_size and str(vm_size) in (str(sizes[size]['id']), str(size)):
            return sizes[size]['id']
    raise SaltCloudNotFound(
        'The specified size, {0!r}, could not be found.'.format(vm_size)
    )


def preferred_ip(vm_, ips):
    '''
    Return the preferred Internet protocol. Either 'ipv4' (default) or 'ipv6'.
    '''
    proto = config.get_cloud_config_value(
        'protocol', vm_, __opts__, default='ipv4', search_global=False
    )

    family = socket.AF_INET
    if proto == 'ipv6':
        family = socket.AF_INET6
    for ip in ips:
        try:
            socket.inet_pton(family, ip)
            return ip
        except Exception:
            continue

    return False


def ignore_cidr(vm_, ip):
    '''
    Return True if we are to ignore the specified IP. Compatible with IPv4.
    '''
    if HAS_NETADDR is False:
        log.error('Error: netaddr is not installed')
        return 'Error: netaddr is not installed'

    cidr = config.get_cloud_config_value(
        'ignore_cidr', vm_, __opts__, default='', search_global=False
    )
    if cidr != '' and all_matching_cidrs(ip, [cidr]):
        log.warning(
            'IP "{0}" found within "{1}"; ignoring it.'.format(ip, cidr)
        )
        return True

    return False


def ssh_interface(vm_):
    '''
    Return the ssh_interface type to connect to. Either 'public_ips' (default)
    or 'private_ips'.
    '''
    return config.get_cloud_config_value(
        'ssh_interface', vm_, __opts__, default='public_ips',
        search_global=False
    )


def rackconnect(vm_):
    '''
    Determine if we should wait for rackconnect automation before running.
    Either 'False' (default) or 'True'.
    '''
    return config.get_cloud_config_value(
        'rackconnect', vm_, __opts__, default='False',
        search_global=False
    )


def managedcloud(vm_):
    '''
    Determine if we should wait for the managed cloud automation before
    running. Either 'False' (default) or 'True'.
    '''
    return config.get_cloud_config_value(
        'managedcloud', vm_, __opts__, default='False',
        search_global=False
    )


def destroy(name, conn=None, call=None):
    '''
    Delete a single VM
    '''
    if call == 'function':
        raise SaltCloudSystemExit(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )

    salt.utils.cloud.fire_event(
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )

    if not conn:
        conn = get_conn()   # pylint: disable=E0602

    node = conn.server_by_name(name)
    profiles = get_configured_provider()['profiles']  # pylint: disable=E0602
    if node is None:
        log.error('Unable to find the VM {0}'.format(name))
    profile = None
    if 'metadata' in node.extra and 'profile' in node.extra['metadata']:
        profile = node.extra['metadata']['profile']
    flush_mine_on_destroy = False
    if profile is not None and profile in profiles:
        if 'flush_mine_on_destroy' in profiles[profile]:
            flush_mine_on_destroy = profiles[profile]['flush_mine_on_destroy']
    if flush_mine_on_destroy:
        log.info('Clearing Salt Mine: {0}'.format(name))
        salt_client = salt.client.get_local_client(__opts__['conf_file'])
        minions = salt_client.cmd(name, 'mine.flush')

    log.info('Clearing Salt Mine: {0}, {1}'.format(
        name,
        flush_mine_on_destroy
    ))
    log.info('Destroying VM: {0}'.format(name))
    ret = conn.delete(node.id)
    if ret:
        log.info('Destroyed VM: {0}'.format(name))
        # Fire destroy action
        salt.utils.cloud.fire_event(
            'event',
            'destroyed instance',
            'salt/cloud/{0}/destroyed'.format(name),
            {'name': name},
            transport=__opts__['transport']
        )
        if __opts__.get('delete_sshkeys', False) is True:
            salt.utils.cloud.remove_sshkey(getattr(node, __opts__.get('ssh_interface', 'public_ips'))[0])
        if __opts__.get('update_cachedir', False) is True:
            salt.utils.cloud.delete_minion_cachedir(name, __active_provider_name__.split(':')[0], __opts__)
        return True

    log.error('Failed to Destroy VM: {0}'.format(name))
    return False


def request_instance(vm_=None, call=None):
    '''
    Put together all of the information necessary to request an instance
    through Novaclient and then fire off the request the instance.

    Returns data about the instance
    '''
    if call == 'function':
        # Technically this function may be called other ways too, but it
        # definitely cannot be called with --function.
        raise SaltCloudSystemExit(
            'The request_instance action must be called with -a or --action.'
        )
    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    salt.utils.cloud.check_name(vm_['name'], 'a-zA-Z0-9._-')
    conn = get_conn()
    kwargs = vm_.copy()

    try:
        kwargs['image_id'] = get_image(conn, vm_)
    except Exception as exc:
        raise SaltCloudSystemExit(
            'Error creating {0} on OPENSTACK\n\n'
            'Could not find image {1}: {2}\n'.format(
                vm_['name'], vm_['image'], exc
            )
        )

    try:
        kwargs['flavor_id'] = get_size(conn, vm_)
    except Exception as exc:
        raise SaltCloudSystemExit(
            'Error creating {0} on OPENSTACK\n\n'
            'Could not find size {1}: {2}\n'.format(
                vm_['name'], vm_['size'], exc
            )
        )

    kwargs['key_name'] = config.get_cloud_config_value(
        'ssh_key_name', vm_, __opts__, search_global=False
    )

    security_groups = config.get_cloud_config_value(
        'security_groups', vm_, __opts__, search_global=False
    )
    if security_groups is not None:
        vm_groups = security_groups.split(',')
        avail_groups = conn.secgroup_list()
        group_list = []

        for vmg in vm_groups:
            if vmg in [name for name, details in six.iteritems(avail_groups)]:
                group_list.append(vmg)
            else:
                raise SaltCloudNotFound(
                    'No such security group: \'{0}\''.format(vmg)
                )

        kwargs['security_groups'] = group_list

    avz = config.get_cloud_config_value(
        'availability_zone', vm_, __opts__, default=None, search_global=False
    )
    if avz is not None:
        kwargs['availability_zone'] = avz

    kwargs['nics'] = config.get_cloud_config_value(
        'networks', vm_, __opts__, search_global=False, default=None
    )

    files = config.get_cloud_config_value(
        'files', vm_, __opts__, search_global=False
    )
    if files:
        kwargs['files'] = {}
        for src_path in files:
            if os.path.exists(files[src_path]):
                with salt.utils.fopen(files[src_path], 'r') as fp_:
                    kwargs['files'][src_path] = fp_.read()
            else:
                kwargs['files'][src_path] = files[src_path]

    userdata_file = config.get_cloud_config_value(
        'userdata_file', vm_, __opts__, search_global=False
    )

    if userdata_file is not None:
        with salt.utils.fopen(userdata_file, 'r') as fp:
            kwargs['userdata'] = fp.read()

    kwargs['config_drive'] = config.get_cloud_config_value(
        'config_drive', vm_, __opts__, search_global=False
    )

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': {'name': kwargs['name'],
                    'image': kwargs['image_id'],
                    'size': kwargs['flavor_id']}},
        transport=__opts__['transport']
    )

    try:
        data = conn.boot(**kwargs)
    except Exception as exc:
        raise SaltCloudSystemExit(
            'Error creating {0} on Nova\n\n'
            'The following exception was thrown by libcloud when trying to '
            'run the initial deployment: {1}\n'.format(
                vm_['name'], exc
            )
        )
    vm_['password'] = data.extra.get('password', '')

    return data, vm_


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    deploy = config.get_cloud_config_value('deploy', vm_, __opts__)
    key_filename = config.get_cloud_config_value(
        'ssh_key_file', vm_, __opts__, search_global=False, default=None
    )
    if key_filename is not None and not os.path.isfile(key_filename):
        raise SaltCloudConfigError(
            'The defined ssh_key_file {0!r} does not exist'.format(
                key_filename
            )
        )

    vm_['key_filename'] = key_filename

    salt.utils.cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
        transport=__opts__['transport']
    )
    conn = get_conn()

    if 'instance_id' in vm_:
        # This was probably created via another process, and doesn't have
        # things like salt keys created yet, so let's create them now.
        if 'pub_key' not in vm_ and 'priv_key' not in vm_:
            log.debug('Generating minion keys for {0[name]!r}'.format(vm_))
            vm_['priv_key'], vm_['pub_key'] = salt.utils.cloud.gen_keys(
                salt.config.get_cloud_config_value(
                    'keysize',
                    vm_,
                    __opts__
                )
            )
        data = conn.server_show_libcloud(vm_['instance_id'])
        if vm_['key_filename'] is None and 'change_password' in __opts__ and __opts__['change_password'] is True:
            vm_['password'] = sup.secure_password()
            conn.root_password(vm_['instance_id'], vm_['password'])
    else:
        # Put together all of the information required to request the instance,
        # and then fire off the request for it
        data, vm_ = request_instance(vm_)

        # Pull the instance ID, valid for both spot and normal instances
        vm_['instance_id'] = data.id

    def __query_node_data(vm_, data):
        try:
            node = show_instance(vm_['name'], 'action')
            log.debug(
                'Loaded node data for {0}:\n{1}'.format(
                    vm_['name'],
                    pprint.pformat(node)
                )
            )
        except Exception as err:
            log.error(
                'Failed to get nodes list: {0}'.format(
                    err
                ),
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
            # Trigger a failure in the wait for IP function
            return False

        running = node['state'] == 'ACTIVE'
        if not running:
            # Still not running, trigger another iteration
            return

        rackconnectv3 = config.get_cloud_config_value(
            'rackconnectv3', vm_, __opts__, default='False',
            search_global=False
        )

        if rackconnectv3:
            networkname = rackconnectv3
            for network in node['addresses'].get(networkname, []):
                if network['version'] is 4:
                    node['extra']['access_ip'] = network['addr']
                    break
            vm_['rackconnect'] = True

        if rackconnect(vm_) is True:
            extra = node.get('extra', {})
            rc_status = extra.get('metadata', {}).get(
                'rackconnect_automation_status', '')
            access_ip = extra.get('access_ip', '')

            if rc_status != 'DEPLOYED' and not rackconnectv3:
                log.debug('Waiting for Rackconnect automation to complete')
                return

        if managedcloud(vm_) is True:
            extra = conn.server_show_libcloud(
                node['id']
            ).extra
            mc_status = extra.get('metadata', {}).get(
                'rax_service_level_automation', '')

            if mc_status != 'Complete':
                log.debug('Waiting for managed cloud automation to complete')
                return

        result = []

        if 'private_ips' not in node and 'public_ips' not in node and \
           'access_ip' in node.get('extra', {}):
            result = [node['extra']['access_ip']]

        private = node.get('private_ips', [])
        public = node.get('public_ips', [])
        if private and not public:
            log.warn(
                'Private IPs returned, but not public... Checking for '
                'misidentified IPs'
            )
            for private_ip in private:
                private_ip = preferred_ip(vm_, [private_ip])
                if salt.utils.cloud.is_public_ip(private_ip):
                    log.warn('{0} is a public IP'.format(private_ip))
                    data.public_ips.append(private_ip)
                    log.warn(
                        (
                            'Public IP address was not ready when we last'
                            ' checked.  Appending public IP address now.'
                        )
                    )
                    public = data.public_ips
                else:
                    log.warn('{0} is a private IP'.format(private_ip))
                    ignore_ip = ignore_cidr(vm_, private_ip)
                    if private_ip not in data.private_ips and not ignore_ip:
                        result.append(private_ip)

        if rackconnect(vm_) is True:
            if ssh_interface(vm_) != 'private_ips' or rackconnectv3:
                data.public_ips = access_ip
                return data

        if result:
            log.debug('result = {0}'.format(result))
            data.private_ips = result
            if ssh_interface(vm_) == 'private_ips':
                return data

        if public:
            data.public_ips = public
            if ssh_interface(vm_) != 'private_ips':
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
            raise SaltCloudSystemExit(str(exc))

    log.debug('VM is now running')

    if ssh_interface(vm_) == 'private_ips':
        ip_address = preferred_ip(vm_, data.private_ips)
    elif rackconnect(vm_) is True and ssh_interface(vm_) != 'private_ips':
        ip_address = data.public_ips
    else:
        ip_address = preferred_ip(vm_, data.public_ips)
    log.debug('Using IP address {0}'.format(ip_address))

    if get_salt_interface(vm_) == 'private_ips':
        salt_ip_address = preferred_ip(vm_, data.private_ips)
        log.info('Salt interface set to: {0}'.format(salt_ip_address))
    elif rackconnect(vm_) is True and get_salt_interface(vm_) != 'private_ips':
        salt_ip_address = data.public_ips
    else:
        salt_ip_address = preferred_ip(vm_, data.public_ips)
        log.debug('Salt interface set to: {0}'.format(salt_ip_address))

    if not ip_address:
        raise SaltCloudSystemExit('A valid IP address was not found')

    vm_['ssh_host'] = ip_address
    vm_['salt_host'] = salt_ip_address

    ret = salt.utils.cloud.bootstrap(vm_, __opts__)

    ret.update(data.__dict__)

    if 'password' in ret['extra']:
        del ret['extra']['password']

    log.info('Created Cloud VM {0[name]!r}'.format(vm_))
    log.debug(
        '{0[name]!r} VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data)
        )
    )

    salt.utils.cloud.fire_event(
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
        transport=__opts__['transport']
    )

    return ret


def avail_images():
    '''
    Return a dict of all available VM images on the cloud provider.
    '''
    conn = get_conn()
    return conn.image_list()


def avail_sizes():
    '''
    Return a dict of all available VM sizes on the cloud provider.
    '''
    conn = get_conn()
    return conn.flavor_list()


def list_nodes(call=None, **kwargs):
    '''
    Return a list of the VMs that in this location
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    ret = {}
    conn = get_conn()
    server_list = conn.server_list()

    if not server_list:
        return {}
    for server in server_list:
        server_tmp = conn.server_show(server_list[server]['id'])[server]

        private = []
        public = []
        if 'addresses' not in server_tmp:
            server_tmp['addresses'] = {}
        for network in server_tmp['addresses'].keys():
            for address in server_tmp['addresses'][network]:
                if salt.utils.cloud.is_public_ip(address.get('addr', '')):
                    public.append(address['addr'])
                elif ':' in address['addr']:
                    public.append(address['addr'])
                elif '.' in address['addr']:
                    private.append(address['addr'])

        if server_tmp['accessIPv4']:
            if salt.utils.cloud.is_public_ip(server_tmp['accessIPv4']):
                public.append(server_tmp['accessIPv4'])
            else:
                private.append(server_tmp['accessIPv4'])
        if server_tmp['accessIPv6']:
            public.append(server_tmp['accessIPv6'])

        ret[server] = {
            'id': server_tmp['id'],
            'image': server_tmp['image']['id'],
            'size': server_tmp['flavor']['id'],
            'state': server_tmp['state'],
            'private_ips': private,
            'public_ips': public,
        }
    return ret


def list_nodes_full(call=None, **kwargs):
    '''
    Return a list of the VMs that in this location
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            (
                'The list_nodes_full function must be called with'
                ' -f or --function.'
            )
        )

    ret = {}
    conn = get_conn()
    server_list = conn.server_list()

    if not server_list:
        return {}
    for server in server_list:
        try:
            ret[server] = conn.server_show_libcloud(
                server_list[server]['id']
            ).__dict__
        except IndexError as exc:
            ret = {}

    salt.utils.cloud.cache_node_list(ret, __active_provider_name__.split(':')[0], __opts__)
    return ret


def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(), __opts__['query.selection'], call,
    )


def volume_create(name, size=100, snapshot=None, voltype=None, **kwargs):
    '''
    Create block storage device
    '''
    conn = get_conn()
    create_kwargs = {'name': name,
                     'size': size,
                     'snapshot': snapshot,
                     'voltype': voltype}
    create_kwargs['availability_zone'] = kwargs.get('availability_zone', None)
    return conn.volume_create(**create_kwargs)


# Command parity with EC2 and Azure
create_volume = volume_create


def volume_delete(name, **kwargs):
    '''
    Delete block storage device
    '''
    conn = get_conn()
    return conn.volume_delete(name)


def volume_detach(name, **kwargs):
    '''
    Detach block volume
    '''
    conn = get_conn()
    return conn.volume_detach(
        name,
        timeout=300
    )


def volume_attach(name, server_name, device='/dev/xvdb', **kwargs):
    '''
    Attach block volume
    '''
    conn = get_conn()
    return conn.volume_attach(
        name,
        server_name,
        device,
        timeout=300
    )


# Command parity with EC2 and Azure
attach_volume = volume_attach


def volume_create_attach(name, call=None, **kwargs):
    '''
    Create and attach volumes to created node
    '''
    if call == 'function':
        raise SaltCloudSystemExit(
            'The create_attach_volumes action must be called with '
            '-a or --action.'
        )

    if type(kwargs['volumes']) is str:
        volumes = yaml.safe_load(kwargs['volumes'])
    else:
        volumes = kwargs['volumes']

    ret = []
    for volume in volumes:
        created = False

        volume_dict = {
            'name': volume['name'],
        }
        if 'volume_id' in volume:
            volume_dict['volume_id'] = volume['volume_id']
        elif 'snapshot' in volume:
            volume_dict['snapshot'] = volume['snapshot']
        else:
            volume_dict['size'] = volume['size']

            if 'type' in volume:
                volume_dict['type'] = volume['type']
            if 'iops' in volume:
                volume_dict['iops'] = volume['iops']

        if 'id' not in volume_dict:
            created_volume = create_volume(**volume_dict)
            created = True
            volume_dict.update(created_volume)

        attach = attach_volume(
            name=volume['name'],
            server_name=name,
            device=volume.get('device', None),
            call='action'
        )

        if attach:
            msg = (
                '{0} attached to {1} (aka {2})'.format(
                    volume_dict['id'],
                    name,
                    volume_dict['name'],
                )
            )
            log.info(msg)
            ret.append(msg)
    return ret


# Command parity with EC2 and Azure
create_attach_volumes = volume_create_attach


def volume_list(**kwargs):
    '''
    List block devices
    '''
    conn = get_conn()
    return conn.volume_list()


def network_list(call=None, **kwargs):
    '''
    List private networks
    '''
    conn = get_conn()
    return conn.network_list()


def network_create(name, **kwargs):
    '''
    Create private networks
    '''
    conn = get_conn()
    return conn.network_create(name, **kwargs)


def virtual_interface_list(name, **kwargs):
    '''
    Create private networks
    '''
    conn = get_conn()
    return conn.virtual_interface_list(name)


def virtual_interface_create(name, net_name, **kwargs):
    '''
    Create private networks
    '''
    conn = get_conn()
    return conn.virtual_interface_create(name, net_name)
