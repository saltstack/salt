# -*- coding: utf-8 -*-
'''
vSphere Cloud Module
====================

.. versionadded:: 2014.7.0

The vSphere cloud module is used to control access to VMWare vSphere.

:depends:   - PySphere Python module

Use of this module only requires a URL, username and password. Set up the cloud
configuration at:

``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/vsphere.conf``:

.. code-block:: yaml

    my-vsphere-config:
      provider: vsphere
      user: myuser
      password: verybadpass
      url: 'https://10.1.1.1:443'

folder: Name of the folder that will contain the new VM. If not set, the VM will
        be added to the folder the original VM belongs to.

resourcepool: MOR of the resourcepool to be used for the new vm. If not set, it
              uses the same resourcepool than the original vm.

datastore: MOR of the datastore where the virtual machine should be located. If
           not specified, the current datastore is used.

host: MOR of the host where the virtual machine should be registered.
    IF not specified:
        * if resourcepool is not specified, current host is used.
        * if resourcepool is specified, and the target pool represents a
          stand-alone host, the host is used.
        * if resourcepool is specified, and the target pool represents a
          DRS-enabled cluster, a host selected by DRS is used.
        * if resourcepool is specified and the target pool represents a cluster
          without DRS enabled, an InvalidArgument exception will be thrown.

template: Specifies whether or not the new virtual machine should be marked as a
          template. Default is False.
'''

# Import python libs
import pprint
import logging
import time

# Import salt libs
import salt.utils.cloud
import salt.utils.xmlutil
from salt.cloud.exceptions import SaltCloudSystemExit

# Import salt cloud libs
import salt.config as config

# Attempt to import pysphere lib
HAS_LIBS = False
try:
    from pysphere import VIServer, MORTypes
    HAS_LIBS = True
except Exception:  # pylint: disable=W0703
    pass

# Get logging started
log = logging.getLogger(__name__)


