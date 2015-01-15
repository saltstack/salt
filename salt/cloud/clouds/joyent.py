# -*- coding: utf-8 -*-
'''
Joyent Cloud Module
===================

The Joyent Cloud module is used to interact with the Joyent cloud system.

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/joyent.conf``:

.. code-block:: yaml

    my-joyent-config:
      # The Joyent login user
      user: fred
      # The Joyent user's password
      password: saltybacon
      # The location of the ssh private key that can log into the new VM
      private_key: /root/joyent.pem
      provider: joyent

When creating your profiles for the joyent cloud, add the location attribute to
the profile, this will automatically get picked up when performing tasks
associated with that vm. An example profile might look like:

.. code-block:: yaml

      joyent_512:
        provider: my-joyent-config
        size: Extra Small 512 MB
        image: centos-6
        location: us-east-1

:depends: requests
'''
# pylint: disable=E0102

# The import section is mostly libcloud boilerplate

# Import python libs
import os
import copy
import httplib
import requests
import json
import logging
import base64
import pprint
import inspect
import yaml

# Import generic libcloud functions
from salt.cloud.libcloudfuncs import *   # pylint: disable=W0614,W0401

# Import salt.cloud libs
import salt.utils.cloud
import salt.config as config
from salt.utils import namespaced_function
from salt.utils.cloud import is_public_ip
from salt.exceptions import (
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout
)

# Get logging started
log = logging.getLogger(__name__)

JOYENT_API_HOST_SUFFIX = '.api.joyentcloud.com'
JOYENT_API_VERSION = '~6.5'

JOYENT_LOCATIONS = {
    'us-east-1': 'North Virginia, USA',
    'us-west-1': 'Bay Area, California, USA',
    'us-sw-1': 'Las Vegas, Nevada, USA',
    'eu-ams-1': 'Amsterdam, Netherlands'
}
DEFAULT_LOCATION = 'us-east-1'

# joyent no longer reports on all data centers, so setting this value to true
# causes the list_nodes function to get information on machines from all
# data centers
POLL_ALL_LOCATIONS = True

VALID_RESPONSE_CODES = [
    httplib.OK,
    httplib.ACCEPTED,
    httplib.CREATED,
    httplib.NO_CONTENT
]


