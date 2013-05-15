'''
Joyent Cloud Module
===================

The Joyent Cloud module is used to interact with the Joyent cloud system.

Using the old cloud configuration syntax, it requires that the ``username`` and
``password`` to the joyent account be configured:

.. code-block:: yaml

    # The Joyent login user
    JOYENT.user: fred
    # The Joyent user's password
    JOYENT.password: saltybacon
    # The location of the ssh private key that can log into the new VM
    JOYENT.private_key: /root/joyent.pem

Using the new format, set up the cloud configuration at
 ``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/joyent.conf``:

.. code-block:: yaml

    my-joyent-config:
      # The Joyent login user
      user: fred
      # The Joyent user's password
      password: saltybacon
      # The location of the ssh private key that can log into the new VM
      private_key: /root/joyent.pem
      provider: joyent

When creating your profiles for the joyent cloud, add the location attribute to the profile, this will automatically
get picked up when performing tasks associated with that vm.

'''

# The import section is mostly libcloud boilerplate

# Import python libs
import os
import urllib
import httplib
import urllib2
import json
import logging
import base64
import pprint
import inspect
import time
import yaml

# Import generic libcloud functions
from saltcloud.libcloudfuncs import *   # pylint: disable-msg=W0614,W0401

# Import saltcloud libs
import saltcloud.utils
import saltcloud.config as config
from saltcloud.utils import namespaced_function, is_public_ip
from saltcloud.exceptions import SaltCloudSystemExit

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


# this variable is used to support asynchronous node creation, new joyent api does not return ip addresses
# in the create machine call, it must be polled until successful creation of the node,
NODE_CREATE_TIMEOUT=60

# joyent no longer reports on all datacenters, so setting this value to true causes the list_nodes function
# to get information on machines from all datacenters
POLL_ALL_LOCATIONS=True

valid_response_codes = [httplib.OK, httplib.ACCEPTED, httplib.CREATED, httplib.NO_CONTENT]

class DictObject(dict):
    '''
    handy class to make a dictionary into a simple object
    '''
    def __init__(self, data):

        self.update(data)
        for k, v in data.items():
            setattr(self, k, v)


