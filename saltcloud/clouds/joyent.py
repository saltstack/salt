'''
Joyent Cloud Module
===================

The Joyent Cloud module is used to intereact with the Joyent cloud system

it requires that the username and password to the joyent accound be configured

.. code-block:: yaml

    # The Joyent login user
    JOYENT.user: fred
    # The Joyent user's password
    JOYENT.password: saltybacon
    # The location of the ssh private key that can log into the new vm
    JOYENT.private_key: /root/joyent.pem

'''

# The import section is mostly libcloud boilerplate

# Import python libs
import os
import subprocess
import types

# Import libcloud 
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment

# Import generic libcloud functions
import saltcloud.utils
from saltcloud.libcloudfuncs import *


# Some of the libcloud functions need to be in the same namespace as the
# functions defined in the module, so we create new function objects inside
# this module namespace
avail_images = types.FunctionType(avail_images.__code__, globals())
avail_sizes = types.FunctionType(avail_sizes.__code__, globals())
script = types.FunctionType(script.__code__, globals())
destroy = types.FunctionType(destroy.__code__, globals())
list_nodes = types.FunctionType(list_nodes.__code__, globals())


# Only load in this module is the JOYENT configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for JOYENT configs
    '''
    if 'JOYENT.user' in __opts__ and 'JOYENT.password' in __opts__:
        return 'joyent'
    return False


def get_conn():
    '''
    Return a conn object for the passed vm data
    '''
    driver = get_driver(Provider.JOYENT)
    return driver(
            __opts__['JOYENT.user'],
            __opts__['JOYENT.password'],
            )


def create(vm_):
    '''
    Create a single vm from a data dict
    '''
    print('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()
    deploy_script = script(vm_)
    kwargs = {}
    kwargs['name'] = vm_['name']
    kwargs['image'] = get_image(conn, vm_)
    kwargs['size'] = get_size(conn, vm_)
    try:
        data = conn.create_node(**kwargs)
    except Exception as exc:
        err = ('Error creating {0} on JOYENT\n\n'
               'The following exception was thrown by libcloud when trying to '
               'run the initial deployment: \n{1}').format(
                       vm_['name'], exc.message
                       )
        sys.stderr.write(err)
        return False
    if saltcloud.utils.wait_for_ssh(data.public_ips[0]):
        cmd = ('ssh -oStrictHostKeyChecking=no -t -i {0} {1}@{2} '
               '"{3}"').format(
                       __opts__['JOYENT.private_key'],
                       'root',
                       data.public_ips[0],
                       deploy_script.script,
                       )
        subprocess.call(cmd, shell=True)
    else:
        print('Failed to start Salt on Cloud VM {0}'.format(vm_['name']))

    print('Created Cloud VM {0} with the following values:'.format(
        vm_['name']
        ))
    for key, val in data.__dict__.items():
        print('  {0}: {1}'.format(key, val))
