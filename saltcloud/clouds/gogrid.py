'''
GoGrid Cloud Module
====================

The GoGrid cloud module. This module interfaces with the gogrid public cloud
service. To use Salt Cloud with GoGrid log into the GoGrid web interface and
create an api key. Do this by clicking on "My Account" and then going to the
API Keys tab.

The GOGRID.apikey and the GOGRID.sharedsecret configuration paramaters need to
be set in the config file to enable interfacing with GoGrid

.. code-block:: yaml

    # The generated api key to use
    GOGRID.apikey: asdff7896asdh789
    # The apikey's shared secret
    GOGRID.sharedsecret: saltybacon

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


# Only load in this module is the GOGRID configurations are in place
def __virtual__():
    '''
    Set up the libcloud funcstions and check for RACKSPACE configs
    '''
    if 'GOGRID.apikey' in __opts__ and 'GOGRID.sharedsecret' in __opts__:
        return 'gogrid'
    return False


def get_conn():
    '''
    Return a conn object for the passed vm data
    '''
    driver = get_driver(Provider.GOGRID)
    return driver(
            __opts__['GOGRID.apikey'],
            __opts__['GOGRID.sharedsecret'],
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
    try:
        data = conn.deploy_node(**kwargs)
    except Exception as exc:
        message = str(exc)
        print('The following error was returned: {0}'.format(message))
        return
    print('Created Cloud VM {0} with the following values:'.format(
        vm_['name']
        ))
    for key, val in data.__dict__.items():
        print('  {0}: {1}'.format(key, val))