# Only load in this module is the JOYENT configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for JOYENT configs
    '''
    if get_configured_provider() is False:
        log.debug(
            'There is no Joyent cloud provider configuration available. Not '
            'loading module.'
        )
        return False

    log.debug('Loading Joyent cloud module')

    global script, list_nodes_select
    conn = None
    script = namespaced_function(script, globals(), (conn,))
    list_nodes_select = namespaced_function(list_nodes_select, globals(), (conn,))

    return 'joyent'


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__, 'joyent', ('user', 'password')
    )


def get_image(vm_):
    '''
    Return the image object to use
    '''
    images = avail_images()

    vm_image = config.get_config_value('image', vm_, __opts__)

    if vm_image and str(vm_image) in images.keys():
        return images[vm_image]

    raise SaltCloudNotFound('The specified image could not be found.')


def get_size(vm_):
    '''
    Return the VM's size object
    '''
    sizes = avail_sizes()
    vm_size = config.get_config_value('size', vm_, __opts__)
    if not vm_size:
        raise SaltCloudNotFound('No size specified for this VM.')

    if vm_size and str(vm_size) in sizes.keys():
        return sizes[vm_size]

    raise SaltCloudNotFound('The specified size could not be found.')


def create(vm_):
    '''
    Create a single VM from a data dict


        CLI Example:

        salt-cloud -p profile_name vm_name
    '''

    deploy = config.get_config_value('deploy', vm_, __opts__)
    key_filename = config.get_config_value(
        'private_key', vm_, __opts__, search_global=False, default=None
    )
    if deploy is True and key_filename is None and salt.utils.which('sshpass') is None:
        raise SaltCloudSystemExit(
            'Cannot deploy salt in a VM if the \'private_key\' setting '
            'is not set and \'sshpass\' binary is not present on the '
            'system for the password.'
        )

    log.info('Creating Cloud VM {0} in {1}'.format(vm_['name'], vm_['location']))

    ## added . for fqdn hostnames
    saltcloud.utils.check_name(vm_['name'], 'a-zA-Z0-9-.')
    kwargs = {
        'name': vm_['name'],
        'image': get_image(vm_),
        'size': get_size(vm_),
        'location': vm_['location']

    }
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
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return False

    ret = {}

    vm_id = data['id']
    # with the new api, the ip addresses are not returned in the create machine call, as a result we must poll until we
    # get ip addresses from query of the node, this can take up to 10 seconds on a small node.
    if 'ips' in data:
        if isinstance(data['ips'], list) and len(data['ips']) <= 0:
            log.info("New joyent asynchronous machine creation api detected ... \n           -- please wait for IP addresses to be assigned...")
            for i in range(NODE_CREATE_TIMEOUT):
                rc,data = query2(command='my/machines/{0}'.format(vm_id), method='GET', location=vm_['location'])
                if rc in valid_response_codes and  isinstance(data['ips'], list) and len(data['ips']) > 0:
                    break
                time.sleep(1)

    data = reformat_node(data)

    if config.get_config_value('deploy', vm_, __opts__) is True:
        host = data.public_ips[0]
        if ssh_interface(vm_) == 'private_ips':
            host = data.private_ips[0]

        deploy_script = script(vm_)
        deploy_kwargs = {
            'host': host,
            'username': 'root',
            'key_filename': key_filename,
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


def create_node(**kwargs):
    '''
    convenience function to make the rest api call for node creation.
    '''
    name = kwargs['name']
    size = kwargs['size']
    image = kwargs['image']
    location = kwargs['location']

    data = json.dumps({'name': name, 'package': size.id, 'dataset': image.id})

    try:
        ret = query2(command='/my/machines', data=data, method='POST', location=location)
        if ret[0] in valid_response_codes:
            return ret[1]
    except Exception as exc:
        log.error(
            'Failed to create node {0}: {1}'.format(name, exc)
        )

    return {}


def destroy(name, call=None):
    """
    destroy a machine by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: array of booleans , true if successful;ly stopped and true if successfully removed

        CLI Example:

        salt-cloud -d vm_name

    """
    node = get_node(name)
    ret = query2(command='my/machines/{0}'.format(node.id), location=node.location, method='DELETE')
    return ret[0] in valid_response_codes


def reboot(name, call=None):
    """
    reboot a machine by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful


    CLI Example:

        salt-cloud -a reboot vm_name
    """
    node = get_node(name)
    ret = take_action(name=name, call=call, method='POST', command='/my/machines/%s' %  node.id, location=node.location,
                      data={'action': 'reboot'})
    return ret[0] in valid_response_codes


def stop(name, call=None):
    """
    stop a machine by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful


    CLI Example:

        salt-cloud -a stop vm_name
    """
    node = get_node(name)
    ret = take_action(name=name, call=call, method='POST', command='/my/machines/%s' %  node.id, location=node.location,
                      data={'action': 'stop'})
    return ret[0] in valid_response_codes


def start(name, call=None):
    """
    start a machine by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful


    CLI Example:

        salt-cloud -a start vm_name
    """
    node = get_node(name)
    ret = take_action(name=name, call=call, method='POST', command='/my/machines/%s' % node.id, location=node.location,
                      data={'action': 'start'})
    return ret[0] in valid_response_codes


def take_action(name=None, call=None, command=None, data=None, method='GET', location=DEFAULT_LOCATION):

    """
    take action call used by start,stop, reboot
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :command: api path
    :data: any data to be passed to the api, must be in json format
    :method: GET,POST,or DELETE
    :location: datacenter to execute the command on
    :return: true if successful
    """
    caller = inspect.stack()[1][3]

    if call != 'action':
        raise SaltCloudSystemExit(
            'This action must be called with -a or --action.'
        )

    if data:
        data = json.dumps(data)

    ret = []
    try:

        ret = query2(command=command, data=data, method=method, location=location)
        log.info('Success {0} for node {1}'.format(caller, name))
    except Exception as exc:
        if 'InvalidState' in str(exc):
            ret = [200, {}]
        else:
            log.error(
                'Failed to invoke {0} node {1}: {2}'.format(caller, name, exc),
                # Show the traceback if the debug logging level is enabled
                exc_info=log.isEnabledFor(logging.DEBUG)
            )
            ret = [100, {}]

    return ret


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
    Return the joyent datacenter to use, in this order:
        - CLI parameter
        - VM parameter
        - Cloud profile setting
    '''
    return __opts__.get(
        'location',
        config.get_config_value(
            'location',
            vm_ or get_configured_provider(),
            __opts__,
            default=DEFAULT_LOCATION,
            search_global=False
        )
    )


