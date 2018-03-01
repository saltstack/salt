# -*- coding: utf-8 -*-
'''
The generic libcloud template used to create the connections and deploy the
cloud virtual machines
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import os
import logging
from salt.ext import six
from salt.ext.six.moves import zip


# pylint: disable=W0611
# Import libcloud
try:
    import libcloud
    import re
    from libcloud.compute.types import Provider
    from libcloud.compute.providers import get_driver
    from libcloud.compute.deployment import (
        MultiStepDeployment,
        ScriptDeployment
    )
    HAS_LIBCLOUD = True
    LIBCLOUD_VERSION_INFO = tuple([
        int(part) for part in libcloud.__version__.replace('-', '.').replace('rc', '.').split('.')[:3]
    ])

except ImportError:
    HAS_LIBCLOUD = False
    LIBCLOUD_VERSION_INFO = (1000,)
# pylint: enable=W0611


# Import salt libs
import salt.utils.event
import salt.client

# Import salt cloud libs
import salt.utils.cloud
import salt.utils.data
import salt.config as config
from salt.exceptions import SaltCloudNotFound, SaltCloudSystemExit

# Get logging started
log = logging.getLogger(__name__)


LIBCLOUD_MINIMAL_VERSION = (0, 14, 0)


def node_state(id_):
    '''
    Libcloud supported node states
    '''
    states_int = {
        0: 'RUNNING',
        1: 'REBOOTING',
        2: 'TERMINATED',
        3: 'PENDING',
        4: 'UNKNOWN',
        5: 'STOPPED',
        6: 'SUSPENDED',
        7: 'ERROR',
        8: 'PAUSED'}
    states_str = {
        'running': 'RUNNING',
        'rebooting': 'REBOOTING',
        'starting': 'STARTING',
        'terminated': 'TERMINATED',
        'pending': 'PENDING',
        'unknown': 'UNKNOWN',
        'stopping': 'STOPPING',
        'stopped': 'STOPPED',
        'suspended': 'SUSPENDED',
        'error': 'ERROR',
        'paused': 'PAUSED',
        'reconfiguring': 'RECONFIGURING'
    }
    return states_str[id_] if isinstance(id_, six.string_types) else states_int[id_]


def check_libcloud_version(reqver=LIBCLOUD_MINIMAL_VERSION, why=None):
    '''
    Compare different libcloud versions
    '''
    if not HAS_LIBCLOUD:
        return False

    if not isinstance(reqver, (list, tuple)):
        raise RuntimeError(
            '\'reqver\' needs to passed as a tuple or list, i.e., (0, 14, 0)'
        )
    try:
        import libcloud  # pylint: disable=redefined-outer-name
    except ImportError:
        raise ImportError(
            'salt-cloud requires >= libcloud {0} which is not installed'.format(
                '.'.join([six.text_type(num) for num in reqver])
            )
        )

    if LIBCLOUD_VERSION_INFO >= reqver:
        return libcloud.__version__

    errormsg = 'Your version of libcloud is {0}. '.format(libcloud.__version__)
    errormsg += 'salt-cloud requires >= libcloud {0}'.format(
        '.'.join([six.text_type(num) for num in reqver])
    )
    if why:
        errormsg += ' for {0}'.format(why)
    errormsg += '. Please upgrade.'
    raise ImportError(errormsg)


def get_node(conn, name):
    '''
    Return a libcloud node for the named VM
    '''
    nodes = conn.list_nodes()
    for node in nodes:
        if node.name == name:
            __utils__['cloud.cache_node'](salt.utils.data.simple_types_filter(node.__dict__), __active_provider_name__, __opts__)
            return node


def avail_locations(conn=None, call=None):
    '''
    Return a dict of all available VM locations on the cloud provider with
    relevant data
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_locations function must be called with '
            '-f or --function, or with the --list-locations option'
        )

    if not conn:
        conn = get_conn()   # pylint: disable=E0602

    locations = conn.list_locations()
    ret = {}
    for img in locations:
        if isinstance(img.name, six.string_types) and not six.PY3:
            img_name = img.name.encode('ascii', 'salt-cloud-force-ascii')
        else:
            img_name = str(img.name)  # future lint: disable=blacklisted-function

        ret[img_name] = {}
        for attr in dir(img):
            if attr.startswith('_') or attr == 'driver':
                continue

            attr_value = getattr(img, attr)
            if isinstance(attr_value, six.string_types) and not six.PY3:
                attr_value = attr_value.encode(
                    'ascii', 'salt-cloud-force-ascii'
                )
            ret[img_name][attr] = attr_value

    return ret


