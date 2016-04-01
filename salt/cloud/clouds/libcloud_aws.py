# -*- coding: utf-8 -*-
'''
The AWS Cloud Module
====================

The AWS cloud module is used to interact with the Amazon Web Services system.

This module has been replaced by the EC2 cloud module, and is no longer
supported. The documentation shown here is for reference only; it is highly
recommended to change all usages of this driver over to the EC2 driver.

If this driver is still needed, set up the cloud configuration at
 ``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/aws.conf``:

.. code-block:: yaml

    my-aws-config:
      # The AWS API authentication id
      id: GKTADJGHEIQSXMKKRBJ08H
      # The AWS API authentication key
      key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
      # The ssh keyname to use
      keyname: default
      # The amazon security group
      securitygroup: ssh_open
      # The location of the private key which corresponds to the keyname
      private_key: /root/default.pem

      driver: aws

'''
from __future__ import absolute_import
# pylint: disable=E0102

# Import python libs
import os
import stat
import uuid
import pprint
import logging

# Import salt.cloud libs
import salt.utils.cloud
import salt.config as config
from salt.utils import namespaced_function

from salt.exceptions import (
    SaltCloudException,
    SaltCloudSystemExit,
    SaltCloudConfigError,
    SaltCloudExecutionTimeout,
    SaltCloudExecutionFailure
)
import salt.ext.six as six

try:
    from salt.cloud.libcloudfuncs import *   # pylint: disable=W0614,W0401
    from salt.cloud.libcloudfuncs import destroy as libcloudfuncs_destroy
    from libcloud.compute.types import Provider

    EC2_LOCATIONS = {
        'ap-northeast-1': Provider.EC2_AP_NORTHEAST,
        'ap-southeast-1': Provider.EC2_AP_SOUTHEAST,
        'eu-west-1': Provider.EC2_EU_WEST,
        'sa-east-1': Provider.EC2_SA_EAST,
        'us-east-1': Provider.EC2_US_EAST,
        'us-west-1': Provider.EC2_US_WEST,
        'us-west-2': Provider.EC2_US_WEST_OREGON
    }
    DEFAULT_LOCATION = 'us-east-1'
    if hasattr(Provider, 'EC2_AP_SOUTHEAST2'):
        EC2_LOCATIONS['ap-southeast-2'] = Provider.EC2_AP_SOUTHEAST2

    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False

# Get logging started
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'aws'


# Only load in this module if the AWS configurations are in place
def __virtual__():
    '''
    Set up the libcloud funcstions and check for AWS configs
    '''
    try:
        import botocore
        # Since we have botocore, we won't load the libcloud AWS module
        return False
    except ImportError:
        pass

    if get_configured_provider() is False:
        return False

    if get_dependencies() is False:
        return False

    for provider, details in six.iteritems(__opts__['providers']):
        if 'provider' not in details or details['provider'] != 'aws':
            continue

        if not os.path.exists(details['private_key']):
            raise SaltCloudException(
                'The AWS key file {0!r} used in the {1!r} provider '
                'configuration does not exist\n'.format(
                    details['private_key'],
                    provider
                )
            )

        keymode = str(
            oct(stat.S_IMODE(os.stat(details['private_key']).st_mode))
        )
        if keymode not in ('0400', '0600'):
            raise SaltCloudException(
                'The AWS key file {0!r} used in the {1!r} provider '
                'configuration needs to be set to mode 0400 or 0600\n'.format(
                    details['private_key'],
                    provider
                )
            )

    global avail_images, avail_sizes, script, list_nodes
    global avail_locations, list_nodes_full, list_nodes_select, get_image
    global get_size, libcloudfuncs_destroy, show_instance

    # open a connection in a specific region
    conn = get_conn(**{'location': get_location()})

    # Init the libcloud functions
    get_size = namespaced_function(get_size, globals(), (conn,))
    get_image = namespaced_function(get_image, globals(), (conn,))
    avail_locations = namespaced_function(avail_locations, globals(), (conn,))
    avail_images = namespaced_function(avail_images, globals(), (conn,))
    avail_sizes = namespaced_function(avail_sizes, globals(), (conn,))
    script = namespaced_function(script, globals(), (conn,))
    list_nodes = namespaced_function(list_nodes, globals(), (conn,))
    list_nodes_full = namespaced_function(list_nodes_full, globals(), (conn,))
    list_nodes_select = namespaced_function(
        list_nodes_select, globals(), (conn,)
    )
    libcloudfuncs_destroy = namespaced_function(
        libcloudfuncs_destroy, globals(), (conn,)
    )
    show_instance = namespaced_function(show_instance, globals())

    log.warning('This driver has been deprecated and will be removed in the '
                'Boron release of Salt. Please use the ec2 driver instead.')

    return __virtualname__


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'aws',
        ('id', 'key', 'keyname', 'securitygroup', 'private_key')
    )


