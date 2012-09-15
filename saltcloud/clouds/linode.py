'''
Linode Cloud Module
===================

The Linode cloud module is used to control access to the Linode VPS system

Use of this module only requires the LINODE.apikey paramater to be set in
the cloud configuration file

.. code-block:: yaml

    # Linode account api key
    LINODE.apikey: JVkbSJDGHSDKUKSDJfhsdklfjgsjdkflhjlsdfffhgdgjkenrtuinv

'''

# Import python libs
import os
import types

# Import libcloud
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment
from libcloud.compute.types import NodeState
from libcloud.compute.base import NodeAuthPassword

# Import salt libs
from saltcloud.libcloudfuncs import *

# Redirect linode functions to this module namespace
avail_images = types.FunctionType(avail_images.__code__, globals())
avail_sizes = types.FunctionType(avail_sizes.__code__, globals())
script = types.FunctionType(script.__code__, globals())
destroy = types.FunctionType(destroy.__code__, globals())
list_nodes = types.FunctionType(list_nodes.__code__, globals())


# Only load in this module if the LINODE configurations are in place
def __virtual__():
    '''
    Set up the libcloud funcstions and check for RACKSPACE configs
    '''
    if 'LINODE.apikey' in __opts__:
        return 'linode'
    return False


def get_conn():
    '''
    Return a conn object for the passed vm data
    '''
    driver = get_driver(Provider.LINODE)
    return driver(
            __opts__['LINODE.apikey'],
            )


def get_location(conn, vm_):
    '''
    Return the node location to use
    '''
    locations = conn.list_locations()
    # Default to Dallas if not otherwise set
    loc = 2
    if 'location' in vm_:
        loc = vm_['location']
    elif 'LINODE.location' in __opts__:
        loc = __opts__['LINODE.location']
    for location in locations:
        if str(location.id) == str(loc):
            return location
        if location.name == loc:
            return location


def get_password(vm_):
    '''
    Return the password to use
    '''
    if 'password' in vm_:
        return vm_['password']
    elif 'passwd' in vm_:
        return vm_['passwd']
    elif 'LINODE.password' in __opts__:
        return __opts__['LINODE.password']


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
    kwargs['location'] = get_location(conn, vm_)
    kwargs['auth'] = NodeAuthPassword(get_password(vm_))
    try:
        data = conn.deploy_node(**kwargs)
    except Exception as exc:
        err = ('Error creating {0} on LINODE\n\n'
               'The following exception was thrown by libcloud when trying to '
               'run the initial deployment: \n{1}').format(
                       vm_['name'], exc.message
                       )
        sys.stderr.write(err)
        return False
    print('Created Cloud VM {0} with the following values:'.format(
        vm_['name']
        ))
    for key, val in data.__dict__.items():
        print('  {0}: {1}'.format(key, val))
