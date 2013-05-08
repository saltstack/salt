'''
Rackspace Cloud Module
======================

The Rackspace cloud module. This module uses the preferred means to set up a
libcloud based cloud module and should be used as the general template for
setting up additional libcloud based modules.

The rackspace cloud module interfaces with the Rackspace public cloud service
and requires that two configuration parameters be set for use, ``user`` and
``apikey``.

Using the old cloud providers configuration syntax:

.. code-block:: yaml

    # The Rackspace login user
    RACKSPACE.user: fred
    # The Rackspace user's apikey
    RACKSPACE.apikey: 901d3f579h23c8v73q9


Using the new format, set up the cloud configuration at
 ``/etc/salt/cloud.providers`` or
 ``/etc/salt/cloud.providers.d/rackspace.conf``:

.. code-block:: yaml

    my-rackspace-config:
      # The Rackspace login user
      user: fred
      # The Rackspace user's apikey
      apikey: 901d3f579h23c8v73q9

      provider: rackspace

'''

# The import section is mostly libcloud boilerplate

# Import python libs
import logging
import socket
import pprint
import time

# Import libcloud
from libcloud.compute.base import NodeState

# Import generic libcloud functions
from saltcloud.libcloudfuncs import *   # pylint: disable-msg=W0614,W0401

# Import salt libs
import salt.utils

# Import saltcloud libs
import saltcloud.config as config
from saltcloud.utils import namespaced_function
from saltcloud.exceptions import SaltCloudSystemExit


# Get logging started
log = logging.getLogger(__name__)


# Some of the libcloud functions need to be in the same namespace as the
# functions defined in the module, so we create new function objects inside
# this module namespace
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


# Only load in this module is the RACKSPACE configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for Rackspace configuration.
    '''
    if get_configured_provider() is False:
        log.debug(
            'There is no Rackspace cloud provider configuration available. '
            'Not loading module.'
        )
        return False

    log.debug('Loading Rackspace cloud module')
    return 'rackspace'


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__, 'rackspace', ('user', 'apikey')
    )


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    driver = get_driver(Provider.RACKSPACE)
    return driver(
        config.get_config_value(
            'user',
            get_configured_provider(),
            __opts__,
            search_global=False
        ),
        config.get_config_value(
            'apikey',
            get_configured_provider(),
            __opts__,
            search_global=False
        )
    )


def preferred_ip(vm_, ips):
    '''
    Return the preferred Internet protocol. Either 'ipv4' (default) or 'ipv6'.
    '''
    proto = config.get_config_value(
        'protocol', vm_, __opts__, default='ipv4', search_global=False
    )
    family = socket.AF_INET
    if proto == 'ipv6':
        family = socket.AF_INET6
    for ip in ips:
        try:
            socket.inet_pton(family, ip)
            return ip
        except:
            continue
    return False


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
    if deploy is True and salt.utils.which('sshpass') is None:
        raise SaltCloudSystemExit(
            'Cannot deploy salt in a VM if the \'sshpass\' binary is not '
            'present on the system.'
        )

    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()
    kwargs = {
        'name': vm_['name'],
        'image': get_image(conn, vm_),
        'size': get_size(conn, vm_)
    }
    try:
        data = conn.create_node(**kwargs)
    except Exception as exc:
        log.error(
            'Error creating {0} on RACKSPACE\n\n'
            'The following exception was thrown by libcloud when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_['name'], exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return False

    not_ready = True
    sleep_time = 15
    nr_count = 100
    failures = 0
    while not_ready:
        if failures > 5:
            raise SaltCloudSystemExit(
                'Failed to get information too many times.'
            )
        try:
            nodelist = list_nodes()
            log.debug(
                'Loaded node data for {0}:\n{1}'.format(
                    vm_['name'],
                    pprint.pformat(
                        nodelist[vm_['name']]
                    )
                )
            )
        except Exception, err:
            log.error(
                'Failed to get nodes list: {0}'.format(
                    err
                ),
                # Show the traceback if the debug logging level is enabled
                exc_info=log.isEnabledFor(logging.DEBUG)
            )
            failures += 1
            continue

        log.debug(
            'Waiting for VM to become ready. Giving up in {0} seconds. '
            'State(current/desired): {1}/{2}'.format(
                nr_count * sleep_time,
                nodelist[vm_['name']]['state'],
                node_state(NodeState.RUNNING)
            )
        )

        private = nodelist[vm_['name']]['private_ips']
        public = nodelist[vm_['name']]['public_ips']
        running = nodelist[vm_['name']]['state'] == node_state(
            NodeState.RUNNING
        )

        if running and private and not public:
            log.warn(
                'Private IPs returned, but not public... checking for '
                'misidentified IPs'
            )
            for private_ip in private:
                private_ip = preferred_ip(vm_, [private_ip])
                if saltcloud.utils.is_public_ip(private_ip):
                    log.warn('{0} is a public ip'.format(private_ip))
                    data.public_ips.append(private_ip)
                    not_ready = False
                else:
                    log.warn('{0} is a private ip'.format(private_ip))
                    if private_ip not in data.private_ips:
                        data.private_ips.append(private_ip)
            if ssh_interface(vm_) == 'private_ips' and data.private_ips:
                not_ready = False
                break

        if running and public:
            data.public_ips = public
            not_ready = False

        if not_ready is False:
            break

        nr_count -= 1
        if nr_count == 0:
            log.warn('Timed out waiting for a public ip, continuing anyway')
            break
        time.sleep(sleep_time)

    log.debug('VM is now running')

    if ssh_interface(vm_) == 'private_ips':
        ip_address = preferred_ip(vm_, data.private_ips)
    else:
        ip_address = preferred_ip(vm_, data.public_ips)
    log.debug('Using IP address {0}'.format(ip_address))

    if not ip_address:
        raise SaltCloudSystemExit(
            'No IP addresses could be found.'
        )

    ret = {}
    if deploy is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'host': ip_address,
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
            'preseed_minion_keys': vm_.get('preseed_minion_keys', None),
            'display_ssh_output': config.get_config_value(
                'display_ssh_output', vm_, __opts__, default=True
            ),
            'script_args': config.get_config_value(
                'script_args', vm_, __opts__
            ),
            'minion_conf': saltcloud.utils.minion_conf_string(__opts__, vm_)
        }

        # Deploy salt-master files, if necessary
        if config.get_config_value('make_master', vm_, __opts__) is True:
            deploy_kwargs['make_master'] = True
            deploy_kwargs['master_pub'] = vm_['master_pub']
            deploy_kwargs['master_pem'] = vm_['master_pem']
            master_conf = saltcloud.utils.master_conf(__opts__, vm_)
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
                'Failed to deploy and start Salt on Cloud VM {0}'.format(
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
