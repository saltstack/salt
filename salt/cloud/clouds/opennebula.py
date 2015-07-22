# -*- coding: utf-8 -*-
'''
OpenNebula Cloud Module
=======================

The OpenNebula cloud module is used to control access to an OpenNebula cloud.

.. versionadded:: 2014.7.0

:depends: lxml

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
from salt.utils import is_true

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


def get_image_id(kwargs=None, call=None):
    '''
    Returns an image's ID from the given image name.

    .. versionadded:: Boron

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_image_id opennebula name=my-image-name
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The get_image_id function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    if name is None:
        raise SaltCloudSystemExit(
            'The get_image_id function requires a name.'
        )

    return _list_images()[name]['id']


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


def get_secgroup_id(kwargs=None, call=None):
    '''
    Returns a security group's ID from the given security group name.

    .. versionadded:: Boron

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_secgroup_id opennebula name=my-secgroup-name
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The get_secgroup_id function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)

    return _list_security_groups()[name]['id']


def get_template_id(kwargs=None, call=None):
    '''
    Returns a template's ID from the given template name.

    .. versionadded:: Boron

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_template_id opennebula name=my-template-name
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)

    if name is None:
        raise SaltCloudSystemExit(
            'The get_template_id function requires a name.'
        )

    return _get_template(name)['id']


def create(vm_):
    '''
    Create a single VM from a data dict.

    vm_
        The name of the VM to create.

    CLI Example:

    .. code-block:: bash

        salt-cloud -p my-opennebula-profile vm_name

    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if config.is_profile_configured(__opts__,
                                        __active_provider_name__ or 'opennebula',
                                        vm_['profile']) is False:
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
        transport=__opts__['transport']
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


def image_clone(call=None, kwargs=None):
    '''
    Clones an existing image.

    .. versionadded:: Boron

    name
        The name of the new image.

    image_id
        The ID of the image to be cloned.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f image_clone opennebula name=my-new-image image_id=10

    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The image_clone function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    image_id = kwargs.get('image_id', None)

    if not name or not image_id:
        raise SaltCloudSystemExit(
            'The image_clone function requires a name and an image_id '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])

    response = server.one.image.clone(auth, int(image_id), name)

    data = {
        'action': 'image.clone',
        'cloned': response[0],
        'cloned_image_id': response[1],
        'cloned_image_name': name,
        'error_code': response[2],
    }

    return data


def image_delete(call=None, kwargs=None):
    '''
    Deletes the given image from OpenNebula. Either a name or an image_id must
    be supplied.

    .. versionadded:: Boron

    name
        The name of the image to delete.

    image_id
        The ID of the image to delete.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f image_delete opennebula name=my-image
        salt-cloud --function image_delete opennebula image_id=100
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The image_delete function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    image_id = kwargs.get('image_id', None)

    if not name and not image_id:
        raise SaltCloudSystemExit(
            'The image_delete function requires a name or an image_id '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])

    if name and not image_id:
        image_id = get_image_id(kwargs={'name': name})

    response = server.one.image.delete(auth, int(image_id))

    data = {
        'action': 'image.delete',
        'deleted': response[0],
        'image_id': response[1],
        'error_code': response[2],
    }

    return data


def image_info(call=None, kwargs=None):
    '''
    Retrieves information for a given image. Either a name or an image_id must be
    supplied.

    .. versionadded:: Boron

    name
        The name of the image for which to gather information.

    template_id
        The ID of the image for which to gather information.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f image_info opennebula name=my-image
        salt-cloud --function image_info opennebula image_id=5
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The image_info function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    image_id = kwargs.get('image_id', None)

    if not name and not image_id:
        raise SaltCloudSystemExit(
            'The image_info function requires either a name or an image_id '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])

    if name and not image_id:
        image_id = get_image_id(kwargs={'name': name})

    info = {}
    response = server.one.image.info(auth, int(image_id))[1]
    tree = etree.XML(response)
    info[tree.find('NAME').text] = _xml_to_dict(tree)

    return info


