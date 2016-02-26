# -*- coding: utf-8 -*-
'''
OpenStack Cloud Module
======================

OpenStack is an open source project that is in use by a number a cloud
providers, each of which have their own ways of using it.

:depends: libcloud >= 0.13.2

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
      identity_url: https://region-b.geo-1.identity.hpcloudsvc.com:35357/v2.0/
      # The OpenStack compute region
      compute_region: region-b.geo-1
      # The OpenStack compute service name
      compute_name: Compute
      # The OpenStack tenant name (not tenant ID)
      tenant: myuser-tenant1
      # The OpenStack user name
      user: myuser
      # The OpenStack keypair name
      ssh_key_name: mykey
      # Skip SSL certificate validation
      insecure: false
      # The ssh key file
      ssh_key_file: /path/to/keyfile/test.pem
      # The OpenStack network UUIDs
      networks:
          - fixed:
              - 4402cd51-37ee-435e-a966-8245956dc0e6
          - floating:
              - Ext-Net
      files:
          /path/to/dest.txt:
              /local/path/to/src.txt
      # Skips the service catalog API endpoint, and uses the following
      base_url: http://192.168.1.101:3000/v2/12345
      driver: openstack
      userdata_file: /tmp/userdata.txt
      # config_drive is required for userdata at rackspace
      config_drive: True

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

Optionally, if you don't want to save plain-text password in your configuration file, you can use keyring:

.. code-block:: yaml

    my-openstack-keyring-config:
      # The OpenStack password is stored in keyring
      # don't forget to set the password by running something like:
      # salt-cloud --set-password=myuser my-openstack-keyring-config
      password: USE_KEYRING

For local installations that only use private IP address ranges, the
following option may be useful. Using the old syntax:

.. code-block:: yaml

    my-openstack-config:
      # Ignore IP addresses on this network for bootstrap
      ignore_cidr: 192.168.50.0/24

It is possible to upload a small set of files (no more than 5, and nothing too
large) to the remote server. Generally this should not be needed, as salt
itself can upload to the server after it is spun up, with nowhere near the
same restrictions.

.. code-block:: yaml

    my-openstack-config:
      files:
          /path/to/dest.txt:
              /local/path/to/src.txt

Alternatively, one could use the private IP to connect by specifying:

.. code-block:: yaml

    my-openstack-config:
      ssh_interface: private_ips


'''

# Import python libs
from __future__ import absolute_import
import os
import logging
import socket
import pprint

# Import libcloud
try:
    from libcloud.compute.base import NodeState
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False

# These functions require libcloud trunk or >= 0.14.0
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

__virtualname__ = 'openstack'


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
get_node = namespaced_function(get_node, globals())


