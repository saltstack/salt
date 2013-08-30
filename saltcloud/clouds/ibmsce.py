'''
IBM SCE Cloud Module
====================

The IBM SCE cloud module. This module interfaces with the IBM SCE public cloud
service. To use Salt Cloud with IBM SCE log into the IBM SCE web interface and
create an SSH key.

Using the old configuration syntax, the following parameters are required in
order to create a node:

.. code-block:: yaml

    # The generated api key to use
    IBMSCE.user: myuser@mycompany.com
    # The user's password
    IBMSCE.password: saltybacon
    # The name of the ssh key to use
    IBMSCE.ssh_key_name: mykey
    # The ID of the datacenter to use
    IBMSCE.location: Raleigh


Using the new format, set up the cloud configuration at
``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/ibmsce.conf``:

.. code-block:: yaml

    my-imbsce-config:
      # The generated api key to use
      user: myuser@mycompany.com
      # The user's password
      password: saltybacon
      # The name of the ssh key to use
      ssh_key_name: mykey
      # The ID of the datacenter to use
      location: Raleigh

      provider: ibmsce


'''

# The import section is mostly libcloud boilerplate

# Import python libs
import time
import pprint
import logging

# Import libcloud
from libcloud.compute.base import NodeAuthSSHKey

# Import generic libcloud functions
from saltcloud.libcloudfuncs import *   # pylint: disable-msg=W0614,W0401

# Import saltcloud libs
import saltcloud.config as config
from saltcloud.utils import namespaced_function
from saltcloud.exceptions import (
    SaltCloudConfigError,
    SaltCloudSystemExit,
    SaltCloudExecutionTimeout,
    SaltCloudExecutionFailure
)

# Get logging started
log = logging.getLogger(__name__)

# Some of the libcloud functions need to be in the same namespace as the
# functions defined in the module, so we create new function objects inside
# this module namespace
get_size = namespaced_function(get_size, globals())
get_image = namespaced_function(get_image, globals())
get_location = namespaced_function(get_location, globals())
avail_images = namespaced_function(avail_images, globals())
avail_sizes = namespaced_function(avail_sizes, globals())
avail_locations = namespaced_function(avail_locations, globals())
script = namespaced_function(script, globals())
destroy = namespaced_function(destroy, globals())
list_nodes = namespaced_function(list_nodes, globals())
list_nodes_full = namespaced_function(list_nodes_full, globals())
list_nodes_select = namespaced_function(list_nodes_select, globals())


# Only load in this module is the IBMSCE configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for RACKSPACE configs
    '''
    if get_configured_provider() is False:
        log.debug(
            'There is no IBM SCE cloud provider configuration available. Not '
            'loading module.'
        )
        return False

    log.debug('Loading IBM SCE cloud module')
    return 'ibmsce'


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'ibmsce',
        ('user', 'password')
    )


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    vm_ = get_configured_provider()
    driver = get_driver(Provider.IBM)
    return driver(
        config.get_config_value('user', vm_, __opts__, search_global=False),
        config.get_config_value('password', vm_, __opts__, search_global=False)
    )


def ssh_interface(vm_):
    '''
    Return the ssh_interface type to connect to. Either 'public_ips' (default)
    or 'private_ips'.
    '''
    return config.get_config_value(
        'ssh_interface', vm_, __opts__, default='public_ips',
        search_global=False
    )


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    deploy = config.get_config_value('deploy', vm_, __opts__)
    key_filename = config.get_config_value(
        'ssh_key_file', vm_, __opts__, search_global=False, default=None
    )
    if key_filename is not None and not os.path.isfile(key_filename):
        raise SaltCloudConfigError(
            'The defined ssh_key_file {0!r} does not exist'.format(
                key_filename
            )
        )

    if deploy is True and key_filename is None and \
            salt.utils.which('sshpass') is None:
        raise SaltCloudSystemExit(
            'Cannot deploy salt in a VM if the \'ssh_key_file\' setting '
            'is not set and \'sshpass\' binary is not present on the '
            'system for the password.'
        )

    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()

    vm_['location'] = config.get_config_value('location', vm_, __opts__)
    kwargs = {
        'name': vm_['name'],
        'image': get_image(conn, vm_),
        'size': get_size(conn, vm_),
        'location': get_location(conn, vm_),
        'auth': NodeAuthSSHKey(
            config.get_config_value('ssh_key_name', vm_, __opts__)
        )
    }

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
                vm_['name'], exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return False

    def __query_node_data(vm_name, data):
        nodelist = list_nodes()
        public_ips = nodelist[vm_name]['public_ips']
        private_ips = nodelist[vm_name]['private_ips']

        if private_ips:
            data.private_ips = private_ips
        if public_ips:
            data.public_ips = public_ips

        if ssh_interface(vm_) == 'private_ips' and private_ips:
            return data

        if ssh_interface(vm_) == 'public_ips' and public_ips:
            return data

    try:
        data = saltcloud.utils.wait_for_ip(
            __query_node_data,
            update_args=(vm_['name'], data),
            timeout=25 * 60,
            interval=15
        )
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
        try:
            # It might be already up, let's destroy it!
            destroy(vm_['name'])
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(exc.message)

    ret = {}
    if config.get_config_value('deploy', vm_, __opts__) is True:
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
            'key_filename': key_filename,
            'script': deploy_script.script,
            'name': vm_['name'],
            'sudo': True,
            'start_action': __opts__['start_action'],
            'parallel': __opts__['parallel'],
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
            'minion_conf': saltcloud.utils.minion_config(__opts__, vm_)
        }

        # Deploy salt-master files, if necessary
        if config.get_config_value('make_master', vm_, __opts__) is True:
            deploy_kwargs['make_master'] = True
            deploy_kwargs['master_pub'] = vm_['master_pub']
            deploy_kwargs['master_pem'] = vm_['master_pem']
            master_conf = saltcloud.utils.master_config(__opts__, vm_)
            deploy_kwargs['master_conf'] = master_conf

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
                'Failed to start Salt on Cloud VM {0}'.format(vm_['name'])
            )

    log.info('Created Cloud VM {0[name]!r}'.format(vm_))
    log.debug(
        '{0[name]!r} VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data.__dict__)
        )
    )
    ret.update(data.__dict__)
    return ret
