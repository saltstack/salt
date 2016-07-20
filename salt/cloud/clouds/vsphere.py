# -*- coding: utf-8 -*-
'''
vSphere Cloud Module
====================

.. note::

    .. deprecated:: Carbon

        The :py:func:`vsphere <salt.cloud.clouds.vsphere>` cloud driver has been
        deprecated in favor of the :py:func:`vmware <salt.cloud.clouds.vmware>`
        cloud driver and will be removed in Salt Carbon. Please refer to
        :doc:`Getting started with VMware </topics/cloud/vmware>` to get started
        and convert your vsphere provider configurations to use the vmware driver.

The vSphere cloud module is used to control access to VMWare vSphere.

:depends: PySphere Python module >= 0.1.8

Note: Ensure python pysphere module is installed by running following one-liner
check. The output should be 0.

.. code-block:: bash

   python -c "import pysphere" ; echo $?
   # if this fails install using
   pip install https://pysphere.googlecode.com/files/pysphere-0.1.8.zip

Use of this module only requires a URL, username and password. Set up the cloud
configuration at:

``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/vsphere.conf``:

.. code-block:: yaml

    my-vsphere-config:
      driver: vsphere
      user: myuser
      password: verybadpass
      template_user: root
      template_password: mybadVMpassword
      url: 'https://10.1.1.1:443'

Note: Your URL may or may not look like any of the following, depending on how
your VMWare installation is configured:

.. code-block:: bash

    10.1.1.1
    10.1.1.1:443
    https://10.1.1.1:443
    https://10.1.1.1:443/sdk
    10.1.1.1:443/sdk


folder
    Name of the folder that will contain the new VM. If not set, the VM will be added to
    the folder the original VM belongs to.

resourcepool
    MOR of the resourcepool to be used for the new vm. If not set, it uses the same
    resourcepool than the original vm.

datastore
    MOR of the datastore where the virtual machine should be located. If not specified,
    the current datastore is used.

host
    MOR of the host where the virtual machine should be registered.

    Id not specified:
        * if resourcepool is not specified, current host is used.
        * if resourcepool is specified, and the target pool represents a
          stand-alone host, the host is used.
        * if resourcepool is specified, and the target pool represents a
          DRS-enabled cluster, a host selected by DRS is used.
        * if resourcepool is specified and the target pool represents a cluster
          without DRS enabled, an InvalidArgument exception will be thrown.

template
    Specifies whether or not the new virtual machine should be marked as a template.
    Default is False.

template_user
    Specifies the user to access the VM. Should be

template_password
    The password with which to access the VM.

sudo
    The user to access the VM with sudo privileges.

    .. versionadded:: 2015.5.2

sudo_password
    The password corresponding to the sudo user to access the VM with sudo privileges.

    .. versionadded:: 2015.5.2
'''
from __future__ import absolute_import

# Import python libs
import pprint
import logging
import time

# Import salt libs
import salt.utils.cloud
import salt.utils.xmlutil
from salt.exceptions import SaltCloudSystemExit
from salt.utils import warn_until

# Import salt cloud libs
import salt.config as config

# Attempt to import pysphere lib
HAS_LIBS = False
try:
    from pysphere import VIServer, MORTypes, VIException
    HAS_LIBS = True
except Exception:  # pylint: disable=W0703
    pass

# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = 'vsphere'


# Only load in this module if the vSphere configurations are in place
def __virtual__():
    '''
    Check for vSphere configurations.
    '''
    if get_configured_provider() is False:
        return False

    if get_dependencies() is False:
        return False

    warn_until(
        'Carbon',
        'The vsphere driver is deprecated in favor of the vmware driver and will be removed '
        'in Salt Carbon. Please convert your vsphere provider configs to use the vmware driver.'
    )

    return __virtualname__


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ('user',)
    )


