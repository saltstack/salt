# -*- coding: utf-8 -*-
'''
OpenNebula Cloud Module
==========================

The OpenNebula cloud module is used to control access to an OpenNebula
cloud.

:depends: lxml

Use of this module requires the ``xml_rpc``, ``user`` and
``password`` parameter to be set. Set up the cloud configuration
at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/opennebula.conf``:

.. code-block:: yaml

    my-opennebula-config:
      xml_rpc: http://localhost:2633/RPC2
      user: oneadmin
      password: JHGhgsayu32jsa
      provider: opennebula

'''
from __future__ import absolute_import

# Import python libs
import os
import copy
import time
import pprint
import logging

# Import salt cloud libs
import salt.utils.cloud
import salt.config as config
from salt.exceptions import (
    SaltCloudConfigError,
    SaltCloudNotFound,
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout
)

# Attempt to import xmlrpclib and lxml
try:
    import salt.ext.six.moves.xmlrpc_client  # pylint: disable=E0611
    from lxml import etree
    HAS_XMLLIBS = True
except ImportError:
    HAS_XMLLIBS = False

# Get logging started
log = logging.getLogger(__name__)


# Helper functions
def _xmltodict(xml):
    dicts = {}
    for item in xml:
        key = item.tag.lower()
        idx = 1
        while key in dicts:
            key = key + str(idx)
            idx += 1
        if item.text is None:
            dicts[key] = _xmltodict(item)
        else:
            dicts[key] = item.text

    return dicts


def _get_xml_rpc():
    xml_rpc = config.get_cloud_config_value(
        'xml_rpc', get_configured_provider(), __opts__
    )
    user = config.get_cloud_config_value(
        'user', get_configured_provider(), __opts__
    )
    password = config.get_cloud_config_value(
        'password', get_configured_provider(), __opts__
    )
    server = salt.ext.six.moves.xmlrpc_client.ServerProxy(xml_rpc)

    return server, user, password


# Only load in this module if the OpenNebula configurations are in place
def __virtual__():
    '''
    Check for OpenNebula configurations
    '''
    if not HAS_XMLLIBS:
        return False

    if get_configured_provider() is False:
        return False

    return True


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'opennebula',
        ('xml_rpc', 'user', 'password')
    )


def avail_locations(call=None):
    '''
    Return a dict of all available VM locations on the cloud provider with
    relevant data
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_locations function must be called with '
            '-f or --function, or with the --list-locations option'
        )

    server, user, password = _get_xml_rpc()
    hostpool = server.one.hostpool.info(user+':'+password)[1]

    locations = {}
    for host in etree.XML(hostpool):
        locations[host.find('NAME').text] = _xmltodict(host)

    return locations


def avail_images(call=None):
    '''
    Return a list of the templates that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    server, user, password = _get_xml_rpc()
    templatepool = server.one.templatepool.info(user+':'+password, -1, -1, -1)[1]

    templates = {}
    for template in etree.XML(templatepool):
        templates[template.find('NAME').text] = _xmltodict(template)

    return templates


def avail_sizes(call=None):
    '''
    Because sizes are built into templates with OpenNebula, there will be no sizes to
    return here
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-sizes option'
        )

    return {}


def list_nodes(call=None):
    '''
    Return a list of the VMs that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    server, user, password = _get_xml_rpc()
    vmpool = server.one.vmpool.info(user+':'+password, -1, -1, -1, -1)[1]

    vms = {}
    for vm in etree.XML(vmpool):
        vms[vm.find('NAME').text] = {}
        vms[vm.find('NAME').text]['id'] = vm.find('ID').text
        image = 'template_id {0}'.format(
            vm.find('TEMPLATE').find('TEMPLATE_ID').text
        )
        vms[vm.find('NAME').text]['image'] = image
        size = 'cpu {0}, memory {1}'.format(
            vm.find('TEMPLATE').find('CPU').text, vm.find('TEMPLATE').find('MEMORY').text
        )
        vms[vm.find('NAME').text]['size'] = size
        vms[vm.find('NAME').text]['state'] = vm.find('STATE').text
        private_ips = []
        for nic in vm.find('TEMPLATE').findall('NIC'):
            private_ips.append(nic.find('IP').text)
        vms[vm.find('NAME').text]['private_ips'] = private_ips
        vms[vm.find('NAME').text]['public_ips'] = []

    return vms


def list_nodes_full(call=None):
    '''
    Return a list of the VMs that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    server, user, password = _get_xml_rpc()
    vmpool = server.one.vmpool.info(user+':'+password, -1, -1, -1, -1)[1]

    vms = {}
    for vm in etree.XML(vmpool):
        vms[vm.find('NAME').text] = _xmltodict(vm)
        vms[vm.find('NAME').text]['id'] = vm.find('ID').text
        image = 'template_id {0}'.format(
            vm.find('TEMPLATE').find('TEMPLATE_ID').text
        )
        vms[vm.find('NAME').text]['image'] = image
        size = 'cpu {0}, memory {1}'.format(
            vm.find('TEMPLATE').find('CPU').text, vm.find('TEMPLATE').find('MEMORY').text
        )
        vms[vm.find('NAME').text]['size'] = size
        vms[vm.find('NAME').text]['state'] = vm.find('STATE').text
        private_ips = []
        for nic in vm.find('TEMPLATE').findall('NIC'):
            private_ips.append(nic.find('IP').text)
        vms[vm.find('NAME').text]['private_ips'] = private_ips
        vms[vm.find('NAME').text]['public_ips'] = []

    return vms


def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full('function'), __opts__['query.selection'], call,
    )


def get_image(vm_):
    '''
    Return the image object to use
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
    Return the VM's location
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
            'provider': vm_['provider'],
        },
    )

    return ret


def script(vm_):
    '''
    Return the script deployment object
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
    Show the details from OpenNebula concerning a VM
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )
    node = _get_node(name)
    salt.utils.cloud.cache_node(node, __active_provider_name__, __opts__)
    return node


def _get_node(name):
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


def destroy(name, call=None):
    '''
    Destroy a node. Will check termination protection and warn if enabled.

    CLI Example:

    .. code-block:: bash

        salt-cloud --destroy mymachine
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

    data = show_instance(name, call='action')
    node = server.one.vm.action(user+':'+password, 'delete', int(data['id']))[1]

    salt.utils.cloud.fire_event(
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        {'name': name},
    )

    if __opts__.get('update_cachedir', False) is True:
        salt.utils.cloud.delete_minion_cachedir(name, __active_provider_name__.split(':')[0], __opts__)

    return node
