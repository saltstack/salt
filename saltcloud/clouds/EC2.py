'''
The EC2 cloud module
====================

The EC2 cloud module is used to interact with the amazon Web Services system.

To use the EC2 cloud module the following configuration parameters need to be
set in the main cloud config:

.. code-block:: yaml

    # The EC2 API authentication id
    EC2.id: GKTADJGHEIQSXMKKRBJ08H
    # The EC2 API authentication key
    EC2.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
    # The ssh keyname to use
    EC2.keyname: default
    # The amazon security group
    EC2.securitygroup: ssh_open
    # The location of the private key which corresponds to the keyname
    EC2.private_key: /root/default.pem

'''

# Import python libs
import os
import sys
import types
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
destroy = types.FunctionType(destroy.__code__, globals())
list_nodes = types.FunctionType(list_nodes.__code__, globals())


# Only load in this module if the EC2 configurations are in place
def __virtual__():
    '''
    Set up the libcloud funcstions and check for RACKSPACE configs
    '''
    confs = [
            'EC2.id',
            'EC2.key',
            'EC2.keyname',
            'EC2.securitygroup',
            'EC2.private_key',
            ]
    for conf in confs:
        if conf not in __opts__:
            return False
    return 'EC2'


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
