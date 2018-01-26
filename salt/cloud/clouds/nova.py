# -*- coding: utf-8 -*-
'''
OpenStack Nova Cloud Module
===========================

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
      # The name of the configuration profile to use on said minion
      config_profile: my_openstack_profile

      ssh_key_name: mykey

      driver: nova
      userdata_file: /tmp/userdata.txt

To use keystoneauth1 instead of keystoneclient, include the `use_keystoneauth`
option in the provider config.

.. note:: this is required to use keystone v3 as for authentication.

.. code-block:: yaml

    my-openstack-config:
      use_keystoneauth: True
      identity_url: 'https://controller:5000/v3'
      auth_version: 3
      compute_name: nova
      compute_region: RegionOne
      service_type: compute
      verify: '/path/to/custom/certs/ca-bundle.crt'
      tenant: admin
      user: admin
      password: passwordgoeshere
      driver: nova

Note: by default the nova driver will attempt to verify its connection
utilizing the system certificates. If you need to verify against another bundle
of CA certificates or want to skip verification altogether you will need to
specify the verify option. You can specify True or False to verify (or not)
against system certificates, a path to a bundle or CA certs to check against, or
None to allow keystoneauth to search for the certificates on its own.(defaults to True)

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
      driver: nova

    my-api:
      identity_url: 'https://identity.api.rackspacecloud.com/v2.0/'
      compute_region: IAD
      user: myusername
      api_key: <api_key>
      os_auth_plugin: rackspace
      tenant: <userid>
      driver: nova
      networks:
        - net-id: 47a38ff2-fe21-4800-8604-42bd1848e743
        - net-id: 00000000-0000-0000-0000-000000000000
        - net-id: 11111111-1111-1111-1111-111111111111

This is an example profile.

.. code-block:: yaml

    debian8-2-iad-cloudqe4:
      provider: cloudqe4-iad
      size: performance1-2
      image: Debian 8 (Jessie) (PVHVM)
      script_args: -UP -p python-zmq git 2015.8

and one using cinder volumes already attached

.. code-block:: yaml

    # create the block storage device
    centos7-2-iad-rackspace:
      provider: rackspace-iad
      size: general1-2
      block_device:
        - source: image
          id: <image_id>
          dest: volume
          size: 100
          shutdown: <preserve/remove>
          bootindex: 0

    # with the volume already created
    centos7-2-iad-rackspace:
      provider: rackspace-iad
      size: general1-2
      boot_volume: <volume id>

    # create the volume from a snapshot
    centos7-2-iad-rackspace:
      provider: rackspace-iad
      size: general1-2
      snapshot: <cinder snapshot id>

    # create the create an extra ephemeral disk
    centos7-2-iad-rackspace:
      provider: rackspace-iad
      size: general1-2
      ephemeral:
        - size: 100
          format: <swap/ext4>

    # create the create an extra ephemeral disk
    centos7-2-iad-rackspace:
      provider: rackspace-iad
      size: general1-2
      swap: <size>

Block Device can also be used for having more than one block storage device attached

.. code-block:: yaml

    centos7-2-iad-rackspace:
      provider: rackspace-iad
      size: general1-2
      block_device:
        - source: image
          id: <image_id>
          dest: volume
          size: 100
          shutdown: <preserve/remove>
          bootindex: 0
        - source: blank
          dest: volume
          device: xvdc
          size: 100
          shutdown: <preserve/remove>

Floating IPs can be auto assigned and ssh_interface can be set to fixed_ips, floating_ips, public_ips or private_ips

.. code-block:: yaml

    centos7-2-iad-rackspace:
      provider: rackspace-iad
      size: general1-2
      ssh_interface: floating_ips
      floating_ip:
        auto_assign: True
        pool: public


Note: You must include the default net-ids when setting networks or the server
will be created without the rest of the interfaces

Note: For rackconnect v3, rackconnectv3 needs to be specified with the
rackconnect v3 cloud network as its variable.
'''
# pylint: disable=E0102

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import logging
import socket
import pprint

