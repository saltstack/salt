'''
Linode Cloud Module
===================

The Linode cloud module is used to control access to the Linode VPS system

Use of this module only requires the ``apikey`` parameter.
If using the old cloud configuration syntax, add to salt cloud configuration
file:

.. code-block:: yaml

    # Linode account api key
    LINODE.apikey: JVkbSJDGHSDKUKSDJfhsdklfjgsjdkflhjlsdfffhgdgjkenrtuinv


Using the new format, set up the cloud configuration at
 ``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/linode.conf``:

.. code-block:: yaml

    my-linode-config:
      # Linode account api key
      apikey: JVkbSJDGHSDKUKSDJfhsdklfjgsjdkflhjlsdfffhgdgjkenrtuinv
      provider: linode

'''

# Import python libs
import sys
import logging

# Import libcloud
from libcloud.compute.base import NodeAuthPassword

# Import salt cloud libs
import saltcloud.config as config
from saltcloud.libcloudfuncs import *
from saltcloud.utils import namespaced_function


# Get logging started
log = logging.getLogger(__name__)


# Redirect linode functions to this module namespace
get_size = namespaced_function(get_size, globals())
get_image = namespaced_function(get_image, globals())
avail_locations = namespaced_function(avail_locations, globals())
avail_images = namespaced_function(avail_images, globals())
avail_sizes = namespaced_function(avail_sizes, globals())
script = namespaced_function(script, globals())
destroy = namespaced_function(destroy, globals())
list_nodes = namespaced_function(list_nodes, globals())
list_nodes_full = namespaced_function(list_nodes_full, globals())
list_nodes_select = namespaced_function(list_nodes_select, globals())


# Only load in this module if the LINODE configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for Linode configurations.
    '''
    if get_configured_provider() is False:
        log.debug(
            'There is no Linode cloud provider configuration available. Not '
            'loading module.'
        )
        return False

    log.debug('Loading Linode cloud module')
    return False


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(__opts__, 'linode', ('apikey',))


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    driver = get_driver(Provider.LINODE)
    return driver(
        config.get_config_value(
            'apikey', get_configured_provider(), __opts__, search_global=False
        )
    )


def get_location(conn, vm_):
    '''
    Return the node location to use
    '''
    locations = conn.list_locations()
    # Default to Dallas if not otherwise set
    loc = config.get_config_value('location', vm_, __opts__, default=2)
    for location in locations:
        if str(loc) in (str(location.id), str(location.name)):
            return location


def get_password(vm_):
    '''
    Return the password to use
    '''
    return config.get_config_value(
        'password', vm_, __opts__, default=config.get_config_value(
            'passwd', vm_, __opts__, search_global=False
        ), search_global=False
    )


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()
    kwargs = {
        'name': vm_['name'],
        'image': get_image(conn, vm_),
        'size': get_size(conn, vm_),
        'location': get_location(conn, vm_),
        'auth': NodeAuthPassword(get_password(vm_))
    }
    try:
        data = conn.create_node(**kwargs)
    except Exception as exc:
        log.error(
            'Error creating {0} on LINODE\n\n'
            'The following exception was thrown by libcloud when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_['name'], exc.message
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return False

    ret = {}
    if config.get_config_value('deploy', vm_, __opts__) is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'host': data.public_ips[0],
            'username': 'root',
            'password': get_password(vm_),
            'script': deploy_script.script,
            'name': vm_['name'],
            'deploy_command': '/tmp/deploy.sh',
            'start_action': __opts__['start_action'],
            'sock_dir': __opts__['sock_dir'],
            'conf_file': __opts__['conf_file'],
            'minion_pem': vm_['priv_key'],
            'minion_pub': vm_['pub_key'],
            'keep_tmp': __opts__['keep_tmp'],
            'script_args': config.get_config_value(
                'script_args', vm_, __opts__
            )
        }

        deploy_kwargs['minion_conf'] = saltcloud.utils.minion_conf_string(
            __opts__,
            vm_
        )

        # Deploy salt-master files, if necessary
        if config.get_config_value('make_master', vm_, __opts__) is True:
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
            if __opts__.get('show_deploy_args', False) is True:
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