def avail_images(conn=None, call=None):
    '''
    Return a dict of all available VM images on the cloud provider with
    relevant data
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    if not conn:
        conn = get_conn()   # pylint: disable=E0602

    images = conn.list_images()
    ret = {}
    for img in images:
        if isinstance(img.name, six.string_types) and not six.PY3:
            img_name = img.name.encode('ascii', 'salt-cloud-force-ascii')
        else:
            img_name = str(img.name)  # future lint: disable=blacklisted-function

        ret[img_name] = {}
        for attr in dir(img):
            if attr.startswith('_') or attr in ('driver', 'get_uuid'):
                continue
            attr_value = getattr(img, attr)
            if isinstance(attr_value, six.string_types) and not six.PY3:
                attr_value = attr_value.encode(
                    'ascii', 'salt-cloud-force-ascii'
                )
            ret[img_name][attr] = attr_value
    return ret


def avail_sizes(conn=None, call=None):
    '''
    Return a dict of all available VM images on the cloud provider with
    relevant data
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-sizes option'
        )

    if not conn:
        conn = get_conn()   # pylint: disable=E0602

    sizes = conn.list_sizes()
    ret = {}
    for size in sizes:
        if isinstance(size.name, six.string_types) and not six.PY3:
            size_name = size.name.encode('ascii', 'salt-cloud-force-ascii')
        else:
            size_name = str(size.name)  # future lint: disable=blacklisted-function

        ret[size_name] = {}
        for attr in dir(size):
            if attr.startswith('_') or attr in ('driver', 'get_uuid'):
                continue

            try:
                attr_value = getattr(size, attr)
            except Exception:
                pass

            if isinstance(attr_value, six.string_types) and not six.PY3:
                attr_value = attr_value.encode(
                    'ascii', 'salt-cloud-force-ascii'
                )
            ret[size_name][attr] = attr_value
    return ret


def get_location(conn, vm_):
    '''
    Return the location object to use
    '''
    locations = conn.list_locations()
    vm_location = config.get_cloud_config_value('location', vm_, __opts__)
    if not six.PY3:
        vm_location = vm_location.encode(
            'ascii', 'salt-cloud-force-ascii'
        )

    for img in locations:
        if isinstance(img.id, six.string_types) and not six.PY3:
            img_id = img.id.encode('ascii', 'salt-cloud-force-ascii')
        else:
            img_id = str(img.id)  # future lint: disable=blacklisted-function

        if isinstance(img.name, six.string_types) and not six.PY3:
            img_name = img.name.encode('ascii', 'salt-cloud-force-ascii')
        else:
            img_name = str(img.name)  # future lint: disable=blacklisted-function

        if vm_location and vm_location in (img_id, img_name):
            return img

    raise SaltCloudNotFound(
        'The specified location, \'{0}\', could not be found.'.format(
            vm_location
        )
    )


def get_image(conn, vm_):
    '''
    Return the image object to use
    '''
    images = conn.list_images()
    vm_image = config.get_cloud_config_value('image', vm_, __opts__)

    if not six.PY3:
        vm_image = vm_image.encode('ascii', 'salt-cloud-force-ascii')

    for img in images:
        if isinstance(img.id, six.string_types) and not six.PY3:
            img_id = img.id.encode('ascii', 'salt-cloud-force-ascii')
        else:
            img_id = str(img.id)  # future lint: disable=blacklisted-function

        if isinstance(img.name, six.string_types) and not six.PY3:
            img_name = img.name.encode('ascii', 'salt-cloud-force-ascii')
        else:
            img_name = str(img.name)  # future lint: disable=blacklisted-function

        if vm_image and vm_image in (img_id, img_name):
            return img

    raise SaltCloudNotFound(
        'The specified image, \'{0}\', could not be found.'.format(vm_image)
    )


