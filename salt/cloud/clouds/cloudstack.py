# -*- coding: utf-8 -*-
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
# pylint: disable=E0102

# Import python libs
import copy
import pprint
import logging

# Import salt cloud libs
import salt.config as config
from salt.cloud.libcloudfuncs import *   # pylint: disable=W0614,W0401
from salt.utils import namespaced_function
from salt.cloud.exceptions import SaltCloudSystemExit

# CloudStackNetwork will be needed during creation of a new node
try:
    from libcloud.compute.drivers.cloudstack import CloudStackNetwork
    HASLIBS = True
except ImportError:
    HASLIBS = False

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
show_instance = namespaced_function(show_instance, globals())


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

    verify_ssl_cert = config.get_cloud_config_value('verify_ssl_cert',
            get_configured_provider(),
            __opts__,
            default=True,
            search_global=False)

    if verify_ssl_cert is False:
        try:
            import libcloud.security
            libcloud.security.VERIFY_SSL_CERT = False
        except (ImportError, AttributeError):
            raise SaltCloudSystemExit(
                'Could not disable SSL certificate verification. '
                'Not loading module.'
            )

    return driver(
        key=config.get_cloud_config_value(
            'apikey', get_configured_provider(), __opts__, search_global=False
        ),
        secret=config.get_cloud_config_value(
            'secretkey', get_configured_provider(), __opts__,
            search_global=False
        ),
        secure=config.get_cloud_config_value(
            'secure', get_configured_provider(), __opts__,
            default=True, search_global=False
        ),
        host=config.get_cloud_config_value(
            'host', get_configured_provider(), __opts__, search_global=False
        ),
        path=config.get_cloud_config_value(
            'path', get_configured_provider(), __opts__, search_global=False
        ),
        port=config.get_cloud_config_value(
            'port', get_configured_provider(), __opts__,
            default=None, search_global=False
        )
    )


def get_location(conn, vm_):
    '''
    Return the node location to use
    '''
    locations = conn.list_locations()
    # Default to Dallas if not otherwise set
    loc = config.get_cloud_config_value('location', vm_, __opts__, default=2)
    for location in locations:
        if str(loc) in (str(location.id), str(location.name)):
            return location


def get_password(vm_):
    '''
    Return the password to use
    '''
    return config.get_cloud_config_value(
        'password', vm_, __opts__, default=config.get_cloud_config_value(
            'passwd', vm_, __opts__, search_global=False
        ), search_global=False
    )


def get_key():
    '''
    Returns the ssk private key for VM access
    '''
    return config.get_cloud_config_value(
        'private_key', get_configured_provider(), __opts__, search_global=False
    )


def get_keypair(vm_):
    '''
    Return the keypair to use
    '''
    keypair = config.get_cloud_config_value('keypair', vm_, __opts__)

    if keypair:
        return keypair
    else:
        return False


def get_ip(data):
    '''
    Return the IP address of the VM
    If the VM has  public IP as defined by libcloud module then use it
    Otherwise try to extract the private IP and use that one.
    '''
    try:
        ip = data.public_ips[0]
    except Exception:
        ip = data.private_ips[0]
    return ip


