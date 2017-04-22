# -*- coding: utf-8 -*-
'''
Dimension Data Cloud Module
===========================

This is a cloud module for the Dimension Data Cloud,
using the existing Libcloud driver for Dimension Data.

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers
    # or any file in the
    # /etc/salt/cloud.providers.d/ directory.

    my-dimensiondata-config:
      user_id: my_username
      key: myPassword!
      region: dd-na
      driver: dimensiondata

'''

# Import python libs
from __future__ import absolute_import
import logging
import socket
import pprint

# Import libcloud
try:
    from libcloud.compute.base import NodeState
    from libcloud.compute.base import NodeAuthPassword
    from libcloud.compute.types import Provider
    from libcloud.compute.providers import get_driver
    from libcloud.loadbalancer.base import Member
    from libcloud.loadbalancer.types import Provider as Provider_lb
    from libcloud.loadbalancer.providers import get_driver as get_driver_lb
    # See https://github.com/saltstack/salt/issues/32743
    import libcloud.security
    libcloud.security.CA_CERTS_PATH.append('/etc/ssl/certs/YaST-CA.pem')
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False

# Import generic libcloud functions
# from salt.cloud.libcloudfuncs import *

# Import salt libs
import salt.utils

# Import salt.cloud libs
from salt.cloud.libcloudfuncs import *  # pylint: disable=redefined-builtin,wildcard-import,unused-wildcard-import
from salt.utils import namespaced_function
import salt.utils.cloud
import salt.config as config
from salt.exceptions import (
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout
)

try:
    from netaddr import all_matching_cidrs  # pylint: disable=unused-import
    HAS_NETADDR = True
except ImportError:
    HAS_NETADDR = False


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

# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = 'dimensiondata'


def __virtual__():
    '''
    Set up the libcloud functions and check for dimensiondata configurations.
    '''
    if get_configured_provider() is False:
        return False

    if get_dependencies() is False:
        return False

    for provider, details in six.iteritems(__opts__['providers']):
        if 'dimensiondata' not in details:
            continue

    return __virtualname__


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'dimensiondata',
        ('user_id', 'key', 'region')
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