# Only load in this module is the OPENSTACK configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for OPENSTACK configurations
    '''
    if get_configured_provider() is False:
        return False

    if get_dependencies() is False:
        return False

    salt.utils.warn_until(
        'Carbon',
        'This driver has been deprecated and will be removed in the '
        'Carbon release of Salt. Please use the nova driver instead.'
    )

    return __virtualname__


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ('user',)
    )


def get_dependencies():
    '''
    Warn if dependencies aren't met.
    '''
    deps = {
        'libcloud': HAS_LIBCLOUD,
        'netaddr': HAS_NETADDR
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

    service_type = config.get_cloud_config_value('service_type',
                                                 vm_,
                                                 __opts__,
                                                 search_global=False)
    if service_type:
        authinfo['ex_force_service_type'] = service_type

    base_url = config.get_cloud_config_value('base_url',
                                             vm_,
                                             __opts__,
                                             search_global=False)

    if base_url:
        authinfo['ex_force_base_url'] = base_url

    insecure = config.get_cloud_config_value(
        'insecure', vm_, __opts__, search_global=False
    )
    if insecure:
        import libcloud.security
        libcloud.security.VERIFY_SSL_CERT = False

    user = config.get_cloud_config_value(
        'user', vm_, __opts__, search_global=False
    )
    password = config.get_cloud_config_value(
        'password', vm_, __opts__, search_global=False
    )

    if password is not None:
        authinfo['ex_force_auth_version'] = '2.0_password'
        log.debug('OpenStack authenticating using password')
        if password == 'USE_KEYRING':
            # retrieve password from system keyring
            credential_id = "salt.cloud.provider.{0}".format(__active_provider_name__)
            logging.debug("Retrieving keyring password for {0} ({1})".format(
                credential_id,
                user)
            )
            # attempt to retrieve driver specific password first
            driver_password = salt.utils.cloud.retrieve_password_from_keyring(
                credential_id,
                user
            )
            if driver_password is None:
                provider_password = salt.utils.cloud.retrieve_password_from_keyring(
                    credential_id.split(':')[0],  # fallback to provider level
                    user)
                if provider_password is None:
                    raise SaltCloudSystemExit(
                        "Unable to retrieve password from keyring for provider {0}".format(
                            __active_provider_name__
                        )
                    )
                else:
                    actual_password = provider_password
            else:
                actual_password = driver_password
        else:
            actual_password = password
        return driver(
            user,
            actual_password,
            **authinfo
        )

    authinfo['ex_force_auth_version'] = '2.0_apikey'
    log.debug('OpenStack authenticating using apikey')
    return driver(
        user,
        config.get_cloud_config_value('apikey', vm_, __opts__,
                                      search_global=False), **authinfo)


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
        log.warning(
            'IP \'{0}\' found within \'{1}\'; ignoring it.'.format(ip, cidr)
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


def networks(vm_, kwargs=None):
    conn = get_conn()
    if kwargs is None:
        kwargs = {}

    floating = _assign_floating_ips(vm_, conn, kwargs)
    vm_['floating'] = floating


def request_instance(vm_=None, call=None):
    '''
    Put together all of the information necessary to request an instance on Openstack
    and then fire off the request the instance.

    Returns data about the instance
    '''
    if call == 'function':
        # Technically this function may be called other ways too, but it
        # definitely cannot be called with --function.
        raise SaltCloudSystemExit(
            'The request_instance action must be called with -a or --action.'
        )
    salt.utils.cloud.check_name(vm_['name'], 'a-zA-Z0-9._-')
    conn = get_conn()
    kwargs = {
        'name': vm_['name']
    }

    try:
        kwargs['image'] = get_image(conn, vm_)
    except Exception as exc:
        raise SaltCloudSystemExit(
            'Error creating {0} on OPENSTACK\n\n'
            'Could not find image {1}: {2}\n'.format(
                vm_['name'], vm_['image'], exc
            )
        )

    try:
        kwargs['size'] = get_size(conn, vm_)
    except Exception as exc:
        raise SaltCloudSystemExit(
            'Error creating {0} on OPENSTACK\n\n'
            'Could not find size {1}: {2}\n'.format(
                vm_['name'], vm_['size'], exc
            )
        )

    # Note: This currently requires libcloud trunk
    avz = config.get_cloud_config_value(
        'availability_zone', vm_, __opts__, default=None, search_global=False
    )
    if avz is not None:
        kwargs['ex_availability_zone'] = avz

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

    floating = _assign_floating_ips(vm_, conn, kwargs)
    vm_['floating'] = floating

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

    config_drive = config.get_cloud_config_value(
        'config_drive', vm_, __opts__, default=None, search_global=False
    )
    if config_drive is not None:
        kwargs['ex_config_drive'] = config_drive

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': {'name': kwargs['name'],
                    'image': kwargs['image'].name,
                    'size': kwargs['size'].name,
                    'profile': vm_['profile']}},
        transport=__opts__['transport']
    )

    default_profile = {}
    if 'profile' in vm_ and vm_['profile'] is not None:
        default_profile = {'profile': vm_['profile']}

    kwargs['ex_metadata'] = config.get_cloud_config_value(
        'metadata', vm_, __opts__, default=default_profile, search_global=False
    )
    if not isinstance(kwargs['ex_metadata'], dict):
        raise SaltCloudConfigError('\'metadata\' should be a dict.')

    try:
        data = conn.create_node(**kwargs)
    except Exception as exc:
        raise SaltCloudSystemExit(
            'Error creating {0} on OpenStack\n\n'
            'The following exception was thrown by libcloud when trying to '
            'run the initial deployment: {1}\n'.format(
                vm_['name'], exc
            )
        )

    vm_['password'] = data.extra.get('password', None)
    return data, vm_


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or 'openstack',
                                                           vm_['profile'],
                                                           vm_=vm_) is False:
            return False
    except AttributeError:
        pass

    # Since using "provider: <provider-engine>" is deprecated, alias provider
    # to use driver: "driver: <provider-engine>"
    if 'provider' in vm_:
        vm_['driver'] = vm_.pop('provider')

    deploy = config.get_cloud_config_value('deploy', vm_, __opts__)
    key_filename = config.get_cloud_config_value(
        'ssh_key_file', vm_, __opts__, search_global=False, default=None
    )
    if key_filename is not None:
        key_filename = os.path.expanduser(key_filename)
        if not os.path.isfile(key_filename):
            raise SaltCloudConfigError(
                'The defined ssh_key_file \'{0}\' does not exist'.format(
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
            'provider': vm_['driver'],
        },
        transport=__opts__['transport']
    )

    conn = get_conn()

    if 'instance_id' in vm_:
        # This was probably created via another process, and doesn't have
        # things like salt keys created yet, so let's create them now.
        if 'pub_key' not in vm_ and 'priv_key' not in vm_:
            log.debug('Generating minion keys for \'{0[name]}\''.format(vm_))
            vm_['priv_key'], vm_['pub_key'] = salt.utils.cloud.gen_keys(
                salt.config.get_cloud_config_value(
                    'keysize',
                    vm_,
                    __opts__
                )
            )
        data = conn.ex_get_node_details(vm_['instance_id'])
        if vm_['key_filename'] is None and 'change_password' in __opts__ and __opts__['change_password'] is True:
            vm_['password'] = sup.secure_password()
            conn.ex_set_password(data, vm_['password'])
        networks(vm_)
    else:
        # Put together all of the information required to request the instance,
        # and then fire off the request for it
        data, vm_ = request_instance(vm_)

        # Pull the instance ID, valid for both spot and normal instances
        vm_['instance_id'] = data.id

    def __query_node_data(vm_, data, floating):
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

        running = node['state'] == NodeState.RUNNING
        if not running:
            # Still not running, trigger another iteration
            return

        if rackconnect(vm_) is True:
            check_libcloud_version((0, 14, 0), why='rackconnect: True')
            extra = node.get('extra')
            rc_status = extra.get('metadata', {}).get(
                'rackconnect_automation_status', '')
            access_ip = extra.get('access_ip', '')

            if rc_status != 'DEPLOYED':
                log.debug('Waiting for Rackconnect automation to complete')
                return

        if managedcloud(vm_) is True:
            extra = node.get('extra')
            mc_status = extra.get('metadata', {}).get(
                'rax_service_level_automation', '')

            if mc_status != 'Complete':
                log.debug('Waiting for managed cloud automation to complete')
                return

        public = node['public_ips']
        if floating:
            try:
                name = data.name
                ip = floating[0].ip_address
                conn.ex_attach_floating_ip_to_node(data, ip)
                log.info(
                    'Attaching floating IP \'{0}\' to node \'{1}\''.format(
                        ip, name
                    )
                )
                data.public_ips.append(ip)
                public = data.public_ips
            except Exception:
                # Note(pabelanger): Because we loop, we only want to attach the
                # floating IP address one. So, expect failures if the IP is
                # already attached.
                pass

        result = []
        private = node['private_ips']
        if private and not public:
            log.warning(
                'Private IPs returned, but not public... Checking for '
                'misidentified IPs'
            )
            for private_ip in private:
                private_ip = preferred_ip(vm_, [private_ip])
                if salt.utils.cloud.is_public_ip(private_ip):
                    log.warning('{0} is a public IP'.format(private_ip))
                    data.public_ips.append(private_ip)
                    log.warning(
                        'Public IP address was not ready when we last checked.'
                        ' Appending public IP address now.'
                    )
                    public = data.public_ips
                else:
                    log.warning('{0} is a private IP'.format(private_ip))
                    ignore_ip = ignore_cidr(vm_, private_ip)
                    if private_ip not in data.private_ips and not ignore_ip:
                        result.append(private_ip)

        if rackconnect(vm_) is True and ssh_interface(vm_) != 'private_ips':
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
            update_args=(vm_, data, vm_['floating']),
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

    if salt.utils.cloud.get_salt_interface(vm_, __opts__) == 'private_ips':
        salt_ip_address = preferred_ip(vm_, data.private_ips)
        log.info('Salt interface set to: {0}'.format(salt_ip_address))
    else:
        salt_ip_address = preferred_ip(vm_, data.public_ips)
        log.debug('Salt interface set to: {0}'.format(salt_ip_address))

    if not ip_address:
        raise SaltCloudSystemExit('A valid IP address was not found')

    vm_['salt_host'] = salt_ip_address
    vm_['ssh_host'] = ip_address
    ret = salt.utils.cloud.bootstrap(vm_, __opts__)
    ret.update(data.__dict__)

    if hasattr(data, 'extra') and 'password' in data.extra:
        del data.extra['password']

    log.info('Created Cloud VM \'{0[name]}\''.format(vm_))
    log.debug(
        '\'{0[name]}\' VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data.__dict__)
        )
    )

    salt.utils.cloud.fire_event(
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
        transport=__opts__['transport']
    )

    return ret


def _assign_floating_ips(vm_, conn, kwargs):
    floating = []
    nets = config.get_cloud_config_value(
        'networks', vm_, __opts__, search_global=False
    )

    if HAS014:
        if nets is not None:
            for net in nets:
                if 'fixed' in net:
                    kwargs['networks'] = [
                        OpenStackNetwork(n, None, None, None)
                        for n in net['fixed']
                    ]
                elif 'floating' in net:
                    pool = OpenStack_1_1_FloatingIpPool(
                        net['floating'], conn.connection
                    )
                    for idx in [pool.create_floating_ip()]:
                        if idx.node_id is None:
                            floating.append(idx)
                    if not floating:
                        # Note(pabelanger): We have no available floating IPs.
                        # For now, we raise an exception and exit.
                        # A future enhancement might be to allow salt-cloud
                        # to dynamically allocate new address but that might
                        raise SaltCloudSystemExit(
                            'Floating pool \'{0}\' does not have any more '
                            'please create some more or use a different '
                            'pool.'.format(net['floating'])
                        )
        # otherwise, attempt to obtain list without specifying pool
        # this is the same as 'nova floating-ip-list'
        elif ssh_interface(vm_) != 'private_ips':
            try:
                # This try/except is here because it appears some
                # *cough* Rackspace *cough*
                # OpenStack providers return a 404 Not Found for the
                # floating ip pool URL if there are no pools setup
                pool = OpenStack_1_1_FloatingIpPool(
                    '', conn.connection
                )
                for idx in [pool.create_floating_ip()]:
                    if idx.node_id is None:
                        floating.append(idx)
                if not floating:
                    # Note(pabelanger): We have no available floating IPs.
                    # For now, we raise an exception and exit.
                    # A future enhancement might be to allow salt-cloud to
                    # dynamically allocate new address but that might be
                    # tricky to manage.
                    raise SaltCloudSystemExit(
                        'There are no more floating IP addresses '
                        'available, please create some more'
                    )
            except Exception as e:
                if str(e).startswith('404'):
                    pass
                else:
                    raise
    return floating
