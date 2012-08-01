'''
ElasticHosts Cloud Module
=========================

.. code-block:: yaml

    # The ElasticHosts login user
    ELASTICHOSTS.user: fred@example.com
    # The ElasticHosts user's password
    ELASTICHOSTS.password: saltybacon
    # The ElasticHosts loaction
    ELASTICHOSTS.location: UK1

'''

# The import section is mostly libcloud boilerplate

# Import python libs
import os
import types

# Import libcloud 
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment

# Import generic libcloud functions
from saltcloud.libcloudfuncs import *

# Some of the libcloud functions need to be in the same namespace as the
# functions defined in the module, so we create new function objects inside
# this module namespace
avail_images = types.FunctionType(avail_images.__code__, globals())
avail_sizes = types.FunctionType(avail_sizes.__code__, globals())
script = types.FunctionType(script.__code__, globals())
destroy = types.FunctionType(destroy.__code__, globals())
list_nodes = types.FunctionType(list_nodes.__code__, globals())


# Only load in this module is the ELASTICHOSTS configurations are in place
def __virtual__():
    '''
    Set up the libcloud funcstions and check for ELASTICHOSTS configs
    '''
    if 'ELASTICHOSTS.user' in __opts__ and 'ELASTICHOSTS.password' in __opts__:
        return 'elastichosts'
    return False


def get_conn():
    '''
    Return a conn object for the passed vm data
    '''
    driver = get_driver(
            getattr(
                Provider,
                'ELASTICHOSTS_{1}'.format(__opts__['ELASTICHOSTS.location'])
                )
            )
    return driver(
            __opts__['ELASTICHOSTS.user'],
            __opts__['ELASTICHOSTS.password'],
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
