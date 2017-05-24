# -*- coding: utf-8 -*-
'''
OpenNebula Cloud Module
=======================

The OpenNebula cloud module is used to control access to an OpenNebula cloud.

.. versionadded:: 2014.7.0

:depends: lxml
:depends: OpenNebula installation running version ``4.14`` or later.

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

This driver supports accessing new VM instances via DNS entry instead
of IP address.  To enable this feature, in the provider or profile file
add `fqdn_base` with a value matching the base of your fully-qualified
domain name.  Example:

.. code-block:: yaml

    my-opennebula-config:
      [...]
      fqdn_base: <my.basedomain.com>
      [...]

The driver will prepend the hostname to the fqdn_base and do a DNS lookup
to find the IP of the new VM.

.. note:

    Whenever ``data`` is provided as a kwarg to a function and the
    attribute=value syntax is used, the entire ``data`` value must be
    wrapped in single or double quotes. If the value given in the
    attribute=value data string contains multiple words, double quotes
    *must* be used for the value while the entire data string should
    be encapsulated in single quotes. Failing to do so will result in
    an error. Example:

.. code-block:: bash

    salt-cloud -f image_allocate opennebula datastore_name=default \\
        data='NAME="My New Image" DESCRIPTION="Description of the image." \\
        PATH=/home/one_user/images/image_name.img'
    salt-cloud -f secgroup_allocate opennebula \\
        data="Name = test RULE = [PROTOCOL = TCP, RULE_TYPE = inbound, \\
        RANGE = 1000:2000]"

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
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout,
    SaltCloudNotFound,
    SaltCloudSystemExit
)
import salt.utils

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
        {'lmxl': HAS_XML_LIBS}
    )


def avail_images(call=None):
    '''
    Return available OpenNebula images.

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

    image_pool = server.one.imagepool.info(auth, -2, -1, -1)[1]

    images = {}
    for image in _get_xml(image_pool):
        images[image.find('NAME').text] = _xml_to_dict(image)

    return images


def avail_locations(call=None):
    '''
    Return available OpenNebula locations.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-locations opennebula
        salt-cloud --function avail_locations opennebula
        salt-cloud -f avail_locations opennebula

    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_locations function must be called with '
            '-f or --function, or with the --list-locations option.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    host_pool = server.one.hostpool.info(auth)[1]

    locations = {}
    for host in _get_xml(host_pool):
        locations[host.find('NAME').text] = _xml_to_dict(host)

    return locations


def avail_sizes(call=None):
    '''
    Because sizes are built into templates with OpenNebula, there will be no sizes to
    return here.
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-sizes option.'
        )

    log.warning(
        'Because sizes are built into templates with OpenNebula, there are no sizes '
        'to return.'
    )

    return {}


def list_clusters(call=None):
    '''
    Returns a list of clusters in OpenNebula.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_clusters opennebula
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_clusters function must be called with -f or --function.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    cluster_pool = server.one.clusterpool.info(auth)[1]

    clusters = {}
    for cluster in _get_xml(cluster_pool):
        clusters[cluster.find('NAME').text] = _xml_to_dict(cluster)

    return clusters


def list_datastores(call=None):
    '''
    Returns a list of data stores on OpenNebula.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_datastores opennebula
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_datastores function must be called with -f or --function.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    datastore_pool = server.one.datastorepool.info(auth)[1]

    datastores = {}
    for datastore in _get_xml(datastore_pool):
        datastores[datastore.find('NAME').text] = _xml_to_dict(datastore)

    return datastores


def list_hosts(call=None):
    '''
    Returns a list of hosts on OpenNebula.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_hosts opennebula
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_hosts function must be called with -f or --function.'
        )

    return avail_locations()


def list_nodes(call=None):
    '''
    Return a list of VMs on OpenNebula.

    CLI Example:

    .. code-block:: bash

        salt-cloud -Q
        salt-cloud --query
        salt-cloud --function list_nodes opennebula
        salt-cloud -f list_nodes opennebula

    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    return _list_nodes(full=False)


def list_nodes_full(call=None):
    '''
    Return a list of the VMs on OpenNebula.

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
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    return __utils__['cloud.list_nodes_select'](
        list_nodes_full('function'), __opts__['query.selection'], call,
    )


def list_security_groups(call=None):
    '''
    Lists all security groups available to the user and the user's groups.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_security_groups opennebula
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_security_groups function must be called with -f or --function.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    secgroup_pool = server.one.secgrouppool.info(auth, -2, -1, -1)[1]

    groups = {}
    for group in _get_xml(secgroup_pool):
        groups[group.find('NAME').text] = _xml_to_dict(group)

    return groups


def list_templates(call=None):
    '''
    Lists all templates available to the user and the user's groups.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_templates opennebula
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_templates function must be called with -f or --function.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    template_pool = server.one.templatepool.info(auth, -2, -1, -1)[1]

    templates = {}
    for template in _get_xml(template_pool):
        templates[template.find('NAME').text] = _xml_to_dict(template)

    return templates


def list_vns(call=None):
    '''
    Lists all virtual networks available to the user and the user's groups.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_vns opennebula
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_vns function must be called with -f or --function.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vn_pool = server.one.vnpool.info(auth, -2, -1, -1)[1]

    vns = {}
    for v_network in _get_xml(vn_pool):
        vns[v_network.find('NAME').text] = _xml_to_dict(v_network)

    return vns


def reboot(name, call=None):
    '''
    Reboot a VM.

    .. versionadded:: 2016.3.0

    name
        The name of the VM to reboot.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reboot my-vm
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The start action must be called with -a or --action.'
        )

    log.info('Rebooting node {0}'.format(name))

    return vm_action(name, kwargs={'action': 'reboot'}, call=call)


def start(name, call=None):
    '''
    Start a VM.

    .. versionadded:: 2016.3.0

    name
        The name of the VM to start.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a start my-vm
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The start action must be called with -a or --action.'
        )

    log.info('Starting node {0}'.format(name))

    return vm_action(name, kwargs={'action': 'resume'}, call=call)


def stop(name, call=None):
    '''
    Stop a VM.

    .. versionadded:: 2016.3.0

    name
        The name of the VM to stop.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop my-vm
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The start action must be called with -a or --action.'
        )

    log.info('Stopping node {0}'.format(name))

    return vm_action(name, kwargs={'action': 'stop'}, call=call)


def get_one_version(kwargs=None, call=None):
    '''
    Returns the OpenNebula version.

    .. versionadded:: 2016.3.5

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_one_version one_provider_name
    '''

    if call == 'action':
        raise SaltCloudSystemExit(
            'The get_cluster_id function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])

    return server.one.system.version(auth)[1]


def get_cluster_id(kwargs=None, call=None):
    '''
    Returns a cluster's ID from the given cluster name.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_cluster_id opennebula name=my-cluster-name
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The get_cluster_id function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    if name is None:
        raise SaltCloudSystemExit(
            'The get_cluster_id function requires a name.'
        )

    try:
        ret = list_clusters()[name]['id']
    except KeyError:
        raise SaltCloudSystemExit(
            'The cluster \'{0}\' could not be found'.format(name)
        )

    return ret


def get_datastore_id(kwargs=None, call=None):
    '''
    Returns a data store's ID from the given data store name.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_datastore_id opennebula name=my-datastore-name
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The get_datastore_id function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    if name is None:
        raise SaltCloudSystemExit(
            'The get_datastore_id function requires a name.'
        )

    try:
        ret = list_datastores()[name]['id']
    except KeyError:
        raise SaltCloudSystemExit(
            'The datastore \'{0}\' could not be found.'.format(name)
        )

    return ret


def get_host_id(kwargs=None, call=None):
    '''
    Returns a host's ID from the given host name.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_host_id opennebula name=my-host-name
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The get_host_id function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    if name is None:
        raise SaltCloudSystemExit(
            'The get_host_id function requires a name.'
        )

    try:
        ret = avail_locations()[name]['id']
    except KeyError:
        raise SaltCloudSystemExit(
            'The host \'{0}\' could not be found'.format(name)
        )

    return ret


def get_image(vm_):
    r'''
    Return the image object to use.

    vm\_
        The VM dictionary for which to obtain an image.
    '''
    images = avail_images()
    vm_image = str(config.get_cloud_config_value(
        'image', vm_, __opts__, search_global=False
    ))
    for image in images:
        if vm_image in (images[image]['name'], images[image]['id']):
            return images[image]['id']
    raise SaltCloudNotFound(
        'The specified image, \'{0}\', could not be found.'.format(vm_image)
    )


def get_image_id(kwargs=None, call=None):
    '''
    Returns an image's ID from the given image name.

    .. versionadded:: 2016.3.0

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

    try:
        ret = avail_images()[name]['id']
    except KeyError:
        raise SaltCloudSystemExit(
            'The image \'{0}\' could not be found'.format(name)
        )

    return ret


def get_location(vm_):
    r'''
    Return the VM's location.

    vm\_
        The VM dictionary for which to obtain a location.
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
        'The specified location, \'{0}\', could not be found.'.format(
            vm_location
        )
    )


def get_secgroup_id(kwargs=None, call=None):
    '''
    Returns a security group's ID from the given security group name.

    .. versionadded:: 2016.3.0

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
    if name is None:
        raise SaltCloudSystemExit(
            'The get_secgroup_id function requires a \'name\'.'
        )

    try:
        ret = list_security_groups()[name]['id']
    except KeyError:
        raise SaltCloudSystemExit(
            'The security group \'{0}\' could not be found.'.format(name)
        )

    return ret


def get_template_image(kwargs=None, call=None):
    '''
    Returns a template's image from the given template name.

    .. versionadded:: oxygen

    .. code-block:: bash

        salt-cloud -f get_template_image opennebula name=my-template-name
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The get_template_image function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    if name is None:
        raise SaltCloudSystemExit(
            'The get_template_image function requires a \'name\'.'
        )

    try:
        ret = list_templates()[name]['template']['disk']['image']
    except KeyError:
        raise SaltCloudSystemExit(
            'The image for template \'{1}\' could not be found.'.format(name)
        )

    return ret


def get_template_id(kwargs=None, call=None):
    '''
    Returns a template's ID from the given template name.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_template_id opennebula name=my-template-name
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The get_template_id function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    if name is None:
        raise SaltCloudSystemExit(
            'The get_template_id function requires a \'name\'.'
        )

    try:
        ret = list_templates()[name]['id']
    except KeyError:
        raise SaltCloudSystemExit(
            'The template \'{0}\' could not be found.'.format(name)
        )

    return ret


def get_template(vm_):
    r'''
    Return the template id for a VM.

    .. versionadded:: 2016.11.0

    vm\_
        The VM dictionary for which to obtain a template.
    '''

    vm_template = str(config.get_cloud_config_value(
        'template', vm_, __opts__, search_global=False
    ))
    try:
        return list_templates()[vm_template]['id']
    except KeyError:
        raise SaltCloudNotFound(
            'The specified template, \'{0}\', could not be found.'.format(vm_template)
        )


def get_vm_id(kwargs=None, call=None):
    '''
    Returns a virtual machine's ID from the given virtual machine's name.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_vm_id opennebula name=my-vm
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The get_vm_id function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    if name is None:
        raise SaltCloudSystemExit(
            'The get_vm_id function requires a name.'
        )

    try:
        ret = list_nodes()[name]['id']
    except KeyError:
        raise SaltCloudSystemExit(
            'The VM \'{0}\' could not be found.'.format(name)
        )

    return ret