# Import Salt Libs
from salt.ext import six
import salt.utils.cloud
import salt.utils.files
import salt.utils.pycrypto
import salt.utils.yaml
import salt.client
from salt.utils.openstack import nova
try:
    import novaclient.exceptions
except ImportError as exc:
    pass

# Import Salt Cloud Libs
from salt.cloud.libcloudfuncs import *  # pylint: disable=W0614,W0401
import salt.config as config
from salt.utils.functools import namespaced_function
from salt.exceptions import (
    SaltCloudConfigError,
    SaltCloudNotFound,
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout
)

try:
    from netaddr import all_matching_cidrs
    HAS_NETADDR = True
except ImportError:
    HAS_NETADDR = False

# Get logging started
log = logging.getLogger(__name__)
request_log = logging.getLogger('requests')

__virtualname__ = 'nova'

# Some of the libcloud functions need to be in the same namespace as the
# functions defined in the module, so we create new function objects inside
# this module namespace
script = namespaced_function(script, globals())
reboot = namespaced_function(reboot, globals())


# Only load in this module if the Nova configurations are in place
def __virtual__():
    '''
    Check for Nova configurations
    '''
    request_log.setLevel(getattr(logging, __opts__.get('requests_log_level', 'warning').upper()))

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
        ('user', 'tenant', 'identity_url', 'compute_region',)
    )


