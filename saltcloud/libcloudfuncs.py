'''
The generic libcloud template used to create the connections and deploy the
cloud virtual machines
'''

# Import python libs
import os
import logging


# pylint: disable-msg=W0611
# Import libcloud
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.deployment import (
    MultiStepDeployment,
    ScriptDeployment,
    SSHKeyDeployment
)
# pylint: enable-msg=W0611


# Import salt libs
import salt._compat
import salt.utils.event

# Import salt cloud libs
import saltcloud.utils
import saltcloud.config as config
from saltcloud.exceptions import SaltCloudNotFound

# Get logging started
log = logging.getLogger(__name__)


def node_state(id_):
    states = {0: 'RUNNING',
              1: 'REBOOTING',
              2: 'TERMINATED',
              3: 'PENDING',
              4: 'UNKNOWN'}
    return states[id_]


def libcloud_version():
    '''
    Require the minimal libcloud version
    '''
    try:
        import libcloud
    except ImportError:
        raise ImportError('salt-cloud requires >= libcloud 0.11.4')

    ver = libcloud.__version__
    ver = ver.replace('-', '.')
    comps = ver.split('.')
    version = []
    for number in comps[:3]:
        version.append(int(number))
    if version < [0, 11, 4]:
        raise ImportError(
            'Your version of libcloud is {0}. salt-cloud requires >= '
            'libcloud 0.11.4. Please upgrade.'.format(libcloud.__version__)
        )
    return libcloud.__version__


def get_node(conn, name):
    '''
    Return a libcloud node for the named VM
    '''
    nodes = conn.list_nodes()
    for node in nodes:
        if node.name == name:
            return node


def ssh_pub(vm_):
    '''
    Deploy the primary ssh authentication key
    '''
    ssh = config.get_config_value('ssh_auth', vm_, __opts__)
    if not ssh:
        return None

    ssh = os.path.expanduser(ssh)
    if os.path.isfile(ssh):
        return None

    return SSHKeyDeployment(open(ssh).read())


def avail_locations(conn=None):
    '''
    Return a dict of all available VM locations on the cloud provider with
    relevant data
    '''
    if not conn:
        conn = get_conn()   # pylint: disable-msg=E0602

    locations = conn.list_locations()
    ret = {}
    for img in locations:
        if isinstance(img.name, salt._compat.string_types):
            img_name = img.name.encode('ascii', 'salt-cloud-force-ascii')
        else:
            img_name = str(img.name)

        ret[img_name] = {}
        for attr in dir(img):
            if attr.startswith('_'):
                continue

            attr_value = getattr(img, attr)
            if isinstance(attr_value, salt._compat.string_types):
                attr_value = attr_value.encode(
                    'ascii', 'salt-cloud-force-ascii'
                )
            ret[img_name][attr] = attr_value

    return ret


def avail_images(conn=None):
    '''
    Return a dict of all available VM images on the cloud provider with
    relevant data
    '''
    if not conn:
        conn = get_conn()   # pylint: disable-msg=E0602

    images = conn.list_images()
    ret = {}
    for img in images:
        if isinstance(img.name, salt._compat.string_types):
            img_name = img.name.encode('ascii', 'salt-cloud-force-ascii')
        else:
            img_name = str(img.name)

        ret[img_name] = {}
        for attr in dir(img):
            if attr.startswith('_'):
                continue
            attr_value = getattr(img, attr)
            if isinstance(attr_value, salt._compat.string_types):
                attr_value = attr_value.encode(
                    'ascii', 'salt-cloud-force-ascii'
                )
            ret[img_name][attr] = attr_value
    return ret


def avail_sizes(conn=None):
    '''
    Return a dict of all available VM images on the cloud provider with
    relevant data
    '''
    if not conn:
        conn = get_conn()   # pylint: disable-msg=E0602

    sizes = conn.list_sizes()
    ret = {}
    for size in sizes:
        if isinstance(size.name, salt._compat.string_types):
            size_name = size.name.encode('ascii', 'salt-cloud-force-ascii')
        else:
            size_name = str(size.name)

        ret[size_name] = {}
        for attr in dir(size):
            if attr.startswith('_'):
                continue

            try:
                attr_value = getattr(size, attr)
            except Exception:
                pass

            if isinstance(attr_value, salt._compat.string_types):
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
    vm_location = config.get_config_value('location', vm_, __opts__).encode(
        'ascii', 'salt-cloud-force-ascii'
    )

    for img in locations:
        if isinstance(img.id, salt._compat.string_types):
            img_id = img.id.encode('ascii', 'salt-cloud-force-ascii')
        else:
            img_id = str(img.id)

        if isinstance(img.name, salt._compat.string_types):
            img_name = img.name.encode('ascii', 'salt-cloud-force-ascii')
        else:
            img_name = str(img.name)

        if vm_location and vm_location in (img_id, img_name):
            return img

    raise SaltCloudNotFound(
        'The specified location, {0!r}, could not be found.'.format(
            vm_location
        )
    )


