'''
OpenStack Cloud Module
======================

OpenStack is an open source project that is in use by a number a cloud
providers, each of which have their own ways of using it.

OpenStack provides a number of ways to authenticate. This module uses password-
based authentication, using auth v2.0. It is likely to start supporting other
methods of authentication provided by OpenStack in the future.

Note that there is currently a dependency upon netaddr. This can be installed
on Debian-based systems by means of the python-netaddr package.

This module has been tested to work with HP Cloud and Rackspace. See the
documentation for specific options for either of these providers. Some
examples, using the old cloud configuration syntax, are provided below:

.. code-block:: yaml

    # The OpenStack identity service url
    OPENSTACK.identity_url: https://region-a.geo-1.identity.hpcloudsvc.com:35357/v2.0/
    # The OpenStack compute region
    OPENSTACK.compute_region: az-1.region-a.geo-1
    # The OpenStack compute service name
    OPENSTACK.compute_name: Compute
    # The OpenStack tenant name (not tenant ID)
    OPENSTACK.tenant: myuser-tenant1
    # The OpenStack user name
    OPENSTACK.user: myuser
    # The OpenStack keypair name
    OPENSTACK.ssh_key_name

Either a password or an API key must also be specified:

.. code-block:: yaml

    # The OpenStack password
    OPENSTACK.password: letmein
    # The OpenStack API key
    OPENSTACK.apikey: 901d3f579h23c8v73q9


And using the new format, these examples could be set up in the cloud
configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/openstack.conf``:


.. code-block:: yaml

    my-openstack-config:
      # The OpenStack identity service url
      identity_url: https://region-a.geo-1.identity.hpcloudsvc.com:35357/v2.0/
      # The OpenStack compute region
      compute_region: az-1.region-a.geo-1
      # The OpenStack compute service name
      compute_name: Compute
      # The OpenStack tenant name (not tenant ID)
      tenant: myuser-tenant1
      # The OpenStack user name
      user: myuser
      # The OpenStack keypair name
      ssh_key_name

      provider: openstack

Either a password or an API key must also be specified:

.. code-block:: yaml

    my-openstack-password-or-api-config:
      # The OpenStack password
      password: letmein
      # The OpenStack API key
      apikey: 901d3f579h23c8v73q9


For local installations that only use private IP address ranges, the
following option may be useful. Using the old syntax:

.. code-block:: yaml

    # Ignore IP addresses on this network for bootstrap
    OPENSTACK.ignore_ip_addr: 192.168.50.0/24


Using the new syntax:

.. code-block:: yaml

    my-openstack-config:
      # Ignore IP addresses on this network for bootstrap
      ignore_ip_addr: 192.168.50.0/24

'''

# The import section is mostly libcloud boilerplate

# Import python libs
import os
import logging
import socket
import pprint

# Import libcloud
from libcloud.compute.base import NodeState

# Import generic libcloud functions
from saltcloud.libcloudfuncs import *   # pylint: disable-msg=W0614,W0401

# Import salt libs
import salt.utils

# Import saltcloud libs
import saltcloud.utils
import saltcloud.config as config
from saltcloud.utils import namespaced_function
from saltcloud.exceptions import (
    SaltCloudConfigError,
    SaltCloudNotFound,
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout
)

# Import netaddr IP matching
try:
    from netaddr import all_matching_cidrs
    HAS_NETADDR = True
except:
    HAS_NETADDR = False

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