def get_networkid(vm_):
    '''
    Return the networkid to use, only valid for Advanced Zone
    '''
    networkid = config.get_cloud_config_value('networkid', vm_, __opts__)

    if networkid is not None:
        return networkid
    else:
        return False


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    salt.utils.cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
    )

    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()
    kwargs = {
        'name': vm_['name'],
        'image': get_image(conn, vm_),
        'size': get_size(conn, vm_),
        'location': get_location(conn, vm_),
    }

    if get_keypair(vm_) is not False:
        kwargs['extra_args'] = {'keypair': get_keypair(vm_)}

    if get_networkid(vm_) is not False:
        kwargs['networkids'] = get_networkid(vm_)

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': {'name': kwargs['name'],
                    'image': kwargs['image'].name,
                    'size': kwargs['size'].name}},
    )

    try:
        data = conn.create_node(**kwargs)
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

    ssh_username = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__, default='root'
    )

    ret = {}
    if config.get_cloud_config_value('deploy', vm_, __opts__) is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'host': get_ip(data),
            'username': ssh_username,
            #'password': data.extra['password'],
            'key_filename': get_key(),
            'script': deploy_script.script,
            'name': vm_['name'],
            'tmp_dir': config.get_cloud_config_value(
                'tmp_dir', vm_, __opts__, default='/tmp/.saltcloud'
            ),
            'deploy_command': config.get_cloud_config_value(
                'deploy_command', vm_, __opts__,
                default='/tmp/.saltcloud/deploy.sh',
            ),
            'start_action': __opts__['start_action'],
            'parallel': __opts__['parallel'],
            'sock_dir': __opts__['sock_dir'],
            'conf_file': __opts__['conf_file'],
            'minion_pem': vm_['priv_key'],
            'minion_pub': vm_['pub_key'],
            'keep_tmp': __opts__['keep_tmp'],
            'preseed_minion_keys': vm_.get('preseed_minion_keys', None),
            'sudo': config.get_cloud_config_value(
                'sudo', vm_, __opts__, default=(ssh_username != 'root')
            ),
            'sudo_password': config.get_cloud_config_value(
                'sudo_password', vm_, __opts__, default=None
            ),
            'tty': config.get_cloud_config_value(
                'tty', vm_, __opts__, default=False
            ),
            'display_ssh_output': config.get_cloud_config_value(
                'display_ssh_output', vm_, __opts__, default=True
            ),
            'script_args': config.get_cloud_config_value(
                'script_args', vm_, __opts__
            ),
            'script_env': config.get_cloud_config_value('script_env', vm_, __opts__),
            'minion_conf': salt.utils.cloud.minion_config(__opts__, vm_)
        }

        # Deploy salt-master files, if necessary
        if config.get_cloud_config_value('make_master', vm_, __opts__) is True:
            deploy_kwargs['make_master'] = True
            deploy_kwargs['master_pub'] = vm_['master_pub']
            deploy_kwargs['master_pem'] = vm_['master_pem']
            master_conf = salt.utils.cloud.master_config(__opts__, vm_)
            deploy_kwargs['master_conf'] = master_conf

            if master_conf.get('syndic_master', None):
                deploy_kwargs['make_syndic'] = True

        deploy_kwargs['make_minion'] = config.get_cloud_config_value(
            'make_minion', vm_, __opts__, default=True
        )

        # Check for Windows install params
        win_installer = config.get_cloud_config_value('win_installer', vm_, __opts__)
        if win_installer:
            deploy_kwargs['win_installer'] = win_installer
            minion = salt.utils.cloud.minion_config(__opts__, vm_)
            deploy_kwargs['master'] = minion['master']
            deploy_kwargs['username'] = config.get_cloud_config_value(
                'win_username', vm_, __opts__, default='Administrator'
            )
            deploy_kwargs['password'] = config.get_cloud_config_value(
                'win_password', vm_, __opts__, default=''
            )

        # Store what was used to the deploy the VM
        event_kwargs = copy.deepcopy(deploy_kwargs)
        del event_kwargs['minion_pem']
        del event_kwargs['minion_pub']
        del event_kwargs['sudo_password']
        if 'password' in event_kwargs:
            del event_kwargs['password']
        ret['deploy_kwargs'] = event_kwargs

        salt.utils.cloud.fire_event(
            'event',
            'executing deploy script',
            'salt/cloud/{0}/deploying'.format(vm_['name']),
            {'kwargs': event_kwargs},
        )

        deployed = False
        if win_installer:
            deployed = salt.utils.cloud.deploy_windows(**deploy_kwargs)
        else:
            deployed = salt.utils.cloud.deploy_script(**deploy_kwargs)

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

    salt.utils.cloud.fire_event(
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
    )

    return ret
