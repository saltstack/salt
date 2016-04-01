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
      driver: opennebula

'''
from __future__ import absolute_import

# Import python libs
import os
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

__virtualname__ = 'opennebula'


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
    if get_configured_provider() is False:
        return False

    if get_dependencies() is False:
        return False

    return __virtualname__


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ('xml_rpc', 'user', 'password')
    )


def get_dependencies():
    '''
    Warn if dependencies aren't met.
    '''
    return config.check_driver_dependencies(
        __virtualname__,
        {'lmxl': HAS_XMLLIBS}
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
            try:
                private_ips.append(nic.find('IP').text)
            except AttributeError:
                # There is no private IP; skip it
                pass
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
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or 'opennebula',
                                                           vm_['profile'],
                                                           vm_=vm_) is False:
            return False
    except AttributeError:
        pass

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
    )

    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    kwargs = {
        'name': vm_['name'],
        'image_id': get_image(vm_),
        'region_id': get_location(vm_),
    }

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
        auth = ':'.join([user, password])
        server.one.template.instantiate(auth,
                                        int(kwargs['image_id']),
                                        kwargs['name'],
                                        False,
                                        region)
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
        node_data = show_instance(vm_name, call='action')
        if not node_data:
            # Trigger an error in the wait_for_ip function
            return False
        if node_data['state'] == '7':
            return False
        if node_data['lcm_state'] == '3':
            return node_data

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

    key_filename = config.get_cloud_config_value(
        'private_key', vm_, __opts__, search_global=False, default=None
    )
    if key_filename is not None and not os.path.isfile(key_filename):
        raise SaltCloudConfigError(
            'The defined key_filename {0!r} does not exist'.format(
                key_filename
            )
        )

    try:
        private_ip = data['private_ips'][0]
    except KeyError:
        private_ip = data['template']['nic']['ip']

    ssh_username = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__, default='root'
    )

    vm_['username'] = ssh_username
    vm_['key_filename'] = key_filename
    vm_['ssh_host'] = private_ip

    ret = salt.utils.cloud.bootstrap(vm_, __opts__)

    ret['id'] = data['id']
    ret['image'] = vm_['image']
    ret['name'] = vm_['name']
    ret['size'] = data['template']['memory']
    ret['state'] = data['state']
    ret['private_ips'] = private_ip
    ret['public_ips'] = []

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
