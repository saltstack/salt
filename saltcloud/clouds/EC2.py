'''
The generic libcloud template used to create the connections and deploy the
cloud virtual machines
'''

# Import python libs
import os
import sys
import subprocess

# Import libcloud
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment

# Import salt libs
import saltcloud.utils

# Import paramiko
import paramiko

def get_conn():
    '''
    Return a conn object for the passed vm data
    '''
    prov = 'EC2'
    if not hasattr(Provider, prov):
        return None
    driver = get_driver(getattr(Provider, 'EC2'))
    return driver(
            __opts__['EC2.id'],
            __opts__['EC2.key'],
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
                ),
            name='/home/ec2-user/deployment.sh'
            )


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


def keyname(vm_):
    '''
    Return the keyname
    '''
    return vm_.get('EC2.keyname', __opts__.get('EC2.keyname', ''))


def securitygroup(vm_):
    '''
    Return the keyname
    '''
    return vm_.get(
            'EC2.securitygroup',
            __opts__.get('EC2.securitygroup', 'default')
            )


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


def create(vm_):
    '''
    Create a single vm from a data dict
    '''
    print('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()
    kwargs = {'ssh_username': 'ec2-user',
              'ssh_key': __opts__['EC2.private_key']}
    kwargs['name'] = vm_['name']
    kwargs['deploy'] = script(vm_)
    kwargs['image'] = get_image(conn, vm_)
    kwargs['size'] = get_size(conn, vm_)
    ex_keyname = keyname(vm_)
    if ex_keyname:
        kwargs['ex_keyname'] = ex_keyname
    ex_securitygroup = securitygroup(vm_)
    if ex_securitygroup:
        kwargs['ex_securitygroup'] = ex_securitygroup
    try:
        data = conn.deploy_node(**kwargs)
    except Exception as exc:
        err = ('The following exception was thrown by libcloud when trying to '
               'run the initial deployment: \n{0}\n\nThe vm {1} has been '
               'created but Salt could not be intsalled. Please verify that '
               'your ssh keys are in order and that the security group is '
               'accepting inbound connections from port 22.\n').format(
                       exc, vm_['name']
                       )
        sys.stderr.write(err)
        return False
    cmd = ('ssh -oStrictHostKeyChecking=no -t -i {0} {1}@{2} "sudo '
           '/home/ec2-user/deployment.sh"').format(
                   __opts__['EC2.private_key'],
                   'ec2-user',
                   data.public_ips[0]
                   )
    subprocess.call(cmd, shell=True)
    print('Created Cloud VM {0} with the following values:'.format(
        vm_['name']
        ))
    for key, val in data.__dict__.items():
        print('  {0}: {1}'.format(key, val))