def get_dependencies():
    '''
    Warn if dependencies aren't met.
    '''
    deps = {
        'netaddr': HAS_NETADDR,
        'python-novaclient': nova.check_nova(),
    }
    return config.check_driver_dependencies(
        __virtualname__,
        deps
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
    kwargs['use_keystoneauth'] = vm_.get('use_keystoneauth', False)

    if 'password' in vm_:
        kwargs['password'] = vm_['password']

    if 'verify' in vm_ and vm_['use_keystoneauth'] is True:
        kwargs['verify'] = vm_['verify']
    elif 'verify' in vm_ and vm_['use_keystoneauth'] is False:
        log.warning('SSL Certificate verification option is specified but use_keystoneauth is False or not present')
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
    vm_image = config.get_cloud_config_value('image', vm_, __opts__, default='').encode(
        'ascii', 'salt-cloud-force-ascii'
    )
    if not vm_image:
        log.debug('No image set, must be boot from volume')
        return None

    image_list = conn.image_list()

    for img in image_list:
        if vm_image in (image_list[img]['id'], img):
            return image_list[img]['id']

    try:
        image = conn.image_show(vm_image)
        return image['id']
    except novaclient.exceptions.NotFound as exc:
        raise SaltCloudNotFound(
            'The specified image, \'{0}\', could not be found: {1}'.format(
                vm_image,
                exc
            )
        )


def get_block_mapping_opts(vm_):
    ret = {}
    ret['block_device_mapping'] = config.get_cloud_config_value('block_device_mapping', vm_, __opts__, default={})
    ret['block_device'] = config.get_cloud_config_value('block_device', vm_, __opts__, default=[])
    ret['ephemeral'] = config.get_cloud_config_value('ephemeral', vm_, __opts__, default=[])
    ret['swap'] = config.get_cloud_config_value('swap', vm_, __opts__, default=None)
    ret['snapshot'] = config.get_cloud_config_value('snapshot', vm_, __opts__, default=None)
    ret['boot_volume'] = config.get_cloud_config_value('boot_volume', vm_, __opts__, default=None)
    return ret


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
    __utils__['cloud.cache_node'](node, __active_provider_name__, __opts__)
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
        if vm_size and six.text_type(vm_size) in (six.text_type(sizes[size]['id']), six.text_type(size)):
            return sizes[size]['id']
    raise SaltCloudNotFound(
        'The specified size, \'{0}\', could not be found.'.format(vm_size)
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
        log.warning('IP "%s" found within "%s"; ignoring it.', ip, cidr)
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
        'rackconnect', vm_, __opts__, default=False,
        search_global=False
    )


def rackconnectv3(vm_):
    '''
    Determine if server is using rackconnectv3 or not
    Return the rackconnect network name or False
    '''
    return config.get_cloud_config_value(
        'rackconnectv3', vm_, __opts__, default=False,
        search_global=False
    )


def cloudnetwork(vm_):
    '''
    Determine if we should use an extra network to bootstrap
    Either 'False' (default) or 'True'.
    '''
    return config.get_cloud_config_value(
        'cloudnetwork', vm_, __opts__, default=False,
        search_global=False
    )


def managedcloud(vm_):
    '''
    Determine if we should wait for the managed cloud automation before
    running. Either 'False' (default) or 'True'.
    '''
    return config.get_cloud_config_value(
        'managedcloud', vm_, __opts__, default=False,
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

    __utils__['cloud.fire_event'](
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    if not conn:
        conn = get_conn()   # pylint: disable=E0602

    node = conn.server_by_name(name)
    profiles = get_configured_provider()['profiles']  # pylint: disable=E0602
    if node is None:
        log.error('Unable to find the VM %s', name)
    profile = None
    if 'metadata' in node.extra and 'profile' in node.extra['metadata']:
        profile = node.extra['metadata']['profile']

    flush_mine_on_destroy = False
    if profile and profile in profiles and 'flush_mine_on_destroy' in profiles[profile]:
        flush_mine_on_destroy = profiles[profile]['flush_mine_on_destroy']

    if flush_mine_on_destroy:
        log.info('Clearing Salt Mine: %s', name)
        salt_client = salt.client.get_local_client(__opts__['conf_file'])
        minions = salt_client.cmd(name, 'mine.flush')

    log.info('Clearing Salt Mine: %s, %s', name, flush_mine_on_destroy)
    log.info('Destroying VM: %s', name)
    ret = conn.delete(node.id)
    if ret:
        log.info('Destroyed VM: %s', name)
        # Fire destroy action
        __utils__['cloud.fire_event'](
            'event',
            'destroyed instance',
            'salt/cloud/{0}/destroyed'.format(name),
            args={'name': name},
            sock_dir=__opts__['sock_dir'],
            transport=__opts__['transport']
        )
        if __opts__.get('delete_sshkeys', False) is True:
            salt.utils.cloud.remove_sshkey(getattr(node, __opts__.get('ssh_interface', 'public_ips'))[0])
        if __opts__.get('update_cachedir', False) is True:
            __utils__['cloud.delete_minion_cachedir'](name, __active_provider_name__.split(':')[0], __opts__)
        __utils__['cloud.cachedir_index_del'](name)
        return True

    log.error('Failed to Destroy VM: %s', name)
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
    log.info('Creating Cloud VM %s', vm_['name'])
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
        vm_groups = security_groups
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
                with salt.utils.files.fopen(files[src_path], 'r') as fp_:
                    kwargs['files'][src_path] = fp_.read()
            else:
                kwargs['files'][src_path] = files[src_path]

    userdata_file = config.get_cloud_config_value(
        'userdata_file', vm_, __opts__, search_global=False, default=None
    )
    if userdata_file is not None:
        try:
            with salt.utils.files.fopen(userdata_file, 'r') as fp_:
                kwargs['userdata'] = salt.utils.cloud.userdata_template(
                    __opts__, vm_, fp_.read()
                )
        except Exception as exc:
            log.exception(
                'Failed to read userdata from %s: %s', userdata_file, exc)

    kwargs['config_drive'] = config.get_cloud_config_value(
        'config_drive', vm_, __opts__, search_global=False
    )

    kwargs.update(get_block_mapping_opts(vm_))

    event_kwargs = {
        'name': kwargs['name'],
        'image': kwargs.get('image_id', 'Boot From Volume'),
        'size': kwargs['flavor_id'],
    }

    __utils__['cloud.fire_event'](
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        args={
            'kwargs': __utils__['cloud.filter_event']('requesting', event_kwargs, list(event_kwargs)),
        },
        sock_dir=__opts__['sock_dir'],
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
    if data.extra.get('password', None) is None and vm_.get('key_filename', None) is None:
        raise SaltCloudSystemExit('No password returned.  Set ssh_key_file.')

    floating_ip_conf = config.get_cloud_config_value('floating_ip',
                                                     vm_,
                                                     __opts__,
                                                     search_global=False,
                                                     default={})
    if floating_ip_conf.get('auto_assign', False):
        floating_ip = None
        if floating_ip_conf.get('ip_address', None) is not None:
            ip_address = floating_ip_conf.get('ip_address', None)
            try:
                fl_ip_dict = conn.floating_ip_show(ip_address)
                floating_ip = fl_ip_dict['ip']
            except Exception as err:
                raise SaltCloudSystemExit(
                    'Error assigning floating_ip for {0} on Nova\n\n'
                    'The following exception was thrown by libcloud when trying to '
                    'assign a floating ip: {1}\n'.format(
                        vm_['name'], err
                    )
                )

        else:
            pool = floating_ip_conf.get('pool', 'public')
            try:
                floating_ip = conn.floating_ip_create(pool)['ip']
            except Exception:
                log.info('A new IP address was unable to be allocated. '
                         'An IP address will be pulled from the already allocated list, '
                         'This will cause a race condition when building in parallel.')
                for fl_ip, opts in six.iteritems(conn.floating_ip_list()):
                    if opts['fixed_ip'] is None and opts['pool'] == pool:
                        floating_ip = fl_ip
                        break
                if floating_ip is None:
                    log.error('No IP addresses available to allocate for this server: %s', vm_['name'])

        def __query_node_data(vm_):
            try:
                node = show_instance(vm_['name'], 'action')
                log.debug('Loaded node data for %s:\n%s', vm_['name'], pprint.pformat(node))
            except Exception as err:
                log.error(
                    'Failed to get nodes list: %s', err,
                    # Show the traceback if the debug logging level is enabled
                    exc_info_on_loglevel=logging.DEBUG
                )
                # Trigger a failure in the wait for IP function
                return False
            return node['state'] == 'ACTIVE' or None

        # if we associate the floating ip here,then we will fail.
        # As if we attempt to associate a floating IP before the Nova instance has completed building,
        # it will fail.So we should associate it after the Nova instance has completed building.
        try:
            salt.utils.cloud.wait_for_ip(
                __query_node_data,
                update_args=(vm_,)
            )
        except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
            try:
                # It might be already up, let's destroy it!
                destroy(vm_['name'])
            except SaltCloudSystemExit:
                pass
            finally:
                raise SaltCloudSystemExit(six.text_type(exc))

        try:
            conn.floating_ip_associate(vm_['name'], floating_ip)
            vm_['floating_ip'] = floating_ip
        except Exception as exc:
            raise SaltCloudSystemExit(
                'Error assigning floating_ip for {0} on Nova\n\n'
                'The following exception was thrown by libcloud when trying to '
                'assign a floating ip: {1}\n'.format(
                    vm_['name'], exc
                )
            )

    if not vm_.get('password', None):
        vm_['password'] = data.extra.get('password', '')

    return data, vm_


def _query_node_data(vm_, data, conn):
    try:
        node = show_instance(vm_['name'], 'action')
        log.debug('Loaded node data for %s:\n%s', vm_['name'], pprint.pformat(node))
    except Exception as err:
        # Show the traceback if the debug logging level is enabled
        log.error(
            'Failed to get nodes list: %s', err,
            exc_info_on_loglevel=logging.DEBUG
        )
        # Trigger a failure in the wait for IP function
        return False

    running = node['state'] == 'ACTIVE'
    if not running:
        # Still not running, trigger another iteration
        return

    if rackconnect(vm_) is True:
        extra = node.get('extra', {})
        rc_status = extra.get('metadata', {}).get('rackconnect_automation_status', '')
        if rc_status != 'DEPLOYED':
            log.debug('Waiting for Rackconnect automation to complete')
            return

    if managedcloud(vm_) is True:
        extra = conn.server_show_libcloud(node['id']).extra
        mc_status = extra.get('metadata', {}).get('rax_service_level_automation', '')

        if mc_status != 'Complete':
            log.debug('Waiting for managed cloud automation to complete')
            return

    access_ip = node.get('extra', {}).get('access_ip', '')

    rcv3 = rackconnectv3(vm_) in node['addresses']
    sshif = ssh_interface(vm_) in node['addresses']

    if any((rcv3, sshif)):
        networkname = rackconnectv3(vm_) if rcv3 else ssh_interface(vm_)
        for network in node['addresses'].get(networkname, []):
            if network['version'] is 4:
                access_ip = network['addr']
                break
        vm_['cloudnetwork'] = True

    # Conditions to pass this
    #
    #     Rackconnect v2: vm_['rackconnect'] = True
    #         If this is True, then the server will not be accessible from the ipv4 addres in public_ips.
    #         That interface gets turned off, and an ipv4 from the dedicated firewall is routed to the
    #         server.  In this case we can use the private_ips for ssh_interface, or the access_ip.
    #
    #     Rackconnect v3: vm['rackconnectv3'] = <cloudnetwork>
    #         If this is the case, salt will need to use the cloud network to login to the server.  There
    #         is no ipv4 address automatically provisioned for these servers when they are booted.  SaltCloud
    #         also cannot use the private_ips, because that traffic is dropped at the hypervisor.
    #
    #     CloudNetwork: vm['cloudnetwork'] = True
    #         If this is True, then we should have an access_ip at this point set to the ip on the cloud
    #         network.  If that network does not exist in the 'addresses' dictionary, then SaltCloud will
    #         use the initial access_ip, and not overwrite anything.

    if (any((cloudnetwork(vm_), rackconnect(vm_)))
            and (ssh_interface(vm_) != 'private_ips' or rcv3)
            and access_ip != ''):
        data.public_ips = [access_ip]
        return data

    result = []

    if ('private_ips' not in node
            and 'public_ips' not in node
            and 'floating_ips' not in node
            and 'fixed_ips' not in node
            and 'access_ip' in node.get('extra', {})):
        result = [node['extra']['access_ip']]

    private = node.get('private_ips', [])
    public = node.get('public_ips', [])
    fixed = node.get('fixed_ips', [])
    floating = node.get('floating_ips', [])

    if private and not public:
        log.warning('Private IPs returned, but not public. '
                    'Checking for misidentified IPs')
        for private_ip in private:
            private_ip = preferred_ip(vm_, [private_ip])
            if private_ip is False:
                continue
            if salt.utils.cloud.is_public_ip(private_ip):
                log.warning('%s is a public IP', private_ip)
                data.public_ips.append(private_ip)
                log.warning('Public IP address was not ready when we last checked. '
                            'Appending public IP address now.')
                public = data.public_ips
            else:
                log.warning('%s is a private IP', private_ip)
                ignore_ip = ignore_cidr(vm_, private_ip)
                if private_ip not in data.private_ips and not ignore_ip:
                    result.append(private_ip)

    # populate return data with private_ips
    # when ssh_interface is set to private_ips and public_ips exist
    if not result and ssh_interface(vm_) == 'private_ips':
        for private_ip in private:
            ignore_ip = ignore_cidr(vm_, private_ip)
            if private_ip not in data.private_ips and not ignore_ip:
                result.append(private_ip)

    non_private_ips = []

    if public:
        data.public_ips = public
        if ssh_interface(vm_) == 'public_ips':
            non_private_ips.append(public)

    if floating:
        data.floating_ips = floating
        if ssh_interface(vm_) == 'floating_ips':
            non_private_ips.append(floating)

    if fixed:
        data.fixed_ips = fixed
        if ssh_interface(vm_) == 'fixed_ips':
            non_private_ips.append(fixed)

    if non_private_ips:
        log.debug('result = %s', non_private_ips)
        data.private_ips = result
        if ssh_interface(vm_) != 'private_ips':
            return data

    if result:
        log.debug('result = %s', result)
        data.private_ips = result
        if ssh_interface(vm_) == 'private_ips':
            return data


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or 'nova',
                                                           vm_['profile'],
                                                           vm_=vm_) is False:
            return False
    except AttributeError:
        pass

    deploy = config.get_cloud_config_value('deploy', vm_, __opts__)
    key_filename = config.get_cloud_config_value(
        'ssh_key_file', vm_, __opts__, search_global=False, default=None
    )
    if key_filename is not None and not os.path.isfile(key_filename):
        raise SaltCloudConfigError(
            'The defined ssh_key_file \'{0}\' does not exist'.format(
                key_filename
            )
        )

    vm_['key_filename'] = key_filename

    __utils__['cloud.fire_event'](
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        args=__utils__['cloud.filter_event']('creating', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )
    conn = get_conn()

    if 'instance_id' in vm_:
        # This was probably created via another process, and doesn't have
        # things like salt keys created yet, so let's create them now.
        if 'pub_key' not in vm_ and 'priv_key' not in vm_:
            log.debug('Generating minion keys for \'%s\'', vm_['name'])
            vm_['priv_key'], vm_['pub_key'] = salt.utils.cloud.gen_keys(
                salt.config.get_cloud_config_value(
                    'keysize',
                    vm_,
                    __opts__
                )
            )
        data = conn.server_show_libcloud(vm_['instance_id'])
        if vm_['key_filename'] is None and 'change_password' in __opts__ and __opts__['change_password'] is True:
            vm_['password'] = salt.utils.pycrypto.secure_password()
            conn.root_password(vm_['instance_id'], vm_['password'])
    else:
        # Put together all of the information required to request the instance,
        # and then fire off the request for it
        data, vm_ = request_instance(vm_)

        # Pull the instance ID, valid for both spot and normal instances
        vm_['instance_id'] = data.id

    try:
        data = salt.utils.cloud.wait_for_ip(
            _query_node_data,
            update_args=(vm_, data, conn),
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
            raise SaltCloudSystemExit(six.text_type(exc))

    log.debug('VM is now running')

    if ssh_interface(vm_) == 'private_ips':
        ip_address = preferred_ip(vm_, data.private_ips)
    elif ssh_interface(vm_) == 'fixed_ips':
        ip_address = preferred_ip(vm_, data.fixed_ips)
    elif ssh_interface(vm_) == 'floating_ips':
        ip_address = preferred_ip(vm_, data.floating_ips)
    else:
        ip_address = preferred_ip(vm_, data.public_ips)
    log.debug('Using IP address %s', ip_address)

    if salt.utils.cloud.get_salt_interface(vm_, __opts__) == 'private_ips':
        salt_ip_address = preferred_ip(vm_, data.private_ips)
        log.info('Salt interface set to: %s', salt_ip_address)
    elif salt.utils.cloud.get_salt_interface(vm_, __opts__) == 'fixed_ips':
        salt_ip_address = preferred_ip(vm_, data.fixed_ips)
        log.info('Salt interface set to: %s', salt_ip_address)
    elif salt.utils.cloud.get_salt_interface(vm_, __opts__) == 'floating_ips':
        salt_ip_address = preferred_ip(vm_, data.floating_ips)
        log.info('Salt interface set to: %s', salt_ip_address)
    else:
        salt_ip_address = preferred_ip(vm_, data.public_ips)
        log.debug('Salt interface set to: %s', salt_ip_address)

    if not ip_address:
        raise SaltCloudSystemExit('A valid IP address was not found')

    vm_['ssh_host'] = ip_address
    vm_['salt_host'] = salt_ip_address

    ret = __utils__['cloud.bootstrap'](vm_, __opts__)

    ret.update(data.__dict__)

    if 'password' in ret['extra']:
        del ret['extra']['password']

    log.info('Created Cloud VM \'%s\'', vm_['name'])
    log.debug(
        '\'%s\' VM creation details:\n%s',
        vm_['name'], pprint.pformat(data.__dict__)
    )

    event_data = {
        'name': vm_['name'],
        'profile': vm_['profile'],
        'provider': vm_['driver'],
        'instance_id': vm_['instance_id'],
        'floating_ips': data.floating_ips,
        'fixed_ips': data.fixed_ips,
        'private_ips': data.private_ips,
        'public_ips': data.public_ips
    }

    __utils__['cloud.fire_event'](
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        args=__utils__['cloud.filter_event']('created', event_data, list(event_data)),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )
    __utils__['cloud.cachedir_index_add'](vm_['name'], vm_['profile'], 'nova', vm_['driver'])
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
        server_tmp = conn.server_show(server_list[server]['id']).get(server)

        # If the server is deleted while looking it up, skip
        if server_tmp is None:
            continue

        private = []
        public = []
        if 'addresses' not in server_tmp:
            server_tmp['addresses'] = {}
        for network in server_tmp['addresses']:
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

    __utils__['cloud.cache_node_list'](ret, __active_provider_name__.split(':')[0], __opts__)
    return ret


def list_nodes_min(call=None, **kwargs):
    '''
    Return a list of the VMs that in this location
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            (
                'The list_nodes_min function must be called with'
                ' -f or --function.'
            )
        )

    conn = get_conn()
    server_list = conn.server_list_min()

    if not server_list:
        return {}
    return server_list


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
        volumes = salt.utils.yaml.safe_load(kwargs['volumes'])
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


def floating_ip_pool_list(call=None):
    '''
    List all floating IP pools

    .. versionadded:: 2016.3.0
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The floating_ip_pool_list action must be called with -f or --function'
        )

    conn = get_conn()
    return conn.floating_ip_pool_list()


def floating_ip_list(call=None):
    '''
    List floating IPs

    .. versionadded:: 2016.3.0
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The floating_ip_list action must be called with -f or --function'
        )

    conn = get_conn()
    return conn.floating_ip_list()


def floating_ip_create(kwargs, call=None):
    '''
    Allocate a floating IP

    .. versionadded:: 2016.3.0
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The floating_ip_create action must be called with -f or --function'
        )

    if 'pool' not in kwargs:
        log.error('pool is required')
        return False

    conn = get_conn()
    return conn.floating_ip_create(kwargs['pool'])


def floating_ip_delete(kwargs, call=None):
    '''
    De-allocate floating IP

    .. versionadded:: 2016.3.0
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The floating_ip_delete action must be called with -f or --function'
        )

    if 'floating_ip' not in kwargs:
        log.error('floating_ip is required')
        return False

    conn = get_conn()
    return conn.floating_ip_delete(kwargs['floating_ip'])


def floating_ip_associate(name, kwargs, call=None):
    '''
    Associate a floating IP address to a server

    .. versionadded:: 2016.3.0
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The floating_ip_associate action must be called with -a of --action.'
        )

    if 'floating_ip' not in kwargs:
        log.error('floating_ip is required')
        return False

    conn = get_conn()
    conn.floating_ip_associate(name, kwargs['floating_ip'])
    return list_nodes()[name]


def floating_ip_disassociate(name, kwargs, call=None):
    '''
    Disassociate a floating IP from a server

    .. versionadded:: 2016.3.0
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The floating_ip_disassociate action must be called with -a of --action.'
        )

    if 'floating_ip' not in kwargs:
        log.error('floating_ip is required')
        return False

    conn = get_conn()
    conn.floating_ip_disassociate(name, kwargs['floating_ip'])
    return list_nodes()[name]
