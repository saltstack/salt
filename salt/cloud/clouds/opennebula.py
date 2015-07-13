# -*- coding: utf-8 -*-
'''
OpenNebula Cloud Module
=======================

The OpenNebula cloud module is used to control access to an OpenNebula cloud.

.. versionadded:: 2014.7.0

Use of this module requires the ``xml_rpc``, ``user``, and ``password``
parameters to be set.

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/opennebula.conf``:

.. code-block:: yaml

    my-opennebula-config:
      xml_rpc: http://localhost:2633/RPC2
      user: oneadmin
      password: JHGhgsayu32jsa
      driver: opennebula

'''

# Import Python Libs
from __future__ import absolute_import
import copy
import logging
import os
import pprint
import time

# Import Salt Libs
import salt.config as config
from salt.exceptions import (
    SaltCloudConfigError,
    SaltCloudException,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout,
    SaltCloudNotFound,
    SaltCloudSystemExit
)

# Import Salt Cloud Libs
import salt.utils.cloud

# Import Third Party Libs
try:
    import salt.ext.six.moves.xmlrpc_client  # pylint: disable=E0611
    from lxml import etree
    HAS_XML_LIBS = True
except ImportError:
    HAS_XML_LIBS = False

# Get Logging Started
log = logging.getLogger(__name__)

__virtualname__ = 'opennebula'


def __virtual__():
    '''
    Check for OpenNebula configs.
    '''
    if not HAS_XML_LIBS:
        return False

    if get_configured_provider() is False:
        return False

    return __virtualname__


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'opennebula',
        ('xml_rpc', 'user', 'password')
    )


def avail_images(call=None):
    '''
    Return available OpenNebula images.

    call
        Optional type of call to use with this function such as ``function``.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-images opennebula
        salt-cloud --function avail_images opennebula
        salt-cloud -f avail_images opennebula

    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    image_pool = server.one.imagepool.info(auth, -1, -1, -1)[1]

    images = {}
    for image in etree.XML(image_pool):
        images[image.find('NAME').text] = _xml_to_dict(image)

    return images


def avail_locations(call=None):
    '''
    Return available OpenNebula locations.

    call
        Optional type of call to use with this function such as ``function``.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-locations opennebula
        salt-cloud --function avail_locations opennebula
        salt-cloud -f avail_locations opennebula

    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_locations function must be called with '
            '-f or --function, or with the --list-locations option'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    host_pool = server.one.hostpool.info(auth)[1]

    locations = {}
    for host in etree.XML(host_pool):
        locations[host.find('NAME').text] = _xml_to_dict(host)

    return locations


def avail_sizes():
    '''
    Because sizes are built into templates with OpenNebula, there will be no sizes to
    return here.
    '''
    log.info('Because sizes are built into templates with OpenNebula, '
             'there are no sizes to return.')
    return {}


def list_nodes(call=None):
    '''
    Return a list of VMs on OpenNebubla.

    call
        Optional type of call to use with this function such as ``function``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -Q
        salt-cloud --query
        salt-cloud --fuction list_nodes opennebula
        salt-cloud -f list_nodes opennebula

    '''
    if call == 'action':
        raise SaltCloudException(
            'The list_nodes function must be called with -f or --function.'
        )

    return _list_nodes(full=False)