# Only load in this module is the JOYENT configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for JOYENT configs
    '''
    if get_configured_provider() is False:
        return False

    global script
    conn = None
    script = namespaced_function(script, globals(), (conn,))
    return True


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'joyent',
        ('user', 'password')
    )


def get_image(vm_):
    '''
    Return the image object to use
    '''
    images = avail_images()

    vm_image = config.get_cloud_config_value('image', vm_, __opts__)

    if vm_image and str(vm_image) in images:
        return images[vm_image]

    raise SaltCloudNotFound(
        'The specified image, {0!r}, could not be found.'.format(vm_image)
    )


def get_size(vm_):
    '''
    Return the VM's size object
    '''
    sizes = avail_sizes()
    vm_size = config.get_cloud_config_value('size', vm_, __opts__)
    if not vm_size:
        raise SaltCloudNotFound('No size specified for this VM.')

    if vm_size and str(vm_size) in sizes:
        return sizes[vm_size]

    raise SaltCloudNotFound(
        'The specified size, {0!r}, could not be found.'.format(vm_size)
    )


def create(vm_):
    '''
    Create a single VM from a data dict

    CLI Example:

    .. code-block:: bash

        salt-cloud -p profile_name vm_name
    '''
    key_filename = config.get_cloud_config_value(
        'private_key', vm_, __opts__, search_global=False, default=None
    )

    salt.utils.cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
        transport=__opts__['transport']
    )

    log.info(
        'Creating Cloud VM {0} in {1}'.format(
            vm_['name'],
            vm_.get('location', DEFAULT_LOCATION)
        )
    )

    ## added . for fqdn hostnames
    salt.utils.cloud.check_name(vm_['name'], 'a-zA-Z0-9-.')
    kwargs = {
        'name': vm_['name'],
        'image': get_image(vm_),
        'size': get_size(vm_),
        'location': vm_.get('location', DEFAULT_LOCATION)

    }

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': kwargs},
        transport=__opts__['transport']
    )

    try:
        data = create_node(**kwargs)
    except Exception as exc:
        log.error(
            'Error creating {0} on JOYENT\n\n'
            'The following exception was thrown when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_['name'], str(exc)
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return False

    ret = {}

    def __query_node_data(vm_id, vm_location):
        rcode, data = query(
            command='my/machines/{0}'.format(vm_id),
            method='GET',
            location=vm_location
        )
        if rcode not in VALID_RESPONSE_CODES:
            # Trigger a wait for IP error
            return False

        if data['state'] != 'running':
            # Still not running, trigger another iteration
            return

        if isinstance(data['ips'], list) and len(data['ips']) > 0:
            return data

    if 'ips' in data:
        if isinstance(data['ips'], list) and len(data['ips']) <= 0:
            log.info(
                'New joyent asynchronous machine creation api detected...'
                '\n\t\t-- please wait for IP addresses to be assigned...'
            )
        try:
            data = salt.utils.cloud.wait_for_ip(
                __query_node_data,
                update_args=(
                    data['id'],
                    vm_.get('location', DEFAULT_LOCATION)
                ),
                timeout=config.get_cloud_config_value(
                    'wait_for_ip_timeout', vm_, __opts__, default=5 * 60),
                interval=config.get_cloud_config_value(
                    'wait_for_ip_interval', vm_, __opts__, default=1),
            )
        except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
            try:
                # It might be already up, let's destroy it!
                destroy(vm_['name'])
            except SaltCloudSystemExit:
                pass
            finally:
                raise SaltCloudSystemExit(str(exc))

    data = reformat_node(data)

    ssh_username = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__, default='root'
    )

    if config.get_cloud_config_value('deploy', vm_, __opts__) is True:
        host = data['public_ips'][0]
        if ssh_interface(vm_) == 'private_ips':
            host = data['private_ips'][0]

        deploy_script = script(vm_)
        deploy_kwargs = {
            'opts': __opts__,
            'host': host,
            'username': ssh_username,
            'key_filename': key_filename,
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
                'tty', vm_, __opts__, default=True
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
            transport=__opts__['transport']
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

    ret.update(data)

    log.info('Created Cloud VM {0[name]!r}'.format(vm_))
    log.debug(
        '{0[name]!r} VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data)
        )
    )

    salt.utils.cloud.fire_event(
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
        transport=__opts__['transport']
    )

    return ret


def create_node(**kwargs):
    '''
    convenience function to make the rest api call for node creation.
    '''
    name = kwargs['name']
    size = kwargs['size']
    image = kwargs['image']
    location = kwargs['location']

    data = json.dumps({
        'name': name,
        'package': size['name'],
        'dataset': image['name']
    })

    try:
        ret = query(command='/my/machines', data=data, method='POST',
                     location=location)
        if ret[0] in VALID_RESPONSE_CODES:
            return ret[1]
    except Exception as exc:
        log.error(
            'Failed to create node {0}: {1}'.format(name, exc)
        )

    return {}


def destroy(name, call=None):
    '''
    destroy a machine by name

    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: array of booleans , true if successfully stopped and true if
             successfully removed

    CLI Example:

    .. code-block:: bash

        salt-cloud -d vm_name

    '''
    if call == 'function':
        raise SaltCloudSystemExit(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )

    salt.utils.cloud.fire_event(
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )

    node = get_node(name)
    ret = query(command='my/machines/{0}'.format(node['id']),
                 location=node['location'], method='DELETE')

    salt.utils.cloud.fire_event(
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )

    if __opts__.get('update_cachedir', False) is True:
        salt.utils.cloud.delete_minion_cachedir(name, __active_provider_name__.split(':')[0], __opts__)

    return ret[0] in VALID_RESPONSE_CODES


def reboot(name, call=None):
    '''
    reboot a machine by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reboot vm_name
    '''
    node = get_node(name)
    ret = take_action(name=name, call=call, method='POST',
                      command='/my/machines/{0}'.format(node['id']),
                      location=node['location'], data={'action': 'reboot'})
    return ret[0] in VALID_RESPONSE_CODES


def stop(name, call=None):
    '''
    stop a machine by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop vm_name
    '''
    node = get_node(name)
    ret = take_action(name=name, call=call, method='POST',
                      command='/my/machines/{0}'.format(node['id']),
                      location=node['location'], data={'action': 'stop'})
    return ret[0] in VALID_RESPONSE_CODES


def start(name, call=None):
    '''
    start a machine by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful


    CLI Example:

    .. code-block:: bash

        salt-cloud -a start vm_name
    '''
    node = get_node(name)
    ret = take_action(name=name, call=call, method='POST',
                      command='/my/machines/{0}'.format(node['id']),
                      location=node['location'], data={'action': 'start'})
    return ret[0] in VALID_RESPONSE_CODES


def take_action(name=None, call=None, command=None, data=None, method='GET',
                location=DEFAULT_LOCATION):

    '''
    take action call used by start,stop, reboot
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :command: api path
    :data: any data to be passed to the api, must be in json format
    :method: GET,POST,or DELETE
    :location: data center to execute the command on
    :return: true if successful
    '''
    caller = inspect.stack()[1][3]

    if call != 'action':
        raise SaltCloudSystemExit(
            'This action must be called with -a or --action.'
        )

    if data:
        data = json.dumps(data)

    ret = []
    try:

        ret = query(command=command, data=data, method=method,
                     location=location)
        log.info('Success {0} for node {1}'.format(caller, name))
    except Exception as exc:
        if 'InvalidState' in str(exc):
            ret = [200, {}]
        else:
            log.error(
                'Failed to invoke {0} node {1}: {2}'.format(caller, name, exc),
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
            ret = [100, {}]

    return ret


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
    Return the joyent data center to use, in this order:
        - CLI parameter
        - VM parameter
        - Cloud profile setting
    '''
    return __opts__.get(
        'location',
        config.get_cloud_config_value(
            'location',
            vm_ or get_configured_provider(),
            __opts__,
            default=DEFAULT_LOCATION,
            search_global=False
        )
    )


