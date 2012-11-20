'''
IBM SCE Cloud Module
====================

The IBM SCE cloud module. This module interfaces with the IBM SCE public cloud
service. To use Salt Cloud with IBM SCE log into the IBM SCE web interface and
create an SSH key.

The following paramters are required in order to create a node:

.. code-block:: yaml

    # The generated api key to use
    IBMSCE.user: myuser@mycompany.com
    # The user's password
    IBMSCE.password: saltybacon
    # The name of the ssh key to use
    IBMSCE.ssh_key_name: mykey
    # The ID of the datacenter to use
    IBMSCE.location: Raleigh

'''

# The import section is mostly libcloud boilerplate

# Import python libs
import os
import sys
import subprocess
import time
import types
import logging

# Import libcloud 
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment
from libcloud.compute.base import NodeAuthSSHKey

# Import generic libcloud functions
from saltcloud.libcloudfuncs import *

# Get logging started
log = logging.getLogger(__name__)

# Some of the libcloud functions need to be in the same namespace as the
# functions defined in the module, so we create new function objects inside
# this module namespace
avail_locations = types.FunctionType(avail_locations.__code__, globals())
avail_images = types.FunctionType(avail_images.__code__, globals())
avail_sizes = types.FunctionType(avail_sizes.__code__, globals())
script = types.FunctionType(script.__code__, globals())
destroy = types.FunctionType(destroy.__code__, globals())
list_nodes = types.FunctionType(list_nodes.__code__, globals())
list_nodes_full = types.FunctionType(list_nodes_full.__code__, globals())
list_nodes_select = types.FunctionType(list_nodes_select.__code__, globals())


# Only load in this module is the IBMSCE configurations are in place
def __virtual__():
    '''
    Set up the libcloud funcstions and check for RACKSPACE configs
    '''
    if 'IBMSCE.user' in __opts__ and 'IBMSCE.password' in __opts__:
        log.debug('Loading IBM SCE cloud module')
        return 'ibmsce'
    return False


def get_conn():
    '''
    Return a conn object for the passed vm data
    '''
    driver = get_driver(Provider.IBM)
    return driver(
            __opts__['IBMSCE.user'],
            __opts__['IBMSCE.password'],
            )


def create(vm_):
    '''
    Create a single vm from a data dict
    '''
    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()
    deploy_script = script(vm_)
    kwargs = {}
    vm_['location'] = __opts__['IBMSCE.location']
    kwargs['name'] = vm_['name']
    kwargs['image'] = get_image(conn, vm_)
    kwargs['size'] = get_size(conn, vm_)
    kwargs['location'] = get_location(conn, vm_)
    kwargs['auth'] = NodeAuthSSHKey(__opts__['IBMSCE.ssh_key_name'])

    log.debug('Creating instance on {0} at {1}'.format(time.strftime('%Y-%m-%d'), time.strftime('%H:%M:%S')))
    try:
        data = conn.create_node(**kwargs)
    except Exception as exc:
        message = str(exc)
        err = ('Error creating {0} on IBMSCE\n\n'
               'The following exception was thrown by libcloud when trying to '
               'run the initial deployment: \n{1}').format(
                       vm_['name'], message
                       )
        log.error(err)
        return False

    not_ready = True
    nr_count = 0
    while not_ready:
        msg=('Looking for IP addresses for IBM SCE host {0} ({1} {2})'.format(
                vm_['name'],
                time.strftime('%Y-%m-%d'),
                time.strftime('%H:%M:%S'),
            ))
        log.debug(msg)
        nodelist = list_nodes()
        private = nodelist[vm_['name']]['private_ips']
        if private:
            data.private_ips = private
        public = nodelist[vm_['name']]['public_ips']
        if public:
            data.public_ips = public
            not_ready = False
        nr_count += 1
        if nr_count > 100:
            not_ready = False
        time.sleep(15)

    if __opts__['deploy'] is True:
        log.debug('Deploying {0} using IP address {1}'.format(vm_['name'], data.public_ips[0]))
        deployed = saltcloud.utils.deploy_script(
            host=data.public_ips[0],
            username='idcuser',
            key_filename=__opts__['IBMSCE.ssh_key_file'],
            script=deploy_script.script,
            name=vm_['name'],
            provider='ibmsce',
            sudo=True,
            start_action=__opts__['start_action'],
            sock_dir=__opts__['sock_dir'])
        if deployed:
            log.info('Salt installed on {0}'.format(vm_['name']))
        else:
            log.error('Failed to start Salt on Cloud VM {0}'.format(vm_['name']))

    log.info('Created Cloud VM {0} with the following values:'.format(vm_['name']))
    for key, val in data.__dict__.items():
        log.info('  {0}: {1}'.format(key, val))