def get_dependencies():
    '''
    Warn if dependencies aren't met.
    '''
    return config.check_driver_dependencies(
        __virtualname__,
        {'libcloud': HAS_LIBCLOUD}
    )


def get_conn(**kwargs):
    '''
    Return a conn object for the passed VM data
    '''
    if 'location' in kwargs:
        location = kwargs['location']
        if location not in EC2_LOCATIONS:
            raise SaltCloudException(
                'The specified location does not seem to be valid: '
                '{0}\n'.format(
                    location
                )
            )
    else:
        location = DEFAULT_LOCATION

    driver = get_driver(EC2_LOCATIONS[location])
    vm_ = get_configured_provider()
    return driver(
        config.get_cloud_config_value('id', vm_, __opts__, search_global=False),
        config.get_cloud_config_value('key', vm_, __opts__, search_global=False)
    )


def keyname(vm_):
    '''
    Return the keyname
    '''
    return config.get_cloud_config_value(
        'keyname', vm_, __opts__, search_global=False
    )


def securitygroup(vm_):
    '''
    Return the security group
    '''
    return config.get_cloud_config_value(
        'securitygroup', vm_, __opts__, search_global=False
    )


def iam_profile(vm_):
    '''
    Return the IAM role
    '''
    return config.get_cloud_config_value(
        'iam_profile', vm_, __opts__, search_global=False
    )


def block_device_mappings(vm_):
    '''
    Return the block device mapping:

    ::

        [{'DeviceName': '/dev/sdb', 'VirtualName': 'ephemeral0'},
          {'DeviceName': '/dev/sdc', 'VirtualName': 'ephemeral1'}]
    '''
    return config.get_cloud_config_value(
        'block_device_mappings', vm_, __opts__, search_global=False
    )


def ssh_username(vm_):
    '''
    Return the ssh_username. Defaults to 'ec2-user'.
    '''
    usernames = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__
    )

    if not isinstance(usernames, list):
        usernames = [usernames]

    # get rid of None's or empty names
    usernames = [x for x in usernames if x]
    # Keep a copy of the usernames the user might have provided
    initial = usernames[:]

    # Add common usernames to the list to be tested
    for name in 'ec2-user', 'ubuntu', 'admin', 'bitnami', 'root':
        if name not in usernames:
            usernames.append(name)
    # Add the user provided usernames to the end of the list since enough time
    # might need to pass before the remote service is available for logins and
    # the proper username might have passed its iteration.
    # This has detected in a CentOS 5.7 EC2 image
    usernames.extend(initial)
    return usernames


def ssh_interface(vm_):
    '''
    Return the ssh_interface type to connect to. Either 'public_ips' (default)
    or 'private_ips'.
    '''
    return config.get_cloud_config_value(
        'ssh_interface', vm_, __opts__, default='public_ips',
        search_global=False
    )


def get_location(vm_=None):
    '''
    Return the AWS region to use, in this order:
        - CLI parameter
        - Cloud profile setting
        - Global salt-cloud config
    '''
    return __opts__.get(
        'location',
        config.get_cloud_config_value(
            'location',
            vm_ or get_configured_provider(), __opts__,
            default=DEFAULT_LOCATION
        )
    )