def avail_locations(call=None):
    '''
    List all available locations
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_locations function must be called with '
            '-f or --function, or with the --list-locations option'
        )

    ret = {}
    for key in JOYENT_LOCATIONS:
        ret[key] = {
            'name': key,
            'region': JOYENT_LOCATIONS[key]
        }

    # this can be enabled when the bug in the joyent get data centers call is
    # corrected, currently only the european dc (new api) returns the correct
    # values
    # ret = {}
    # rcode, datacenters = query(
    #     command='my/datacenters', location=DEFAULT_LOCATION, method='GET'
    # )
    # if rcode in VALID_RESPONSE_CODES and isinstance(datacenters, dict):
    #     for key in datacenters:
    #     ret[key] = {
    #         'name': key,
    #         'url': datacenters[key]
    #     }
    return ret


def has_method(obj, method_name):
    '''
    Find if the provided object has a specific method
    '''
    if method_name in dir(obj):
        return True

    log.error(
        'Method {0!r} not yet supported!'.format(
            method_name
        )
    )
    return False


def key_list(key='name', items=None):
    '''
    convert list to dictionary using the key as the identifier
    :param key: identifier - must exist in the arrays elements own dictionary
    :param items: array to iterate over
    :return: dictionary
    '''
    if items is None:
        items = []

    ret = {}
    if items and isinstance(items, list):
        for item in items:
            if 'name' in item:
                # added for consistency with old code
                if 'id' not in item:
                    item['id'] = item['name']
                ret[item['name']] = item
    return ret


def get_node(name):
    '''
    gets the node from the full node list by name
    :param name: name of the vm
    :return: node object
    '''
    nodes = list_nodes()
    if name in nodes:
        return nodes[name]
    return None


def joyent_node_state(id_):
    '''
    Convert joyent returned state to state common to other data center return
    values for consistency

    :param id_: joyent state value
    :return: libcloudfuncs state value
    '''
    states = {'running': 0,
              'stopped': 2,
              'stopping': 2,
              'provisioning': 3,
              'deleted': 2,
              'unknown': 4}

    if id_ not in states:
        id_ = 'unknown'

    return node_state(states[id_])


def reformat_node(item=None, full=False):
    '''
    Reformat the returned data from joyent, determine public/private IPs and
    strip out fields if necessary to provide either full or brief content.

    :param item: node dictionary
    :param full: full or brief output
    :return: dict
    '''
    desired_keys = [
        'id', 'name', 'state', 'public_ips', 'private_ips', 'size', 'image',
        'location'
    ]
    item['private_ips'] = []
    item['public_ips'] = []
    if 'ips' in item:
        for ip in item['ips']:
            if is_public_ip(ip):
                item['public_ips'].append(ip)
            else:
                item['private_ips'].append(ip)

    # add any undefined desired keys
    for key in desired_keys:
        if key not in item:
            item[key] = None

    # remove all the extra key value pairs to provide a brief listing
    if not full:
        for key in item.keys():  # iterate over a copy of the keys
            if key not in desired_keys:
                del item[key]

    if 'state' in item:
        item['state'] = joyent_node_state(item['state'])

    return item


def list_nodes(full=False, call=None):
    '''
    list of nodes, keeping only a brief listing

    CLI Example:

    .. code-block:: bash

        salt-cloud -Q
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    ret = {}
    if POLL_ALL_LOCATIONS:
        for location in JOYENT_LOCATIONS:
            result = query(command='my/machines', location=location,
                            method='GET')
            nodes = result[1]
            for node in nodes:
                if 'name' in node:
                    node['location'] = location
                    ret[node['name']] = reformat_node(item=node, full=full)

    else:
        result = query(command='my/machines', location=DEFAULT_LOCATION,
                        method='GET')
        nodes = result[1]
        for node in nodes:
            if 'name' in node:
                node['location'] = DEFAULT_LOCATION
                ret[node['name']] = reformat_node(item=node, full=full)
    return ret