def avail_locations():
    '''
    List all available locations
    '''
    ret = {}
    for key in JOYENT_LOCATIONS:
        ret[key] = {
            'name': key,
            'region': JOYENT_LOCATIONS[key]
        }

    # this can be enabled when the bug in the joyent get datacenters call is corrected, currently only the
    # european dc (new api) returns the correct values
    # ret = {}
    # rc, datacenters =  query2(command='my/datacenters',  location=DEFAULT_LOCATION, method='GET')
    # if rc in valid_response_codes and isinstance(datacenters,dict):
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


def key_list(key='name', items=[]):
    """
    convert list to dictionary using the key as the identifier
    :param key: identifier - must exist in the arrays elements own dictionary
    :param items: array to iterate over
    :return: dictionary
    """
    ret = {}
    if items and isinstance(items, list):
        for item in items:
            if 'name' in item:
                # added for consistency with old code
                if not 'id' in item:
                    item['id'] = item['name']
                ret[item['name']] = DictObject(item)
    return ret


def get_node(name):
    """
    gets the node from the full node list by name
    :param name: name of the vm
    :return: node object
    """
    nodes = list_nodes()
    if name in nodes.keys():
        return nodes[name]
    return None


def joyent_node_state(id_):
    """
    convert joyent returned state to state common to other datacenter return  values for consistency
    :param id_: joyent state value
    :return: libcloudfuncs state value
    """
    states = {'running': 0,
              'stopped': 2,
              'stopping': 2,
              'provisioning': 3,
              'deleted': 2,
              'unknown': 4
    }
    if id_ not in states.keys():
        id_ = 'unknown'

    return node_state(states[id_])


def reformat_node(item=None, full=False):
    """
    reformat the returned data from joyent, determine public/private ips and strip out fields if necessary to provide
    either full or brief content
    :param item: node dictionary
    :param full: full or brief output
    :return: DictObject
    """
    desired_keys = ['id', 'name', 'state', 'public_ips', 'private_ips', 'size', 'image', 'location']
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
        if not key in item.keys():
            item[key] = None

    # remove all the extra key value pairs to provide a brief listing
    if not full:
        for key in item.keys():
            if not key in desired_keys:
                del item[key]


    if 'state' in item.keys():
        item['state'] = joyent_node_state(item['state'])

    return DictObject(item)


def list_nodes(full=False):
    """
    list of nodes, keeping only a brief listing


    CLI Example:

        salt-cloud -Q
    """
    ret = {}
    if POLL_ALL_LOCATIONS:
        for location in JOYENT_LOCATIONS.keys():
            result = query2(command='my/machines',  location=location, method='GET')
            nodes=result[1]
            for node in nodes:
                if 'name' in node:
                    node['location'] = location
                    ret[node['name']] = reformat_node(item=node, full=full)

    else:
        result = query2(command='my/machines',  location=DEFAULT_LOCATION, method='GET')
        nodes=result[1]
        for node in nodes:
            if 'name' in node:
                node['location'] = DEFAULT_LOCATION
                ret[node['name']] = reformat_node(item=node, full=full)
    return ret


def list_nodes_full():
    """
    list of nodes, maintaining all content provided from joyent listings


    CLI Example:

        salt-cloud -F
    """
    return list_nodes(full=True)


def avail_images():
    """
    get list of available images

    CLI Example:

        salt-cloud --list-images

    """
    rc, items = query2(command='/my/datasets')
    if rc not in valid_response_codes:
        return {}
    return key_list(items=items)


def avail_sizes():
    """
    get list of available packages

    CLI Example:

        salt-cloud --list-sizes
    """
    rc, items = query2(command='/my/packages')
    if rc not in valid_response_codes:
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
    data = query(action='keys')
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

    data = query(action='keys/{0}'.format(kwargs['keyname']))
    return {'keys': {data['name']: data['key']}}