def get_image(conn, vm_):
    '''
    Return the image object to use
    '''
    images = conn.list_images()

    vm_image = config.get_config_value('image', vm_, __opts__).encode(
        'ascii', 'salt-cloud-force-ascii'
    )

    for img in images:
        if isinstance(img.id, salt._compat.string_types):
            img_id = img.id.encode('ascii', 'salt-cloud-force-ascii')
        else:
            img_id = str(img.id)

        if isinstance(img.name, salt._compat.string_types):
            img_name = img.name.encode('ascii', 'salt-cloud-force-ascii')
        else:
            img_name = str(img.name)

        if vm_image and vm_image in (img_id, img_name):
            return img

    raise SaltCloudNotFound(
        'The specified image, {0!r}, could not be found.'.format(vm_image)
    )


def get_size(conn, vm_):
    '''
    Return the VM's size object
    '''
    sizes = conn.list_sizes()
    vm_size = config.get_config_value('size', vm_, __opts__)
    if not vm_size:
        return sizes[0]

    for size in sizes:
        if vm_size and str(vm_size) in (str(size.id), str(size.name)):
            return size
    raise SaltCloudNotFound(
        'The specified size, {0!r}, could not be found.'.format(vm_size)
    )


def script(vm_):
    '''
    Return the script deployment object
    '''
    return ScriptDeployment(
        saltcloud.utils.os_script(
            config.get_config_value('os', vm_, __opts__),
            vm_,
            __opts__,
            saltcloud.utils.salt_config_to_yaml(
                saltcloud.utils.minion_config(__opts__, vm_)
            )
        )
    )


def destroy(name, conn=None):
    '''
    Delete a single VM
    '''
    if not conn:
        conn = get_conn()   # pylint: disable-msg=E0602

    node = get_node(conn, name)
    if node is None:
        log.error('Unable to find the VM {0}'.format(name))
    log.info('Destroying VM: {0}'.format(name))
    ret = conn.destroy_node(node)
    if ret:
        log.info('Destroyed VM: {0}'.format(name))
        # Fire destroy action
        event = salt.utils.event.SaltEvent('master', __opts__['sock_dir'])
        try:
            event.fire_event(
                '{0} has been destroyed'.format(name), 'salt-cloud'
            )
        except ValueError:
            # We're using develop or a 0.17.x version of salt
            event.fire_event(
                {name: '{0} has been destroyed'.format(name)}, 'salt-cloud'
            )
        if __opts__['delete_sshkeys'] is True:
            saltcloud.utils.remove_sshkey(node.public_ips[0])
        return True

    log.error('Failed to Destroy VM: {0}'.format(name))
    return False


def reboot(name, conn=None):
    '''
    Reboot a single VM
    '''
    if not conn:
        conn = get_conn()   # pylint: disable-msg=E0602

    node = get_node(conn, name)
    if node is None:
        log.error('Unable to find the VM {0}'.format(name))
    log.info('Rebooting VM: {0}'.format(name))
    ret = conn.reboot_node(node)
    if ret:
        log.info('Rebooted VM: {0}'.format(name))
        # Fire reboot action
        # Fire destroy action
        event = salt.utils.event.SaltEvent('master', __opts__['sock_dir'])
        try:
            event.fire_event(
                '{0} has been rebooted'.format(name), 'salt-cloud'
            )
        except ValueError:
            # We're using develop or a 0.17.x version of salt
            event.fire_event(
                {name: '{0} has been rebooted'.format(name)}, 'salt-cloud'
            )
        return True

    log.error('Failed to reboot VM: {0}'.format(name))
    return False


def list_nodes(conn=None):
    '''
    Return a list of the VMs that are on the provider
    '''
    if not conn:
        conn = get_conn()   # pylint: disable-msg=E0602

    nodes = conn.list_nodes()
    ret = {}
    for node in nodes:
        ret[node.name] = {
            'id': node.id,
            'image': node.image,
            'private_ips': node.private_ips,
            'public_ips': node.public_ips,
            'size': node.size,
            'state': node_state(node.state)
        }
    return ret


def list_nodes_full(conn=None):
    '''
    Return a list of the VMs that are on the provider, with all fields
    '''
    if not conn:
        conn = get_conn()   # pylint: disable-msg=E0602

    nodes = conn.list_nodes()
    ret = {}
    for node in nodes:
        pairs = {}
        for key, value in zip(node.__dict__.keys(), node.__dict__.values()):
            pairs[key] = value
        ret[node.name] = pairs
    return ret


def list_nodes_select(conn=None):
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    if not conn:
        conn = get_conn()   # pylint: disable-msg=E0602

    nodes = conn.list_nodes()
    ret = {}
    for node in nodes:
        pairs = {}
        data = node.__dict__
        data.update(node.extra)
        for key in data:
            if str(key) in __opts__['query.selection']:
                value = data[key]
                pairs[key] = value
        ret[node.name] = pairs
    return ret


def conn_has_method(conn, method_name):
    '''
    Find if the provided connection object has a specific method
    '''
    if method_name in dir(conn):
        return True

    log.error(
        'Method {0!r} not yet supported!'.format(
            method_name
        )
    )
    return False
