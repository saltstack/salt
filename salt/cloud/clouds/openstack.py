# -*- coding: utf-8 -*-
'''
'''

# Import Python Libs
import json
import logging
import os
import pprint
import socket

# Import Salt Libs
import salt.config as config
import salt.ext.six as six
from salt.exceptions import (
    SaltCloudSystemExit,
    SaltCloudExecutionTimeout,
    SaltCloudExecutionFailure,
    SaltCloudConfigError,
)

# Import 3rd-Party Libs
try:
    import shade.openstackcloud
    import shade.exc
    import os_client_config
    import munch
    HAS_SHADE = True
except ImportError:
    HAS_SHADE = False

log = logging.getLogger(__name__)
__virtualname__ = 'openstack'


def __virtual__():
    '''
    Check for Openstack dependencies
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
        __opts__, __active_provider_name__ or __virtualname__,
        ('auth', 'region_name'), log_message=False,
    ) or config.is_provider_configured(
        __opts__, __active_provider_name__ or __virtualname__,
        ('cloud', 'region_name')
    )


def get_dependencies():
    '''
    Warn if dependencies aren't met.
    '''
    deps = {
        'shade': HAS_SHADE,
        'os_client_config': HAS_SHADE,
    }
    return config.check_driver_dependencies(
        __virtualname__,
        deps
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
    return config.get_cloud_config_value('ssh_interface', vm_, __opts__, default='public_ips', search_global=False)


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    if __active_provider_name__ in __context__:
        return __context__[__active_provider_name__]
    vm_ = get_configured_provider()
    profile = vm_.pop('profile', None)
    if profile is not None:
        vm_ = __utils__['dictupdate.update'](os_client_config.vendors.get_profile(profile), vm_)
    conn = shade.openstackcloud.OpenStackCloud(cloud_config=None, **vm_)
    if __active_provider_name__ is not None:
        __context__[__active_provider_name__] = conn
    return conn


def list_nodes(conn=None, call=None):
    '''
    List VMs on this Openstack account
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )
    ret = {}
    for node, info in list_nodes_full(conn=conn).items():
        for key in ('id', 'name', 'size', 'state', 'private_ips', 'public_ips', 'floating_ips', 'fixed_ips', 'image'):
            ret.setdefault(node, {}).setdefault(key, info.get(key))

    return ret


def list_nodes_min(conn=None, call=None):
    '''
    List VMs on this Openstack account
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_min function must be called with -f or --function.'
        )
    if conn is None:
        conn = get_conn()
    ret = {}
    for node in conn.list_servers(bare=True):
        ret[node.name] = {'id': node.id, 'state': node.status}
    return ret

def _get_ips(node, addr_type='public'):
    ret = []
    for _, interface in node.addresses.items():
        for addr in interface:
            if addr_type in ('floating', 'fixed') and addr_type == addr['OS-EXT-IPS:type']:
                ret.append(addr['addr'])
            elif addr_type == 'public' and __utils__['cloud.is_public_ip'](addr['addr']):
                ret.append(addr['addr'])
            elif addr_type == 'private' and not __utils__['cloud.is_public_ip'](addr['addr']):
                ret.append(addr['addr'])
    return ret

def list_nodes_full(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    List VMs on this Openstack account
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )
    if conn is None:
        conn = get_conn()
    ret = {}
    for node in conn.list_servers(detailed=True):
        ret[node.name] = dict(node)
        ret[node.name]['id'] = node.id
        ret[node.name]['name'] = node.name
        ret[node.name]['size'] = node.flavor.name
        ret[node.name]['state'] = node.status
        ret[node.name]['private_ips'] = _get_ips(node, 'private')
        ret[node.name]['public_ips'] = _get_ips(node, 'public')
        ret[node.name]['floating_ips'] = _get_ips(node, 'floating')
        ret[node.name]['fixed_ips'] = _get_ips(node, 'fixed')
        ret[node.name]['image'] = node.image.name
    return ret


def list_nodes_select(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_select function must be called with -f or --function.'
        )
    return __utils__['cloud.list_nodes_select'](
        list_nodes(conn, 'function'), __opts__['query.selection'], call,
    )


def show_instance(name, conn=None, call=None):
    '''
    Get VM on this Openstack account
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )
    if conn is None:
        conn = get_conn()

    node = conn.get_server(name, bare=True)
    ret = dict(node)
    ret['id'] = node.id
    ret['name'] = node.name
    ret['size'] = conn.get_flavor(node.flavor.id).name
    ret['state'] = node.status
    ret['private_ips'] = _get_ips(node, 'private')
    ret['public_ips'] = _get_ips(node, 'public')
    ret['floating_ips'] = _get_ips(node, 'floating')
    ret['fixed_ips'] = _get_ips(node, 'fixed')
    ret['image'] = conn.get_image(node.image.id).name
    return ret