# Only load in this module if the vSphere configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for vSphere configurations.
    '''
    if get_configured_provider() is False:
        return False

    return True


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'vsphere',
        ('user',)
    )


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    server = VIServer()
    server.connect(
        config.get_cloud_config_value(
            'url', get_configured_provider(), __opts__, search_global=False
        ),
        config.get_cloud_config_value(
            'user', get_configured_provider(), __opts__, search_global=False
        ),
        config.get_cloud_config_value(
            'password', get_configured_provider(), __opts__, search_global=False
        ),
    )
    return server


def script(vm_):
    '''
    Return the script deployment object
    '''
    script_name = config.get_cloud_config_value('script', vm_, __opts__)
    if not script_name:
        script_name = 'bootstrap-salt'

    return salt.utils.cloud.os_script(
        script_name,
        vm_,
        __opts__,
        salt.utils.cloud.salt_config_to_yaml(
            salt.utils.cloud.minion_config(__opts__, vm_)
        )
    )


def avail_locations():
    '''
    Return a dict of all available VM locations on the cloud provider with
    relevant data
    '''
    conn = get_conn()
    return conn.get_resource_pools()


def avail_images():
    '''
    Return a dict of all available VM images on the cloud provider.
    '''
    ret = {}
    conn = get_conn()
    props = conn._retrieve_properties_traversal(
        property_names=['name', 'config.template'],
        from_node=None,
        obj_type=MORTypes.VirtualMachine,
    )
    for prop in props:
        is_template = None
        for item in prop.PropSet:
            if item.Name == 'name':
                name = item.Val
            elif item.Name == 'config.template':
                is_template = item.Val
        if type(is_template) is bool and is_template is True:
            ret[name] = {'Name': name}
    return ret


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
        transport=__opts__['transport']
    )

    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': vm_},
        transport=__opts__['transport']
    )

    folder = config.get_cloud_config_value(
        'folder', vm_, __opts__, default=None
    )
    resourcepool = config.get_cloud_config_value(
        'resourcepool', vm_, __opts__, default=None
    )
    datastore = config.get_cloud_config_value(
        'datastore', vm_, __opts__, default=None
    )
    host = config.get_cloud_config_value('host', vm_, __opts__, default=None)
    template = config.get_cloud_config_value(
        'template',
        vm_,
        __opts__,
        default=False
    )

    clone_kwargs = {
        'name': vm_['name'],
        'folder': folder,
        'resourcepool': resourcepool,
        'datastore': datastore,
        'host': host,
        'template': template,
    }
    log.debug('clone_kwargs are set to {0}'.format(
        pprint.pformat(clone_kwargs))
    )

    try:
        template = conn.get_vm_by_name(vm_['image'])
        new_instance = template.clone(**clone_kwargs)
        data = new_instance.get_properties()  # pylint: disable=W0612
    except Exception as exc:  # pylint: disable=W0703
        log.error(
            'Error creating {0} on vSphere\n\n'
            'The following exception was thrown by libcloud when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_['name'], exc.message
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return False

    log.debug('VM {0} is created, waiting for it to boot'.format(vm_['name']))

    def wait_for_ip():
        '''
        Wait for the IP address to become available
        '''
        instance = show_instance(name=vm_['name'], call='action')
        if 'ip_address' in instance:
            return instance['ip_address']
        time.sleep(1)
        return False

    ip_address = salt.utils.cloud.wait_for_fun(wait_for_ip)
    log.debug('Using IP address {0}'.format(ip_address))

    template_user = config.get_cloud_config_value(
        'template_user', vm_, __opts__
    )
    template_password = config.get_cloud_config_value(
        'template_password', vm_, __opts__
    )

    ret = new_instance.get_properties()
    ret['ip_address'] = ip_address
    ret['username'] = template_user
    ret['password'] = template_password

    if config.get_cloud_config_value('deploy', vm_, __opts__) is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'opts': __opts__,
            'host': ip_address,
            'username': template_user,
            'password': template_password,
            'script': deploy_script,
            'name': vm_['name'],
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
            'script_args': config.get_cloud_config_value(
                'script_args', vm_, __opts__
            ),
            'script_env': config.get_cloud_config_value(
                'script_env', vm_, __opts__
            ),
            'minion_conf': salt.utils.cloud.minion_config(__opts__, vm_)
        }

        # Store what was used to the deploy the VM
        ret['deploy_kwargs'] = deploy_kwargs

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
        win_installer = config.get_cloud_config_value(
            'win_installer', vm_, __opts__
        )
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

        salt.utils.cloud.fire_event(
            'event',
            'executing deploy script',
            'salt/cloud/{0}/deploying'.format(vm_['name']),
            {'kwargs': deploy_kwargs},
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

    log.info('Created Cloud VM {0[name]!r}'.format(vm_))
    log.debug(
        '{0[name]!r} VM creation details:\n{1}'.format(
            vm_, pprint.pformat(ret['deploy_kwargs'])
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


def list_nodes_full():
    '''
    Return a list of the VMs that are on the provider
    '''
    ret = {}
    conn = get_conn()
    nodes = conn.get_registered_vms()
    for node in nodes:
        instance = conn.get_vm_by_path(node)
        properties = salt.utils.cloud.simple_types_filter(
            instance.get_properties()
        )
        ret[properties['name']] = {}
        for prop in ('guest_full_name', 'guest_id', 'memory_mb', 'name',
                     'num_cpu', 'path', 'devices', 'disks', 'files',
                     'ip_address', 'net', 'hostname'):
            if prop in properties:
                ret[properties['name']][prop] = properties[prop]
        count = 0
        for disk in ret[properties['name']]['disks']:  # pylint: disable=W0612
            del ret[properties['name']]['disks'][count]['device']['_obj']
            count += 1
        for device in ret[properties['name']]['devices']:
            del ret[properties['name']]['devices'][device]['_obj']
        ret[properties['name']]['status'] = instance.get_status()
        ret[properties['name']]['tools_status'] = instance.get_tools_status()
    return ret


def list_nodes_min():
    '''
    Return a list of the nodes in the provider, with no details
    '''
    log.debug('function list_nodes_min()')
    ret = {}
    conn = get_conn()
    nodes = conn.get_registered_vms()
    for node in nodes:
        comps1 = node.split()
        comps2 = comps1[1].split('/')
        ret[comps2[0]] = True

    return ret


def list_nodes():
    '''
    Return a list of the VMs that are on the provider
    '''
    ret = {}
    conn = get_conn()
    nodes = conn.get_registered_vms()
    for node in nodes:
        instance = conn.get_vm_by_path(node)
        properties = salt.utils.cloud.simple_types_filter(
            instance.get_properties()
        )
        ret[properties['name']] = {
            'id': properties['name'],
            'ram': properties['memory_mb'],
            'cpus': properties['num_cpu'],
        }
        if 'ip_address' in properties:
            ret[properties['name']]['ip_address'] = properties['ip_address']
    return ret


def list_nodes_select():
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    ret = {}

    nodes = list_nodes_full()
    if 'error' in nodes:
        raise SaltCloudSystemExit(
            'An error occurred while listing nodes: {0}'.format(
                nodes['error']['Errors']['Error']['Message']
            )
        )

    for node in nodes:
        pairs = {}
        data = nodes[node]
        for key in data:
            if str(key) in __opts__['query.selection']:
                value = data[key]
                pairs[key] = value
        ret[node] = pairs

    return ret


def show_instance(name, call=None):
    '''
    Show the details from vSphere concerning a guest
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

    conn = get_conn()
    instance = conn.get_vm_by_name(name)
    ret = instance.get_properties()
    ret['status'] = instance.get_status()
    ret['tools_status'] = instance.get_tools_status()
    salt.utils.cloud.cache_node(ret, __active_provider_name__, __opts__)
    return ret