def get_availability_zone(conn, vm_):
    '''
    Return the availability zone to use
    '''
    avz = config.get_cloud_config_value(
        'availability_zone', vm_, __opts__, search_global=False
    )

    locations = conn.list_locations()

    if avz is None:
        # Default to first zone
        return locations[0]

    for loc in locations:
        if loc.availability_zone.name == avz:
            return loc


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or 'aws',
                                                           vm_['profile'],
                                                           vm_=vm_) is False:
            return False
    except AttributeError:
        pass

    key_filename = config.get_cloud_config_value(
        'private_key', vm_, __opts__, search_global=False, default=None
    )
    if key_filename is not None and not os.path.isfile(key_filename):
        raise SaltCloudConfigError(
            'The defined key_filename {0!r} does not exist'.format(
                key_filename
            )
        )

    location = get_location(vm_)
    log.info('Creating Cloud VM {0} in {1}'.format(vm_['name'], location))
    conn = get_conn(location=location)
    usernames = ssh_username(vm_)
    kwargs = {
        'ssh_key': config.get_cloud_config_value(
            'private_key', vm_, __opts__, search_global=False
        ),
        'name': vm_['name'],
        'image': get_image(conn, vm_),
        'size': get_size(conn, vm_),
        'location': get_availability_zone(conn, vm_)
    }
    ex_keyname = keyname(vm_)
    if ex_keyname:
        kwargs['ex_keyname'] = ex_keyname
    ex_securitygroup = securitygroup(vm_)
    if ex_securitygroup:
        kwargs['ex_securitygroup'] = ex_securitygroup
    ex_blockdevicemappings = block_device_mappings(vm_)
    if ex_blockdevicemappings:
        kwargs['ex_blockdevicemappings'] = ex_blockdevicemappings

    ex_iam_profile = iam_profile(vm_)
    if ex_iam_profile:
        # libcloud does not implement 'iam_profile' yet.
        # A pull request has been suggested
        # https://github.com/apache/libcloud/pull/150
        raise SaltCloudConfigError(
            'libcloud does not implement \'iam_profile\' yet. '
            'Use EC2 driver instead.'
        )

    tags = config.get_cloud_config_value('tag', vm_, __opts__, {}, search_global=False)
    if not isinstance(tags, dict):
        raise SaltCloudConfigError(
                '\'tag\' should be a dict.'
        )
    kwargs['ex_metadata'] = config.get_cloud_config_value('metadata', vm_, __opts__, default={}, search_global=False)
    if not isinstance(kwargs['ex_metadata'], dict):
        raise SaltCloudConfigError(
                '\'metadata\' should be a dict.'
        )

    try:
        data = conn.create_node(**kwargs)
    except Exception as exc:
        log.error(
            'Error creating {0} on AWS\n\n'
            'The following exception was thrown by libcloud when trying to '
            'run the initial deployment: {1}\n'.format(
                vm_['name'], exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return False

    log.info('Created node {0}'.format(vm_['name']))

    def __get_node_data(conn, vm_name):
        data = get_node(conn, vm_name)

        if data is None:
            # Trigger a failure in the waiting function
            return False

        if ssh_interface(vm_) == 'private_ips' and data.private_ips:
            return data

        if ssh_interface(vm_) == 'public_ips' and data.public_ips:
            return data

    try:
        data = salt.utils.cloud.wait_for_ip(
            __get_node_data,
            update_args=(conn, vm_['name']),
            timeout=config.get_cloud_config_value(
                'wait_for_ip_timeout', vm_, __opts__, default=5 * 60),
            interval=config.get_cloud_config_value(
                'wait_for_ip_interval', vm_, __opts__, default=0.5),
        )
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
        try:
            # It might be already up, let's destroy it!
            destroy(vm_['name'])
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(str(exc))

    if tags:
        set_tags(vm_['name'], tags, call='action')

    if ssh_interface(vm_) == 'private_ips':
        log.info('Salt node data. Private_ip: {0}'.format(data.private_ips[0]))
        ip_address = data.private_ips[0]
    else:
        log.info('Salt node data. Public_ip: {0}'.format(data.public_ips[0]))
        ip_address = data.public_ips[0]

    if salt.utils.cloud.get_salt_interface(vm_, __opts__) == 'private_ips':
        salt_ip_address = data.private_ips[0]
        log.info('Salt interface set to: {0}'.format(salt_ip_address))
    else:
        salt_ip_address = data.public_ips[0]
        log.debug('Salt interface set to: {0}'.format(salt_ip_address))

    username = 'ec2-user'
    ssh_connect_timeout = config.get_cloud_config_value(
        'ssh_connect_timeout', vm_, __opts__, 900   # 15 minutes
    )
    ssh_port = config.get_cloud_config_value(
        'ssh_port', vm_, __opts__, 22
    )
    if salt.utils.cloud.wait_for_port(ip_address, timeout=ssh_connect_timeout):
        for user in usernames:
            if salt.utils.cloud.wait_for_passwd(
                    host=ip_address,
                    username=user,
                    ssh_timeout=config.get_cloud_config_value(
                        'wait_for_passwd_timeout', vm_, __opts__,
                        default=1 * 60
                    ),
                    key_filename=key_filename,
                    known_hosts_file=config.get_cloud_config_value(
                        'known_hosts_file', vm_, __opts__,
                        default='/dev/null'
                    ),
                ):
                username = user
                break
        else:
            raise SaltCloudSystemExit(
                'Failed to authenticate against remote ssh'
            )

    ret = {}
    if config.get_cloud_config_value('deploy', vm_, __opts__) is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'opts': __opts__,
            'host': ip_address,
            'port': ssh_port,
            'salt_host': salt_ip_address,
            'username': username,
            'key_filename': key_filename,
            'tmp_dir': config.get_cloud_config_value(
                'tmp_dir', vm_, __opts__, default='/tmp/.saltcloud'
            ),
            'deploy_command': config.get_cloud_config_value(
                'deploy_command', vm_, __opts__,
                default='/tmp/.saltcloud/deploy.sh',
            ),
            'tty': config.get_cloud_config_value(
                'tty', vm_, __opts__, default=True
            ),
            'script': deploy_script.script,
            'name': vm_['name'],
            'sudo': config.get_cloud_config_value(
                'sudo', vm_, __opts__, default=(username != 'root')
            ),
            'sudo_password': config.get_cloud_config_value(
                'sudo_password', vm_, __opts__, default=None
            ),
            'start_action': __opts__['start_action'],
            'parallel': __opts__['parallel'],
            'conf_file': __opts__['conf_file'],
            'sock_dir': __opts__['sock_dir'],
            'minion_pem': vm_['priv_key'],
            'minion_pub': vm_['pub_key'],
            'keep_tmp': __opts__['keep_tmp'],
            'preseed_minion_keys': vm_.get('preseed_minion_keys', None),
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
        ret['deploy_kwargs'] = deploy_kwargs

        deployed = False
        if win_installer:
            deployed = salt.utils.cloud.deploy_windows(**deploy_kwargs)
        else:
            deployed = salt.utils.cloud.deploy_script(**deploy_kwargs)

        if deployed:
            log.info('Salt installed on {name}'.format(**vm_))
        else:
            log.error('Failed to start Salt on Cloud VM {name}'.format(**vm_))

    ret.update(data.__dict__)

    log.info('Created Cloud VM {0[name]!r}'.format(vm_))
    log.debug(
        '{0[name]!r} VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data.__dict__)
        )
    )

    volumes = config.get_cloud_config_value(
        'volumes', vm_, __opts__, search_global=True
    )
    if volumes:
        log.info('Create and attach volumes to node {0}'.format(data.name))
        create_attach_volumes(volumes, location, data)

    return ret


def create_attach_volumes(volumes, location, data):
    '''
    Create and attach volumes to created node
    '''
    conn = get_conn(location=location)
    node_avz = data.__dict__.get('extra').get('availability')
    avz = None
    for avz in conn.list_locations():
        if avz.availability_zone.name == node_avz:
            break
    for volume in volumes:
        volume_name = '{0} on {1}'.format(volume['device'], data.name)
        created_volume = conn.create_volume(volume['size'], volume_name, avz)
        attach = conn.attach_volume(data, created_volume, volume['device'])
        if attach:
            log.info(
                '{0} attached to {1} (aka {2}) as device {3}'.format(
                    created_volume.id, data.id, data.name, volume['device']
                )
            )


def stop(name, call=None):
    '''
    Stop a node
    '''
    data = {}

    if call != 'action':
        raise SaltCloudSystemExit(
            'This action must be called with -a or --action.'
        )

    location = get_location()
    conn = get_conn(location=location)
    node = get_node(conn, name)
    try:
        data = conn.ex_stop_node(node=node)
        log.debug(data)
        log.info('Stopped node {0}'.format(name))
    except Exception:
        log.error('Failed to stop node {0}\n'.format(name), exc_info=True)

    return data


def start(name, call=None):
    '''
    Start a node
    '''
    data = {}

    if call != 'action':
        raise SaltCloudSystemExit(
            'This action must be called with -a or --action.'
        )

    location = get_location()
    conn = get_conn(location=location)
    node = get_node(conn, name)
    try:
        data = conn.ex_start_node(node=node)
        log.debug(data)
        log.info('Started node {0}'.format(name))
    except Exception:
        log.error('Failed to start node {0}\n'.format(name), exc_info=True)

    return data


def set_tags(name, tags, call=None):
    '''
    Set tags for a node

    CLI Example:

    .. code-block:: bash

        salt-cloud -a set_tags mymachine tag1=somestuff tag2='Other stuff'
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'This action must be called with -a or --action.'
        )

    location = get_location()
    conn = get_conn(location=location)
    node = get_node(conn, name)
    try:
        log.info('Setting tags for {0}'.format(name))
        conn.ex_create_tags(resource=node, tags=tags)

        # print the new tags- with special handling for renaming of a node
        if 'Name' in tags:
            return get_tags(tags['Name'])
        return get_tags(name)
    except Exception:
        log.error('Failed to set tags for {0}\n'.format(name), exc_info=True)


def get_tags(name, call=None):
    '''
    Retrieve tags for a node
    '''
    data = {}

    if call != 'action':
        raise SaltCloudSystemExit(
            'This action must be called with -a or --action.'
        )

    location = get_location()
    conn = get_conn(location=location)
    node = get_node(conn, name)
    try:
        log.info('Retrieving tags from {0}'.format(name))
        data = conn.ex_describe_tags(resource=node)
        log.info(data)
    except Exception:
        log.error(
            'Failed to retrieve tags from {0}\n'.format(name),
            exc_info=True
        )

    return data


def del_tags(name, kwargs, call=None):
    '''
    Delete tags for a node

    CLI Example:

    .. code-block:: bash

        salt-cloud -a del_tags mymachine tag1,tag2,tag3
    '''
    ret = {}

    if call != 'action':
        raise SaltCloudSystemExit(
            'This action must be called with -a or --action.'
        )

    location = get_location()
    conn = get_conn(location=location)
    node = get_node(conn, name)
    current_tags = conn.ex_describe_tags(resource=node)

    tags = {}
    for tag in kwargs['tags'].split(','):
        tags[tag] = current_tags[tag]

    try:
        conn.ex_delete_tags(resource=node, tags=tags)
        log.info('Deleting tags from {0}'.format(name))
        ret = get_tags(name)
    except Exception:
        log.error(
            'Failed to delete tags from {0}\n'.format(name),
            exc_info=True
        )

    return ret


def rename(name, kwargs, call=None):
    '''
    Properly rename a node. Pass in the new name as "new name".

    CLI Example:

    .. code-block:: bash

        salt-cloud -a rename mymachine newname=yourmachine
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'This action must be called with -a or --action.'
        )

    location = get_location()
    conn = get_conn(location=location)
    node = get_node(conn, name)
    tags = {'Name': kwargs['newname']}
    try:
        log.info('Renaming {0} to {1}'.format(name, kwargs['newname']))
        conn.ex_create_tags(resource=node, tags=tags)
        salt.utils.cloud.rename_key(
            __opts__['pki_dir'], name, kwargs['newname']
        )
    except Exception as exc:
        log.error(
            'Failed to rename {0} to {1}: {2}\n'.format(
                name, kwargs['newname'], exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
    return kwargs['newname']


def destroy(name):
    '''
    Wrap core libcloudfuncs destroy method, adding check for termination
    protection
    '''
    ret = {}

    newname = name

    # Default behavior is to rename AWS VMs when destroyed
    # via salt-cloud, unless explicitly set to False.
    rename_on_destroy = config.get_cloud_config_value('rename_on_destroy',
                                                      get_configured_provider(),
                                                      __opts__,
                                                      search_global=False)
    if rename_on_destroy is not False:
        newname = '{0}-DEL{1}'.format(name, uuid.uuid4().hex)
        rename(name, kwargs={'newname': newname}, call='action')
        log.info(
            'Machine will be identified as {0} until it has been '
            'cleaned up by AWS.'.format(
                newname
            )
        )
        ret['newname'] = newname

    try:
        result = libcloudfuncs_destroy(newname, get_conn())
        ret.update({'Destroyed': result})
    except Exception as exc:
        if not str(exc).startswith('OperationNotPermitted'):
            log.exception(exc)
            raise exc

        log.info(
            'Failed: termination protection is enabled on {0}'.format(
                name
            )
        )

    if __opts__.get('update_cachedir', False) is True:
        salt.utils.cloud.delete_minion_cachedir(name, __active_provider_name__.split(':')[0], __opts__)

    return ret