def avail_images(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    List available images for Openstack
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )
    if conn is None:
        conn = get_conn()
    return conn.list_images()


def avail_sizes(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    List available sizes for Openstack
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-sizes option'
        )
    if conn is None:
        conn = get_conn()
    return conn.list_flavors()


def list_networks(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    List virtual networks
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_networks function must be called with '
            '-f or --function'
        )
    if conn is None:
        conn = get_conn()
    return conn.list_networks()


def list_subnets(conn=None, call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    List subnets in a virtual network

    network
    	network to list subnets of

    .. code-block::

    	salt-cloud -f list_subnets network=salt-net
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_subnets function must be called with '
            '-f or --function.'
        )
    if conn is None:
        conn = get_conn()
    if kwargs is None or (isinstance(kwargs, dict) and 'network' not in kwargs):
        raise SaltCloudSystemExit(
            'A `network` must be specified'
        )
    return conn.list_subnets(filters={'network': kwargs['network']})


def _clean_kwargs(**kwargs):
    VALID_OPTS = {
        'name': six.string_types,
        'image': six.string_types,
        'flavor': six.string_types,
        'auto_ip': bool,
        'ips': list,
        'ip_pool': six.string_types,
        'root_volume': six.string_types,
        'boot_volume': six.string_types,
        'terminate_volume': bool,
        'volumes': list,
        'meta': dict,
        'files': dict,
        'reservation_id': six.string_types,
        'security_groups': list,
        'key_name': six.string_types,
        'availability_zone': six.string_types,
        'block_device_mapping': dict,
        'block_device_mapping_v2': dict,
        'nics': list,
        'scheduler_hints': dict,
        'config_drive': bool,
        'disk_config': six.string_types,  # AUTO or MANUAL
        'admin_pass': six.string_types,
        'wait': bool,
        'timeout': int,
        'reuse_ips': bool,
        'network': dict,
        'boot_from_volume': bool,
        'volume_size': int,
        'nat_destination': six.string_types,
        'group': six.string_types,
    }
    extra = kwargs.pop('extra', {})
    for key, value in six.iteritems(kwargs.copy()):
        if key in VALID_OPTS:
            if isinstance(value, VALID_OPTS[key]):
                continue
            log.error('Error {0}: {1} is not of type {2}'.format(key, value, VALID_OPTS[key]))
        kwargs.pop(key)
    return __utils__['dictupdate.update'](kwargs, extra)