def get_size(conn, vm_):
    '''
    Return the VM's size object
    '''
    sizes = conn.list_sizes()
    vm_size = config.get_cloud_config_value('size', vm_, __opts__)
    if not vm_size:
        return sizes[0]

    for size in sizes:
        if vm_size and str(vm_size) in (str(size.id), str(size.name)):  # pylint: disable=blacklisted-function
            return size
    raise SaltCloudNotFound(
        'The specified size, \'{0}\', could not be found.'.format(vm_size)
    )


def script(vm_):
    '''
    Return the script deployment object
    '''
    return ScriptDeployment(
        salt.utils.cloud.os_script(
            config.get_cloud_config_value('os', vm_, __opts__),
            vm_,
            __opts__,
            salt.utils.cloud.salt_config_to_yaml(
                salt.utils.cloud.minion_config(__opts__, vm_)
            )
        )
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

    node = get_node(conn, name)
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

        mopts_ = salt.config.DEFAULT_MINION_OPTS
        conf_path = '/'.join(__opts__['conf_file'].split('/')[:-1])
        mopts_.update(
            salt.config.minion_config(os.path.join(conf_path, 'minion'))
        )
        client = salt.client.get_local_client(mopts_)
        minions = client.cmd(name, 'mine.flush')

    log.info('Clearing Salt Mine: %s, %s', name, flush_mine_on_destroy)
    log.info('Destroying VM: %s', name)
    ret = conn.destroy_node(node)
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
        if __opts__['delete_sshkeys'] is True:
            public_ips = getattr(node, __opts__.get('ssh_interface', 'public_ips'))
            if public_ips:
                salt.utils.cloud.remove_sshkey(public_ips[0])

            private_ips = getattr(node, __opts__.get('ssh_interface', 'private_ips'))
            if private_ips:
                salt.utils.cloud.remove_sshkey(private_ips[0])

        if __opts__.get('update_cachedir', False) is True:
            __utils__['cloud.delete_minion_cachedir'](name, __active_provider_name__.split(':')[0], __opts__)

        return True

    log.error('Failed to Destroy VM: %s', name)
    return False


def reboot(name, conn=None):
    '''
    Reboot a single VM
    '''
    if not conn:
        conn = get_conn()   # pylint: disable=E0602

    node = get_node(conn, name)
    if node is None:
        log.error('Unable to find the VM %s', name)
    log.info('Rebooting VM: %s', name)
    ret = conn.reboot_node(node)
    if ret:
        log.info('Rebooted VM: %s', name)
        # Fire reboot action
        __utils__['cloud.fire_event'](
            'event',
            '{0} has been rebooted'.format(name), 'salt-cloud'
            'salt/cloud/{0}/rebooting'.format(name),
            args={'name': name},
            sock_dir=__opts__['sock_dir'],
            transport=__opts__['transport']
        )
        return True

    log.error('Failed to reboot VM: %s', name)
    return False


def list_nodes(conn=None, call=None):
    '''
    Return a list of the VMs that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()   # pylint: disable=E0602

    nodes = conn.list_nodes()
    ret = {}
    for node in nodes:
        ret[node.name] = {
            'id': node.id,
            'image': node.image,
            'name': node.name,
            'private_ips': node.private_ips,
            'public_ips': node.public_ips,
            'size': node.size,
            'state': node_state(node.state)
        }
    return ret


def list_nodes_full(conn=None, call=None):
    '''
    Return a list of the VMs that are on the provider, with all fields
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()   # pylint: disable=E0602

    nodes = conn.list_nodes()
    ret = {}
    for node in nodes:
        pairs = {}
        for key, value in zip(node.__dict__, six.itervalues(node.__dict__)):
            pairs[key] = value
        ret[node.name] = pairs
        del ret[node.name]['driver']

    __utils__['cloud.cache_node_list'](ret, __active_provider_name__.split(':')[0], __opts__)
    return ret


def list_nodes_select(conn=None, call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    if not conn:
        conn = get_conn()   # pylint: disable=E0602

    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(conn, 'function'), __opts__['query.selection'], call,
    )


def show_instance(name, call=None):
    '''
    Show the details from the provider concerning an instance
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

    nodes = list_nodes_full()
    __utils__['cloud.cache_node'](nodes[name], __active_provider_name__, __opts__)
    return nodes[name]


def conn_has_method(conn, method_name):
    '''
    Find if the provided connection object has a specific method
    '''
    if method_name in dir(conn):
        return True

    log.error('Method \'%s\' not yet supported!', method_name)
    return False
