# -*- coding: utf-8 -*-
'''
OpenStack Cloud Module
======================

OpenStack is an open source project that is in use by a number a cloud
providers, each of which have their own ways of using it.

OpenStack provides a number of ways to authenticate. This module uses password-
based authentication, using auth v2.0. It is likely to start supporting other
methods of authentication provided by OpenStack in the future.

Note that there is currently a dependency upon netaddr. This can be installed
on Debian-based systems by means of the python-netaddr package.

This module has been tested to work with HP Cloud and Rackspace. See the
documentation for specific options for either of these providers. Some
examples, using the old cloud configuration syntax, are provided below:

Set up in the cloud configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/openstack.conf``:


.. code-block:: yaml

    my-openstack-config:
      # The OpenStack identity service url
      identity_url: https://region-a.geo-1.identity.hpcloudsvc.com:35357/v2.0/
      # The OpenStack compute region
      compute_region: az-1.region-a.geo-1
      # The OpenStack compute service name
      compute_name: Compute
      # The OpenStack tenant name (not tenant ID)
      tenant: myuser-tenant1
      # The OpenStack user name
      user: myuser
      # The OpenStack keypair name
      ssh_key_name
      # The OpenStack network UUIDs
      networks:
          - fixed:
              - 4402cd51-37ee-435e-a966-8245956dc0e6
          - floating:
              - Ext-Net
      files:
          /path/to/dest.txt
              /local/path/to/src.txt

      provider: openstack
      userdata_file: /tmp/userdata.txt

For in-house Openstack Essex installation, libcloud needs the service_type :

.. code-block:: yaml

  my-openstack-config:
    identity_url: 'http://control.openstack.example.org:5000/v2.0/'
    compute_name : Compute Service
    service_type : compute


Either a password or an API key must also be specified:

.. code-block:: yaml

    my-openstack-password-or-api-config:
      # The OpenStack password
      password: letmein
      # The OpenStack API key
      apikey: 901d3f579h23c8v73q9


For local installations that only use private IP address ranges, the
following option may be useful. Using the old syntax:

.. code-block:: yaml

    my-openstack-config:
      # Ignore IP addresses on this network for bootstrap
      ignore_cidr: 192.168.50.0/24

It is possible to upload a small set of files (no more than 5, and nothing too
large) to the remote server. Generally this should not be needed, as salt itself
can upload to the server after it is spun up, with nowhere near the same
restrictions.

.. code-block:: yaml

    my-openstack-config:
      files:
          /path/to/dest.txt
              /local/path/to/src.txt
'''

# The import section is mostly libcloud boilerplate

# Import python libs
import os
import copy
import logging
import socket
import pprint

# Import libcloud
from libcloud.compute.base import NodeState

# These functions requre libcloud trunk or >= 0.14.0
HAS014 = False
try:
    from libcloud.compute.drivers.openstack import OpenStackNetwork
    from libcloud.compute.drivers.openstack import OpenStack_1_1_FloatingIpPool
    HAS014 = True
except Exception:
    pass

# Import generic libcloud functions
from salt.cloud.libcloudfuncs import *   # pylint: disable=W0614,W0401

# Import salt libs
import salt.utils

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
get_size = namespaced_function(get_size, globals())
get_image = namespaced_function(get_image, globals())
avail_locations = namespaced_function(avail_locations, globals())
avail_images = namespaced_function(avail_images, globals())
avail_sizes = namespaced_function(avail_sizes, globals())
script = namespaced_function(script, globals())
destroy = namespaced_function(destroy, globals())
reboot = namespaced_function(reboot, globals())
list_nodes = namespaced_function(list_nodes, globals())
list_nodes_full = namespaced_function(list_nodes_full, globals())
list_nodes_select = namespaced_function(list_nodes_select, globals())
show_instance = namespaced_function(show_instance, globals())


