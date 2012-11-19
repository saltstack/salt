'''
The generic libcloud template used to create the connections and deploy the
cloud virtual machines
'''

# Import python libs
import os
import logging

# Import libcloud
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment

# Import salt libs
import salt.utils.event
import saltcloud.utils

# Get logging started
log = logging.getLogger(__name__)


def get_node(conn, name):
    '''
    Return a libcloud node for the named vm
    '''
    nodes = conn.list_nodes()
    for node in nodes:
        if node.name == name:
            return node


def ssh_pub(vm_):
    '''
    Deploy the primary ssh authentication key
    '''
    ssh = ''
    if 'ssh_auth' in vm_:
        if not os.path.isfile(vm_['ssh_auth']):
            return None
        ssh = vm_['ssh_auth']
    if not ssh:
        if not os.path.isfile(__opts__['ssh_auth']):
            return None
        ssh = __opts__['ssh_auth']

    return SSHKeyDeployment(open(os.path.expanduser(ssh)).read())


def avail_locations():
    '''
    Return a dict of all available vm locations on the cloud provider with
    relevant data
    '''
    conn = get_conn()
    locations = conn.list_locations()
    ret = {}
    for img in locations:
        ret[img.name] = {}
        for attr in dir(img):
            if attr.startswith('_'):
                continue
            ret[img.name][attr] = getattr(img, attr)
    return ret


def avail_images():
    '''
    Return a dict of all available vm images on the cloud provider with
    relevant data
    '''
    conn = get_conn()
    images = conn.list_images()
    ret = {}
    for img in images:
        ret[img.name] = {}
        for attr in dir(img):
            if attr.startswith('_'):
                continue
            ret[img.name][attr] = getattr(img, attr)
    return ret


def avail_sizes():
    '''
    Return a dict of all available vm images on the cloud provider with
    relevant data
    '''
    conn = get_conn()
    sizes = conn.list_sizes()
    ret = {}
    for size in sizes:
        ret[size.name] = {}
        for attr in dir(size):
            if attr.startswith('_'):
                continue
            try:
                ret[size.name][attr] = getattr(size, attr)
            except Exception:
                pass
    return ret


def get_location(conn, vm_):
    '''
    Return the location object to use
    '''
    locations = conn.list_locations()
    for img in locations:
        if str(img.id) == str(vm_['location']):
            return img
        if img.name == str(vm_['location']):
            return img
    raise ValueError("The specified location could not be found.")


def get_image(conn, vm_):
    '''
    Return the image object to use
    '''
    images = conn.list_images()
    for img in images:
        if str(img.id) == str(vm_['image']):
            return img
        if img.name == str(vm_['image']):
            return img
    raise ValueError("The specified image could not be found.")


def get_size(conn, vm_):
    '''
    Return the vm's size object
    '''
    sizes = conn.list_sizes()
    if not 'size' in vm_:
        return sizes[0]
    for size in sizes:
        if str(size.id) == str(vm_['size']):
            return size
        if str(size.name) == str(vm_['size']):
            return size
    raise ValueError("The specified size could not be found.")


def script(vm_):
    '''
    Return the script deployment object
    '''
    minion = saltcloud.utils.minion_conf_string(__opts__, vm_)
    return ScriptDeployment(
            saltcloud.utils.os_script(
                saltcloud.utils.get_option(
                    'os',
                    __opts__,
                    vm_
                    ),
                vm_,
                __opts__,
                minion,
                )
            )


def destroy(name):
    '''
    Delete a single vm
    '''
    conn = get_conn()
    node = get_node(conn, name)
    if node is None:
        log.error('Unable to find the VM {0}'.format(name))
    log.info('Destroying VM: {0}'.format(name))
    ret = conn.destroy_node(node)
    if ret:
        log.info('Destroyed VM: {0}'.format(name))
        # Fire destroy action
        event = salt.utils.event.SaltEvent(
            'master',
            __opts__['sock_dir']
            )
        event.fire_event('{0} has been destroyed'.format(name), 'salt-cloud')
        return True
    else:
        log.error('Failed to Destroy VM: {0}'.format(name))
        return False


def list_nodes():
    '''
    Return a list of the vms that are on the provider
    '''
    conn = get_conn() 
    nodes = conn.list_nodes()
    ret = {}
    for node in nodes:
        ret[node.name] = {
                'id': node.id,
                'image': node.image,
                'private_ips': node.private_ips,
                'public_ips': node.public_ips,
                'size': node.size,
                'state': node.state}
    return ret


def list_nodes_full():
    '''
    Return a list of the vms that are on the provider, with all fields
    '''
    conn = get_conn() 
    nodes = conn.list_nodes()
    ret = {}
    for node in nodes:
        pairs = {}
        for key, value in zip(node.__dict__.keys(), node.__dict__.values()):
            pairs[key] = value
        ret[node.name] = pairs
    return ret


def list_nodes_select():
    '''
    Return a list of the vms that are on the provider, with select fields
    '''
    conn = get_conn() 
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

