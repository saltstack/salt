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
from saltcloud.libcloudfuncs import *

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