def import_key(kwargs=None, call=None):
    '''
    List the keys available

    CLI Example:

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

    data = query(action='keys', method='POST', data=kwargs['data'],
                 headers={'Content-Type': 'application/json'})
    return {'keys': {data['name']: data['key']}}


def delete_key(kwargs=None, call=None):
    '''
    List the keys available

    CLI Example:

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

    data = query(action='keys/{0}'.format(kwargs['keyname']), method='DELETE')
    return data



def query(action=None, command=None, args=None, method='GET', data=None,
          headers=None):
    '''
    Make a web call to Joyent
    '''
    location = get_location()
    path = 'https://{0}.api.joyentcloud.com/{1}/'.format(
        location,
        config.get_config_value(
            'user', get_configured_provider(), __opts__, search_global=False
        ),
    )
    auth_handler = urllib2.HTTPBasicAuthHandler()
    auth_handler.add_password(
        realm='SmartDataCenter',
        uri=path,
        user=config.get_config_value(
            'user', get_configured_provider(), __opts__, search_global=False
        ),
        passwd=config.get_config_value(
            'password', get_configured_provider(), __opts__,
            search_global=False
        )
    )
    opener = urllib2.build_opener(auth_handler)
    urllib2.install_opener(opener)

    if action:
        path += action

    if command:
        path += '/{0}'.format(command)

    if type(args) is not dict:
        args = {}

    kwargs = {'data': data}
    kwargs['headers'] = {
        'Accept': 'application/json',
        'X-Api-Version': '~6.5',
    }
    if type(headers) is dict:
        for header in headers.keys():
            kwargs['headers'][header] = headers[header]

    pprint(kwargs['headers'])

    if args:
        path += '?%s'
        params = urllib.urlencode(args)
        req = urllib2.Request(url=path % params, **kwargs)
    else:
        req = urllib2.Request(url=path, **kwargs)

    req.get_method = lambda: method

    log.debug('{0} {1}'.format(method, req.get_full_url()))
    if data:
        log.debug(data)

    try:
        result = urllib2.urlopen(req)
        log.debug(
            'Joyent Response Status Code: {0}'.format(
                result.getcode()
            )
        )

        content = result.read()
        result.close()

        data = yaml.safe_load(content)
        return data
    except urllib2.URLError as exc:
        log.error(
            'Joyent Response Status Code: {0} {1}'.format(
                exc.code,
                exc.msg
            )
        )
        log.error(exc)
        return {'error': exc}


def get_location_path(location=DEFAULT_LOCATION):
    """
    create url from location variable
    :param location: joyent datacenter location
    :return: url
    """
    return 'https://{0}{1}'.format(location, JOYENT_API_HOST_SUFFIX)


def query2(action=None, command=None, args=None, method='GET', location=None, data=None):
    '''

    Make a web call to Joyent
    '''

    user = config.get_config_value(
        'user', get_configured_provider(), __opts__, search_global=False
    )

    password = config.get_config_value(
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

    log.debug("PATH: {2}\nCredentials: {0}/{1}".format(user, password, path))

    authKey = base64.b64encode('{0}:{1}'.format(user, password))

    log.debug("Data: {0}".format(data))

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Api-Version': JOYENT_API_VERSION,
        'Authorization': 'Basic ' + authKey}

    if type(args) is not dict:
        args = {}
    request = None
    if args:
        path += '?%s'
        params = urllib.urlencode(args)
        path = path % params

    request = urllib2.Request(path)
    request.get_method = lambda: method

    # post form data
    if not data:
        data = json.dumps({})

    request.add_data(data)

    for key, value in headers.items():
        request.add_header(key, value)

    return_content = None
    try:

        result = urllib2.urlopen(request)
        log.debug(
            'Joyent Response Status Code: {0}'.format(
                result.getcode()
            )
        )
        if 'content-length' in result.headers:
            content = result.read()
            result.close()
            return_content = yaml.safe_load(content)

        return [result.getcode(), return_content]

    except urllib2.URLError as exc:
        log.error(
            'Joyent Response Status Code: {0}'.format(
                str(exc)
            )
        )
        log.error(exc)
        return [0, {'error': exc}]