def get_vn_id(kwargs=None, call=None):
    '''
    Returns a virtual network's ID from the given virtual network's name.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_vn_id opennebula name=my-vn-name
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The get_vn_id function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    if name is None:
        raise SaltCloudSystemExit(
            'The get_vn_id function requires a name.'
        )

    try:
        ret = list_vns()[name]['id']
    except KeyError:
        raise SaltCloudSystemExit(
            'The VN \'{0}\' could not be found.'.format(name)
        )

    return ret


def _get_device_template(disk, disk_info, template=None):
    '''
    Returns the template format to create a disk in open nebula

    .. versionadded:: oxygen

    '''
    def _require_disk_opts(*args):
        for arg in args:
            if arg not in disk_info:
                raise SaltCloudSystemExit(
                    'The disk {0} requires a {1}\
                    argument'.format(disk, arg)
                )

    _require_disk_opts('disk_type', 'size')

    size = disk_info['size']
    disk_type = disk_info['disk_type']

    if disk_type == 'clone':
        if 'image' in disk_info:
            clone_image = disk_info['image']
        else:
            clone_image = get_template_image(kwargs={'name':
                                                    template})

        clone_image_id = get_image_id(kwargs={'name': clone_image})
        temp = 'DISK=[IMAGE={0}, IMAGE_ID={1}, CLONE=YES,\
                        SIZE={2}]'.format(clone_image, clone_image_id,
                                          size)
        return temp

    if disk_type == 'volatile':
        _require_disk_opts('type')
        v_type = disk_info['type']
        temp = 'DISK=[TYPE={0}, SIZE={1}]'.format(v_type, size)

        if v_type == 'fs':
            _require_disk_opts('format')
            format = disk_info['format']
            temp = 'DISK=[TYPE={0}, SIZE={1}, FORMAT={2}]'.format(v_type,
                                                                  size, format)
        return temp
    #TODO add persistant disk_type


def create(vm_):
    r'''
    Create a single VM from a data dict.

    vm\_
        The dictionary use to create a VM.

    Optional vm_ dict options for overwriting template:

    region_id
        Optional - OpenNebula Zone ID

    memory
        Optional - In MB

    cpu
        Optional - Percent of host CPU to allocate

    vcpu
        Optional - Amount of vCPUs to allocate

     CLI Example:

     .. code-block:: bash

         salt-cloud -p my-opennebula-profile vm_name

        salt-cloud -p my-opennebula-profile vm_name memory=16384 cpu=2.5 vcpu=16

    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or 'opennebula',
                                                           vm_['profile']) is False:
            return False
    except AttributeError:
        pass

    __utils__['cloud.fire_event'](
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        args=__utils__['cloud.filter_event']('creating', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    kwargs = {
        'name': vm_['name'],
        'template_id': get_template(vm_),
        'region_id': get_location(vm_),
    }
    if 'template' in vm_:
        kwargs['image_id'] = get_template_id({'name': vm_['template']})

    private_networking = config.get_cloud_config_value(
        'private_networking', vm_, __opts__, search_global=False, default=None
    )
    kwargs['private_networking'] = 'true' if private_networking else 'false'

    __utils__['cloud.fire_event'](
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        args={
            'kwargs': __utils__['cloud.filter_event']('requesting', kwargs, kwargs.keys()),
        },
        sock_dir=__opts__['sock_dir'],
    )

    template = []
    if kwargs.get('region_id'):
        template.append('SCHED_REQUIREMENTS="ID={0}"'.format(kwargs.get('region_id')))
    if vm_.get('memory'):
        template.append('MEMORY={0}'.format(vm_.get('memory')))
    if vm_.get('cpu'):
        template.append('CPU={0}'.format(vm_.get('cpu')))
    if vm_.get('vcpu'):
        template.append('VCPU={0}'.format(vm_.get('vcpu')))
    if vm_.get('disk'):
        get_disks = vm_.get('disk')
        template_name = vm_['image']
        for disk in get_disks:
            template.append(_get_device_template(disk, get_disks[disk],
                                 template=template_name))
        if 'CLONE' not in str(template):
            raise SaltCloudSystemExit(
                'Missing an image disk to clone. Must define a clone disk alongside all other disk definitions.'
            )

    template_args = "\n".join(template)

    try:
        server, user, password = _get_xml_rpc()
        auth = ':'.join([user, password])
        cret = server.one.template.instantiate(auth,
                                        int(kwargs['template_id']),
                                        kwargs['name'],
                                        False,
                                        template_args)
        if not cret[0]:
            log.error(
                'Error creating {0} on OpenNebula\n\n'
                'The following error was returned when trying to '
                'instantiate the template: {1}'.format(
                    vm_['name'],
                    cret[1]
                ),
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
            return False
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

    fqdn = vm_.get('fqdn_base')
    if fqdn is not None:
        fqdn = '{0}.{1}'.format(vm_['name'], fqdn)

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
        data = __utils__['cloud.wait_for_ip'](
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
            'The defined key_filename \'{0}\' does not exist'.format(
                key_filename
            )
        )

    if fqdn:
        vm_['ssh_host'] = fqdn
        private_ip = '0.0.0.0'
    else:
        try:
            private_ip = data['private_ips'][0]
        except KeyError:
            try:
                private_ip = data['template']['nic']['ip']
            except KeyError:
                # if IPv6 is used try this as last resort
                # OpenNebula does not yet show ULA address here so take global
                private_ip = data['template']['nic']['ip6_global']

            vm_['ssh_host'] = private_ip

    ssh_username = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__, default='root'
    )

    vm_['username'] = ssh_username
    vm_['key_filename'] = key_filename

    ret = __utils__['cloud.bootstrap'](vm_, __opts__)

    ret['id'] = data['id']
    ret['image'] = vm_['image']
    ret['name'] = vm_['name']
    ret['size'] = data['template']['memory']
    ret['state'] = data['state']
    ret['private_ips'] = private_ip
    ret['public_ips'] = []

    log.info('Created Cloud VM \'{0[name]}\''.format(vm_))
    log.debug(
        '\'{0[name]}\' VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data)
        )
    )

    __utils__['cloud.fire_event'](
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        args=__utils__['cloud.filter_event']('created', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
    )

    return ret


def destroy(name, call=None):
    '''
    Destroy a node. Will check termination protection and warn if enabled.

    name
        The name of the vm to be destroyed.

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

    __utils__['cloud.fire_event'](
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
    )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])

    data = show_instance(name, call='action')
    node = server.one.vm.action(auth, 'delete', int(data['id']))

    __utils__['cloud.fire_event'](
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
    )

    if __opts__.get('update_cachedir', False) is True:
        __utils__['cloud.delete_minion_cachedir'](
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


def image_allocate(call=None, kwargs=None):
    '''
    Allocates a new image in OpenNebula.

    .. versionadded:: 2016.3.0

    path
        The path to a file containing the template of the image to allocate.
        Syntax within the file can be the usual attribute=value or XML. Can be
        used instead of ``data``.

    data
        The data containing the template of the image to allocate. Syntax can be the
        usual attribute=value or XML. Can be used instead of ``path``.

    datastore_id
        The ID of the data-store to be used for the new image. Can be used instead
        of ``datastore_name``.

    datastore_name
        The name of the data-store to be used for the new image. Can be used instead of
        ``datastore_id``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f image_allocate opennebula path=/path/to/image_file.txt datastore_id=1
        salt-cloud -f image_allocate opennebula datastore_name=default \\
            data='NAME="Ubuntu 14.04" PATH="/home/one_user/images/ubuntu_desktop.img" \\
            DESCRIPTION="Ubuntu 14.04 for development."'
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The image_allocate function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    path = kwargs.get('path', None)
    data = kwargs.get('data', None)
    datastore_id = kwargs.get('datastore_id', None)
    datastore_name = kwargs.get('datastore_name', None)

    if datastore_id:
        if datastore_name:
            log.warning(
                'Both a \'datastore_id\' and a \'datastore_name\' were provided. '
                '\'datastore_id\' will take precedence.'
            )
    elif datastore_name:
        datastore_id = get_datastore_id(kwargs={'name': datastore_name})
    else:
        raise SaltCloudSystemExit(
            'The image_allocate function requires either a \'datastore_id\' or a '
            '\'datastore_name\' to be provided.'
        )

    if data:
        if path:
            log.warning(
                'Both the \'data\' and \'path\' arguments were provided. '
                '\'data\' will take precedence.'
            )
    elif path:
        with salt.utils.fopen(path, mode='r') as rfh:
            data = rfh.read()
    else:
        raise SaltCloudSystemExit(
            'The image_allocate function requires either a file \'path\' or \'data\' '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.image.allocate(auth, data, int(datastore_id))

    ret = {
        'action': 'image.allocate',
        'allocated': response[0],
        'image_id': response[1],
        'error_code': response[2],
    }

    return ret


def image_clone(call=None, kwargs=None):
    '''
    Clones an existing image.

    .. versionadded:: 2016.3.0

    name
        The name of the new image.

    image_id
        The ID of the image to be cloned. Can be used instead of ``image_name``.

    image_name
        The name of the image to be cloned. Can be used instead of ``image_id``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f image_clone opennebula name=my-new-image image_id=10
        salt-cloud -f image_clone opennebula name=my-new-image image_name=my-image-to-clone
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The image_clone function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    image_id = kwargs.get('image_id', None)
    image_name = kwargs.get('image_name', None)

    if name is None:
        raise SaltCloudSystemExit(
            'The image_clone function requires a \'name\' to be provided.'
        )

    if image_id:
        if image_name:
            log.warning(
                'Both the \'image_id\' and \'image_name\' arguments were provided. '
                '\'image_id\' will take precedence.'
            )
    elif image_name:
        image_id = get_image_id(kwargs={'name': image_name})
    else:
        raise SaltCloudSystemExit(
            'The image_clone function requires either an \'image_id\' or an '
            '\'image_name\' to be provided.'
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

    .. versionadded:: 2016.3.0

    name
        The name of the image to delete. Can be used instead of ``image_id``.

    image_id
        The ID of the image to delete. Can be used instead of ``name``.

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

    if image_id:
        if name:
            log.warning(
                'Both the \'image_id\' and \'name\' arguments were provided. '
                '\'image_id\' will take precedence.'
            )
    elif name:
        image_id = get_image_id(kwargs={'name': name})
    else:
        raise SaltCloudSystemExit(
            'The image_delete function requires either an \'image_id\' or a '
            '\'name\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
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

    .. versionadded:: 2016.3.0

    name
        The name of the image for which to gather information. Can be used instead
        of ``image_id``.

    image_id
        The ID of the image for which to gather information. Can be used instead of
        ``name``.

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

    if image_id:
        if name:
            log.warning(
                'Both the \'image_id\' and \'name\' arguments were provided. '
                '\'image_id\' will take precedence.'
            )
    elif name:
        image_id = get_image_id(kwargs={'name': name})
    else:
        raise SaltCloudSystemExit(
            'The image_info function requires either a \'name or an \'image_id\' '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])

    info = {}
    response = server.one.image.info(auth, int(image_id))[1]
    tree = _get_xml(response)
    info[tree.find('NAME').text] = _xml_to_dict(tree)

    return info


def image_persistent(call=None, kwargs=None):
    '''
    Sets the Image as persistent or not persistent.

    .. versionadded:: 2016.3.0

    name
        The name of the image to set. Can be used instead of ``image_id``.

    image_id
        The ID of the image to set. Can be used instead of ``name``.

    persist
        A boolean value to set the image as persistent or not. Set to true
        for persistent, false for non-persistent.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f image_persistent opennebula name=my-image persist=True
        salt-cloud --function image_persistent opennebula image_id=5 persist=False
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

    if persist is None:
        raise SaltCloudSystemExit(
            'The image_persistent function requires \'persist\' to be set to \'True\' '
            'or \'False\'.'
        )

    if image_id:
        if name:
            log.warning(
                'Both the \'image_id\' and \'name\' arguments were provided. '
                '\'image_id\' will take precedence.'
            )
    elif name:
        image_id = get_image_id(kwargs={'name': name})
    else:
        raise SaltCloudSystemExit(
            'The image_persistent function requires either a \'name\' or an '
            '\'image_id\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.image.persistent(auth, int(image_id), salt.utils.is_true(persist))

    data = {
        'action': 'image.persistent',
        'response': response[0],
        'image_id': response[1],
        'error_code': response[2],
    }

    return data


def image_snapshot_delete(call=None, kwargs=None):
    '''
    Deletes a snapshot from the image.

    .. versionadded:: 2016.3.0

    image_id
        The ID of the image from which to delete the snapshot. Can be used instead of
        ``image_name``.

    image_name
        The name of the image from which to delete the snapshot. Can be used instead
        of ``image_id``.

    snapshot_id
        The ID of the snapshot to delete.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f image_snapshot_delete vm_id=106 snapshot_id=45
        salt-cloud -f image_snapshot_delete vm_name=my-vm snapshot_id=111
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The image_snapshot_delete function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    image_id = kwargs.get('image_id', None)
    image_name = kwargs.get('image_name', None)
    snapshot_id = kwargs.get('snapshot_id', None)

    if snapshot_id is None:
        raise SaltCloudSystemExit(
            'The image_snapshot_delete function requires a \'snapshot_id\' to be provided.'
        )

    if image_id:
        if image_name:
            log.warning(
                'Both the \'image_id\' and \'image_name\' arguments were provided. '
                '\'image_id\' will take precedence.'
            )
    elif image_name:
        image_id = get_image_id(kwargs={'name': image_name})
    else:
        raise SaltCloudSystemExit(
            'The image_snapshot_delete function requires either an \'image_id\' '
            'or a \'image_name\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.image.snapshotdelete(auth, int(image_id), int(snapshot_id))

    data = {
        'action': 'image.snapshotdelete',
        'deleted': response[0],
        'snapshot_id': response[1],
        'error_code': response[2],
    }

    return data


def image_snapshot_revert(call=None, kwargs=None):
    '''
    Reverts an image state to a previous snapshot.

    .. versionadded:: 2016.3.0

    image_id
        The ID of the image to revert. Can be used instead of ``image_name``.

    image_name
        The name of the image to revert. Can be used instead of ``image_id``.

    snapshot_id
        The ID of the snapshot to which the image will be reverted.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f image_snapshot_revert vm_id=106 snapshot_id=45
        salt-cloud -f image_snapshot_revert vm_name=my-vm snapshot_id=120
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The image_snapshot_revert function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    image_id = kwargs.get('image_id', None)
    image_name = kwargs.get('image_name', None)
    snapshot_id = kwargs.get('snapshot_id', None)

    if snapshot_id is None:
        raise SaltCloudSystemExit(
            'The image_snapshot_revert function requires a \'snapshot_id\' to be provided.'
        )

    if image_id:
        if image_name:
            log.warning(
                'Both the \'image_id\' and \'image_name\' arguments were provided. '
                '\'image_id\' will take precedence.'
            )
    elif image_name:
        image_id = get_image_id(kwargs={'name': image_name})
    else:
        raise SaltCloudSystemExit(
            'The image_snapshot_revert function requires either an \'image_id\' or '
            'an \'image_name\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.image.snapshotrevert(auth, int(image_id), int(snapshot_id))

    data = {
        'action': 'image.snapshotrevert',
        'reverted': response[0],
        'snapshot_id': response[1],
        'error_code': response[2],
    }

    return data


def image_snapshot_flatten(call=None, kwargs=None):
    '''
    Flattens the snapshot of an image and discards others.

    .. versionadded:: 2016.3.0

    image_id
        The ID of the image. Can be used instead of ``image_name``.

    image_name
        The name of the image. Can be used instead of ``image_id``.

    snapshot_id
        The ID of the snapshot to flatten.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f image_snapshot_flatten vm_id=106 snapshot_id=45
        salt-cloud -f image_snapshot_flatten vm_name=my-vm snapshot_id=45
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The image_snapshot_flatten function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    image_id = kwargs.get('image_id', None)
    image_name = kwargs.get('image_name', None)
    snapshot_id = kwargs.get('snapshot_id', None)

    if snapshot_id is None:
        raise SaltCloudSystemExit(
            'The image_stanpshot_flatten function requires a \'snapshot_id\' '
            'to be provided.'
        )

    if image_id:
        if image_name:
            log.warning(
                'Both the \'image_id\' and \'image_name\' arguments were provided. '
                '\'image_id\' will take precedence.'
            )
    elif image_name:
        image_id = get_image_id(kwargs={'name': image_name})
    else:
        raise SaltCloudSystemExit(
            'The image_snapshot_flatten function requires either an '
            '\'image_id\' or an \'image_name\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.image.snapshotflatten(auth, int(image_id), int(snapshot_id))

    data = {
        'action': 'image.snapshotflatten',
        'flattened': response[0],
        'snapshot_id': response[1],
        'error_code': response[2],
    }

    return data


def image_update(call=None, kwargs=None):
    '''
    Replaces the image template contents.

    .. versionadded:: 2016.3.0

    image_id
        The ID of the image to update. Can be used instead of ``image_name``.

    image_name
        The name of the image to update. Can be used instead of ``image_id``.

    path
        The path to a file containing the template of the image. Syntax within the
        file can be the usual attribute=value or XML. Can be used instead of ``data``.

    data
        Contains the template of the image. Syntax can be the usual attribute=value
        or XML. Can be used instead of ``path``.

    update_type
        There are two ways to update an image: ``replace`` the whole template
        or ``merge`` the new template with the existing one.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f image_update opennebula image_id=0 file=/path/to/image_update_file.txt update_type=replace
        salt-cloud -f image_update opennebula image_name="Ubuntu 14.04" update_type=merge \\
            data='NAME="Ubuntu Dev" PATH="/home/one_user/images/ubuntu_desktop.img" \\
            DESCRIPTION = "Ubuntu 14.04 for development."'
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The image_allocate function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    image_id = kwargs.get('image_id', None)
    image_name = kwargs.get('image_name', None)
    path = kwargs.get('path', None)
    data = kwargs.get('data', None)
    update_type = kwargs.get('update_type', None)
    update_args = ['replace', 'merge']

    if update_type is None:
        raise SaltCloudSystemExit(
            'The image_update function requires an \'update_type\' to be provided.'
        )

    if update_type == update_args[0]:
        update_number = 0
    elif update_type == update_args[1]:
        update_number = 1
    else:
        raise SaltCloudSystemExit(
            'The update_type argument must be either {0} or {1}.'.format(
                update_args[0],
                update_args[1]
            )
        )

    if image_id:
        if image_name:
            log.warning(
                'Both the \'image_id\' and \'image_name\' arguments were provided. '
                '\'image_id\' will take precedence.'
            )
    elif image_name:
        image_id = get_image_id(kwargs={'name': image_name})
    else:
        raise SaltCloudSystemExit(
            'The image_update function requires either an \'image_id\' or an '
            '\'image_name\' to be provided.'
        )

    if data:
        if path:
            log.warning(
                'Both the \'data\' and \'path\' arguments were provided. '
                '\'data\' will take precedence.'
            )
    elif path:
        with salt.utils.fopen(path, mode='r') as rfh:
            data = rfh.read()
    else:
        raise SaltCloudSystemExit(
            'The image_update function requires either \'data\' or a file \'path\' '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.image.update(auth, int(image_id), data, int(update_number))

    ret = {
        'action': 'image.update',
        'updated': response[0],
        'image_id': response[1],
        'error_code': response[2],
    }

    return ret


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
    __utils__['cloud.cache_node'](node, __active_provider_name__, __opts__)

    return node


def secgroup_allocate(call=None, kwargs=None):
    '''
    Allocates a new security group in OpenNebula.

    .. versionadded:: 2016.3.0

    path
        The path to a file containing the template of the security group. Syntax
        within the file can be the usual attribute=value or XML. Can be used
        instead of ``data``.

    data
        The template data of the security group. Syntax can be the usual
        attribute=value or XML. Can be used instead of ``path``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f secgroup_allocate opennebula path=/path/to/secgroup_file.txt
        salt-cloud -f secgroup_allocate opennebula \\
            data="NAME = test RULE = [PROTOCOL = TCP, RULE_TYPE = inbound, \\
            RANGE = 1000:2000]"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The secgroup_allocate function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    path = kwargs.get('path', None)
    data = kwargs.get('data', None)

    if data:
        if path:
            log.warning(
                'Both the \'data\' and \'path\' arguments were provided. '
                '\'data\' will take precedence.'
            )
    elif path:
        with salt.utils.fopen(path, mode='r') as rfh:
            data = rfh.read()
    else:
        raise SaltCloudSystemExit(
            'The secgroup_allocate function requires either \'data\' or a file '
            '\'path\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.secgroup.allocate(auth, data)

    ret = {
        'action': 'secgroup.allocate',
        'allocated': response[0],
        'secgroup_id': response[1],
        'error_code': response[2],
    }

    return ret


def secgroup_clone(call=None, kwargs=None):
    '''
    Clones an existing security group.

    .. versionadded:: 2016.3.0

    name
        The name of the new template.

    secgroup_id
        The ID of the security group to be cloned. Can be used instead of
        ``secgroup_name``.

    secgroup_name
        The name of the security group to be cloned. Can be used instead of
        ``secgroup_id``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f secgroup_clone opennebula name=my-cloned-secgroup secgroup_id=0
        salt-cloud -f secgroup_clone opennebula name=my-cloned-secgroup secgroup_name=my-secgroup
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The secgroup_clone function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    secgroup_id = kwargs.get('secgroup_id', None)
    secgroup_name = kwargs.get('secgroup_name', None)

    if name is None:
        raise SaltCloudSystemExit(
            'The secgroup_clone function requires a \'name\' to be provided.'
        )

    if secgroup_id:
        if secgroup_name:
            log.warning(
                'Both the \'secgroup_id\' and \'secgroup_name\' arguments were provided. '
                '\'secgroup_id\' will take precedence.'
            )
    elif secgroup_name:
        secgroup_id = get_secgroup_id(kwargs={'name': secgroup_name})
    else:
        raise SaltCloudSystemExit(
            'The secgroup_clone function requires either a \'secgroup_id\' or a '
            '\'secgroup_name\' to be provided.'
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

    .. versionadded:: 2016.3.0

    name
        The name of the security group to delete. Can be used instead of
        ``secgroup_id``.

    secgroup_id
        The ID of the security group to delete. Can be used instead of ``name``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f secgroup_delete opennebula name=my-secgroup
        salt-cloud --function secgroup_delete opennebula secgroup_id=100
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The secgroup_delete function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    secgroup_id = kwargs.get('secgroup_id', None)

    if secgroup_id:
        if name:
            log.warning(
                'Both the \'secgroup_id\' and \'name\' arguments were provided. '
                '\'secgroup_id\' will take precedence.'
            )
    elif name:
        secgroup_id = get_secgroup_id(kwargs={'name': name})
    else:
        raise SaltCloudSystemExit(
            'The secgroup_delete function requires either a \'name\' or a '
            '\'secgroup_id\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
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

    .. versionadded:: 2016.3.0

    name
        The name of the security group for which to gather information. Can be
        used instead of ``secgroup_id``.

    secgroup_id
        The ID of the security group for which to gather information. Can be
        used instead of ``name``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f secgroup_info opennebula name=my-secgroup
        salt-cloud --function secgroup_info opennebula secgroup_id=5
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The secgroup_info function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    secgroup_id = kwargs.get('secgroup_id', None)

    if secgroup_id:
        if name:
            log.warning(
                'Both the \'secgroup_id\' and \'name\' arguments were provided. '
                '\'secgroup_id\' will take precedence.'
            )
    elif name:
        secgroup_id = get_secgroup_id(kwargs={'name': name})
    else:
        raise SaltCloudSystemExit(
            'The secgroup_info function requires either a name or a secgroup_id '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])

    info = {}
    response = server.one.secgroup.info(auth, int(secgroup_id))[1]
    tree = _get_xml(response)
    info[tree.find('NAME').text] = _xml_to_dict(tree)

    return info


def secgroup_update(call=None, kwargs=None):
    '''
    Replaces the security group template contents.

    .. versionadded:: 2016.3.0

    secgroup_id
        The ID of the security group to update. Can be used instead of
        ``secgroup_name``.

    secgroup_name
        The name of the security group to update. Can be used instead of
        ``secgroup_id``.

    path
        The path to a file containing the template of the security group. Syntax
        within the file can be the usual attribute=value or XML. Can be used instead
        of ``data``.

    data
        The template data of the security group. Syntax can be the usual attribute=value
        or XML. Can be used instead of ``path``.

    update_type
        There are two ways to update a security group: ``replace`` the whole template
        or ``merge`` the new template with the existing one.

    CLI Example:

    .. code-block:: bash

        salt-cloud --function secgroup_update opennebula secgroup_id=100 \\
            path=/path/to/secgroup_update_file.txt \\
            update_type=replace
        salt-cloud -f secgroup_update opennebula secgroup_name=my-secgroup update_type=merge \\
            data="Name = test RULE = [PROTOCOL = TCP, RULE_TYPE = inbound, RANGE = 1000:2000]"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The secgroup_allocate function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    secgroup_id = kwargs.get('secgroup_id', None)
    secgroup_name = kwargs.get('secgroup_name', None)
    path = kwargs.get('path', None)
    data = kwargs.get('data', None)
    update_type = kwargs.get('update_type', None)
    update_args = ['replace', 'merge']

    if update_type is None:
        raise SaltCloudSystemExit(
            'The secgroup_update function requires an \'update_type\' to be provided.'
        )

    if update_type == update_args[0]:
        update_number = 0
    elif update_type == update_args[1]:
        update_number = 1
    else:
        raise SaltCloudSystemExit(
            'The update_type argument must be either {0} or {1}.'.format(
                update_args[0],
                update_args[1]
            )
        )

    if secgroup_id:
        if secgroup_name:
            log.warning(
                'Both the \'secgroup_id\' and \'secgroup_name\' arguments were provided. '
                '\'secgroup_id\' will take precedence.'
            )
    elif secgroup_name:
        secgroup_id = get_secgroup_id(kwargs={'name': secgroup_name})
    else:
        raise SaltCloudSystemExit(
            'The secgroup_update function requires either a \'secgroup_id\' or a '
            '\'secgroup_name\' to be provided.'
        )

    if data:
        if path:
            log.warning(
                'Both the \'data\' and \'path\' arguments were provided. '
                '\'data\' will take precedence.'
            )
    elif path:
        with salt.utils.fopen(path, mode='r') as rfh:
            data = rfh.read()
    else:
        raise SaltCloudSystemExit(
            'The secgroup_update function requires either \'data\' or a file \'path\' '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.secgroup.update(auth, int(secgroup_id), data, int(update_number))

    ret = {
        'action': 'secgroup.update',
        'updated': response[0],
        'secgroup_id': response[1],
        'error_code': response[2],
    }

    return ret


def template_allocate(call=None, kwargs=None):
    '''
    Allocates a new template in OpenNebula.

    .. versionadded:: 2016.3.0

    path
        The path to a file containing the elements of the template to be allocated.
        Syntax within the file can be the usual attribute=value or XML. Can be used
        instead of ``data``.

    data
        Contains the elements of the template to be allocated. Syntax can be the usual
        attribute=value or XML. Can be used instead of ``path``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f template_allocate opennebula path=/path/to/template_file.txt
        salt-cloud -f template_allocate opennebula \\
            data='CPU="1.0" DISK=[IMAGE="Ubuntu-14.04"] GRAPHICS=[LISTEN="0.0.0.0",TYPE="vnc"] \\
            MEMORY="1024" NETWORK="yes" NIC=[NETWORK="192net",NETWORK_UNAME="oneadmin"] \\
            OS=[ARCH="x86_64"] SUNSTONE_CAPACITY_SELECT="YES" SUNSTONE_NETWORK_SELECT="YES" \\
            VCPU="1"'
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The template_allocate function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    path = kwargs.get('path', None)
    data = kwargs.get('data', None)

    if data:
        if path:
            log.warning(
                'Both the \'data\' and \'path\' arguments were provided. '
                '\'data\' will take precedence.'
            )
    elif path:
        with salt.utils.fopen(path, mode='r') as rfh:
            data = rfh.read()
    else:
        raise SaltCloudSystemExit(
            'The template_allocate function requires either \'data\' or a file '
            '\'path\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.template.allocate(auth, data)

    ret = {
        'action': 'template.allocate',
        'allocated': response[0],
        'template_id': response[1],
        'error_code': response[2],
    }

    return ret


def template_clone(call=None, kwargs=None):
    '''
    Clones an existing virtual machine template.

    .. versionadded:: 2016.3.0

    name
        The name of the new template.

    template_id
        The ID of the template to be cloned. Can be used instead of ``template_name``.

    template_name
        The name of the template to be cloned. Can be used instead of ``template_id``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f template_clone opennebula name=my-new-template template_id=0
        salt-cloud -f template_clone opennebula name=my-new-template template_name=my-template
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The template_clone function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    template_id = kwargs.get('template_id', None)
    template_name = kwargs.get('template_name', None)

    if name is None:
        raise SaltCloudSystemExit(
            'The template_clone function requires a name to be provided.'
        )

    if template_id:
        if template_name:
            log.warning(
                'Both the \'template_id\' and \'template_name\' arguments were provided. '
                '\'template_id\' will take precedence.'
            )
    elif template_name:
        template_id = get_template_id(kwargs={'name': template_name})
    else:
        raise SaltCloudSystemExit(
            'The template_clone function requires either a \'template_id\' '
            'or a \'template_name\' to be provided.'
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

    .. versionadded:: 2016.3.0

    name
        The name of the template to delete. Can be used instead of ``template_id``.

    template_id
        The ID of the template to delete. Can be used instead of ``name``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f template_delete opennebula name=my-template
        salt-cloud --function template_delete opennebula template_id=5
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The template_delete function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    template_id = kwargs.get('template_id', None)

    if template_id:
        if name:
            log.warning(
                'Both the \'template_id\' and \'name\' arguments were provided. '
                '\'template_id\' will take precedence.'
            )
    elif name:
        template_id = get_template_id(kwargs={'name': name})
    else:
        raise SaltCloudSystemExit(
            'The template_delete function requires either a \'name\' or a \'template_id\' '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
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

    .. versionadded:: 2016.3.0

    .. note::
        ``template_instantiate`` creates a VM on OpenNebula from a template, but it
        does not install Salt on the new VM. Use the ``create`` function for that
        functionality: ``salt-cloud -p opennebula-profile vm-name``.

    vm_name
        Name for the new VM instance.

    template_id
        The ID of the template from which the VM will be created. Can be used instead
        of ``template_name``.

    template_name
        The name of the template from which the VM will be created. Can be used instead
        of ``template_id``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f template_instantiate opennebula vm_name=my-new-vm template_id=0

    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The template_instantiate function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    vm_name = kwargs.get('vm_name', None)
    template_id = kwargs.get('template_id', None)
    template_name = kwargs.get('template_name', None)

    if vm_name is None:
        raise SaltCloudSystemExit(
            'The template_instantiate function requires a \'vm_name\' to be provided.'
        )

    if template_id:
        if template_name:
            log.warning(
                'Both the \'template_id\' and \'template_name\' arguments were provided. '
                '\'template_id\' will take precedence.'
            )
    elif template_name:
        template_id = get_template_id(kwargs={'name': template_name})
    else:
        raise SaltCloudSystemExit(
            'The template_instantiate function requires either a \'template_id\' '
            'or a \'template_name\' to be provided.'
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


def template_update(call=None, kwargs=None):
    '''
    Replaces the template contents.

    .. versionadded:: 2016.3.0

    template_id
        The ID of the template to update. Can be used instead of ``template_name``.

    template_name
        The name of the template to update. Can be used instead of ``template_id``.

    path
        The path to a file containing the elements of the template to be updated.
        Syntax within the file can be the usual attribute=value or XML. Can be
        used instead of ``data``.

    data
        Contains the elements of the template to be updated. Syntax can be the
        usual attribute=value or XML. Can be used instead of ``path``.

    update_type
        There are two ways to update a template: ``replace`` the whole template
        or ``merge`` the new template with the existing one.

    CLI Example:

    .. code-block:: bash

        salt-cloud --function template_update opennebula template_id=1 update_type=replace \\
            path=/path/to/template_update_file.txt
        salt-cloud -f template_update opennebula template_name=my-template update_type=merge \\
            data='CPU="1.0" DISK=[IMAGE="Ubuntu-14.04"] GRAPHICS=[LISTEN="0.0.0.0",TYPE="vnc"] \\
            MEMORY="1024" NETWORK="yes" NIC=[NETWORK="192net",NETWORK_UNAME="oneadmin"] \\
            OS=[ARCH="x86_64"] SUNSTONE_CAPACITY_SELECT="YES" SUNSTONE_NETWORK_SELECT="YES" \\
            VCPU="1"'
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The template_update function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    template_id = kwargs.get('template_id', None)
    template_name = kwargs.get('template_name', None)
    path = kwargs.get('path', None)
    data = kwargs.get('data', None)
    update_type = kwargs.get('update_type', None)
    update_args = ['replace', 'merge']

    if update_type is None:
        raise SaltCloudSystemExit(
            'The template_update function requires an \'update_type\' to be provided.'
        )

    if update_type == update_args[0]:
        update_number = 0
    elif update_type == update_args[1]:
        update_number = 1
    else:
        raise SaltCloudSystemExit(
            'The update_type argument must be either {0} or {1}.'.format(
                update_args[0],
                update_args[1]
            )
        )

    if template_id:
        if template_name:
            log.warning(
                'Both the \'template_id\' and \'template_name\' arguments were provided. '
                '\'template_id\' will take precedence.'
            )
    elif template_name:
        template_id = get_template_id(kwargs={'name': template_name})
    else:
        raise SaltCloudSystemExit(
            'The template_update function requires either a \'template_id\' '
            'or a \'template_name\' to be provided.'
        )

    if data:
        if path:
            log.warning(
                'Both the \'data\' and \'path\' arguments were provided. '
                '\'data\' will take precedence.'
            )
    elif path:
        with salt.utils.fopen(path, mode='r') as rfh:
            data = rfh.read()
    else:
        raise SaltCloudSystemExit(
            'The template_update function requires either \'data\' or a file '
            '\'path\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.template.update(auth, int(template_id), data, int(update_number))

    ret = {
        'action': 'template.update',
        'updated': response[0],
        'template_id': response[1],
        'error_code': response[2],
    }

    return ret


def vm_action(name, kwargs=None, call=None):
    '''
    Submits an action to be performed on a given virtual machine.

    .. versionadded:: 2016.3.0

    name
        The name of the VM to action.

    action
        The action to be performed on the VM. Available options include:
          - boot
          - delete
          - delete-recreate
          - hold
          - poweroff
          - poweroff-hard
          - reboot
          - reboot-hard
          - release
          - resched
          - resume
          - shutdown
          - shutdown-hard
          - stop
          - suspend
          - undeploy
          - undeploy-hard
          - unresched

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_action my-vm action='release'
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_action function must be called with -a or --action.'
        )

    if kwargs is None:
        kwargs = {}

    action = kwargs.get('action', None)
    if action is None:
        raise SaltCloudSystemExit(
            'The vm_action function must have an \'action\' provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': name}))
    response = server.one.vm.action(auth, action, vm_id)

    data = {
        'action': 'vm.action.' + str(action),
        'actioned': response[0],
        'vm_id': response[1],
        'error_code': response[2],
    }

    return data


def vm_allocate(call=None, kwargs=None):
    '''
    Allocates a new virtual machine in OpenNebula.

    .. versionadded:: 2016.3.0

    path
        The path to a file defining the template of the VM to allocate.
        Syntax within the file can be the usual attribute=value or XML.
        Can be used instead of ``data``.

    data
        Contains the template definitions of the VM to allocate. Syntax can
        be the usual attribute=value or XML. Can be used instead of ``path``.

    hold
        If this parameter is set to ``True``, the VM will be created in
        the ``HOLD`` state. If not set, the VM is created in the ``PENDING``
        state. Default is ``False``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f vm_allocate path=/path/to/vm_template.txt
        salt-cloud --function vm_allocate path=/path/to/vm_template.txt hold=True
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The vm_allocate function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    path = kwargs.get('path', None)
    data = kwargs.get('data', None)
    hold = kwargs.get('hold', False)

    if data:
        if path:
            log.warning(
                'Both the \'data\' and \'path\' arguments were provided. '
                '\'data\' will take precedence.'
            )
    elif path:
        with salt.utils.fopen(path, mode='r') as rfh:
            data = rfh.read()
    else:
        raise SaltCloudSystemExit(
            'The vm_allocate function requires either \'data\' or a file \'path\' '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.vm.allocate(auth, data, salt.utils.is_true(hold))

    ret = {
        'action': 'vm.allocate',
        'allocated': response[0],
        'vm_id': response[1],
        'error_code': response[2],
    }

    return ret


def vm_attach(name, kwargs=None, call=None):
    '''
    Attaches a new disk to the given virtual machine.

    .. versionadded:: 2016.3.0

    name
        The name of the VM for which to attach the new disk.

    path
        The path to a file containing a single disk vector attribute.
        Syntax within the file can be the usual attribute=value or XML.
        Can be used instead of ``data``.

    data
        Contains the data needed to attach a single disk vector attribute.
        Syntax can be the usual attribute=value or XML. Can be used instead
        of ``path``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_attach my-vm path=/path/to/disk_file.txt
        salt-cloud -a vm_attach my-vm data="DISK=[DISK_ID=1]"
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_attach action must be called with -a or --action.'
        )

    if kwargs is None:
        kwargs = {}

    path = kwargs.get('path', None)
    data = kwargs.get('data', None)

    if data:
        if path:
            log.warning(
                'Both the \'data\' and \'path\' arguments were provided. '
                '\'data\' will take precedence.'
            )
    elif path:
        with salt.utils.fopen(path, mode='r') as rfh:
            data = rfh.read()
    else:
        raise SaltCloudSystemExit(
            'The vm_attach function requires either \'data\' or a file '
            '\'path\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': name}))
    response = server.one.vm.attach(auth, vm_id, data)

    ret = {
        'action': 'vm.attach',
        'attached': response[0],
        'vm_id': response[1],
        'error_code': response[2],
    }

    return ret


def vm_attach_nic(name, kwargs=None, call=None):
    '''
    Attaches a new network interface to the given virtual machine.

    .. versionadded:: 2016.3.0

    name
        The name of the VM for which to attach the new network interface.

    path
        The path to a file containing a single NIC vector attribute.
        Syntax within the file can be the usual attribute=value or XML. Can
        be used instead of ``data``.

    data
        Contains the single NIC vector attribute to attach to the VM.
        Syntax can be the usual attribute=value or XML. Can be used instead
        of ``path``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_attach_nic my-vm path=/path/to/nic_file.txt
        salt-cloud -a vm_attach_nic my-vm data="NIC=[NETWORK_ID=1]"
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_attach_nic action must be called with -a or --action.'
        )

    if kwargs is None:
        kwargs = {}

    path = kwargs.get('path', None)
    data = kwargs.get('data', None)

    if data:
        if path:
            log.warning(
                'Both the \'data\' and \'path\' arguments were provided. '
                '\'data\' will take precedence.'
            )
    elif path:
        with salt.utils.fopen(path, mode='r') as rfh:
            data = rfh.read()
    else:
        raise SaltCloudSystemExit(
            'The vm_attach_nic function requires either \'data\' or a file '
            '\'path\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': name}))
    response = server.one.vm.attachnic(auth, vm_id, data)

    ret = {
        'action': 'vm.attachnic',
        'nic_attached': response[0],
        'vm_id': response[1],
        'error_code': response[2],
    }

    return ret


def vm_deploy(name, kwargs=None, call=None):
    '''
    Initiates the instance of the given VM on the target host.

    .. versionadded:: 2016.3.0

    name
        The name of the VM to deploy.

    host_id
        The ID of the target host where the VM will be deployed. Can be used instead
        of ``host_name``.

    host_name
        The name of the target host where the VM will be deployed. Can be used instead
        of ``host_id``.

    capacity_maintained
        True to enforce the Host capacity is not over-committed. This parameter is only
        acknowledged for users in the ``oneadmin`` group. Host capacity will be always
        enforced for regular users.

    datastore_id
        The ID of the target system data-store where the VM will be deployed. Optional
        and can be used instead of ``datastore_name``. If neither ``datastore_id`` nor
        ``datastore_name`` are set, OpenNebula will choose the data-store.

    datastore_name
        The name of the target system data-store where the VM will be deployed. Optional,
        and can be used instead of ``datastore_id``. If neither ``datastore_id`` nor
        ``datastore_name`` are set, OpenNebula will choose the data-store.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_deploy my-vm host_id=0
        salt-cloud -a vm_deploy my-vm host_id=1 capacity_maintained=False
        salt-cloud -a vm_deploy my-vm host_name=host01 datastore_id=1
        salt-cloud -a vm_deploy my-vm host_name=host01 datastore_name=default
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_deploy action must be called with -a or --action.'
        )

    if kwargs is None:
        kwargs = {}

    host_id = kwargs.get('host_id', None)
    host_name = kwargs.get('host_name', None)
    capacity_maintained = kwargs.get('capacity_maintained', True)
    datastore_id = kwargs.get('datastore_id', None)
    datastore_name = kwargs.get('datastore_name', None)

    if host_id:
        if host_name:
            log.warning(
                'Both the \'host_id\' and \'host_name\' arguments were provided. '
                '\'host_id\' will take precedence.'
            )
    elif host_name:
        host_id = get_host_id(kwargs={'name': host_name})
    else:
        raise SaltCloudSystemExit(
            'The vm_deploy function requires a \'host_id\' or a \'host_name\' '
            'to be provided.'
        )

    if datastore_id:
        if datastore_name:
            log.warning(
                'Both the \'datastore_id\' and \'datastore_name\' arguments were provided. '
                '\'datastore_id\' will take precedence.'
            )
    elif datastore_name:
        datastore_id = get_datastore_id(kwargs={'name': datastore_name})
    else:
        datastore_id = '-1'

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = get_vm_id(kwargs={'name': name})
    response = server.one.vm.deploy(auth,
                                    int(vm_id),
                                    int(host_id),
                                    salt.utils.is_true(capacity_maintained),
                                    int(datastore_id))

    data = {
        'action': 'vm.deploy',
        'deployed': response[0],
        'vm_id': response[1],
        'error_code': response[2],
    }

    return data


def vm_detach(name, kwargs=None, call=None):
    '''
    Detaches a disk from a virtual machine.

    .. versionadded:: 2016.3.0

    name
        The name of the VM from which to detach the disk.

    disk_id
        The ID of the disk to detach.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_detach my-vm disk_id=1
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_detach action must be called with -a or --action.'
        )

    if kwargs is None:
        kwargs = {}

    disk_id = kwargs.get('disk_id', None)
    if disk_id is None:
        raise SaltCloudSystemExit(
            'The vm_detach function requires a \'disk_id\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': name}))
    response = server.one.vm.detach(auth, vm_id, int(disk_id))

    data = {
        'action': 'vm.detach',
        'detached': response[0],
        'vm_id': response[1],
        'error_code': response[2],
    }

    return data


def vm_detach_nic(name, kwargs=None, call=None):
    '''
    Detaches a disk from a virtual machine.

    .. versionadded:: 2016.3.0

    name
        The name of the VM from which to detach the network interface.

    nic_id
        The ID of the nic to detach.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_detach_nic my-vm nic_id=1
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_detach_nic action must be called with -a or --action.'
        )

    if kwargs is None:
        kwargs = {}

    nic_id = kwargs.get('nic_id', None)
    if nic_id is None:
        raise SaltCloudSystemExit(
            'The vm_detach_nic function requires a \'nic_id\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': name}))
    response = server.one.vm.detachnic(auth, vm_id, int(nic_id))

    data = {
        'action': 'vm.detachnic',
        'nic_detached': response[0],
        'vm_id': response[1],
        'error_code': response[2],
    }

    return data


def vm_disk_save(name, kwargs=None, call=None):
    '''
    Sets the disk to be saved in the given image.

    .. versionadded:: 2016.3.0

    name
        The name of the VM containing the disk to save.

    disk_id
        The ID of the disk to save.

    image_name
        The name of the new image where the disk will be saved.

    image_type
        The type for the new image. If not set, then the default ``ONED`` Configuration
        will be used. Other valid types include: OS, CDROM, DATABLOCK, KERNEL, RAMDISK,
        and CONTEXT.

    snapshot_id
        The ID of the snapshot to export. If not set, the current image state will be
        used.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_disk_save my-vm disk_id=1 image_name=my-new-image
        salt-cloud -a vm_disk_save my-vm disk_id=1 image_name=my-new-image image_type=CONTEXT snapshot_id=10
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_disk_save action must be called with -a or --action.'
        )

    if kwargs is None:
        kwargs = {}

    disk_id = kwargs.get('disk_id', None)
    image_name = kwargs.get('image_name', None)
    image_type = kwargs.get('image_type', '')
    snapshot_id = int(kwargs.get('snapshot_id', '-1'))

    if disk_id is None or image_name is None:
        raise SaltCloudSystemExit(
            'The vm_disk_save function requires a \'disk_id\' and an \'image_name\' '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': name}))
    response = server.one.vm.disksave(auth,
                                      vm_id,
                                      int(disk_id),
                                      image_name,
                                      image_type,
                                      snapshot_id)

    data = {
        'action': 'vm.disksave',
        'saved': response[0],
        'image_id': response[1],
        'error_code': response[2],
    }

    return data


def vm_disk_snapshot_create(name, kwargs=None, call=None):
    '''
    Takes a new snapshot of the disk image.

    .. versionadded:: 2016.3.0

    name
        The name of the VM of which to take the snapshot.

    disk_id
        The ID of the disk to save.

    description
        The description for the snapshot.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_disk_snapshot_create my-vm disk_id=0 description="My Snapshot Description"
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_disk_snapshot_create action must be called with -a or --action.'
        )

    if kwargs is None:
        kwargs = {}

    disk_id = kwargs.get('disk_id', None)
    description = kwargs.get('description', None)

    if disk_id is None or description is None:
        raise SaltCloudSystemExit(
            'The vm_disk_snapshot_create function requires a \'disk_id\' and a \'description\' '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': name}))
    response = server.one.vm.disksnapshotcreate(auth,
                                                vm_id,
                                                int(disk_id),
                                                description)

    data = {
        'action': 'vm.disksnapshotcreate',
        'created': response[0],
        'snapshot_id': response[1],
        'error_code': response[2],
    }

    return data


def vm_disk_snapshot_delete(name, kwargs=None, call=None):
    '''
    Deletes a disk snapshot based on the given VM and the disk_id.

    .. versionadded:: 2016.3.0

    name
        The name of the VM containing the snapshot to delete.

    disk_id
        The ID of the disk to save.

    snapshot_id
        The ID of the snapshot to be deleted.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_disk_snapshot_delete my-vm disk_id=0 snapshot_id=6
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_disk_snapshot_delete action must be called with -a or --action.'
        )

    if kwargs is None:
        kwargs = {}

    disk_id = kwargs.get('disk_id', None)
    snapshot_id = kwargs.get('snapshot_id', None)

    if disk_id is None or snapshot_id is None:
        raise SaltCloudSystemExit(
            'The vm_disk_snapshot_create function requires a \'disk_id\' and a \'snapshot_id\' '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': name}))
    response = server.one.vm.disksnapshotdelete(auth,
                                                vm_id,
                                                int(disk_id),
                                                int(snapshot_id))

    data = {
        'action': 'vm.disksnapshotdelete',
        'deleted': response[0],
        'snapshot_id': response[1],
        'error_code': response[2],
    }

    return data


def vm_disk_snapshot_revert(name, kwargs=None, call=None):
    '''
    Reverts a disk state to a previously taken snapshot.

    .. versionadded:: 2016.3.0

    name
        The name of the VM containing the snapshot.

    disk_id
        The ID of the disk to revert its state.

    snapshot_id
        The ID of the snapshot to which the snapshot should be reverted.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_disk_snapshot_revert my-vm disk_id=0 snapshot_id=6
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_disk_snapshot_revert action must be called with -a or --action.'
        )

    if kwargs is None:
        kwargs = {}

    disk_id = kwargs.get('disk_id', None)
    snapshot_id = kwargs.get('snapshot_id', None)

    if disk_id is None or snapshot_id is None:
        raise SaltCloudSystemExit(
            'The vm_disk_snapshot_revert function requires a \'disk_id\' and a \'snapshot_id\' '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': name}))
    response = server.one.vm.disksnapshotrevert(auth,
                                                vm_id,
                                                int(disk_id),
                                                int(snapshot_id))

    data = {
        'action': 'vm.disksnapshotrevert',
        'deleted': response[0],
        'snapshot_id': response[1],
        'error_code': response[2],
    }

    return data


def vm_info(name, call=None):
    '''
    Retrieves information for a given virtual machine. A VM name must be supplied.

    .. versionadded:: 2016.3.0

    name
        The name of the VM for which to gather information.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_info my-vm
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_info action must be called with -a or --action.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': name}))
    response = server.one.vm.info(auth, vm_id)

    if response[0] is False:
        return response[1]
    else:
        info = {}
        tree = _get_xml(response[1])
        info[tree.find('NAME').text] = _xml_to_dict(tree)
        return info


def vm_migrate(name, kwargs=None, call=None):
    '''
    Migrates the specified virtual machine to the specified target host.

    .. versionadded:: 2016.3.0

    name
        The name of the VM to migrate.

    host_id
        The ID of the host to which the VM will be migrated. Can be used instead
        of ``host_name``.

    host_name
        The name of the host to which the VM will be migrated. Can be used instead
        of ``host_id``.

    live_migration
        If set to ``True``, a live-migration will be performed. Default is ``False``.

    capacity_maintained
        True to enforce the Host capacity is not over-committed. This parameter is only
        acknowledged for users in the ``oneadmin`` group. Host capacity will be always
        enforced for regular users.

    datastore_id
        The target system data-store ID where the VM will be migrated. Can be used
        instead of ``datastore_name``.

    datastore_name
        The name of the data-store target system where the VM will be migrated. Can be
        used instead of ``datastore_id``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_migrate my-vm host_id=0 datastore_id=1
        salt-cloud -a vm_migrate my-vm host_id=0 datastore_id=1 live_migration=True
        salt-cloud -a vm_migrate my-vm host_name=host01 datastore_name=default
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_migrate action must be called with -a or --action.'
        )

    if kwargs is None:
        kwargs = {}

    host_id = kwargs.get('host_id', None)
    host_name = kwargs.get('host_name', None)
    live_migration = kwargs.get('live_migration', False)
    capacity_maintained = kwargs.get('capacity_maintained', True)
    datastore_id = kwargs.get('datastore_id', None)
    datastore_name = kwargs.get('datastore_name', None)

    if datastore_id:
        if datastore_name:
            log.warning(
                'Both the \'datastore_id\' and \'datastore_name\' arguments were provided. '
                '\'datastore_id\' will take precedence.'
            )
    elif datastore_name:
        datastore_id = get_datastore_id(kwargs={'name': datastore_name})
    else:
        raise SaltCloudSystemExit(
            'The vm_migrate function requires either a \'datastore_id\' or a '
            '\'datastore_name\' to be provided.'
        )

    if host_id:
        if host_name:
            log.warning(
                'Both the \'host_id\' and \'host_name\' arguments were provided. '
                '\'host_id\' will take precedence.'
            )
    elif host_name:
        host_id = get_host_id(kwargs={'name': host_name})
    else:
        raise SaltCloudSystemExit(
            'The vm_migrate function requires either a \'host_id\' '
            'or a \'host_name\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': name}))
    response = server.one.vm.migrate(auth,
                                     vm_id,
                                     int(host_id),
                                     salt.utils.is_true(live_migration),
                                     salt.utils.is_true(capacity_maintained),
                                     int(datastore_id))

    data = {
        'action': 'vm.migrate',
        'migrated': response[0],
        'vm_id': response[1],
        'error_code': response[2],
    }

    return data


def vm_monitoring(name, call=None):
    '''
    Returns the monitoring records for a given virtual machine. A VM name must be
    supplied.

    The monitoring information returned is a list of VM elements. Each VM element
    contains the complete dictionary of the VM with the updated information returned
    by the poll action.

    .. versionadded:: 2016.3.0

    name
        The name of the VM for which to gather monitoring records.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_monitoring my-vm
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_monitoring action must be called with -a or --action.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': name}))
    response = server.one.vm.monitoring(auth, vm_id)

    if response[0] is False:
        log.error(
            'There was an error retrieving the specified VM\'s monitoring '
            'information.'
        )
        return {}
    else:
        info = {}
        for vm_ in _get_xml(response[1]):
            info[vm_.find('ID').text] = _xml_to_dict(vm_)
        return info


def vm_resize(name, kwargs=None, call=None):
    '''
    Changes the capacity of the virtual machine.

    .. versionadded:: 2016.3.0

    name
        The name of the VM to resize.

    path
        The path to a file containing new capacity elements CPU, VCPU, MEMORY. If one
        of them is not present, or its value is 0, the VM will not be re-sized. Syntax
        within the file can be the usual attribute=value or XML. Can be used instead
        of ``data``.

    data
        Contains the new capacity elements CPU, VCPU, and MEMORY. If one of them is not
        present, or its value is 0, the VM will not be re-sized. Can be used instead of
        ``path``.

    capacity_maintained
        True to enforce the Host capacity is not over-committed. This parameter is only
        acknowledged for users in the ``oneadmin`` group. Host capacity will be always
        enforced for regular users.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_resize my-vm path=/path/to/capacity_template.txt
        salt-cloud -a vm_resize my-vm path=/path/to/capacity_template.txt capacity_maintained=False
        salt-cloud -a vm_resize my-vm data="CPU=1 VCPU=1 MEMORY=1024"
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_resize action must be called with -a or --action.'
        )

    if kwargs is None:
        kwargs = {}

    path = kwargs.get('path', None)
    data = kwargs.get('data', None)
    capacity_maintained = kwargs.get('capacity_maintained', True)

    if data:
        if path:
            log.warning(
                'Both the \'data\' and \'path\' arguments were provided. '
                '\'data\' will take precedence.'
            )
    elif path:
        with salt.utils.fopen(path, mode='r') as rfh:
            data = rfh.read()
    else:
        raise SaltCloudSystemExit(
            'The vm_resize function requires either \'data\' or a file \'path\' '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': name}))
    response = server.one.vm.resize(auth, vm_id, data, salt.utils.is_true(capacity_maintained))

    ret = {
        'action': 'vm.resize',
        'resized': response[0],
        'vm_id': response[1],
        'error_code': response[2],
    }

    return ret


def vm_snapshot_create(vm_name, kwargs=None, call=None):
    '''
    Creates a new virtual machine snapshot from the provided VM.

    .. versionadded:: 2016.3.0

    vm_name
        The name of the VM from which to create the snapshot.

    snapshot_name
        The name of the snapshot to be created.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_snapshot_create my-vm snapshot_name=my-new-snapshot
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_snapshot_create action must be called with -a or --action.'
        )

    if kwargs is None:
        kwargs = {}

    snapshot_name = kwargs.get('snapshot_name', None)
    if snapshot_name is None:
        raise SaltCloudSystemExit(
            'The vm_snapshot_create function requires a \'snapshot_name\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': vm_name}))
    response = server.one.vm.snapshotcreate(auth, vm_id, snapshot_name)

    data = {
        'action': 'vm.snapshotcreate',
        'snapshot_created': response[0],
        'snapshot_id': response[1],
        'error_code': response[2],
    }

    return data


def vm_snapshot_delete(vm_name, kwargs=None, call=None):
    '''
    Deletes a virtual machine snapshot from the provided VM.

    .. versionadded:: 2016.3.0

    vm_name
        The name of the VM from which to delete the snapshot.

    snapshot_id
        The ID of the snapshot to be deleted.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_snapshot_delete my-vm snapshot_id=8
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_snapshot_delete action must be called with -a or --action.'
        )

    if kwargs is None:
        kwargs = {}

    snapshot_id = kwargs.get('snapshot_id', None)
    if snapshot_id is None:
        raise SaltCloudSystemExit(
            'The vm_snapshot_delete function requires a \'snapshot_id\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': vm_name}))
    response = server.one.vm.snapshotdelete(auth, vm_id, int(snapshot_id))

    data = {
        'action': 'vm.snapshotdelete',
        'snapshot_deleted': response[0],
        'vm_id': response[1],
        'error_code': response[2],
    }

    return data


def vm_snapshot_revert(vm_name, kwargs=None, call=None):
    '''
    Reverts a virtual machine to a snapshot

    .. versionadded:: 2016.3.0

    vm_name
        The name of the VM to revert.

    snapshot_id
        The snapshot ID.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_snapshot_revert my-vm snapshot_id=42
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_snapshot_revert action must be called with -a or --action.'
        )

    if kwargs is None:
        kwargs = {}

    snapshot_id = kwargs.get('snapshot_id', None)
    if snapshot_id is None:
        raise SaltCloudSystemExit(
            'The vm_snapshot_revert function requires a \'snapshot_id\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': vm_name}))
    response = server.one.vm.snapshotrevert(auth, vm_id, int(snapshot_id))

    data = {
        'action': 'vm.snapshotrevert',
        'snapshot_reverted': response[0],
        'vm_id': response[1],
        'error_code': response[2],
    }

    return data