def image_persistent(call=None, kwargs=None):
    '''
    Sets the Image as persistent or not persistent.

    .. versionadded:: Boron

    name
        The name of the image to set.

    persist
        A boolean value to set the image as persistent or not. Set to true
        for persistent, false for non-persisent.

    template_id
        The ID of the image to set.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f image_persistent opennebula name=my-image
        salt-cloud --function image_persistent opennebula image_id=5
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The image_persistent function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    persist = kwargs.get('persist', None)
    image_id = kwargs.get('image_id', None)

    if not name and not image_id:
        raise SaltCloudSystemExit(
            'The image_persistent function requires either a name or an image_id '
            'to be provided.'
        )

    if not persist:
        raise SaltCloudSystemExit(
            'The image_persistent function requires \'persist\' to be set to \'True\' '
            'or \'False\'.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])

    if name and not image_id:
        image_id = get_image_id(kwargs={'name': name})

    response = server.one.image.persistent(auth, int(image_id), is_true(persist))

    data = {
        'action': 'image.persistent',
        'response': response[0],
        'image_id': response[1],
        'error_code': response[2],
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


def secgroup_clone(call=None, kwargs=None):
    '''
    Clones an existing security group.

    .. versionadded:: Boron

    name
        The name of the new template.

    secgroup_id
        The ID of the template to be cloned.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f secgroup_clone opennebula name=my-cloned-secgroup secgroup_id=0

    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The secgroup_clone function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    secgroup_id = kwargs.get('secgroup_id', None)

    if not name or not secgroup_id:
        raise SaltCloudSystemExit(
            'The secgroup_clone function requires a name and a secgroup_id '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])

    response = server.one.secgroup.clone(auth, int(secgroup_id), name)

    data = {
        'action': 'secgroup.clone',
        'cloned': response[0],
        'cloned_secgroup_id': response[1],
        'cloned_secgroup_name': name,
        'error_code': response[2],
    }

    return data


def secgroup_delete(call=None, kwargs=None):
    '''
    Deletes the given security group from OpenNebula. Either a name or a secgroup_id
    must be supplied.

    .. versionadded:: Boron

    name
        The name of the security group to delete.

    secgroup_id
        The ID of the security group to delete.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f secgroup_delete opennebula name=my-secgroup
        salt-cloud --function secgroup_delete opennebula secgroup_id=100
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The secgroup_delete function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    secgroup_id = kwargs.get('secgroup_id', None)

    if not name and not secgroup_id:
        raise SaltCloudSystemExit(
            'The secgroup_delete function requires either a name or a secgroup_id '
            'to be provided.'
        )

    # Make the API call to O.N. once and pass them to other functions that need them.
    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])

    if name and not secgroup_id:
        secgroup_id = get_secgroup_id(kwargs={'name': name})

    response = server.one.secgroup.delete(auth, int(secgroup_id))

    data = {
        'action': 'secgroup.delete',
        'deleted': response[0],
        'secgroup_id': response[1],
        'error_code': response[2],
    }

    return data


def secgroup_info(call=None, kwargs=None):
    '''
    Retrieves information for the given security group. Either a name or a
    secgroup_id must be supplied.

    name
        The name of the security group for which to gather information.

    template_id
        The ID of the security group for which to gather information.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f secgroup_info opennebula name=my-secgroup
        salt-cloud --function secgroup_info opennebula secgroup_id=5
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The secgroup_info function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    secgroup_id = kwargs.get('secgroup_id', None)

    if not name and not secgroup_id:
        raise SaltCloudSystemExit(
            'The secgroup_info function requires either a name or a secgroup_id '
            'to be provided.'
        )

    # Make the API call to O.N. once and pass them to other functions that need them.
    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])

    if name and not secgroup_id:
        secgroup_id = get_secgroup_id(kwargs={'name': name})

    info = {}
    response = server.one.secgroup.info(auth, int(secgroup_id))[1]
    tree = etree.XML(response)
    info[tree.find('NAME').text] = _xml_to_dict(tree)

    return info