def list_nodes_full(call=None):
    '''
    list of nodes, maintaining all content provided from joyent listings

    CLI Example:

    .. code-block:: bash

        salt-cloud -F
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    return list_nodes(full=True)


def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full('function'), __opts__['query.selection'], call,
    )


def avail_images(call=None):
    '''
    get list of available images

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-images
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    img_url = 'https://images.joyent.com/images'
    result = requests.get(img_url)
    content = result.text

    ret = {}
    for image in yaml.safe_load(content):
        ret[image['name']] = image
    return ret


def avail_sizes(call=None):
    '''
    get list of available packages

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-sizes
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-sizes option'
        )

    rcode, items = query(command='/my/packages')
    if rcode not in VALID_RESPONSE_CODES:
        return {}
    return key_list(items=items)


def list_keys(kwargs=None, call=None):
    '''
    List the keys available
    '''
    if call != 'function':
        log.error(
            'The list_keys function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    ret = {}
    rcode, data = query(command='my/keys', method='GET')
    for pair in data:
        ret[pair['name']] = pair['key']
    return {'keys': ret}


def show_key(kwargs=None, call=None):
    '''
    List the keys available
    '''
    if call != 'function':
        log.error(
            'The list_keys function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'keyname' not in kwargs:
        log.error('A keyname is required.')
        return False

    rcode, data = query(
        command='my/keys/{0}'.format(kwargs['keyname']),
        method='GET',
    )
    return {'keys': {data['name']: data['key']}}


def import_key(kwargs=None, call=None):
    '''
    List the keys available

    CLI Example:

    .. code-block:: bash

        salt-cloud -f import_key joyent keyname=mykey keyfile=/tmp/mykey.pub
    '''
    if call != 'function':
        log.error(
            'The import_key function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'keyname' not in kwargs:
        log.error('A keyname is required.')
        return False

    if 'keyfile' not in kwargs:
        log.error('The location of the SSH keyfile is required.')
        return False

    if not os.path.isfile(kwargs['keyfile']):
        log.error('The specified keyfile ({0}) does not exist.'.format(
            kwargs['keyfile']
        ))
        return False

    with salt.utils.fopen(kwargs['keyfile'], 'r') as fp_:
        kwargs['key'] = fp_.read()

    send_data = {'name': kwargs['keyname'], 'key': kwargs['key']}
    kwargs['data'] = json.dumps(send_data)

    rcode, data = query(
        command='my/keys',
        method='POST',
        data=kwargs['data'],
    )
    log.debug(pprint.pformat(data))
    return {'keys': {data['name']: data['key']}}


def delete_key(kwargs=None, call=None):
    '''
    List the keys available

    CLI Example:

    .. code-block:: bash

        salt-cloud -f delete_key joyent keyname=mykey
    '''
    if call != 'function':
        log.error(
            'The delete_keys function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'keyname' not in kwargs:
        log.error('A keyname is required.')
        return False

    rcode, data = query(
        command='my/keys/{0}'.format(kwargs['keyname']),
        method='DELETE',
    )
    return data


def get_location_path(location=DEFAULT_LOCATION):
    '''
    create url from location variable
    :param location: joyent data center location
    :return: url
    '''
    return 'https://{0}{1}'.format(location, JOYENT_API_HOST_SUFFIX)


def query(action=None, command=None, args=None, method='GET', location=None,
           data=None):
    '''
    Make a web call to Joyent
    '''
    user = config.get_cloud_config_value(
        'user', get_configured_provider(), __opts__, search_global=False
    )

    password = config.get_cloud_config_value(
        'password', get_configured_provider(), __opts__,
        search_global=False
    )

    if not location:
        location = get_location()

    path = get_location_path(location=location)

    if action:
        path += action

    if command:
        path += '/{0}'.format(command)

    log.debug('User: {0!r} on PATH: {1}'.format(user, path))
    auth_key = base64.b64encode('{0}:{1}'.format(user, password))

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Api-Version': JOYENT_API_VERSION,
        'Authorization': 'Basic {0}'.format(auth_key)}

    if not isinstance(args, dict):
        args = {}

    # post form data
    if not data:
        data = json.dumps({})

    return_content = None
    try:

        result = requests.request(method, path, params=args, headers=headers, data=data)
        log.debug(
            'Joyent Response Status Code: {0}'.format(
                result.status_code
            )
        )
        if 'content-length' in result.headers:
            content = result.text
            return_content = yaml.safe_load(content)

        return [result.status_code, return_content]

    except requests.exceptions.HTTPError as exc:
        log.error(
            'Joyent Response Status Code: {0}'.format(
                str(exc)
            )
        )
        log.error(exc)
        return [0, {'error': exc}]
