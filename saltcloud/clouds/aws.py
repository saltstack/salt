'''
The AWS Cloud Module
====================

The AWS cloud module is used to interact with the Amazon Web Services system.

To use the AWS cloud module the following configuration parameters need to be
set in the main cloud config:

.. code-block:: yaml

    # The AWS API authentication id
    AWS.id: GKTADJGHEIQSXMKKRBJ08H
    # The AWS API authentication key
    AWS.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
    # The ssh keyname to use
    AWS.keyname: default
    # The amazon security group
    AWS.securitygroup: ssh_open
    # The location of the private key which corresponds to the keyname
    AWS.private_key: /root/default.pem

'''

# Import python libs
import os
import sys
import types
import time
import tempfile
import subprocess

# Import libcloud
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment

# Import salt libs
import saltcloud.utils
from saltcloud.libcloudfuncs import *

# Import paramiko
import paramiko

# Init the libcloud functions
avail_images = types.FunctionType(avail_images.__code__, globals())
avail_sizes = types.FunctionType(avail_sizes.__code__, globals())
script = types.FunctionType(script.__code__, globals())
destroy = types.FunctionType(destroy.__code__, globals())
list_nodes = types.FunctionType(list_nodes.__code__, globals())


# Only load in this module if the AWS configurations are in place
def __virtual__():
    '''
    Set up the libcloud funcstions and check for AWS configs
    '''
    confs = [
            'AWS.id',
            'AWS.key',
            'AWS.keyname',
            'AWS.securitygroup',
            'AWS.private_key',
            ]
    for conf in confs:
        if conf not in __opts__:
            return False
    return 'aws'


def get_conn():
    '''
    Return a conn object for the passed vm data
    '''
    prov = 'EC2'
    if not hasattr(Provider, prov):
        return None
    driver = get_driver(getattr(Provider, 'EC2'))
    return driver(
            __opts__['AWS.id'],
            __opts__['AWS.key'],
            )


def keyname(vm_):
    '''
    Return the keyname
    '''
    return str(vm_.get('AWS.keyname', __opts__.get('AWS.keyname', '')))


def securitygroup(vm_):
    '''
    Return the keyname
    '''
    return str(vm_.get(
            'AWS.securitygroup',
            __opts__.get('AWS.securitygroup', 'default')
            ))


def create(vm_):
    '''
    Create a single vm from a data dict
    '''
    print('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()
    kwargs = {'ssh_username': 'ec2-user',
              'ssh_key': __opts__['AWS.private_key']}
    kwargs['name'] = vm_['name']
    deploy_script = script(vm_)
    kwargs['image'] = get_image(conn, vm_)
    kwargs['size'] = get_size(conn, vm_)
    ex_keyname = keyname(vm_)
    if ex_keyname:
        kwargs['ex_keyname'] = ex_keyname
    ex_securitygroup = securitygroup(vm_)
    if ex_securitygroup:
        kwargs['ex_securitygroup'] = ex_securitygroup
    try:
        data = conn.create_node(**kwargs)
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
    while not data.public_ips:
        time.sleep(0.5)
        data = get_node(conn, vm_['name'])
    if saltcloud.utils.wait_for_ssh(data.public_ips[0]):
        fd_, path = tempfile.mkstemp()
        os.close(fd_)
        with open(path, 'w+') as fp_:
            fp_.write(deploy_script.script)
        cmd = ('scp -oStrictHostKeyChecking=no -i {0} {3} {1}@{2}:/tmp/deploy.sh ').format(
                       __opts__['AWS.private_key'],
                       'ec2-user',
                       data.public_ips[0],
                       path,
                       )
        if subprocess.call(cmd, shell=True) != 0:
            time.sleep(15)
            cmd = ('scp -oStrictHostKeyChecking=no -i {0} {3} {1}@{2}:/tmp/deploy.sh ').format(
                       __opts__['AWS.private_key'],
                       'root',
                       data.public_ips[0],
                       path,
                       )
            subprocess.call(cmd, shell=True)
            cmd = ('ssh -oStrictHostKeyChecking=no -t -i {0} {1}@{2} '
                   '"sudo bash /tmp/deploy.sh"').format(
                       __opts__['AWS.private_key'],
                       'root',
                       data.public_ips[0],
                       )
        else:
            cmd = ('ssh -oStrictHostKeyChecking=no -t -i {0} {1}@{2} '
                   '"sudo bash /tmp/deploy.sh"').format(
                       __opts__['AWS.private_key'],
                       'ec2-user',
                       data.public_ips[0],
                       )
        subprocess.call(cmd, shell=True)
        os.remove(path)
    print('Created Cloud VM {0} with the following values:'.format(
        vm_['name']
        ))
    for key, val in data.__dict__.items():
        print('  {0}: {1}'.format(key, val))
