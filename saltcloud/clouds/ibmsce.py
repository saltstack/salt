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
import time
import logging

# Import libcloud
from libcloud.compute.base import NodeAuthSSHKey

# Import generic libcloud functions
from saltcloud.libcloudfuncs import *

# Import saltcloud libs
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
    Return a conn object for the passed VM data
    '''
    driver = get_driver(Provider.IBM)
    return driver(
        __opts__['IBMSCE.user'],
        __opts__['IBMSCE.password'],
    )


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()
    kwargs = {}
    vm_['location'] = __opts__['IBMSCE.location']
    kwargs['name'] = vm_['name']
    kwargs['image'] = get_image(conn, vm_)
    kwargs['size'] = get_size(conn, vm_)
    kwargs['location'] = get_location(conn, vm_)
    kwargs['auth'] = NodeAuthSSHKey(__opts__['IBMSCE.ssh_key_name'])

    log.debug(
        'Creating instance on {0} at {1}'.format(
            time.strftime('%Y-%m-%d'),
            time.strftime('%H:%M:%S')
        )
    )
    try:
        data = conn.create_node(**kwargs)
    except Exception as exc:
        log.error(
            'Error creating {0} on IBMSCE\n\n'
            'The following exception was thrown by libcloud when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_['name'], str(exc)
            )
        )
        return False

    not_ready = True
    nr_count = 0
    while not_ready:
        log.debug(
            'Looking for IP addresses for IBM SCE host {0} ({1} {2})'.format(
                vm_['name'],
                time.strftime('%Y-%m-%d'),
                time.strftime('%H:%M:%S'),
            )
        )
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

    deploy = vm_.get(
        'deploy',
        __opts__.get(
            'IBMSCE.deploy',
            __opts__['deploy']
        )
    )
    ret = {}
    if deploy is True:
        deploy_script = script(vm_)
        log.debug(
            'Deploying {0} using IP address {1}'.format(
                vm_['name'],
                data.public_ips[0]
            )
        )
        deploy_kwargs = {
            'host': data.public_ips[0],
            'username': 'idcuser',
            'provider': 'ibmsce',
            'password': data.extra['password'],
            'key_filename': __opts__['IBMSCE.ssh_key_file'],
            'script': deploy_script.script,
            'name': vm_['name'],
            'sudo': True,
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
            __opts__, vm_
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
                'Failed to start Salt on Cloud VM {0}'.format(vm_['name'])
            )

    log.info(
        'Created Cloud VM {0} with the following values:'.format(vm_['name'])
    )
    for key, val in data.__dict__.items():
        ret[key] = val
        log.info('  {0}: {1}'.format(key, val))

    return ret