def get_dependencies():
    '''
    Warn if dependencies aren't met.
    '''
    return config.check_driver_dependencies(
        __virtualname__,
        {'pysphere': HAS_LIBS}
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
        if is_template is True:
            ret[name] = {'Name': name}
    return ret


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or 'vsphere',
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
    host = config.get_cloud_config_value(
        'host', vm_, __opts__, default=None
    )
    template = config.get_cloud_config_value(
        'template', vm_, __opts__, default=False
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
            'The following exception was thrown when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_['name'], str(exc)
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return False

    deploy_kwargs = None
    if config.get_cloud_config_value('deploy', vm_, __opts__) is True:
        deploy_kwargs = _deploy(vm_)

    ret = show_instance(name=vm_['name'], call='action')
    show_deploy_args = config.get_cloud_config_value(
        'show_deploy_args', vm_, __opts__, default=False
    )
    if show_deploy_args:
        ret['deploy_kwargs'] = deploy_kwargs

    log.info('Created Cloud VM {0[name]!r}'.format(vm_))
    log.debug(
        '{0[name]!r} VM creation details:\n{1}'.format(
            vm_, pprint.pformat(ret)
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
        transport=__opts__['transport']
    )
    return ret


def wait_for_ip(vm_):
    '''
    wait_for_ip
    '''
    def poll_ip():
        '''
        Wait for the IP address to become available
        '''
        instance = show_instance(name=vm_['name'], call='action')
        ip_addrs = instance.get('ip_address', None)

        if ip_addrs is not None:
            return ip_addrs

        time.sleep(1)
        return False

    log.debug('Pulling VM {0} for an IP address'.format(vm_['name']))
    ip_address = salt.utils.cloud.wait_for_fun(poll_ip)

    if ip_address is not False:
        log.debug('VM {0} has IP address {1}'.format(vm_['name'], ip_address))

    return ip_address


def _deploy(vm_):
    '''
    run bootstrap script
    '''
    # TODO: review salt.utils.cloud.bootstrap(vm_, __opts__)
    # TODO: review salt.utils.cloud.wait_for_ip
    ip_address = wait_for_ip(vm_)

    template_user = config.get_cloud_config_value(
        'template_user', vm_, __opts__
    )
    template_password = config.get_cloud_config_value(
        'template_password', vm_, __opts__
    )

    # new_instance = conn.get_vm_by_name(vm_['name'])
    # ret = new_instance.get_properties()
    ret = show_instance(name=vm_['name'], call='action')

    ret['ip_address'] = ip_address
    ret['username'] = template_user
    ret['password'] = template_password

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
        'minion_conf': salt.utils.cloud.minion_config(__opts__, vm_),
        'sudo': config.get_cloud_config_value(
            'sudo', vm_, __opts__, default=(template_user != 'root')
        ),
        'sudo_password': config.get_cloud_config_value(
            'sudo_password', vm_, __opts__, default=None
        ),
        'key_filename': config.get_cloud_config_value(
            'key_filename', vm_, __opts__, default=None
        )
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

    return ret['deploy_kwargs']


def _get_instance_properties(instance, from_cache=True):
    ret = {}
    properties = instance.get_properties(from_cache)
    for prop in ('guest_full_name', 'guest_id', 'memory_mb', 'name',
                 'num_cpu', 'path', 'devices', 'disks', 'files',
                 'net', 'ip_address', 'mac_address', 'hostname'):
        if prop in properties:
            ret[prop] = properties[prop]
        else:
            ret[prop] = instance.get_property(prop, from_cache)
    count = 0
    for disk in ret['disks']:  # pylint: disable=W0612
        del ret['disks'][count]['device']['_obj']
        count += 1
    for device in ret['devices']:
        if '_obj' in ret['devices'][device]:
            del ret['devices'][device]['_obj']

        # TODO: this is a workaround because the net does not return mac...?
        mac_address = ret.get('mac_address', None)
        if mac_address is None and 'macAddress' in ret['devices'][device]:
            ret['mac_address'] = ret['devices'][device]['macAddress']

    ret['status'] = instance.get_status()
    ret['tools_status'] = instance.get_tools_status()

    ret = salt.utils.cloud.simple_types_filter(ret)
    return ret


def list_nodes_full(kwargs=None, call=None):  # pylint: disable=W0613
    '''
    Return a list of the VMs that are on the provider with full details
    '''
    ret = {}
    conn = get_conn()
    nodes = conn.get_registered_vms()
    for node in nodes:
        instance = conn.get_vm_by_path(node)
        properties = _get_instance_properties(instance)
        ret[properties['name']] = properties
    return ret


def list_nodes_min(kwargs=None, call=None):  # pylint: disable=W0613
    '''
    Return a list of the nodes in the provider, with no details
    '''
    ret = {}
    conn = get_conn()
    property_names = ['name']
    result = conn._retrieve_properties_traversal(
        property_names=property_names, obj_type='VirtualMachine'
    )
    for r in result:
        for p in r.PropSet:
            if p.Name == 'name':
                ret[p.Val] = True
    return ret


def list_nodes(kwargs=None, call=None):
    '''
    Return a list of the VMs that are on the provider, with basic fields
    '''
    ret = {}
    conn = get_conn()
    property_names = ['name', 'guest.ipAddress', 'summary.config']
    result = conn._retrieve_properties_traversal(
        property_names=property_names, obj_type='VirtualMachine'
    )
    for r in result:
        vset = {
            'id': None,
            'ip_address': None,
            'cpus': None,
            'ram': None,
        }
        for p in r.PropSet:
            if p.Name == 'name':
                vset['id'] = p.Val
            if p.Name == 'guest.ipAddress':
                vset['ip_address'] = p.Val
            if p.Name == 'summary.config':
                vset['cpus'] = p.Val.NumCpu
                vset['ram'] = p.Val.MemorySizeMB
        ret[vset['id']] = vset
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
    instance = conn.get_vm_by_name(name, )
    ret = _get_instance_properties(instance)
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


def status(name, call=None):
    '''
    To check the status of a VM using its name

    CLI Example:

    .. code-block:: bash

        salt-cloud -a status vmname
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The status action must be called with -a or --action.'
        )

    conn = get_conn()
    instance = conn.get_vm_by_name(name)
    return instance.get_status()


def start(name, call=None):
    '''
    To start/power on a VM using its name

    CLI Example:

    .. code-block:: bash

        salt-cloud -a start vmname
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The start action must be called with -a or --action.'
        )

    conn = get_conn()
    instance = conn.get_vm_by_name(name)
    if instance.is_powered_on():
        ret = 'already powered on'
        log.info('VM {0} {1}'.format(name, ret))
        return ret
    try:
        log.info('Starting VM {0}'.format(name))
        instance.power_on()
    except Exception as exc:
        log.error('Could not power on VM {0}: {1}'.format(name, exc))
        return 'failed to power on'
    return 'powered on'


def stop(name, call=None):
    '''
    To stop/power off a VM using its name

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop vmname
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The stop action must be called with -a or --action.'
        )

    conn = get_conn()
    instance = conn.get_vm_by_name(name)
    if instance.is_powered_off():
        ret = 'already powered off'
        log.info('VM {0} {1}'.format(name, ret))
        return ret
    try:
        log.info('Stopping VM {0}'.format(name))
        instance.power_off()
    except Exception as exc:
        log.error('Could not power off VM {0}: {1}'.format(name, exc))
        return 'failed to power off'
    return 'powered off'


def suspend(name, call=None):
    '''
    To suspend a VM using its name

    CLI Example:

    .. code-block:: bash

        salt-cloud -a suspend vmname
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The suspend action must be called with -a or --action.'
        )

    conn = get_conn()
    instance = conn.get_vm_by_name(name)
    if instance.is_suspended():
        ret = 'already suspended'
        log.info('VM {0} {1}'.format(name, ret))
        return ret
    try:
        log.info('Suspending VM {0}'.format(name))
        instance.suspend()
    except Exception as exc:
        log.error('Could not suspend VM {0}: {1}'.format(name, exc))
        return 'failed to suspend'
    return 'suspended'


def reset(name, call=None):
    '''
    To reset a VM using its name

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reset vmname
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The reset action must be called with -a or --action.'
        )

    conn = get_conn()
    instance = conn.get_vm_by_name(name)
    if instance.is_resetting():
        ret = 'already resetting'
        log.info('VM {0} {1}'.format(name, ret))
        return ret
    try:
        log.info('Resetting VM {0}'.format(name))
        instance.reset()
    except Exception as exc:
        log.error('Could not reset VM {0}: {1}'.format(name, exc))
        return 'failed to reset'
    return 'reset'


def snapshot_list(kwargs=None, call=None):
    '''
    List virtual machines with snapshots

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f snapshot_list
    '''
    ret = {}
    vms = []

    conn = get_conn()

    qry = conn._retrieve_properties_traversal(
        property_names=['name', 'rootSnapshot'],
        obj_type="VirtualMachine"
    )

    for prop in qry:
        has_snapshots = False
        name = ""

        for i in prop.PropSet:
            if i.Name == 'rootSnapshot' and i.Val.ManagedObjectReference:
                has_snapshots = True
            if i.Name == 'name':
                name = i.Val
        if has_snapshots:
            vms.append(name)

    for vm in vms:
        _vm = conn.get_vm_by_name(vm)

        ret[vm] = {'snapshots': []}

        for snap in _vm.get_snapshots():
            ret[vm]['snapshots'] = {
                'name': snap.get_name(),
                'description': snap.get_description(),
                'created': time.strftime("%Y-%m-%d %H:%M:%S", snap.get_create_time()),
                'state': snap.get_state(),
                'path': snap.get_path()
            }

    return ret


def create_snapshot(kwargs=None, call=None):
    '''
    Create a snapshot

    @name: Name of the virtual machine to snapshot
    @snapshot: Name of the snapshot
    @description: Description of the snapshot (optional)
    @memory: Dump of the internal state of the virtual machine (optional)

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

       salt-cloud -f create_snapshot [PROVIDER] name=myvm.example.com snapshot=mysnapshot
       salt-cloud -f create_snapshot [PROVIDER] name=myvm.example.com snapshot=mysnapshot description='My Snapshot' memory=True
    '''
    if call != 'function':
        log.error(
            'The show_keypair function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'name' not in kwargs or 'snapshot' not in kwargs:
        log.error('name and snapshot are required arguments')
        return False

    ret = {}
    conn = get_conn()

    vm = conn.get_vm_by_name(kwargs['name'])

    try:
        log.info('Creating snapshot')
        vm.create_snapshot(
            kwargs['snapshot'],
            kwargs.get('description', None),
            kwargs.get('memory', False)
        )

        ret['name'] = kwargs['name']
        ret['snapshot'] = kwargs['snapshot']
        ret['comment'] = 'Snapshot created'
        ret['result'] = True
    except VIException:
        log.error('Unable to create snapshot')

        ret['name'] = kwargs['name']
        ret['snapshot'] = kwargs['snapshot']
        ret['comment'] = 'Failed to create snapshot'
        ret['result'] = False

    return ret


def delete_snapshot(kwargs=None, call=None):
    '''
    Delete snapshot

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f delete_snapshot [PROVIDER] name=myvm.example.com snapshot=mysnapshot
    '''
    if call != 'function':
        log.error(
            'The show_keypair function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'name' not in kwargs or 'snapshot' not in kwargs:
        log.error('name and snapshot are required arguments')
        return False

    conn = get_conn()

    vm = conn.get_vm_by_name(kwargs['name'])

    try:
        log.info('Deleting snapshot')
        vm.delete_named_snapshot(kwargs['snapshot'], remove_children=True)
        log.info('Snapshot deleted')
    except VIException:
        log.error('Unable to delete snapshot')
        return False

    return True
