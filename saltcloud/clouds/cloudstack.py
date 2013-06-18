'''
CloudStack Cloud Module
=======================

The CloudStack cloud module is used to control access to a CloudStack based
Public Cloud.

Use of this module requires the ``apikey``, ``secretkey``, ``host`` and
``path`` parameters.

.. code-block:: yaml

    my-cloudstack-cloud-config:
      apikey: <your api key >
      secretkey: <your secret key >
      host: localhost
      path: /client/api
      provider: cloudstack

'''

# Import python libs
import pprint
import logging

# Import salt cloud libs
import saltcloud.config as config
from saltcloud.libcloudfuncs import *   # pylint: disable-msg=W0614,W0401
from saltcloud.utils import namespaced_function

# Get logging started
log = logging.getLogger(__name__)

# Redirect CloudStack functions to this module namespace
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


# Only load in this module if the CLOUDSTACK configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for CloudStack configurations.
    '''
    if get_configured_provider() is False:
        log.debug(
            'There is no CloudStack cloud provider configuration available. '
            'Not loading module.'
        )
        return False

    log.debug('Loading CloudStack cloud module')
    return True


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'cloudstack',
        ('apikey', 'secretkey', 'host', 'path')
    )


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    driver = get_driver(Provider.CLOUDSTACK)
    return driver(
        key=config.get_config_value(
            'apikey', get_configured_provider(), __opts__, search_global=False
        ),
        secret=config.get_config_value(
            'secretkey', get_configured_provider(), __opts__,
            search_global=False
        ),
        host=config.get_config_value(
            'host', get_configured_provider(), __opts__, search_global=False
        ),
        path=config.get_config_value(
            'path', get_configured_provider(), __opts__, search_global=False
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


def get_key():
    '''
    Returns the ssk private key for VM access
    '''
    return config.get_config_value(
        'private_key', get_configured_provider(), __opts__, search_global=False
    )


def get_keypair(vm_):
    '''
    Return the keypair to use
    '''

    keypair = config.get_config_value('keypair', vm_, __opts__)

    if keypair is not None:
        return keypair

    raise SaltCloudNotFound('The specified keypair could not be found.')


def get_ip(data):
    '''
    Return the IP address of the VM
    If the VM has  public IP as defined by libcloud module then use it
    Otherwise try to extract the private IP and use that one.
    '''
    try:
        ip = data.public_ips[0]
    except:
        ip = data.private_ips[0]
    return ip


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
        'keypair': get_keypair(vm_),
    }
    try:
        data = conn.create_node(**kwargs)
        print data
    except Exception as exc:
        log.error(
            'Error creating {0} on CLOUDSTACK\n\n'
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
            'host': get_ip(data),
            'username': 'root',
            'key_filename': get_key(),
            'script': deploy_script.script,
            'name': vm_['name'],
            'deploy_command': '/tmp/deploy.sh',
            'start_action': __opts__['start_action'],
            'sock_dir': __opts__['sock_dir'],
            'conf_file': __opts__['conf_file'],
            'minion_pem': vm_['priv_key'],
            'minion_pub': vm_['pub_key'],
            'keep_tmp': __opts__['keep_tmp'],
            'preseed_minion_keys': vm_.get('preseed_minion_keys', None),
            'display_ssh_output': config.get_config_value(
                'display_ssh_output', vm_, __opts__, default=True
            ),
            'script_args': config.get_config_value(
                'script_args', vm_, __opts__
            ),
            'script_env': config.get_config_value('script_env', vm_, __opts__),
            'minion_conf': saltcloud.utils.minion_conf_string(__opts__, vm_)
        }

        # Deploy salt-master files, if necessary
        if config.get_config_value('make_master', vm_, __opts__) is True:
            deploy_kwargs['make_master'] = True
            deploy_kwargs['master_pub'] = vm_['master_pub']
            deploy_kwargs['master_pem'] = vm_['master_pem']
            master_conf = saltcloud.utils.master_config(__opts__, vm_)
            deploy_kwargs['master_conf'] = saltcloud.utils.salt_config_to_yaml(
                master_conf
            )

            if master_conf.get('syndic_master', None):
                deploy_kwargs['make_syndic'] = True

        deploy_kwargs['make_minion'] = config.get_config_value(
            'make_minion', vm_, __opts__, default=True
        )

        # Store what was used to the deploy the VM
        ret['deploy_kwargs'] = deploy_kwargs

        deployed = saltcloud.utils.deploy_script(**deploy_kwargs)
        if deployed:
            log.info('Salt installed on {0}'.format(vm_['name']))
        else:
            log.error(
                'Failed to start Salt on Cloud VM {0}'.format(
                    vm_['name']
                )
            )

    log.info('Created Cloud VM {0[name]!r}'.format(vm_))
    log.debug(
        '{0[name]!r} VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data.__dict__)
        )
    )

    ret.update(data.__dict__)
    return ret