def vm_update(name, kwargs=None, call=None):
    '''
    Replaces the user template contents.

    .. versionadded:: 2016.3.0

    name
        The name of the VM to update.

    path
        The path to a file containing new user template contents. Syntax within the
        file can be the usual attribute=value or XML. Can be used instead of ``data``.

    data
        Contains the new user template contents. Syntax can be the usual attribute=value
        or XML. Can be used instead of ``path``.

    update_type
        There are two ways to update a VM: ``replace`` the whole template
        or ``merge`` the new template with the existing one.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a vm_update my-vm path=/path/to/user_template_file.txt update_type='replace'
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The vm_update action must be called with -a or --action.'
        )

    if kwargs is None:
        kwargs = {}

    path = kwargs.get('path', None)
    data = kwargs.get('data', None)
    update_type = kwargs.get('update_type', None)
    update_args = ['replace', 'merge']

    if update_type is None:
        raise SaltCloudSystemExit(
            'The vm_update function requires an \'update_type\' to be provided.'
        )

    if update_type == update_args[0]:
        update_number = 0
    elif update_type == update_args[1]:
        update_number = 1
    else:
        raise SaltCloudSystemExit(
            'The update_type argument must be either {0} or {1}.'.format(
                update_args[0],
                update_args[1]
            )
        )

    if data:
        if path:
            log.warning(
                'Both the \'data\' and \'path\' arguments were provided. '
                '\'data\' will take precedence.'
            )
    elif path:
        with salt.utils.fopen(path, mode='r') as rfh:
            data = rfh.read()
    else:
        raise SaltCloudSystemExit(
            'The vm_update function requires either \'data\' or a file \'path\' '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    vm_id = int(get_vm_id(kwargs={'name': name}))
    response = server.one.vm.update(auth, vm_id, data, int(update_number))

    ret = {
        'action': 'vm.update',
        'updated': response[0],
        'resource_id': response[1],
        'error_code': response[2],
    }

    return ret


def vn_add_ar(call=None, kwargs=None):
    '''
    Adds address ranges to a given virtual network.

    .. versionadded:: 2016.3.0

    vn_id
        The ID of the virtual network to add the address range. Can be used
        instead of ``vn_name``.

    vn_name
        The name of the virtual network to add the address range. Can be used
        instead of ``vn_id``.

    path
        The path to a file containing the template of the address range to add.
        Syntax within the file can be the usual attribute=value or XML. Can be
        used instead of ``data``.

    data
        Contains the template of the address range to add. Syntax can be the
        usual attribute=value or XML. Can be used instead of ``path``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f vn_add_ar opennebula vn_id=3 path=/path/to/address_range.txt
        salt-cloud -f vn_add_ar opennebula vn_name=my-vn \\
            data="AR=[TYPE=IP4, IP=192.168.0.5, SIZE=10]"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The vn_add_ar function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    vn_id = kwargs.get('vn_id', None)
    vn_name = kwargs.get('vn_name', None)
    path = kwargs.get('path', None)
    data = kwargs.get('data', None)

    if vn_id:
        if vn_name:
            log.warning(
                'Both the \'vn_id\' and \'vn_name\' arguments were provided. '
                '\'vn_id\' will take precedence.'
            )
    elif vn_name:
        vn_id = get_vn_id(kwargs={'name': vn_name})
    else:
        raise SaltCloudSystemExit(
            'The vn_add_ar function requires a \'vn_id\' and a \'vn_name\' to '
            'be provided.'
        )

    if data:
        if path:
            log.warning(
                'Both the \'data\' and \'path\' arguments were provided. '
                '\'data\' will take precedence.'
            )
    elif path:
        with salt.utils.fopen(path, mode='r') as rfh:
            data = rfh.read()
    else:
        raise SaltCloudSystemExit(
            'The vn_add_ar function requires either \'data\' or a file \'path\' '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.vn.add_ar(auth, int(vn_id), data)

    ret = {
        'action': 'vn.add_ar',
        'address_range_added': response[0],
        'resource_id': response[1],
        'error_code': response[2],
    }

    return ret


def vn_allocate(call=None, kwargs=None):
    '''
    Allocates a new virtual network in OpenNebula.

    .. versionadded:: 2016.3.0

    path
        The path to a file containing the template of the virtual network to allocate.
        Syntax within the file can be the usual attribute=value or XML. Can be used
        instead of ``data``.

    data
        Contains the template of the virtual network to allocate. Syntax can be the
        usual attribute=value or XML. Can be used instead of ``path``.

    cluster_id
        The ID of the cluster for which to add the new virtual network. Can be used
        instead of ``cluster_name``. If neither ``cluster_id`` nor ``cluster_name``
        are provided, the virtual network won’t be added to any cluster.

    cluster_name
        The name of the cluster for which to add the new virtual network. Can be used
        instead of ``cluster_id``. If neither ``cluster_name`` nor ``cluster_id`` are
        provided, the virtual network won't be added to any cluster.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f vn_allocate opennebula path=/path/to/vn_file.txt
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The vn_allocate function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    cluster_id = kwargs.get('cluster_id', None)
    cluster_name = kwargs.get('cluster_name', None)
    path = kwargs.get('path', None)
    data = kwargs.get('data', None)

    if data:
        if path:
            log.warning(
                'Both the \'data\' and \'path\' arguments were provided. '
                '\'data\' will take precedence.'
            )
    elif path:
        with salt.utils.fopen(path, mode='r') as rfh:
            data = rfh.read()
    else:
        raise SaltCloudSystemExit(
            'The vn_allocate function requires either \'data\' or a file \'path\' '
            'to be provided.'
        )

    if cluster_id:
        if cluster_name:
            log.warning(
                'Both the \'cluster_id\' and \'cluster_name\' arguments were provided. '
                '\'cluster_id\' will take precedence.'
             )
    elif cluster_name:
        cluster_id = get_cluster_id(kwargs={'name': cluster_name})
    else:
        cluster_id = '-1'

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.vn.allocate(auth, data, int(cluster_id))

    ret = {
        'action': 'vn.allocate',
        'allocated': response[0],
        'vn_id': response[1],
        'error_code': response[2],
    }

    return ret


def vn_delete(call=None, kwargs=None):
    '''
    Deletes the given virtual network from OpenNebula. Either a name or a vn_id must
    be supplied.

    .. versionadded:: 2016.3.0

    name
        The name of the virtual network to delete. Can be used instead of ``vn_id``.

    vn_id
        The ID of the virtual network to delete. Can be used instead of ``name``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f vn_delete opennebula name=my-virtual-network
        salt-cloud --function vn_delete opennebula vn_id=3
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The vn_delete function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    vn_id = kwargs.get('vn_id', None)

    if vn_id:
        if name:
            log.warning(
                'Both the \'vn_id\' and \'name\' arguments were provided. '
                '\'vn_id\' will take precedence.'
            )
    elif name:
        vn_id = get_vn_id(kwargs={'name': name})
    else:
        raise SaltCloudSystemExit(
            'The vn_delete function requires a \'name\' or a \'vn_id\' '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.vn.delete(auth, int(vn_id))

    data = {
        'action': 'vn.delete',
        'deleted': response[0],
        'vn_id': response[1],
        'error_code': response[2],
    }

    return data


def vn_free_ar(call=None, kwargs=None):
    '''
    Frees a reserved address range from a virtual network.

    .. versionadded:: 2016.3.0

    vn_id
        The ID of the virtual network from which to free an address range.
        Can be used instead of ``vn_name``.

    vn_name
        The name of the virtual network from which to free an address range.
        Can be used instead of ``vn_id``.

    ar_id
        The ID of the address range to free.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f vn_free_ar opennebula vn_id=3 ar_id=1
        salt-cloud -f vn_free_ar opennebula vn_name=my-vn ar_id=1
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The vn_free_ar function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    vn_id = kwargs.get('vn_id', None)
    vn_name = kwargs.get('vn_name', None)
    ar_id = kwargs.get('ar_id', None)

    if ar_id is None:
        raise SaltCloudSystemExit(
            'The vn_free_ar function requires an \'rn_id\' to be provided.'
        )

    if vn_id:
        if vn_name:
            log.warning(
                'Both the \'vn_id\' and \'vn_name\' arguments were provided. '
                '\'vn_id\' will take precedence.'
            )
    elif vn_name:
        vn_id = get_vn_id(kwargs={'name': vn_name})
    else:
        raise SaltCloudSystemExit(
            'The vn_free_ar function requires a \'vn_id\' or a \'vn_name\' to '
            'be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.vn.free_ar(auth, int(vn_id), int(ar_id))

    data = {
        'action': 'vn.free_ar',
        'ar_freed': response[0],
        'resource_id': response[1],
        'error_code': response[2],
    }

    return data


def vn_hold(call=None, kwargs=None):
    '''
    Holds a virtual network lease as used.

    .. versionadded:: 2016.3.0

    vn_id
        The ID of the virtual network from which to hold the lease. Can be used
        instead of ``vn_name``.

    vn_name
        The name of the virtual network from which to hold the lease. Can be used
        instead of ``vn_id``.

    path
        The path to a file defining the template of the lease to hold.
        Syntax within the file can be the usual attribute=value or XML. Can be
        used instead of ``data``.

    data
        Contains the template of the lease to hold. Syntax can be the usual
        attribute=value or XML. Can be used instead of ``path``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f vn_hold opennebula vn_id=3 path=/path/to/vn_hold_file.txt
        salt-cloud -f vn_hold opennebula vn_name=my-vn data="LEASES=[IP=192.168.0.5]"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The vn_hold function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    vn_id = kwargs.get('vn_id', None)
    vn_name = kwargs.get('vn_name', None)
    path = kwargs.get('path', None)
    data = kwargs.get('data', None)

    if vn_id:
        if vn_name:
            log.warning(
                'Both the \'vn_id\' and \'vn_name\' arguments were provided. '
                '\'vn_id\' will take precedence.'
            )
    elif vn_name:
        vn_id = get_vn_id(kwargs={'name': vn_name})
    else:
        raise SaltCloudSystemExit(
            'The vn_hold function requires a \'vn_id\' or a \'vn_name\' to '
            'be provided.'
        )

    if data:
        if path:
            log.warning(
                'Both the \'data\' and \'path\' arguments were provided. '
                '\'data\' will take precedence.'
            )
    elif path:
        with salt.utils.fopen(path, mode='r') as rfh:
            data = rfh.read()
    else:
        raise SaltCloudSystemExit(
            'The vn_hold function requires either \'data\' or a \'path\' to '
            'be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.vn.hold(auth, int(vn_id), data)

    ret = {
        'action': 'vn.hold',
        'held': response[0],
        'resource_id': response[1],
        'error_code': response[2],
    }

    return ret


def vn_info(call=None, kwargs=None):
    '''
    Retrieves information for the virtual network.

    .. versionadded:: 2016.3.0

    name
        The name of the virtual network for which to gather information. Can be
        used instead of ``vn_id``.

    vn_id
        The ID of the virtual network for which to gather information. Can be
        used instead of ``name``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f vn_info opennebula vn_id=3
        salt-cloud --function vn_info opennebula name=public
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The vn_info function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    vn_id = kwargs.get('vn_id', None)

    if vn_id:
        if name:
            log.warning(
                'Both the \'vn_id\' and \'name\' arguments were provided. '
                '\'vn_id\' will take precedence.'
            )
    elif name:
        vn_id = get_vn_id(kwargs={'name': name})
    else:
        raise SaltCloudSystemExit(
            'The vn_info function requires either a \'name\' or a \'vn_id\' '
            'to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.vn.info(auth, int(vn_id))

    if response[0] is False:
        return response[1]
    else:
        info = {}
        tree = _get_xml(response[1])
        info[tree.find('NAME').text] = _xml_to_dict(tree)
        return info


def vn_release(call=None, kwargs=None):
    '''
    Releases a virtual network lease that was previously on hold.

    .. versionadded:: 2016.3.0

    vn_id
        The ID of the virtual network from which to release the lease. Can be
        used instead of ``vn_name``.

    vn_name
        The name of the virtual network from which to release the lease.
        Can be used instead of ``vn_id``.

    path
        The path to a file defining the template of the lease to release.
        Syntax within the file can be the usual attribute=value or XML. Can be
        used instead of ``data``.

    data
        Contains the template defining the lease to release. Syntax can be the
        usual attribute=value or XML. Can be used instead of ``path``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f vn_release opennebula vn_id=3 path=/path/to/vn_release_file.txt
        salt-cloud =f vn_release opennebula vn_name=my-vn data="LEASES=[IP=192.168.0.5]"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The vn_reserve function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    vn_id = kwargs.get('vn_id', None)
    vn_name = kwargs.get('vn_name', None)
    path = kwargs.get('path', None)
    data = kwargs.get('data', None)

    if vn_id:
        if vn_name:
            log.warning(
                'Both the \'vn_id\' and \'vn_name\' arguments were provided. '
                '\'vn_id\' will take precedence.'
            )
    elif vn_name:
        vn_id = get_vn_id(kwargs={'name': vn_name})
    else:
        raise SaltCloudSystemExit(
            'The vn_release function requires a \'vn_id\' or a \'vn_name\' to '
            'be provided.'
        )

    if data:
        if path:
            log.warning(
                'Both the \'data\' and \'path\' arguments were provided. '
                '\'data\' will take precedence.'
            )
    elif path:
        with salt.utils.fopen(path, mode='r') as rfh:
            data = rfh.read()
    else:
        raise SaltCloudSystemExit(
            'The vn_release function requires either \'data\' or a \'path\' to '
            'be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.vn.release(auth, int(vn_id), data)

    ret = {
        'action': 'vn.release',
        'released': response[0],
        'resource_id': response[1],
        'error_code': response[2],
    }

    return ret


def vn_reserve(call=None, kwargs=None):
    '''
    Reserve network addresses.

    .. versionadded:: 2016.3.0

    vn_id
        The ID of the virtual network from which to reserve addresses. Can be used
        instead of vn_name.

    vn_name
        The name of the virtual network from which to reserve addresses. Can be
        used instead of vn_id.

    path
        The path to a file defining the template of the address reservation.
        Syntax within the file can be the usual attribute=value or XML. Can be used
        instead of ``data``.

    data
        Contains the template defining the address reservation. Syntax can be the
        usual attribute=value or XML. Data provided must be wrapped in double
        quotes. Can be used instead of ``path``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f vn_reserve opennebula vn_id=3 path=/path/to/vn_reserve_file.txt
        salt-cloud -f vn_reserve opennebula vn_name=my-vn data="SIZE=10 AR_ID=8 NETWORK_ID=1"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The vn_reserve function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    vn_id = kwargs.get('vn_id', None)
    vn_name = kwargs.get('vn_name', None)
    path = kwargs.get('path', None)
    data = kwargs.get('data', None)

    if vn_id:
        if vn_name:
            log.warning(
                'Both the \'vn_id\' and \'vn_name\' arguments were provided. '
                '\'vn_id\' will take precedence.'
            )
    elif vn_name:
        vn_id = get_vn_id(kwargs={'name': vn_name})
    else:
        raise SaltCloudSystemExit(
            'The vn_reserve function requires a \'vn_id\' or a \'vn_name\' to '
            'be provided.'
        )

    if data:
        if path:
            log.warning(
                'Both the \'data\' and \'path\' arguments were provided. '
                '\'data\' will take precedence.'
            )
    elif path:
        with salt.utils.fopen(path, mode='r') as rfh:
            data = rfh.read()
    else:
        raise SaltCloudSystemExit(
            'The vn_reserve function requires a \'path\' to be provided.'
        )

    server, user, password = _get_xml_rpc()
    auth = ':'.join([user, password])
    response = server.one.vn.reserve(auth, int(vn_id), data)

    ret = {
        'action': 'vn.reserve',
        'reserved': response[0],
        'resource_id': response[1],
        'error_code': response[2],
    }

    return ret


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
                'Failed to get the data for node \'{0}\'. Remaining '
                'attempts: {1}'.format(
                    name, attempts
                )
            )

            # Just a little delay between attempts...
            time.sleep(0.5)

    return {}


def _get_xml(xml_str):
    '''
    Intrepret the data coming from opennebula and raise if it's not XML.
    '''
    try:
        xml_data = etree.XML(xml_str)
    # XMLSyntaxError seems to be only available from lxml, but that is the xml
    # library loaded by this module
    except etree.XMLSyntaxError as err:
        # opennebula returned invalid XML, which could be an error message, so
        # log it
        raise SaltCloudSystemExit('opennebula returned: {0}'.format(xml_str))
    return xml_data


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

    vm_pool = server.one.vmpool.info(auth, -2, -1, -1, -1)[1]

    vms = {}
    for vm in _get_xml(vm_pool):
        name = vm.find('NAME').text
        vms[name] = {}

        cpu_size = vm.find('TEMPLATE').find('CPU').text
        memory_size = vm.find('TEMPLATE').find('MEMORY').text

        private_ips = []
        for nic in vm.find('TEMPLATE').findall('NIC'):
            try:
                private_ips.append(nic.find('IP').text)
            except Exception:
                pass

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
