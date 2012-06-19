'''
The generic libcloud template used to create the connections and deploy the
cloud virtual machines
'''

# Import python libs
import os
import tempfile
import shutil

#
# Import libcloud
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment

# Import salt libs
import saltcloud.utils
import salt.crypt


def conn(vm_):
    '''
    Return a conn object for the passed vm data
    '''
    prov = 'EC2'
    if 'location' in vm_:
        prov += '_{0}'.format(vm_['location'])
    elif 'location' in __opts__:
        if __opts__['location']:
            prov += '_{0}'.format(__opts__['location'])
    if not hasattr(Provider, prov):
        return None
    driver = get_driver('EC2')
    return driver(
            __opts__['EC2_user'],
            __opts__['EC2_key'],
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


def script(vm_):
    '''
    Return the deployment object for managing a script
    '''
    os_ = ''
    if 'os' in vm_:
        os_ = vm_['os']
    if not os_:
        os_ = __opts__['os']
    return ScriptDeployment(saltcloud.utils.os_script(os_))


def image(conn, vm_):
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


def size(conn, vm_):
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


def create(vm_):
    '''
    Create a single vm from a data dict
    '''
    connection = conn(vm_)
    msd = MultiStepDeployment([ssh_pub(vm_), script(vm_)])
    image = image(conn, vm_)
    size = size(conn, vm_)
    return conn.deploy_node(
            name=vm_['name'],
            image=image,
            size=size,
            deploy=msd)

