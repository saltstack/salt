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
    # The location of the ssh private key that can log into the new VM
    JOYENT.private_key: /root/joyent.pem

'''

# The import section is mostly libcloud boilerplate

# Import python libs
import logging

# Import generic libcloud functions
from saltcloud.libcloudfuncs import *

# Import saltcloud libs
import saltcloud.utils
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


# Only load in this module is the JOYENT configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for JOYENT configs
    '''
    if 'JOYENT.user' in __opts__ and 'JOYENT.password' in __opts__:
        log.debug('Loading Joyent cloud module')
        return 'joyent'
    return False


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    driver = get_driver(Provider.JOYENT)
    return driver(
            __opts__['JOYENT.user'],
            __opts__['JOYENT.password'],
            )


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    saltcloud.utils.check_name(vm_['name'], '[a-z0-9-]')
    conn = get_conn()
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
        log.error(err)
        return False
    if __opts__['deploy'] is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'host': data.public_ips[0],
            'username': 'root',
            'key_filename': __opts__['JOYENT.private_key'],
            'script': deploy_script.script,
            'name': vm_['name'],
            'deploy_command': '/tmp/deploy.sh',
            'tty': True,
            'start_action': __opts__['start_action'],
            'sock_dir': __opts__['sock_dir'],
            'conf_file': __opts__['conf_file'],
            'minion_pem': vm_['priv_key'],
            'minion_pub': vm_['pub_key'],
            'keep_tmp': __opts__['keep_tmp'],
            }

        if 'script_args' in vm_:
            deploy_kwargs['script_args'] = vm_['script_args']

        deploy_kwargs['minion_conf'] = saltcloud.utils.minion_conf_string(__opts__, vm_)
        deployed = saltcloud.utils.deploy_script(**deploy_kwargs)
        if deployed:
            log.info('Salt installed on {0}'.format(vm_['name']))
        else:
            log.error('Failed to start Salt on Cloud VM {0}'.format(vm_['name']))

    ret = {}
    log.info('Created Cloud VM {0} with the following values:'.format(vm_['name']))
    for key, val in data.__dict__.items():
        ret[key] = val
        log.info('  {0}: {1}'.format(key, val))

    return ret


def stop(name, call=None):
    '''
    Stop a node
    '''
    data = {}

    if call != 'action':
        print('This action must be called with -a or --action.')
        sys.exit(1)

    conn = get_conn()
    node = get_node(conn, name)
    try:
        data = conn.ex_stop_node(node=node)
        log.debug(data)
        log.info('Stopped node {0}'.format(name))
    except Exception as exc:
        log.error('Failed to stop node {0}'.format(name))
        log.error(exc)

    return data

