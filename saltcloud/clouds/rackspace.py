'''
The generic libcloud template used to create the connections and deploy the
cloud virtual machines
'''

# Import python libs
import os

# Import libcloud
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment
from libcloud.compute.types import NodeState

# Import salt libs
import saltcloud.utils


def _get_node(conn, name):
    '''
    Return a libcloud node for the named vm
    '''
    nodes = conn.list_nodes()
    for node in nodes:
        if node.name == name:
            return node


def get_conn():
    '''
    Return a conn object for the passed vm data
    '''
    driver = get_driver(Provider.RACKSPACE)
    return driver(
            __opts__['RACKSPACE.user'],
            __opts__['RACKSPACE.key'],
            )


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
            ret[size.name][attr] = getattr(size, attr)
    return ret


def get_image(conn, vm_):
    '''
    Return the image object to use
    '''
    images = conn.list_images()
    if not 'image' in vm_:
        return images[0]
    if isinstance(vm_['image'], int):
        return images[vm_['image']]
    for img in images:
        if img.id == vm_['image']:
            return img
        if img.name == vm_['image']:
            return img


def get_size(conn, vm_):
    '''
    Return the vm's size object
    '''
    sizes = conn.list_sizes()
    if not 'size' in vm_:
        return sizes[0]
    if isinstance(vm_['size'], int):
        return sizes[vm_['size']]
    for size in sizes:
        if size.id == vm_['size']:
            return size
        if size.name == vm_['size']:
            return size


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


def create(vm_):
    '''
    Create a single vm from a data dict
    '''
    print('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()
    kwargs = {}
    kwargs['name'] = vm_['name']
    kwargs['deploy'] = script(vm_)
    kwargs['image'] = get_image(conn, vm_)
    kwargs['size'] = get_size(conn, vm_)
    data = conn.deploy_node(**kwargs)
    print('Created Cloud VM {0} with the following values:'.format(
        vm_['name']
        ))
    for key, val in data.__dict__.items():
        print('  {0}: {1}'.format(key, val))


def destroy(name):
    '''
    Delete a single vm
    '''
    conn = get_conn()
    node = _get_node(conn, name)
    if node is None:
        print('Unable to find the VM {0}'.format(name))
    print('Destroying VM: {0}'.format(name))
    ret = conn.destroy_node(node)
    if ret:
        print('Destroyed VM: {0}'.format(name))
    else:
        print('Failed to Destroy VM: {0}'.format(name))


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