# Only load in this module is the OPENSTACK configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for OPENSTACK configurations
    '''
    if get_configured_provider() is False:
        log.debug(
            'There is no Openstack cloud provider configuration available. '
            'Not loading module.'
        )
        return False

    log.debug('Loading Openstack cloud module')
    return True


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'openstack',
        ('user',)
    )


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    vm_ = get_configured_provider()
    driver = get_driver(Provider.OPENSTACK)
    authinfo = {
        'ex_force_auth_url': config.get_cloud_config_value(
            'identity_url', vm_, __opts__, search_global=False
        ),
        'ex_force_service_name': config.get_cloud_config_value(
            'compute_name', vm_, __opts__, search_global=False
        ),
        'ex_force_service_region': config.get_cloud_config_value(
            'compute_region', vm_, __opts__, search_global=False
        ),
        'ex_tenant_name': config.get_cloud_config_value(
            'tenant', vm_, __opts__, search_global=False
        ),
   }

    service_type = config.get_cloud_config_value(
            'service_type', vm_, __opts__, search_global=False
        )
    if service_type:
        authinfo['ex_force_service_type'] = service_type

    insecure = config.get_cloud_config_value(
        'insecure', vm_, __opts__, search_global=False
    )
    if insecure:
        import libcloud.security
        libcloud.security.VERIFY_SSL_CERT = False

    password = config.get_cloud_config_value(
        'password', vm_, __opts__, search_global=False
    )
    if password is not None:
        authinfo['ex_force_auth_version'] = '2.0_password'
        log.debug('OpenStack authenticating using password')
        return driver(
            config.get_cloud_config_value(
                'user', vm_, __opts__, search_global=False
            ),
            password,
            **authinfo
        )

    authinfo['ex_force_auth_version'] = '2.0_apikey'
    log.debug('OpenStack authenticating using apikey')
    return driver(
        config.get_cloud_config_value('user', vm_, __opts__, search_global=False),
        config.get_cloud_config_value('apikey', vm_, __opts__, search_global=False),
        **authinfo
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
        # If we cannot check, assume all is ok
        return False

    cidr = config.get_cloud_config_value(
        'ignore_cidr', vm_, __opts__, default='', search_global=False
    )
    if cidr != '' and all_matching_cidrs(ip, [cidr]):
        log.warning('IP "{0}" found within "{1}"; ignoring it.'.format(ip, cidr))
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
    )

    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    salt.utils.cloud.check_name(vm_['name'], 'a-zA-Z0-9._-')
    conn = get_conn()
    kwargs = {
        'name': vm_['name']
    }

    try:
        kwargs['image'] = get_image(conn, vm_)
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
        kwargs['size'] = get_size(conn, vm_)
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

    kwargs['ex_keyname'] = config.get_cloud_config_value(
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

    if HAS014 and networks is not None:
        for net in networks:
            if 'fixed' in net:
                kwargs['networks'] = [
                    OpenStackNetwork(n, None, None, None) for n in net['fixed']
                ]
            elif 'floating' in net:
                pool = OpenStack_1_1_FloatingIpPool(
                    net['floating'], conn.connection
                )
                for idx in pool.list_floating_ips():
                    if idx.node_id is None:
                        floating.append(idx)
                if not floating:
                    # Note(pabelanger): We have no available floating IPs. For
                    # now, we raise an execption and exit. A future enhancement
                    # might be to allow salt-cloud to dynamically allociate new
                    # address but that might be tricky to manage.
                    raise SaltCloudSystemExit(
                        "Floating pool '%s' has not more address available, "
                        "please create some more or use a different pool." %
                        net['floating']
                    )

    files = config.get_cloud_config_value(
        'files', vm_, __opts__, search_global=False
    )
    if files:
        kwargs['ex_files'] = {}
        for src_path in files:
            with salt.utils.fopen(files[src_path], 'r') as fp_:
                kwargs['ex_files'][src_path] = fp_.read()

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
                    'image': kwargs['image'].name,
                    'size': kwargs['size'].name}},
    )

    kwargs['ex_metadata'] = config.get_cloud_config_value(
        'metadata', vm_, __opts__, default={}, search_global=False
    )
    if not isinstance(kwargs['ex_metadata'], dict):
        raise SaltCloudConfigError(
                '\'metadata\' should be a dict.'
        )

    try:
        data = conn.create_node(**kwargs)
    except Exception as exc:
        log.error(
            'Error creating {0} on OpenStack\n\n'
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
            nodelist = list_nodes()
            log.debug(
                'Loaded node data for {0}:\n{1}'.format(
                    vm_['name'],
                    pprint.pformat(
                        nodelist[vm_['name']]
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

        running = nodelist[vm_['name']]['state'] == node_state(
            NodeState.RUNNING
        )
        if not running:
            # Still not running, trigger another iteration
            return

        if rackconnect(vm_) is True:
            extra = nodelist[vm_['name']].get('extra')
            rc_status = extra.get('metadata').get('rackconnect_automation_status')
            access_ip = extra.get('access_ip')

            if rc_status != 'DEPLOYED':
                log.debug('Waiting for Rackconnect automation to complete')
                return

        if managedcloud(vm_) is True:
            extra = nodelist[vm_['name']].get('extra')
            mc_status = extra.get('metadata').get('rax_service_level_automation')

            if mc_status != 'Complete':
                log.debug('Waiting for managed cloud automation to complete')
                return

        if floating:
            try:
                name = data.name
                ip = floating[0].ip_address
                conn.ex_attach_floating_ip_to_node(data, ip)
                log.info(
                    'Attaching floating IP "{0}" to node "{1}"'.format(ip, name)
                )
            except Exception:
                # Note(pabelanger): Because we loop, we only want to attach the
                # floating IP address one. So, expect failures if the IP is
                # already attached.
                pass

        result = []
        private = nodelist[vm_['name']]['private_ips']
        public = nodelist[vm_['name']]['public_ips']
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
                        'Public IP address was not ready when we last checked.  Appending public IP address now.'
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

        # populate return data with private_ips
        # when ssh_interface is set to private_ips and public_ips exist
        if not result and ssh_interface(vm_) == 'private_ips':
            for private_ip in private:
                ignore_ip = ignore_cidr(vm_, private_ip)
                if private_ip not in data.private_ips and not ignore_ip:
                    result.append(private_ip)

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
    elif (rackconnect(vm_) is True and ssh_interface(vm_) != 'private_ips'):
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
        'display_ssh_output': config.get_cloud_config_value(
            'display_ssh_output', vm_, __opts__, default=True
        ),
        'script_args': config.get_cloud_config_value(
            'script_args', vm_, __opts__
        ),
        'script_env': config.get_cloud_config_value('script_env', vm_, __opts__),
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
    sudo = config.get_cloud_config_value(
        'sudo', vm_, __opts__, default=(ssh_username != 'root')
    )
    if sudo is not None:
        deploy_kwargs['sudo'] = sudo
        log.debug('Running root commands using sudo')

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
        win_installer = config.get_cloud_config_value('win_installer', vm_, __opts__)
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

    log.info('Created Cloud VM {0[name]!r}'.format(vm_))
    log.debug(
        '{0[name]!r} VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data.__dict__)
        )
    )

    ret.update(data.__dict__)

    salt.utils.cloud.fire_event(
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
    )

    return ret
