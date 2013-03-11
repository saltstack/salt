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
import sys
import logging

# Import generic libcloud functions
from saltcloud.libcloudfuncs import *

# Import salt cloud utils
from saltcloud.utils import namespaced_function

# Get logging started
log = logging.getLogger(__name__)

# Some of the libcloud functions need to be in the same namespace as the
# functions defined in the module, so we create new function objects inside
# this module namespace
avail_images = namespaced_function(avail_images, globals())
avail_sizes = namespaced_function(avail_sizes, globals())
script = namespaced_function(script, globals())
destroy = namespaced_function(destroy, globals())
list_nodes = namespaced_function(list_nodes, globals())
list_nodes_full = namespaced_function(list_nodes_full, globals())
list_nodes_select = namespaced_function(list_nodes_select, globals())


# Only load in this module is the GOGRID configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for GOGRID configs
    '''
    confs = [
            'apikey',
            'sharedsecret',
            ]
    for conf in confs:
        if not __opts__['providers']['gogrid']:
            return False
        for provider in __opts__['providers']['gogrid']:
            if conf not in __opts__['providers']['gogrid'][provider]:
                return False
    log.debug('Loading GoGrid cloud module')
    return 'gogrid'


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    driver = get_driver(Provider.GOGRID)
    return driver(
            __opts__['GOGRID.apikey'],
            __opts__['GOGRID.sharedsecret'],
            )


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()
    kwargs = {}
    kwargs['name'] = vm_['name']
    kwargs['image'] = get_image(conn, vm_)
    kwargs['size'] = get_size(conn, vm_)
    try:
        data = conn.create_node(**kwargs)
    except Exception as exc:
        message = str(exc)
        err = ('Error creating {0} on GOGRID\n\n'
               'The following exception was thrown by libcloud when trying to '
               'run the initial deployment: \n{1}').format(
                       vm_['name'], message
                       )
        sys.stderr.write(err)
        log.error(err)
        return False

    deploy = vm_.get(
        'deploy',
        __opts__.get(
            'GOGRID.deploy',
            __opts__['deploy']
        )
    )
    ret = {}
    if deploy is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'host': data.public_ips[0],
            'username': 'root',
            'password': data.extra['password'],
            'script': deploy_script.script,
            'name': vm_['name'],
            'start_action': __opts__['start_action'],
            'sock_dir': __opts__['sock_dir'],
            'conf_file': __opts__['conf_file'],
            'minion_pem': vm_['priv_key'],
            'minion_pub': vm_['pub_key'],
            'keep_tmp': __opts__['keep_tmp'],
            }

        if 'script_args' in vm_:
            deploy_kwargs['script_args'] = vm_['script_args']

        deploy_kwargs['minion_conf'] = saltcloud.utils.minion_conf_string(
            __opts__,
            vm_
        )

        # Deploy salt-master files, if necessary
        if 'make_master' in vm_ and vm_['make_master'] is True:
            deploy_kwargs['make_master'] = True
            deploy_kwargs['master_pub'] = vm_['master_pub']
            deploy_kwargs['master_pem'] = vm_['master_pem']
            master_conf = saltcloud.utils.master_conf_string(__opts__, vm_)
            if master_conf:
                deploy_kwargs['master_conf'] = master_conf

            if 'syndic_master' in master_conf:
                deploy_kwargs['make_syndic'] = True

        deployed = saltcloud.utils.deploy_script(**deploy_kwargs)
        if deployed:
            log.info('Salt installed on {0}'.format(vm_['name']))
            ret['deploy_kwargs'] = deploy_kwargs
        else:
            log.error(
                'Failed to start Salt on Cloud VM {0}'.format(
                    vm_['name']
                )
            )

    log.info(
        'Created Cloud VM {0} with the following values:'.format(
            vm_['name']
        )
    )
    for key, val in data.__dict__.items():
        ret[key] = val
        log.info('  {0}: {1}'.format(key, val))

    return ret