# Only load in this module is the OPENSTACK configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for OPENSTACK configurations
    '''
    if get_configured_provider() is False:
        log.debug(
            'There is no Openstack cloud provider configuration available. '
            'Not loading module.'
        )
        return False

    log.debug('Loading Openstack cloud module')
    return 'openstack'


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'openstack',
        ('user',)
    )


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    vm_ = get_configured_provider()
    driver = get_driver(Provider.OPENSTACK)
    authinfo = {
        'ex_force_auth_url': config.get_config_value(
            'identity_url', vm_, __opts__, search_global=False
        ),
        'ex_force_service_name': config.get_config_value(
            'compute_name', vm_, __opts__, search_global=False
        ),
        'ex_force_service_region': config.get_config_value(
            'compute_region', vm_, __opts__, search_global=False
        ),
        'ex_tenant_name': config.get_config_value(
            'tenant', vm_, __opts__, search_global=False
        )
    }

    insecure = config.get_config_value(
        'insecure', vm_, __opts__, search_global=False
    )

    if insecure:
        import libcloud.security
        libcloud.security.VERIFY_SSL_CERT = False

    password = config.get_config_value(
        'password', vm_, __opts__, search_global=False
    )
    if password is not None:
        authinfo['ex_force_auth_version'] = '2.0_password'
        log.debug('OpenStack authenticating using password')
        return driver(
            config.get_config_value(
                'user', vm_, __opts__, search_global=False
            ),
            password,
            **authinfo
        )

    authinfo['ex_force_auth_version'] = '2.0_apikey'
    log.debug('OpenStack authenticating using apikey')
    return driver(
        config.get_config_value('user', vm_, __opts__, search_global=False),
        config.get_config_value('apikey', vm_, __opts__, search_global=False),
        **authinfo
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


def ignore_ip_addr(vm_, ip):
    '''
    Return True if we are to ignore the specified IP. Compatible with IPv4.
    '''
    if HAS_NETADDR is False:
        return 'Error: netaddr is not installed'

    cidr = vm_.get('ip_ignore', __opts__.get('OPENSTACK.ignore_cidr', ''))
    if cidr != '' and all_matching_cidrs(ip, [cidr]):
        return True
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

    saltcloud.utils.fire_event(
        'event',
        'starting create',
        'salt.cloud.{0}.creating'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
    )

    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    saltcloud.utils.check_name(vm_['name'], 'a-zA-Z0-9._-')
    conn = get_conn()
    kwargs = {
        'name': vm_['name']
    }

    try:
        kwargs['image'] = get_image(conn, vm_)
    except Exception as exc:
        log.error(
            'Error creating {0} on OPENSTACK\n\n'
            'Could not find image {1}: {2}\n'.format(
                vm_['name'], vm_['image'], exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return False

    try:
        kwargs['size'] = get_size(conn, vm_)
    except Exception as exc:
        log.error(
            'Error creating {0} on OPENSTACK\n\n'
            'Could not find size {1}: {2}\n'.format(
                vm_['name'], vm_['size'], exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return False

    kwargs['ex_keyname'] = config.get_config_value(
        'ssh_key_name', vm_, __opts__, search_global=False
    )

    security_groups = config.get_config_value(
        'security_groups', vm_, __opts__, search_global=False
    )
    if security_groups is not None:
        vm_groups = security_groups.split(',')
        avail_groups = conn.ex_list_security_groups()
        group_list = []

        for vmg in vm_groups:
            if vmg in [ag.name for ag in avail_groups]:
                group_list.append(vmg)
            else:
                raise SaltCloudNotFound(
                    'No such security group: \'{0}\''.format(vgm)
                )

        kwargs['ex_security_groups'] = [
            g for g in avail_groups if g.name in group_list
        ]

    saltcloud.utils.fire_event(
        'event',
        'requesting instance',
        'salt.cloud.{0}.requesting'.format(vm_['name']),
        {'kwargs': {'name': kwargs['name'],
                    'image': kwargs['image'].name,
                    'size': kwargs['size'].name}},
    )

    try:
        data = conn.create_node(**kwargs)
    except Exception as exc:
        log.error(
            'Error creating {0} on OPENSTACK\n\n'
            'The following exception was thrown by libcloud when trying to '
            'run the initial deployment: {1}\n'.format(
                vm_['name'], exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return False

    def __query_node_data(vm_, data):
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
            # Trigger a failure in the wait for IP function
            return False

        running = nodelist[vm_['name']]['state'] == node_state(
            NodeState.RUNNING
        )
        if not running:
            # Still not running, trigger another iteration
            return

        private = nodelist[vm_['name']]['private_ips']
        public = nodelist[vm_['name']]['public_ips']
        if private and not public:
            log.warn(
                'Private IPs returned, but not public... Checking for '
                'misidentified IPs'
            )
            for private_ip in private:
                private_ip = preferred_ip(vm_, [private_ip])
                if saltcloud.utils.is_public_ip(private_ip):
                    log.warn('{0} is a public IP'.format(private_ip))
                    data.public_ips.append(private_ip)
                    log.warn(
                        'Public IP address was not ready when we last checked.  Appending public IP address now.'
                    )
                    public = data.public_ips
                else:
                    log.warn('{0} is a private IP'.format(private_ip))
                    ignore_ip = ignore_ip_addr(vm_, private_ip)
                    if private_ip not in data.private_ips and not ignore_ip:
                        data.private_ips.append(private_ip)

            if ssh_interface(vm_) == 'private_ips' and data.private_ips:
                return data

        if private:
            data.private_ips = private
            if ssh_interface(vm_) == 'private_ips':
                return data

        if public:
            data.public_ips = public
            if ssh_interface(vm_) != 'private_ips':
                return data

    try:
        data = saltcloud.utils.wait_for_ip(
            __query_node_data,
            update_args=(vm_, data),
            timeout=10 * 60,
            interval=10
        )
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
        try:
            # It might be already up, let's destroy it!
            destroy(vm_['name'])
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(exc.message)

    log.debug('VM is now running')
    if ssh_interface(vm_) == 'private_ips':
        ip_address = preferred_ip(vm_, data.private_ips)
    else:
        ip_address = preferred_ip(vm_, data.public_ips)
    log.debug('Using IP address {0}'.format(ip_address))

    if not ip_address:
        raise SaltCloudSystemExit('A valid IP address was not found')

    deploy_kwargs = {
        'host': ip_address,
        'name': vm_['name'],
        'sock_dir': __opts__['sock_dir'],
        'start_action': __opts__['start_action'],
        'parallel': __opts__['parallel'],
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

    ssh_username = config.get_config_value(
        'ssh_username', vm_, __opts__, default='root'
    )
    if ssh_username != 'root':
        deploy_kwargs['deploy_command'] = '/tmp/deploy.sh'
        deploy_kwargs['username'] = ssh_username
        deploy_kwargs['tty'] = True

    log.debug('Using {0} as SSH username'.format(ssh_username))

    if key_filename is not None:
        deploy_kwargs['key_filename'] = key_filename
        log.debug(
            'Using {0} as SSH key file'.format(key_filename)
        )
    elif 'password' in data.extra:
        deploy_kwargs['password'] = data.extra['password']
        log.debug('Logging into SSH using password')

    ret = {}
    sudo = config.get_config_value(
        'sudo', vm_, __opts__, default=(ssh_username != 'root')
    )
    if sudo is not None:
        deploy_kwargs['sudo'] = sudo
        log.debug('Running root commands using sudo')

    if config.get_config_value('deploy', vm_, __opts__) is True:
        deploy_script = script(vm_)
        deploy_kwargs['script'] = deploy_script.script

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

        saltcloud.utils.fire_event(
            'event',
            'executing deploy script',
            'salt.cloud.{0}.deploying'.format(vm_['name']),
            {'kwargs': deploy_kwargs},
        )

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

    saltcloud.utils.fire_event(
        'event',
        'created instance',
        'salt.cloud.{0}.created'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
    )

    return ret
