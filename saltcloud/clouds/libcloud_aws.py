'''
The AWS Cloud Module
====================

The AWS cloud module is used to interact with the Amazon Web Services system.

To use the AWS cloud module, using the old cloud providers configuration
syntax, the following configuration parameters need to be set in the main cloud
configuration file:

.. code-block:: yaml

    # The AWS API authentication id
    AWS.id: GKTADJGHEIQSXMKKRBJ08H
    # The AWS API authentication key
    AWS.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
    # The ssh keyname to use
    AWS.keyname: default
    # The amazon security group
    AWS.securitygroup: ssh_open
    # The location of the private key which corresponds to the keyname
    AWS.private_key: /root/default.pem


Using the new format, set up the cloud configuration at
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

      provider: aws

'''

# Import python libs
import os
import sys
import stat
import time
import uuid
import logging

# Import saltcloud libs
import saltcloud.utils
import saltcloud.config as config
from saltcloud.utils import namespaced_function
from saltcloud.libcloudfuncs import *
from saltcloud.exceptions import SaltCloudException, SaltCloudSystemExit

# Get logging started
log = logging.getLogger(__name__)


# Only load in this module if the AWS configurations are in place
def __virtual__():
    '''
    Set up the libcloud funcstions and check for AWS configs
    '''
    try:
        import botocore
        # Since we have botocore, we won't load the libcloud AWS module
        log.debug(
            'The \'botocore\' library is installed. The libcloud AWS support '
            'will not be loaded.'
        )
        return False
    except ImportError:
        pass

    if get_configured_provider() is False:
        log.debug(
            'There is no AWS cloud provider configuration available. Not '
            'loading module'
        )
        return False

    for provider, details in __opts__['providers'].iteritems():
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

    global avail_images, avail_sizes, script, destroy, list_nodes
    global avail_locations, list_nodes_full, list_nodes_select, get_image
    global get_size

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

    log.debug('Loading Libcloud AWS cloud module')
    return 'aws'


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


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        'aws',
        ('id', 'key', 'keyname', 'securitygroup', 'private_key')
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
        config.get_config_value('id', vm_, __opts__, search_global=False),
        config.get_config_value('key', vm_, __opts__, search_global=False)
    )


def keyname(vm_):
    '''
    Return the keyname
    '''
    return config.get_config_value(
        'keyname', vm_, __opts__, search_global=False
    )


def securitygroup(vm_):
    '''
    Return the security group
    '''
    return config.get_config_value(
        'securitygroup', vm_, __opts__, search_global=False
    )


def block_device_mappings(vm_):
    '''
    Return the block device mapping
    e.g. [{'DeviceName': '/dev/sdb', 'VirtualName': 'ephemeral0'},
          {'DeviceName': '/dev/sdc', 'VirtualName': 'ephemeral1'}]
    '''
    return config.get_config_value(
        'block_device_mappings', vm_, __opts__, search_global=False
    )


def ssh_username(vm_):
    '''
    Return the ssh_username. Defaults to 'ec2-user'.
    '''
    usernames = config.get_config_value(
        'ssh_username', vm_, __opts__
    )

    if not isinstance(usernames, list):
        usernames = [usernames]

    # get rid of None's or empty names
    usernames = filter(lambda x: x, usernames)

    # Add common usernames to the list to be tested
    for name in ('ec2-user', 'ubuntu', 'admin', 'bitnami', 'root'):
        if name not in usernames:
            usernames.append(name)
    return usernames


def ssh_interface(vm_):
    '''
    Return the ssh_interface type to connect to. Either 'public_ips' (default)
    or 'private_ips'.
    '''
    return config.get_config_value(
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
        config.get_config_value(
            'location',
            vm_ or get_configured_provider(), __opts__,
            default=DEFAULT_LOCATION
        )
    )