def destroy(name, call=None):  # pylint: disable=W0613
    '''
    Destroy a node.

    CLI Example:

    .. code-block:: bash

        salt-cloud --destroy mymachine
    '''
    salt.utils.cloud.fire_event(
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )

    conn = get_conn()
    instance = conn.get_vm_by_name(name)
    if instance.get_status() == 'POWERED ON':
        instance.power_off()
    try:
        instance.destroy()
    except Exception as exc:  # pylint: disable=W0703
        return exc

    salt.utils.cloud.fire_event(
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )
    if __opts__.get('update_cachedir', False) is True:
        salt.utils.cloud.delete_minion_cachedir(name, __active_provider_name__.split(':')[0], __opts__)

    return True


def list_resourcepools(kwargs=None, call=None):  # pylint: disable=W0613
    '''
    List the hosts for this VMware environment
    '''
    if call != 'function':
        log.error(
            'The list_resourcepools function must '
            'be called with -f or --function.'
        )
        return False

    conn = get_conn()
    return conn.get_resource_pools()


def list_datastores(kwargs=None, call=None):  # pylint: disable=W0613
    '''
    List the datastores for this VMware environment
    '''
    if call != 'function':
        log.error(
            'The list_datastores function must be called with -f or --function.'
        )
        return False

    conn = get_conn()
    return conn.get_datastores()


def list_hosts(kwargs=None, call=None):  # pylint: disable=W0613
    '''
    List the hosts for this VMware environment
    '''
    if call != 'function':
        log.error(
            'The list_datastores function must be called with -f or --function.'
        )
        return False

    conn = get_conn()
    return conn.get_hosts()


def list_datacenters(kwargs=None, call=None):  # pylint: disable=W0613
    '''
    List the data centers for this VMware environment
    '''
    if call != 'function':
        log.error(
            'The list_datastores function must be called with -f or --function.'
        )
        return False

    conn = get_conn()
    return conn.get_datacenters()


def list_clusters(kwargs=None, call=None):  # pylint: disable=W0613
    '''
    List the clusters for this VMware environment
    '''
    if call != 'function':
        log.error(
            'The list_datastores function must be called with -f or --function.'
        )
        return False

    conn = get_conn()
    return conn.get_clusters()


def list_folders(kwargs=None, call=None):  # pylint: disable=W0613
    '''
    List the folders for this VMWare environment
    '''
    if call != 'function':
        log.error(
            'The list_datastores function must be called with -f or --function.'
        )
        return False

    ret = []
    conn = get_conn()
    folders = conn._get_managed_objects(MORTypes.Folder)
    for folder in folders:
        ret.append(folders[folder])
    return ret
