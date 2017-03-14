# -*- coding: utf-8 -*-
'''
Rackspace Cloud Module
======================

The Rackspace cloud module. This module uses the preferred means to set up a
libcloud based cloud module and should be used as the general template for
setting up additional libcloud based modules.

:depends: libcloud >= 0.13.2

Please note that the `rackspace` driver is only intended for 1st gen instances,
aka, "the old cloud" at Rackspace. It is required for 1st gen instances, but
will *not* work with OpenStack-based instances. Unless you explicitly have a
reason to use it, it is highly recommended that you use the `openstack` driver
instead.

The rackspace cloud module interfaces with the Rackspace public cloud service
and requires that two configuration parameters be set for use, ``user`` and
``apikey``.

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/rackspace.conf``:

.. code-block:: yaml

    my-rackspace-config:
      driver: rackspace
      # The Rackspace login user
      user: fred
      # The Rackspace user's apikey
      apikey: 901d3f579h23c8v73q9
'''

# Import python libs
from __future__ import absolute_import
import logging
import socket
import pprint

# Import salt libs
import salt.utils
import salt.config as config
from salt.utils import namespaced_function
from salt.exceptions import (
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout
)

# Import salt.cloud libs
from salt.cloud.libcloudfuncs import *   # pylint: disable=W0614,W0401
import salt.utils.cloud

# Import Third Party Libs
try:
    from libcloud.compute.base import NodeState
    # See https://github.com/saltstack/salt/issues/32743
    import libcloud.security
    libcloud.security.CA_CERTS_PATH.append('/etc/ssl/certs/YaST-CA.pem')
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False

# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = 'rackspace'


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
list_nodes = namespaced_function(list_nodes, globals())
list_nodes_full = namespaced_function(list_nodes_full, globals())
list_nodes_select = namespaced_function(list_nodes_select, globals())
show_instance = namespaced_function(show_instance, globals())


# Only load in this module is the RACKSPACE configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for Rackspace configuration.
    '''
    if get_configured_provider() is False:
        return False

    if get_dependencies() is False:
        return False

    return True


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ('user', 'apikey')
    )


def get_dependencies():
    '''
    Warn if dependencies aren't met.
    '''
    return config.check_driver_dependencies(
        __virtualname__,
        {'libcloud': HAS_LIBCLOUD}
    )


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    force_first_gen = config.get_cloud_config_value(
        'force_first_gen',
        get_configured_provider(),
        __opts__,
        search_global=False,
        default=False
    )
    if force_first_gen:
        log.info('Rackspace driver will only have access to first-gen images')
        driver = get_driver(Provider.RACKSPACE_FIRST_GEN)
    else:
        driver = get_driver(Provider.RACKSPACE)

    return driver(
        config.get_cloud_config_value(
            'user',
            get_configured_provider(),
            __opts__,
            search_global=False
        ),
        config.get_cloud_config_value(
            'apikey',
            get_configured_provider(),
            __opts__,
            search_global=False
        ),
        region=config.get_cloud_config_value(
            'compute_region',
            get_configured_provider(),
            __opts__,
            search_global=False,
            default='dfw'
        ).lower()
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


def ssh_interface(vm_):
    '''
    Return the ssh_interface type to connect to. Either 'public_ips' (default)
    or 'private_ips'.
    '''
    return config.get_cloud_config_value(
        'ssh_interface', vm_, __opts__, default='public_ips',
        search_global=False
    )


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or 'rackspace',
                                                           vm_['profile'],
                                                           vm_=vm_) is False:
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

    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()
    kwargs = {
        'name': vm_['name'],
        'image': get_image(conn, vm_),
        'size': get_size(conn, vm_)
    }

    event_kwargs = {
        'name': kwargs['name'],
        'image': kwargs['image'].name,
        'size': kwargs['size'].name,
    }

    __utils__['cloud.fire_event'](
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        args={
            'kwargs': __utils__['cloud.filter_event']('requesting', event_kwargs, event_kwargs.keys()),
        },
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    try:
        data = conn.create_node(**kwargs)
    except Exception as exc:
        log.error(
            'Error creating {0} on RACKSPACE\n\n'
            'The following exception was thrown by libcloud when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_['name'], exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return False

    def __query_node_data(vm_, data):
        running = False
        try:
            node = show_instance(vm_['name'], 'action')
            running = (node['state'] == NodeState.RUNNING)
            log.debug(
                'Loaded node data for {0}:\nname: {1}\nstate: {2}'.format(
                    vm_['name'],
                    pprint.pformat(node['name']),
                    node['state']
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

        if not running:
            # Still not running, trigger another iteration
            return

        private = node['private_ips']
        public = node['public_ips']

        if private and not public:
            log.warning(
                'Private IPs returned, but not public... Checking for '
                'misidentified IPs'
            )
            for private_ip in private:
                private_ip = preferred_ip(vm_, [private_ip])
                if private_ip is False:
                    continue
                if salt.utils.cloud.is_public_ip(private_ip):
                    log.warning('{0} is a public IP'.format(private_ip))
                    data.public_ips.append(private_ip)
                else:
                    log.warning('{0} is a private IP'.format(private_ip))
                    if private_ip not in data.private_ips:
                        data.private_ips.append(private_ip)

            if ssh_interface(vm_) == 'private_ips' and data.private_ips:
                return data

        if private:
            data.private_ips = private
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
                'wait_for_ip_timeout', vm_, __opts__, default=25 * 60),
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
        raise SaltCloudSystemExit(
            'No IP addresses could be found.'
        )

    vm_['salt_host'] = salt_ip_address
    vm_['ssh_host'] = ip_address
    vm_['password'] = data.extra['password']

    ret = __utils__['cloud.bootstrap'](vm_, __opts__)

    ret.update(data.__dict__)

    if 'password' in data.extra:
        del data.extra['password']

    log.info('Created Cloud VM \'{0[name]}\''.format(vm_))
    log.debug(
        '\'{0[name]}\' VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data.__dict__)
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

    return ret
