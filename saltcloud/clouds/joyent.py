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
    # the Datacenter location associated with the new VMS
    JOYENT.location: us-east-1

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
      location: us-east-1

'''

# The import section is mostly libcloud boilerplate

# Import python libs
import os
import json
import yaml
import pprint
import urllib2
import logging

# Import generic libcloud functions
from saltcloud.libcloudfuncs import *   # pylint: disable-msg=W0614,W0401

# Import saltcloud libs
import saltcloud.utils
import saltcloud.config as config
from saltcloud.utils import namespaced_function
from saltcloud.exceptions import SaltCloudSystemExit

# Get logging started
log = logging.getLogger(__name__)


JOYENT_LOCATIONS = {
    'us-east-1': 'North Virginia, USA',
    'us-west-1': 'Bay Area, California, USA',
    'us-sw-1': 'Las Vegas, Nevada, USA',
    'eu-ams-1': 'Amsterdam, Netherlands'
}
DEFAULT_LOCATION = 'us-east-1'


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

    global get_size, get_image, avail_images, avail_sizes, script, destroy
    global list_nodes, list_nodes_full, list_nodes_select

    conn = get_conn(get_location())

    get_size = namespaced_function(get_size, globals(), (conn,))
    get_image = namespaced_function(get_image, globals(), (conn,))
    avail_images = namespaced_function(avail_images, globals(), (conn,))
    avail_sizes = namespaced_function(avail_sizes, globals(), (conn,))
    script = namespaced_function(script, globals(), (conn,))
    destroy = namespaced_function(destroy, globals(), (conn,))
    list_nodes = namespaced_function(list_nodes, globals(), (conn,))
    list_nodes_full = namespaced_function(list_nodes_full, globals(), (conn,))
    list_nodes_select = namespaced_function(
        list_nodes_select, globals(), (conn,)
    )

    log.debug('Loading Joyent cloud module')
    return 'joyent'


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__, 'joyent', ('user', 'password')
    )


def get_conn(location=DEFAULT_LOCATION):
    '''
    Return a conn object for the passed VM data
    '''
    driver = get_driver(Provider.JOYENT)

    log.debug("Loading driver for connection to {0}".format(location))

    return driver(
        config.get_config_value(
            'user',
            get_configured_provider(),
            __opts__,
            search_global=False
        ),
        config.get_config_value(
            'password',
            get_configured_provider(),
            __opts__,
            search_global=False,
        ),
        location=location
    )


def create(vm_):
    '''
    Create a single VM from a data dict
    '''

    deploy = config.get_config_value('deploy', vm_, __opts__)
    key_filename = config.get_config_value(
        'private_key', vm_, __opts__, search_global=False, default=None
    )
    if deploy is True and key_filename is None and \
            salt.utils.which('sshpass') is None:
        raise SaltCloudSystemExit(
            'Cannot deploy salt in a VM if the \'private_key\' setting '
            'is not set and \'sshpass\' binary is not present on the '
            'system for the password.'
        )

    vm_['location'] = get_location()
    conn = get_conn(get_location())

    log.info(
        'Creating Cloud VM {0} in {1}'.format(
            vm_['name'], vm_['location']
        )
    )

    saltcloud.utils.check_name(vm_['name'], 'a-zA-Z0-9-.')
    kwargs = {
        'name': vm_['name'],
        'image': get_image(conn, vm_),
        'size': get_size(conn, vm_),
        'location': vm_['location']

    }

    try:
        data = conn.create_node(**kwargs)
    except Exception as exc:
        log.error(
            'Error creating {0} on JOYENT\n\n'
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


def reboot(name, call=None):
    '''
    Reboot a node.

    CLI Example::

        salt-cloud -a reboot mymachine
    '''
    return __take_action(name, call, 'reboot_node', 'Rebooting', 'reboot')


def stop(name, call=None):
    '''
    Stop a node

    CLI Example::

        salt-cloud -a stop mymachine
    '''
    return __take_action(name, call, 'ex_stop_node', 'Stopped', 'stop')


def start(name, call=None):
    '''
    Start a node

    CLI Example::

        salt-cloud -a start mymachine
    '''
    return __take_action(name, call, 'start_node', 'Started', 'start')


def __take_action(name, call=None, action=None, atext=None, btext=None):
    data = {}

    if call != 'action':
        raise SaltCloudSystemExit(
            'This action must be called with -a or --action.'
        )

    conn = get_conn(get_location())
    if atext is None:
        atext = action
    if btext is None:
        btext = atext

    if not conn_has_method(conn, action):
        return data

    node = get_node(conn, name)
    try:
        data = getattr(conn, action)(node=node)
        log.debug(data)
        log.info('{0} node {1}'.format(atext, name))
    except Exception as exc:
        if 'InvalidState' in str(exc):
            data = 'False'
        else:
            log.error(
                'Failed to {0} node {1}: {2}'.format(
                    btext, name, exc
                ),
                # Show the traceback if the debug logging level is enabled
                exc_info=log.isEnabledFor(logging.DEBUG)
            )

    return data


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
    import pprint
    pprint.pprint(kwargs['headers'])

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
