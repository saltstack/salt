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
      # The OpenStack Nova network UUIDs
      networks:
          - fixed:
              - 4402cd51-37ee-435e-a966-8245956dc0e6
          - floating:
              - Ext-Net

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

'''
# pylint: disable=E0102

# The import section is mostly libcloud boilerplate

# Import python libs
import os
import copy
import logging
import socket
import pprint

# Import generic libcloud functions
from salt.cloud.libcloudfuncs import *   # pylint: disable=W0614,W0401
from salt.utils.openstack import nova

# Import nova libs
HASNOVA = False
try:
    from novaclient.v1_1 import client  # pylint: disable=W0611
    import novaclient.exceptions
    HASNOVA = True
except ImportError:
    pass

# Import salt libs
import salt.utils
import salt.client

# Import salt.cloud libs
import salt.utils.cloud
import salt.config as config
from salt.utils import namespaced_function
from salt.cloud.exceptions import (
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


# Some of the libcloud functions need to be in the same namespace as the
# functions defined in the module, so we create new function objects inside
# this module namespace
avail_locations = namespaced_function(avail_locations, globals())
script = namespaced_function(script, globals())
destroy = namespaced_function(destroy, globals())
reboot = namespaced_function(reboot, globals())


# Only load in this module is the OPENSTACK configurations are in place
def __virtual__():
    '''
    Check for Nova configurations
    '''
    if get_configured_provider() is False:
        return False

    return True


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


def get_image(conn, vm_):
    '''
    Return the image object to use
    '''
    image_list = conn.image_list()

    vm_image = config.get_cloud_config_value('image', vm_, __opts__).encode(
        'ascii', 'salt-cloud-force-ascii'
    )

    for img in image_list.keys():
        if vm_image in (image_list[img]['id'], img):
            return image_list[img]['id']

    try:
        image = conn.image_show(vm_image)
        return image['id']
    except novaclient.exceptions.NotFound as exc:
        raise SaltCloudNotFound(
            'The specified image, {0!r}, could not be found: {1}'.format(
                vm_image,
                exc.message
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
    return conn.show_instance(name)


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
        if __opts__['delete_sshkeys'] is True:
            salt.utils.cloud.remove_sshkey(node.public_ips[0])
        return True

    log.error('Failed to Destroy VM: {0}'.format(name))
    return False


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

    if deploy is True and key_filename is None and \
            salt.utils.which('sshpass') is None:
        raise SaltCloudSystemExit(
            'Cannot deploy salt in a VM if the \'ssh_key_file\' setting '
            'is not set and \'sshpass\' binary is not present on the '
            'system for the password.'
        )

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

    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    salt.utils.cloud.check_name(vm_['name'], 'a-zA-Z0-9._-')
    conn = get_conn()
    kwargs = {
        'name': vm_['name']
    }

    try:
        kwargs['image_id'] = get_image(conn, vm_)
    except Exception as exc:
        log.error(
            'Error creating {0} on OPENSTACK\n\n'
            'Could not find image {1}: {2}\n'.format(
                vm_['name'], vm_['image'], exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return False

    try:
        kwargs['flavor_id'] = get_size(conn, vm_)
    except Exception as exc:
        log.error(
            'Error creating {0} on OPENSTACK\n\n'
            'Could not find size {1}: {2}\n'.format(
                vm_['name'], vm_['size'], exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return False

    kwargs['key_name'] = config.get_cloud_config_value(
        'ssh_key_name', vm_, __opts__, search_global=False
    )

    security_groups = config.get_cloud_config_value(
        'security_groups', vm_, __opts__, search_global=False
    )
    if security_groups is not None:
        vm_groups = security_groups.split(',')
        avail_groups = conn.ex_list_security_groups()
        group_list = []

        for vmg in vm_groups:
            if vmg in [ag.name for ag in avail_groups]:
                group_list.append(vmg)
            else:
                raise SaltCloudNotFound(
                    'No such security group: \'{0}\''.format(vmg)
                )

        kwargs['ex_security_groups'] = [
            g for g in avail_groups if g.name in group_list
        ]

    networks = config.get_cloud_config_value(
        'networks', vm_, __opts__, search_global=False
    )

    floating = []

    files = config.get_cloud_config_value(
        'files', vm_, __opts__, search_global=False
    )
    if files:
        kwargs['files'] = {}
        for src_path in files:
            with salt.utils.fopen(files[src_path], 'r') as fp_:
                kwargs['files'][src_path] = fp_.read()
    userdata_file = config.get_cloud_config_value(
        'userdata_file', vm_, __opts__, search_global=False
    )

    if userdata_file is not None:
        with salt.utils.fopen(userdata_file, 'r') as fp:
            kwargs['ex_userdata'] = fp.read()

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
        log.error(
            'Error creating {0} on Nova\n\n'
            'The following exception was thrown by libcloud when trying to '
            'run the initial deployment: {1}\n'.format(
                vm_['name'], exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return False

    def __query_node_data(vm_, data, floating):
        try:
            nodelist = list_nodes_full()
            log.debug(
                'Loaded node data for {0}:\n{1}'.format(
                    vm_['name'],
                    pprint.pformat(
                        nodelist[vm_['name']].__dict__
                    )
                )
            )
        except Exception as err:
            log.error(
                'Failed to get nodes list: {0}'.format(
                    err
                ),
                # Show the traceback if the debug logging level is enabled
                exc_info=log.isEnabledFor(logging.DEBUG)
            )
            # Trigger a failure in the wait for IP function
            return False

        running = nodelist[vm_['name']].state == 'ACTIVE'
        if not running:
            # Still not running, trigger another iteration
            return

        if rackconnect(vm_) is True:
            extra = nodelist[vm_['name']].get('extra', {})
            rc_status = extra.get('metadata', {}).get(
                'rackconnect_automation_status', '')
            access_ip = extra.get('access_ip', '')

            if rc_status != 'DEPLOYED':
                log.debug('Waiting for Rackconnect automation to complete')
                return

        if managedcloud(vm_) is True:
            extra = conn.server_show_libcloud(
                nodelist[vm_['name']].id
            ).extra
            mc_status = extra.get('metadata', {}).get(
                'rax_service_level_automation', '')

            if mc_status != 'Complete':
                log.debug('Waiting for managed cloud automation to complete')
                return

        if floating:
            try:
                name = data.name
                ip = floating[0].ip_address
                conn.ex_attach_floating_ip_to_node(data, ip)
                log.info(
                    (
                        'Attaching floating IP "{0}"'
                        ' to node "{1}"'
                    ).format(ip, name)
                )
            except Exception as e:
                # Note(pabelanger): Because we loop, we only want to attach the
                # floating IP address one. So, expect failures if the IP is
                # already attached.
                pass

        result = []
        private = nodelist[vm_['name']].private_ips
        public = nodelist[vm_['name']].public_ips
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
            if ssh_interface(vm_) != 'private_ips':
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
            update_args=(vm_, data, floating),
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
            raise SaltCloudSystemExit(exc.message)

    log.debug('VM is now running')

    if ssh_interface(vm_) == 'private_ips':
        ip_address = preferred_ip(vm_, data.private_ips)
    elif rackconnect(vm_) is True and ssh_interface(vm_) != 'private_ips':
        ip_address = data.public_ips
    else:
        ip_address = preferred_ip(vm_, data.public_ips)
    log.debug('Using IP address {0}'.format(ip_address))

    if not ip_address:
        raise SaltCloudSystemExit('A valid IP address was not found')

    ssh_username = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__, default='root'
    )

    deploy_kwargs = {
         'opts': __opts__,
        'host': ip_address,
        'name': vm_['name'],
        'sock_dir': __opts__['sock_dir'],
        'tmp_dir': config.get_cloud_config_value(
            'tmp_dir', vm_, __opts__, default='/tmp/.saltcloud'
        ),
        'deploy_command': config.get_cloud_config_value(
            'deploy_command', vm_, __opts__,
            default='/tmp/.saltcloud/deploy.sh',
        ),
        'start_action': __opts__['start_action'],
        'parallel': __opts__['parallel'],
        'minion_pem': vm_['priv_key'],
        'minion_pub': vm_['pub_key'],
        'keep_tmp': __opts__['keep_tmp'],
        'preseed_minion_keys': vm_.get('preseed_minion_keys', None),
        'sudo': config.get_cloud_config_value(
            'sudo', vm_, __opts__, default=(ssh_username != 'root')
        ),
        'sudo_password': config.get_cloud_config_value(
            'sudo_password', vm_, __opts__, default=None
        ),
        'tty': config.get_cloud_config_value(
            'tty', vm_, __opts__, default=False
        ),
        'display_ssh_output': config.get_cloud_config_value(
            'display_ssh_output', vm_, __opts__, default=True
        ),
        'script_args': config.get_cloud_config_value(
            'script_args', vm_, __opts__
        ),
        'script_env': config.get_cloud_config_value(
            'script_env',
            vm_,
            __opts__
        ),
        'minion_conf': salt.utils.cloud.minion_config(__opts__, vm_)
    }

    if ssh_username != 'root':
        deploy_kwargs['username'] = ssh_username
        deploy_kwargs['tty'] = True

    log.debug('Using {0} as SSH username'.format(ssh_username))

    if key_filename is not None:
        deploy_kwargs['key_filename'] = key_filename
        log.debug(
            'Using {0} as SSH key file'.format(key_filename)
        )
    elif 'password' in data.extra:
        deploy_kwargs['password'] = data.extra['password']
        log.debug('Logging into SSH using password')

    ret = {}
    if config.get_cloud_config_value('deploy', vm_, __opts__) is True:
        deploy_script = script(vm_)
        deploy_kwargs['script'] = deploy_script.script

        # Deploy salt-master files, if necessary
        if config.get_cloud_config_value('make_master', vm_, __opts__) is True:
            deploy_kwargs['make_master'] = True
            deploy_kwargs['master_pub'] = vm_['master_pub']
            deploy_kwargs['master_pem'] = vm_['master_pem']
            master_conf = salt.utils.cloud.master_config(__opts__, vm_)
            deploy_kwargs['master_conf'] = master_conf

            if master_conf.get('syndic_master', None):
                deploy_kwargs['make_syndic'] = True

        deploy_kwargs['make_minion'] = config.get_cloud_config_value(
            'make_minion', vm_, __opts__, default=True
        )

        # Check for Windows install params
        win_installer = config.get_cloud_config_value(
            'win_installer',
            vm_,
            __opts__
        )
        if win_installer:
            deploy_kwargs['win_installer'] = win_installer
            minion = salt.utils.cloud.minion_config(__opts__, vm_)
            deploy_kwargs['master'] = minion['master']
            deploy_kwargs['username'] = config.get_cloud_config_value(
                'win_username', vm_, __opts__, default='Administrator'
            )
            deploy_kwargs['password'] = config.get_cloud_config_value(
                'win_password', vm_, __opts__, default=''
            )

        # Store what was used to the deploy the VM
        event_kwargs = copy.deepcopy(deploy_kwargs)
        del event_kwargs['minion_pem']
        del event_kwargs['minion_pub']
        del event_kwargs['sudo_password']
        if 'password' in event_kwargs:
            del event_kwargs['password']
        ret['deploy_kwargs'] = event_kwargs

        salt.utils.cloud.fire_event(
            'event',
            'executing deploy script',
            'salt/cloud/{0}/deploying'.format(vm_['name']),
            {'kwargs': event_kwargs},
            transport=__opts__['transport']
        )

        deployed = False
        if win_installer:
            deployed = salt.utils.cloud.deploy_windows(**deploy_kwargs)
        else:
            deployed = salt.utils.cloud.deploy_script(**deploy_kwargs)

        if deployed:
            log.info('Salt installed on {0}'.format(vm_['name']))
        else:
            log.error(
                'Failed to deploy and start Salt on Cloud VM {0}'.format(
                    vm_['name']
                )
            )

    ret.update(data.__dict__)

    if 'password' in data.extra:
        del data.extra['password']

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


def avail_locations():
    '''
    Would normally return a list of available datacenters (ComputeRegions?
    Availability Zones?), but those don't seem to be available via the nova
    client.
    '''
    return {}


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
    for server in server_list.keys():
        server_tmp = conn.server_show(server_list[server]['id'])[server]
        ret[server] = {
            'id': server_tmp['id'],
            'image': server_tmp['image']['id'],
            'size': server_tmp['flavor']['id'],
            'state': server_tmp['status'],
            'private_ips': [server_tmp['accessIPv4']],
            'public_ips': [server_tmp['accessIPv4'], server_tmp['accessIPv6']],
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
    for server in server_list.keys():
        ret[server] = conn.server_show_libcloud(
            server_list[server]['id']
        )
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
    return conn.volume_create(
        name,
        size,
        snapshot,
        voltype
    )


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


def volume_list(**kwargs):
    '''
    Attach block volume
    '''
    conn = get_conn()
    return conn.volume_list()