def list_nodes_full(call=None):
    '''
    Return a list of the VMs that are on the provider.

    call
        Optional type of call to use with this function such as ``function``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -F
        salt-cloud --full-query
        salt-cloud --function list_nodes_full opennebula
        salt-cloud -f list_nodes_full opennebula

    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    return _list_nodes(full=True)


def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields.

    call
        Optional type of call to use with this function such as ``function``.
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    return salt.utils.cloud.list_nodes_select(
        list_nodes_full('function'), __opts__['query.selection'], call,
    )


def get_image(vm_):
    '''
    Return the image object to use.

    vm_
        The VM for which to obtain an image.
    '''
    images = avail_images()
    vm_image = str(config.get_cloud_config_value(
        'image', vm_, __opts__, search_global=False
    ))
    for image in images:
        if vm_image in (images[image]['name'], images[image]['id']):
            return images[image]['id']
    raise SaltCloudNotFound(
        'The specified image, {0!r}, could not be found.'.format(vm_image)
    )


def get_location(vm_):
    '''
    Return the VM's location.

    vm_
        The VM for which to obtain a location.
    '''
    locations = avail_locations()
    vm_location = str(config.get_cloud_config_value(
        'location', vm_, __opts__, search_global=False
    ))

    if vm_location == 'None':
        return None

    for location in locations:
        if vm_location in (locations[location]['name'],
                           locations[location]['id']):
            return locations[location]['id']
    raise SaltCloudNotFound(
        'The specified location, {0!r}, could not be found.'.format(
            vm_location
        )
    )


def create(vm_):
    '''
    Create a single VM from a data dict.

    vm_
        The name of the VM to create.

    CLI Example:

    .. code-block:: bash

        salt-cloud -p my-opennebula-profile vm_name

    '''
    # Check for required profile parameters before sending any API calls.
    if config.is_profile_configured(__opts__,
                                    __active_provider_name__ or 'opennebula',
                                    vm_['profile']) is False:
        return False

    # Since using "provider: <provider-engine>" is deprecated, alias provider
    # to use driver: "driver: <provider-engine>"
    if 'provider' in vm_:
        vm_['driver'] = vm_.pop('provider')

    salt.utils.cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
        transport=__opts__['transport']
    )

    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    kwargs = {
        'name': vm_['name'],
        'image_id': get_image(vm_),
        'region_id': get_location(vm_),
    }

    key_filename = config.get_cloud_config_value(
        'ssh_key_file', vm_, __opts__, search_global=False, default=None
    )
    if key_filename is not None and not os.path.isfile(key_filename):
        raise SaltCloudConfigError(
            'The defined key_filename {0!r} does not exist'.format(
                key_filename
            )
        )

    private_networking = config.get_cloud_config_value(
        'private_networking', vm_, __opts__, search_global=False, default=None
    )
    kwargs['private_networking'] = 'true' if private_networking else 'false'

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': kwargs},
    )

    region = ''
    if kwargs['region_id'] is not None:
        region = 'SCHED_REQUIREMENTS="ID={0}"'.format(kwargs['region_id'])
    try:
        server, user, password = _get_xml_rpc()
        ret = server.one.template.instantiate(user+':'+password, int(kwargs['image_id']), kwargs['name'], False, region)[1]
    except Exception as exc:
        log.error(
            'Error creating {0} on OpenNebula\n\n'
            'The following exception was thrown when trying to '
            'run the initial deployment: {1}'.format(
                vm_['name'],
                str(exc)
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return False

    def __query_node_data(vm_name):
        data = show_instance(vm_name, call='action')
        if not data:
            # Trigger an error in the wait_for_ip function
            return False
        if data['state'] == '7':
            return False
        if data['lcm_state'] == '3':
            return data

    try:
        data = salt.utils.cloud.wait_for_ip(
            __query_node_data,
            update_args=(vm_['name'],),
            timeout=config.get_cloud_config_value(
                'wait_for_ip_timeout', vm_, __opts__, default=10 * 60),
            interval=config.get_cloud_config_value(
                'wait_for_ip_interval', vm_, __opts__, default=2),
        )
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
        try:
            # It might be already up, let's destroy it!
            destroy(vm_['name'])
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(str(exc))

    ssh_username = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__, default='root'
    )

    if config.get_cloud_config_value('deploy', vm_, __opts__) is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'host': data['private_ips'][0],
            'username': ssh_username,
            'key_filename': key_filename,
            'script': deploy_script,
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
            'display_ssh_output': config.get_cloud_config_value(
                'display_ssh_output', vm_, __opts__, default=True
            ),
            'sudo': config.get_cloud_config_value(
                'sudo', vm_, __opts__, default=(ssh_username != 'root')
            ),
            'sudo_password': config.get_cloud_config_value(
                'sudo_password', vm_, __opts__, default=None
            ),
            'tty': config.get_cloud_config_value(
                'tty', vm_, __opts__, default=False
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
        ret = {}
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
            'provider': vm_['driver'],
        },
    )

    return ret


def destroy(name, call=None):
    '''
    Destroy a node. Will check termination protection and warn if enabled.

    name
        The name of the vm to be destroyed.

    call
        Optional type of call to use with this function such as ``action``.

    CLI Example:

    .. code-block:: bash

        salt-cloud --destroy vm_name
        salt-cloud -d vm_name
        salt-cloud --action destroy vm_name
        salt-cloud -a destroy vm_name

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
    )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])

    data = show_instance(name, call='action')
    node = server.one.vm.action(auth, 'delete', int(data['id']))

    salt.utils.cloud.fire_event(
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        {'name': name},
    )

    if __opts__.get('update_cachedir', False) is True:
        salt.utils.cloud.delete_minion_cachedir(
            name,
            __active_provider_name__.split(':')[0],
            __opts__
        )

    data = {
        'action': 'vm.delete',
        'deleted': node[0],
        'node_id': node[1],
        'error_code': node[2]
    }

    return data