def template_clone(call=None, kwargs=None):
    '''
    Clones an existing virtual machine template.

    .. versionadded:: Boron

    name
        The name of the new template.

    template_id
        The ID of the template to be cloned.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f template_clone opennebula name=my-cloned-template template_id=0

    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The template_clone function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    template_id = kwargs.get('template_id', None)

    if not name or not template_id:
        raise SaltCloudSystemExit(
            'The template_clone function requires a name and a template_id '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])

    response = server.one.template.clone(auth, int(template_id), name)

    data = {
        'action': 'template.clone',
        'cloned': response[0],
        'cloned_template_id': response[1],
        'cloned_template_name': name,
        'error_code': response[2],
    }

    return data


def template_delete(call=None, kwargs=None):
    '''
    Deletes the given template from OpenNebula. Either a name or a template_id must
    be supplied.

    .. versionadded:: Boron

    name
        The name of the template to delete.

    template_id
        The ID of the template to delete.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f template_delete opennebula name=my-template
        salt-cloud --function template_delete opennebula template_id=5
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The template_delete function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    template_id = kwargs.get('template_id', None)

    if not name and not template_id:
        raise SaltCloudSystemExit(
            'The template_delete function requires either a name or a template_id '
            'to be provided.'
        )

    # Make the API call to O.N. once and pass them to other functions that need them.
    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])

    if template_id and name:
        _check_name_id_collisions(name,
                                  template_id,
                                  server=server,
                                  user=user,
                                  password=password)

    if name and not template_id:
        template_id = get_template_id(kwargs={'name': name})

    response = server.one.template.delete(auth, int(template_id))

    data = {
        'action': 'template.delete',
        'deleted': response[0],
        'template_id': response[1],
        'error_code': response[2],
    }

    return data


def template_instantiate(call=None, kwargs=None):
    '''
    Instantiates a new virtual machine from a template.

    .. versionadded:: Boron

    .. note::
        ``template_instantiate`` creates a VM on OpenNebula from a template, but it
        does not install Salt on the new VM. Use the ``create`` function for that
        functionality: ``salt-cloud -p opennebula-profile vm-name``.

    vm_name
        Name for the new VM instance.

    template_id
        The ID of the template from which the VM will be created.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f template_instantiate opennebula vm_name=my-new-vm template_id=0

    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The template_instantiate function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    vm_name = kwargs.get('vm_name', None)
    template_id = kwargs.get('template_id', None)

    if not vm_name or not template_id:
        raise SaltCloudSystemExit(
            'The template_instantiate function requires a vm_name and a template_id '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])

    response = server.one.template.instantiate(auth, int(template_id), vm_name)

    data = {
        'action': 'template.instantiate',
        'instantiated': response[0],
        'instantiated_vm_id': response[1],
        'vm_name': vm_name,
        'error_code': response[2],
    }

    return data


# Helper Functions

def _check_name_id_collisions(name, id_, server=None, user=None, password=None):
    '''
    Helper function that ensures that a provided name and provided id match.
    '''
    name_id = _get_template(name,
                            server=server,
                            user=user,
                            password=password)['id']
    if name_id != id_:
        raise SaltCloudException(
            'A name and an ID were provided, but the provided id, \'{0}\', does '
            'not match the ID found for the provided name: \'{1}\': \'{2}\'. '
            'Nothing was done.'.format(
                id_,
                name,
                name_id
            )
        )


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


def _get_template(name, server=None, user=None, password=None):
    '''
    Helper function returning all information about a named template.

    name
        The name of the template for which to obtain information.
    '''
    attempts = 10

    while attempts >= 0:
        try:
            return _list_templates(
                server=server,
                user=user,
                password=password)[name]
        except KeyError:
            attempts -= 1
            log.debug(
                'Failed to get the data for the template {0!r}. Remaining '
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


def _list_images(server=None, user=None, password=None):
    '''
    Lists all images available to the user and the user's groups.
    '''
    if not server or not user or not password:
        server, user, password = _get_xml_rpc()

    auth = ':'.join([user, password])
    image_pool = server.one.imagepool.info(auth, -1, -1, -1)[1]

    images = {}
    for image in etree.XML(image_pool):
        images[image.find('NAME').text] = _xml_to_dict(image)

    return images


def _list_security_groups(server=None, user=None, password=None):
    '''
    Lists all security groups available to the user and the user's groups.
    '''
    if not server or not user or not password:
        server, user, password = _get_xml_rpc()

    auth = ':'.join([user, password])
    secgroup_pool = server.one.secgrouppool.info(auth, -1, -1, -1)[1]

    groups = {}
    for group in etree.XML(secgroup_pool):
        groups[group.find('NAME').text] = _xml_to_dict(group)

    return groups


def _list_templates(server=None, user=None, password=None):
    '''
    Lists all templates available to the user and the user's groups.
    '''
    if not server or not user or not password:
        server, user, password = _get_xml_rpc()

    auth = ':'.join([user, password])
    template_pool = server.one.templatepool.info(auth, -1, -1, -1)[1]

    templates = {}
    for template in etree.XML(template_pool):
        templates[template.find('NAME').text] = _xml_to_dict(template)

    return templates


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