def request_instance(conn=None, call=None, kwargs=None):
    if call == 'function':
        # Technically this function may be called other ways too, but it
        # definitely cannot be called with --function.
        raise SaltCloudSystemExit(
            'The request_instance action must be called with -a or --action.'
        )
    vm_ = kwargs.copy()
    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    __utils__['cloud.check_name'](vm_['name'], 'a-zA-Z0-9._-')
    if conn is None:
        conn = get_conn()
    userdata_file = config.get_cloud_config_value(
        'userdata_file', vm_, __opts__, search_global=False, default=None
    )
    if userdata_file is not None:
        try:
            with __utils__['files.fopen'](userdata_file, 'r') as fp_:
                kwargs['userdata'] = __utils__['cloud.userdata_template'](
                    __opts__, vm_, fp_.read()
                )
        except Exception as exc:
            log.exception(
                'Failed to read userdata from %s: %s', userdata_file, exc)
    kwargs['flavor'] = kwargs.pop('size')
    kwargs['wait'] = True
    try:
        conn.create_server(**_clean_kwargs(**kwargs))
    except shade.exc.OpenStackCloudException as exc:
        log.error('Error creating server %s: %s', vm_['name'], exc)
        destroy(vm_['name'], conn=conn, call='action')
        raise SaltCloudSystemExit(str(exc))

    return show_instance(vm_['name'], conn=conn, call='action')


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
            log.debug('Generating minion keys for \'{0[name]}\''.format(vm_))
            vm_['priv_key'], vm_['pub_key'] = __utils__['cloud.gen_keys'](
                config.get_cloud_config_value(
                    'keysize',
                    vm_,
                    __opts__
                )
            )
        data = show_instance(vm_['instance_id'], conn=conn, call='action')
    else:
        # Put together all of the information required to request the instance,
        # and then fire off the request for it
        data = request_instance(kwargs=vm_)
    log.debug('VM is now running')

    def __query_node_ip(vm_):
        data = show_instance(vm_['name'], conn=conn, call='action')
        return preferred_ip(vm_, data[ssh_interface(vm_)])
    try:
        ip_address = __utils__['cloud.wait_for_ip'](
            __query_node_ip,
            update_args=(vm_,)
        )
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
        try:
            # It might be already up, let's destroy it!
            destroy(vm_['name'])
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(str(exc))
    log.debug('Using IP address {0}'.format(ip_address))

    salt_interface = __utils__['cloud.get_salt_interface'](vm_, __opts__)
    salt_ip_address = preferred_ip(vm_, data[salt_interface])
    log.debug('Salt interface set to: {0}'.format(salt_ip_address))

    if not ip_address:
        raise SaltCloudSystemExit('A valid IP address was not found')

    vm_['ssh_host'] = ip_address
    vm_['salt_host'] = salt_ip_address

    ret = __utils__['cloud.bootstrap'](vm_, __opts__)
    ret.update(data)

    log.info('Created Cloud VM \'{0[name]}\''.format(vm_))
    log.debug(
        '\'{0[name]}\' VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data)
        )
    )

    event_data = {
        'name': vm_['name'],
        'profile': vm_['profile'],
        'provider': vm_['driver'],
        'instance_id': data['id'],
        'floating_ips': data['floating_ips'],
        'fixed_ips': data['fixed_ips'],
        'private_ips': data['private_ips'],
        'public_ips': data['public_ips'],
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
    node = show_instance(name, conn=conn, call='action')
    log.info('Destroying VM: {0}'.format(name))
    ret = conn.delete_server(name)
    if ret:
        log.info('Destroyed VM: {0}'.format(name))
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
            __utils__['cloud.remove_sshkey'](getattr(node, __opts__.get('ssh_interface', 'public_ips'))[0])
        if __opts__.get('update_cachedir', False) is True:
            __utils__['cloud.delete_minion_cachedir'](name, __active_provider_name__.split(':')[0], __opts__)
        __utils__['cloud.cachedir_index_del'](name)
        return True

    log.error('Failed to Destroy VM: {0}'.format(name))
    return False


def call(conn=None, call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Call function from shade.

    fun

        function to call from shade.openstackcloud library

    .. code-block::

    	salt-cloud -f call myopenstack fun=list_images
    	salt-cloud -f call myopenstack fun=create_network name=mysubnet
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The call function must be called with '
            '-f or --function.'
        )
    
    if 'func' not in kwargs:
        raise SaltCloudSystemExit(
            'No `func` argument passed'
        )

    if conn is None:
        conn = get_conn()

    func = kwargs.pop('func')
    for key, value in kwargs.items():
        try:
            kwargs[key] = json.loads(value)
        except ValueError:
            continue
    try:
        return getattr(conn, func)(**kwargs)
    except shade.exc.OpenStackCloudException as exc:
        log.error('Error running %s: %s', func, exc)
        raise SaltCloudSystemExit(str(exc))