def script(vm_):
    '''
    Return the script deployment object.

    vm_
        The VM for which to deploy a script.
    '''
    deploy_script = salt.utils.cloud.os_script(
        config.get_cloud_config_value('script', vm_, __opts__),
        vm_,
        __opts__,
        salt.utils.cloud.salt_config_to_yaml(
            salt.utils.cloud.minion_config(__opts__, vm_)
        )
    )
    return deploy_script


def show_instance(name, call=None):
    '''
    Show the details from OpenNebula concerning a named VM.

    name
        The name of the VM for which to display details.

    call
        Type of call to use with this function such as ``function``.

    CLI Example:

    .. code-block:: bash

        salt-cloud --action show_instance vm_name
        salt-cloud -a show_instance vm_name

    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

    node = _get_node(name)
    salt.utils.cloud.cache_node(node, __active_provider_name__, __opts__)

    return node


# Helper Functions

def _get_node(name):
    '''
    Helper function that returns all information about a named node.

    name
        The name of the node for which to get information.
    '''
    attempts = 10

    while attempts >= 0:
        try:
            return list_nodes_full()[name]
        except KeyError:
            attempts -= 1
            log.debug(
                'Failed to get the data for the node {0!r}. Remaining '
                'attempts {1}'.format(
                    name, attempts
                )
            )

            # Just a little delay between attempts...
            time.sleep(0.5)

    return {}


def _get_xml_rpc():
    '''
    Uses the OpenNebula cloud provider configurations to connect to the
    OpenNebula API.

    Returns the server connection created as well as the user and password
    values from the cloud provider config file used to make the connection.
    '''
    vm_ = get_configured_provider()

    xml_rpc = config.get_cloud_config_value(
        'xml_rpc', vm_, __opts__, search_global=False
    )

    user = config.get_cloud_config_value(
        'user', vm_, __opts__, search_global=False
    )

    password = config.get_cloud_config_value(
        'password', vm_, __opts__, search_global=False
    )

    server = salt.ext.six.moves.xmlrpc_client.ServerProxy(xml_rpc)

    return server, user, password


def _list_nodes(full=False):
    '''
    Helper function for the list_* query functions - Constructs the
    appropriate dictionaries to return from the API query.

    full
        If performing a full query, such as in list_nodes_full, change
        this parameter to ``True``.
    '''
    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])

    vm_pool = server.one.vmpool.info(auth, -1, -1, -1, -1)[1]

    vms = {}
    for vm in etree.XML(vm_pool):
        name = vm.find('NAME').text
        vms[name] = {}

        cpu_size = vm.find('TEMPLATE').find('CPU').text
        memory_size = vm.find('TEMPLATE').find('MEMORY').text

        private_ips = []
        for nic in vm.find('TEMPLATE').findall('NIC'):
            private_ips.append(nic.find('IP').text)

        vms[name]['id'] = vm.find('ID').text
        vms[name]['image'] = vm.find('TEMPLATE').find('TEMPLATE_ID').text
        vms[name]['name'] = name
        vms[name]['size'] = {'cpu': cpu_size, 'memory': memory_size}
        vms[name]['state'] = vm.find('STATE').text
        vms[name]['private_ips'] = private_ips
        vms[name]['public_ips'] = []

        if full:
            vms[vm.find('NAME').text] = _xml_to_dict(vm)

    return vms


def _xml_to_dict(xml):
    '''
    Helper function to covert xml into a data dictionary.

    xml
        The xml data to convert.
    '''
    dicts = {}
    for item in xml:
        key = item.tag.lower()
        idx = 1
        while key in dicts:
            key += str(idx)
            idx += 1
        if item.text is None:
            dicts[key] = _xml_to_dict(item)
        else:
            dicts[key] = item.text

    return dicts
