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
from libcloud.compute.base import NodeAuthPassword

# Import salt libs
import saltcloud.utils
from saltcloud.libcloudfuncs import *


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
    data = conn.deploy_node(**kwargs)
    print('Created Cloud VM {0} with the following values:'.format(
        vm_['name']
        ))
    for key, val in data.__dict__.items():
        print('  {0}: {1}'.format(key, val))