def _query_node_data(vm_, data):
    running = False
    try:
        node = show_instance(vm_['name'], 'action')
        running = (node['state'] == NodeState.RUNNING)
        log.debug(
            'Loaded node data for %s:\nname: %s\nstate: %s',
            vm_['name'],
            pprint.pformat(node['name']),
            node['state']
            )
    except Exception as err:
        log.error(
            'Failed to get nodes list: %s', err,
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        # Trigger a failure in the wait for IP function
        return running

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
                log.warning('%s is a public IP', private_ip)
                data.public_ips.append(private_ip)
            else:
                log.warning('%s is a private IP', private_ip)
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

    log.debug('DATA')
    log.debug(data)


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(
                __opts__,
                __active_provider_name__ or 'dimensiondata',
                vm_['profile']) is False:
            return False
    except AttributeError:
        pass

    # Since using "provider: <provider-engine>" is deprecated, alias provider
    # to use driver: "driver: <provider-engine>"
    if 'provider' in vm_:
        vm_['driver'] = vm_.pop('provider')

    __utils__['cloud.fire_event'](
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        args={
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    log.info('Creating Cloud VM %s', vm_['name'])
    conn = get_conn()
    rootPw = NodeAuthPassword(vm_['auth'])

    try:
        location = conn.ex_get_location_by_id(vm_['location'])
        images = conn.list_images(location=location)
        image = [x for x in images if x.id == vm_['image']][0]
        networks = conn.ex_list_network_domains(location=location)
        network_domain = [y for y in networks if y.name ==
                          vm_['network_domain']][0]
        # Use the first VLAN in the network domain
        vlan = conn.ex_list_vlans(location=location,
                                  network_domain=network_domain)[0]
        kwargs = {
            'name': vm_['name'],
            'image': image,
            'auth': rootPw,
            'ex_description': vm_['description'],
            'ex_network_domain': network_domain,
            'ex_vlan': vlan,
            'ex_is_started': vm_['is_started']
        }
        data = conn.create_node(**kwargs)
    except Exception as exc:
        log.error(
            'Error creating %s on DIMENSIONDATA\n\n'
            'The following exception was thrown by libcloud when trying to '
            'run the initial deployment: \n%s',
            vm_['name'], exc,
            exc_info_on_loglevel=logging.DEBUG
        )
        return False

    try:
        data = salt.utils.cloud.wait_for_ip(
            _query_node_data,
            update_args=(vm_, data),
            timeout=config.get_cloud_config_value(
                'wait_for_ip_timeout', vm_, __opts__, default=25 * 60),
            interval=config.get_cloud_config_value(
                'wait_for_ip_interval', vm_, __opts__, default=30),
            max_failures=config.get_cloud_config_value(
                'wait_for_ip_max_failures', vm_, __opts__, default=60),
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
    log.debug('Using IP address %s', ip_address)

    if salt.utils.cloud.get_salt_interface(vm_, __opts__) == 'private_ips':
        salt_ip_address = preferred_ip(vm_, data.private_ips)
        log.info('Salt interface set to: %s', salt_ip_address)
    else:
        salt_ip_address = preferred_ip(vm_, data.public_ips)
        log.debug('Salt interface set to: %s', salt_ip_address)

    if not ip_address:
        raise SaltCloudSystemExit(
            'No IP addresses could be found.'
        )

    vm_['salt_host'] = salt_ip_address
    vm_['ssh_host'] = ip_address
    vm_['password'] = vm_['auth']

    ret = salt.utils.cloud.bootstrap(vm_, __opts__)

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
        args={
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    return ret


def create_lb(kwargs=None, call=None):
    r'''
    Create a load-balancer configuration.
    CLI Example:

    .. code-block:: bash

        salt-cloud -f create_lb dimensiondata \
            name=dev-lb port=80 protocol=http \
            members=w1,w2,w3 algorithm=ROUND_ROBIN
    '''
    conn = get_conn()
    if call != 'function':
        raise SaltCloudSystemExit(
            'The create_lb function must be called with -f or --function.'
        )

    if not kwargs or 'name' not in kwargs:
        log.error(
            'A name must be specified when creating a health check.'
        )
        return False
    if 'port' not in kwargs:
        log.error(
            'A port or port-range must be specified for the load-balancer.'
        )
        return False
    if 'networkdomain' not in kwargs:
        log.error(
            'A network domain must be specified for the load-balancer.'
        )
        return False
    if 'members' in kwargs:
        members = []
        ip = ""
        membersList = kwargs.get('members').split(',')
        log.debug('MemberList: %s', membersList)
        for member in membersList:
            try:
                log.debug('Member: %s', member)
                node = get_node(conn, member)
                log.debug('Node: %s', node)
                ip = node.private_ips[0]
            except Exception as err:
                log.error(
                    'Failed to get node ip: %s', err,
                    # Show the traceback if the debug logging level is enabled
                    exc_info_on_loglevel=logging.DEBUG
                )
            members.append(Member(ip, ip, kwargs['port']))
    else:
        members = None
    log.debug('Members: %s', members)

    networkdomain = kwargs['networkdomain']
    name = kwargs['name']
    port = kwargs['port']
    protocol = kwargs.get('protocol', None)
    algorithm = kwargs.get('algorithm', None)

    lb_conn = get_lb_conn(conn)
    network_domains = conn.ex_list_network_domains()
    network_domain = [y for y in network_domains if y.name == networkdomain][0]

    log.debug('Network Domain: %s', network_domain.id)
    lb_conn.ex_set_current_network_domain(network_domain.id)

    __utils__['cloud.fire_event'](
        'event',
        'create load_balancer',
        'salt/cloud/loadbalancer/creating',
        args=kwargs,
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    lb = lb_conn.create_balancer(
        name, port, protocol, algorithm, members
    )

    __utils__['cloud.fire_event'](
        'event',
        'created load_balancer',
        'salt/cloud/loadbalancer/created',
        args=kwargs,
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )
    return _expand_balancer(lb)


def _expand_balancer(lb):
    '''
    Convert the libcloud load-balancer object into something more serializable.
    '''
    ret = {}
    ret.update(lb.__dict__)
    return ret


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


def stop(name, call=None):
    '''
    Stop a VM in DimensionData.

    name:
        The name of the VM to stop.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop vm_name
    '''
    conn = get_conn()
    node = get_node(conn, name)
    log.debug('Node of Cloud VM: %s', node)

    status = conn.ex_shutdown_graceful(node)
    log.debug('Status of Cloud VM: %s', status)

    return status


def start(name, call=None):
    '''
    Stop a VM in DimensionData.

    :param str name:
        The name of the VM to stop.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop vm_name
    '''

    conn = get_conn()
    node = get_node(conn, name)
    log.debug('Node of Cloud VM: %s', node)

    status = conn.ex_start_node(node)
    log.debug('Status of Cloud VM: %s', status)

    return status


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    vm_ = get_configured_provider()
    driver = get_driver(Provider.DIMENSIONDATA)

    region = config.get_cloud_config_value(
         'region', vm_, __opts__
    )

    user_id = config.get_cloud_config_value(
        'user_id', vm_, __opts__
    )
    key = config.get_cloud_config_value(
        'key', vm_, __opts__
    )

    if key is not None:
        log.debug('DimensionData authenticating using password')

    return driver(
        user_id,
        key,
        region=region
    )


def get_lb_conn(dd_driver=None):
    '''
    Return a load-balancer conn object
    '''
    vm_ = get_configured_provider()

    region = config.get_cloud_config_value(
        'region', vm_, __opts__
    )

    user_id = config.get_cloud_config_value(
       'user_id', vm_, __opts__
    )
    key = config.get_cloud_config_value(
       'key', vm_, __opts__
    )
    if not dd_driver:
        raise SaltCloudSystemExit(
            'Missing dimensiondata_driver for get_lb_conn method.'
        )
    return get_driver_lb(Provider_lb.DIMENSIONDATA)(user_id, key, region=region)