def get_availability_zone(conn, vm_):
    '''
    Return the availability zone to use
    '''
    avz = config.get_config_value(
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
    location = get_location(vm_)
    log.info('Creating Cloud VM {0} in {1}'.format(vm_['name'], location))
    conn = get_conn(location=location)
    usernames = ssh_username(vm_)
    kwargs = {
        'ssh_key': config.get_config_value(
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
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return False

    log.info('Created node {0}'.format(vm_['name']))
    waiting_for_ip = 0
    failures = 0
    while True:
        time.sleep(0.5)
        waiting_for_ip += 1
        data = get_node(conn, vm_['name'])
        if data is None:
            failures += 1
            if failures > 10:
                log.error('Failed to get node data after 10 attempts')
                return {vm_['name']: False}
            log.info(
                'Failed to get node data. Attempts: {0}'.format(
                    failures
                )
            )
            continue
        failures = 0
        if data.public_ips:
            break
        log.warn('Salt node waiting_for_ip {0}'.format(waiting_for_ip))
    if ssh_interface(vm_) == 'private_ips':
        log.info('Salt node data. Private_ip: {0}'.format(data.private_ips[0]))
        ip_address = data.private_ips[0]
    else:
        log.info('Salt node data. Public_ip: {0}'.format(data.public_ips[0]))
        ip_address = data.public_ips[0]

    username = 'ec2-user'
    if saltcloud.utils.wait_for_ssh(ip_address):
        for user in usernames:
            if saltcloud.utils.wait_for_passwd(
                    host=ip_address, username=user, ssh_timeout=60,
                    key_filename=config.get_config_value(
                        'private_key', vm_, __opts__, search_global=False)):
                username = user
                break
        else:
            return {vm_['name']: 'Failed to authenticate'}

    ret = {}
    if config.get_config_value('deploy', vm_, __opts__) is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'host': ip_address,
            'username': username,
            'key_filename': config.get_config_value(
                'private_key', vm_, __opts__, search_global=False
            ),
            'deploy_command': 'sh /tmp/deploy.sh',
            'tty': True,
            'script': deploy_script.script,
            'name': vm_['name'],
            'sudo': config.get_config_value(
                'sudo', vm_, __opts__, default=(username != 'root')
            ),
            'start_action': __opts__['start_action'],
            'conf_file': __opts__['conf_file'],
            'sock_dir': __opts__['sock_dir'],
            'minion_pem': vm_['priv_key'],
            'minion_pub': vm_['pub_key'],
            'keep_tmp': __opts__['keep_tmp'],
            'script_args': config.get_config_value(
                'script_args', vm_, __opts__
            )
        }

        deploy_kwargs['minion_conf'] = saltcloud.utils.minion_conf_string(
            __opts__, vm_
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
            log.info('Salt installed on {name}'.format(**vm_))
            if __opts__.get('show_deploy_args', False) is True:
                ret['deploy_kwargs'] = deploy_kwargs
        else:
            log.error('Failed to start Salt on Cloud VM {name}'.format(**vm_))

    log.info(
        'Created Cloud VM {name} with the following values:'.format(**vm_)
    )
    for key, val in data.__dict__.items():
        ret[key] = val
        log.debug('  {0}: {1}'.format(key, val))
    volumes = config.get_config_value(
        'map_volumes', vm_, __opts__, search_global=False
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

    CLI Example::

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

    CLI Example::

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

    CLI Example::

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
        saltcloud.utils.rename_key(
            __opts__['pki_dir'], name, kwargs['newname']
        )
    except Exception, exc:
        log.error(
            'Failed to rename {0} to {1}: {2}\n'.format(
                name, kwargs['newname'], exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )


def destroy(name):
    '''
    Wrap core libcloudfuncs destroy method, adding check for termination
    protection
    '''
    ret = {}

    newname = name
    if config.get_config_value('rename_on_destroy',
                               get_configured_provider(),
                               __opts__, search_global=False) is True:
        newname = '{0}-DEL{1}'.format(name, uuid.uuid4().hex)
        rename(name, kwargs={'newname': newname}, call='action')
        log.info(
            'Machine will be identified as {0} until it has been '
            'cleaned up by AWS.'.format(
                newname
            )
        )
        ret['newname'] = newname

    from saltcloud.libcloudfuncs import destroy as libcloudfuncs_destroy
    location = get_location()
    conn = get_conn(location=location)
    libcloudfuncs_destroy = namespaced_function(
        libcloudfuncs_destroy, globals(), (conn,)
    )
    try:
        result = libcloudfuncs_destroy(newname, conn)
        ret.update({'Destroyed': result})
    except Exception as e:
        if not e.message.startswith('OperationNotPermitted'):
            raise e

        log.info(
            'Failed: termination protection is enabled on {0}'.format(
                name
            )
        )

    return ret
