# -*- coding: utf-8 -*-
'''
Proxmox Cloud Module
======================

.. versionadded:: 2014.7.0

The Proxmox cloud module is used to control access to cloud providers using
the Proxmox system (KVM / OpenVZ).

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or
 ``/etc/salt/cloud.providers.d/proxmox.conf``:

.. code-block:: yaml

    my-proxmox-config:
      # Proxmox account information
      user: myuser@pam or myuser@pve
      password: mypassword
      url: hypervisor.domain.tld
      provider: proxmox
      verify_ssl: True

:maintainer: Frank Klaassen <frank@cloudright.nl>
:maturity: new
:depends: requests >= 2.2.1
:depends: IPy >= 0.81
'''
from __future__ import absolute_import

# Import python libs
import copy
import time
import pprint
import logging

# Import salt libs
import salt.utils

# Import salt cloud libs
import salt.utils.cloud
import salt.config as config
from salt.exceptions import (
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout
)

# Get logging started
log = logging.getLogger(__name__)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from IPy import IP
    HAS_IPY = True
except ImportError:
    HAS_IPY = False


def __virtual__():
    '''
    Check for PROXMOX configurations
    '''
    if not (HAS_IPY and HAS_REQUESTS):
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
        __active_provider_name__ or 'proxmox',
        ('user',)
    )


url = None
ticket = None
csrf = None
verify_ssl = None


def _authenticate():
    '''
    Retrieve CSRF and API tickets for the Proxmox API
    '''
    global url, ticket, csrf, verify_ssl
    url = config.get_cloud_config_value(
        'url', get_configured_provider(), __opts__, search_global=False
    )
    username = config.get_cloud_config_value(
        'user', get_configured_provider(), __opts__, search_global=False
    ),
    passwd = config.get_cloud_config_value(
        'password', get_configured_provider(), __opts__, search_global=False
    )
    verify_ssl = config.get_cloud_config_value(
        'verify_ssl', get_configured_provider(), __opts__, search_global=False
    )
    if verify_ssl is None:
        verify_ssl = True

    connect_data = {'username': username, 'password': passwd}
    full_url = 'https://{0}:8006/api2/json/access/ticket'.format(url)

    returned_data = requests.post(
        full_url, verify=verify_ssl, data=connect_data).json()

    ticket = {'PVEAuthCookie': returned_data['data']['ticket']}
    csrf = str(returned_data['data']['CSRFPreventionToken'])


def query(conn_type, option, post_data=None):
    '''
    Execute the HTTP request to the API
    '''
    if ticket is None or csrf is None or url is None:
        log.debug('Not authenticated yet, doing that now..')
        _authenticate()

    full_url = 'https://{0}:8006/api2/json/{1}'.format(url, option)

    log.debug('{0}: {1} ({2})'.format(conn_type, full_url, post_data))

    httpheaders = {'Accept': 'application/json',
                   'Content-Type': 'application/x-www-form-urlencoded',
                   'User-Agent': 'salt-cloud-proxmox'}

    if conn_type == 'post':
        httpheaders['CSRFPreventionToken'] = csrf
        response = requests.post(full_url, verify=verify_ssl,
                                 data=post_data,
                                 cookies=ticket,
                                 headers=httpheaders)
    elif conn_type == 'put':
        httpheaders['CSRFPreventionToken'] = csrf
        response = requests.put(full_url, verify=verify_ssl,
                                data=post_data,
                                cookies=ticket,
                                headers=httpheaders)
    elif conn_type == 'delete':
        httpheaders['CSRFPreventionToken'] = csrf
        response = requests.delete(full_url, verify=verify_ssl,
                                   data=post_data,
                                   cookies=ticket,
                                   headers=httpheaders)
    elif conn_type == 'get':
        response = requests.get(full_url, verify=verify_ssl,
                                cookies=ticket)

    response.raise_for_status()

    try:
        returned_data = response.json()
        if 'data' not in returned_data:
            raise SaltCloudExecutionFailure
        return returned_data['data']
    except Exception:
        log.error('Error in trying to process JSON')
        log.error(response)


def _getVmByName(name, allDetails=False):
    '''
    Since Proxmox works based op id's rather than names as identifiers this
    requires some filtering to retrieve the required information.
    '''
    vms = get_resources_vms(includeConfig=allDetails)
    if name in vms:
        return vms[name]

    log.info('VM with name "{0}" could not be found.'.format(name))
    return False


def _getVmById(vmid, allDetails=False):
    '''
    Retrieve a VM based on the ID.
    '''
    for vm_name, vm_details in get_resources_vms(includeConfig=allDetails).items():
        if str(vm_details['vmid']) == str(vmid):
            return vm_details

    log.info('VM with ID "{0}" could not be found.'.format(vmid))
    return False


def _get_next_vmid():
    '''
    Proxmox allows the use of alternative ids instead of autoincrementing.
    Because of that its required to query what the first available ID is.
    '''
    return int(query('get', 'cluster/nextid'))


def _check_ip_available(ip_addr):
    '''
    Proxmox VMs refuse to start when the IP is already being used.
    This function can be used to prevent VMs being created with duplicate
    IP's or to generate a warning.
    '''
    for vm_name, vm_details in get_resources_vms(includeConfig=True).items():
        vm_config = vm_details['config']
        if ip_addr in vm_config['ip_address'] or vm_config['ip_address'] == ip_addr:
            log.debug('IP "{0}" is already defined'.format(ip_addr))
            return False

    log.debug('IP {0!r} is available to be defined'.format(ip_addr))
    return True


def _parse_proxmox_upid(node, vm_=None):
    '''
    Upon requesting a task that runs for a longer period of time a UPID is given.
    This includes information about the job and can be used to lookup information in the log.
    '''
    ret = {}

    upid = node
    # Parse node response
    node = node.split(':')
    if node[0] == 'UPID':
        ret['node'] = str(node[1])
        ret['pid'] = str(node[2])
        ret['pstart'] = str(node[3])
        ret['starttime'] = str(node[4])
        ret['type'] = str(node[5])
        ret['vmid'] = str(node[6])
        ret['user'] = str(node[7])
        # include the upid again in case we'll need it again
        ret['upid'] = str(upid)

        if vm_ is not None and 'technology' in vm_:
            ret['technology'] = str(vm_['technology'])

    return ret


def _lookup_proxmox_task(upid):
    '''
    Retrieve the (latest) logs and retrieve the status for a UPID.
    This can be used to verify whether a task has completed.
    '''
    log.debug('Getting creation status for upid: {0}'.format(upid))
    tasks = query('get', 'cluster/tasks')

    if tasks:
        for task in tasks:
            if task['upid'] == upid:
                log.debug('Found upid task: {0}'.format(task))
                return task

    return False


def get_resources_nodes(call=None, resFilter=None):
    '''
    Retrieve all hypervisors (nodes) available on this environment
    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_resources_nodes my-proxmox-config
    '''
    log.debug('Getting resource: nodes.. (filter: {0})'.format(resFilter))
    resources = query('get', 'cluster/resources')

    ret = {}
    for resource in resources:
        if 'type' in resource and resource['type'] == 'node':
            name = resource['node']
            ret[name] = resource

    if resFilter is not None:
        log.debug('Filter given: {0}, returning requested '
                  'resource: nodes'.format(resFilter))
        return ret[resFilter]

    log.debug('Filter not given: {0}, returning all resource: nodes'.format(ret))
    return ret


def get_resources_vms(call=None, resFilter=None, includeConfig=True):
    '''
    Retrieve all VMs available on this environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_resources_vms my-proxmox-config
    '''
    log.debug('Getting resource: vms.. (filter: {0})'.format(resFilter))
    resources = query('get', 'cluster/resources')

    ret = {}
    for resource in resources:
        if 'type' in resource and resource['type'] in ['openvz', 'qemu']:
            name = resource['name']
            ret[name] = resource

            if includeConfig:
                # Requested to include the detailed configuration of a VM
                ret[name]['config'] = get_vmconfig(
                    ret[name]['vmid'],
                    ret[name]['node'],
                    ret[name]['type']
                )

    if resFilter is not None:
        log.debug('Filter given: {0}, returning requested '
                  'resource: nodes'.format(resFilter))
        return ret[resFilter]

    log.debug('Filter not given: {0}, returning all resource: nodes'.format(ret))
    return ret


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


def avail_locations(call=None):
    '''
    Return a list of the hypervisors (nodes) which this Proxmox PVE machine manages

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-locations my-proxmox-config
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_locations function must be called with '
            '-f or --function, or with the --list-locations option'
        )

    # could also use the get_resources_nodes but speed is ~the same
    nodes = query('get', 'nodes')

    ret = {}
    for node in nodes:
        name = node['node']
        ret[name] = node

    return ret


def avail_images(call=None, location='local'):
    '''
    Return a list of the images that are on the provider

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-images my-proxmox-config
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    ret = {}
    for host_name, host_details in avail_locations().items():
        for item in query('get', 'nodes/{0}/storage/{1}/content'.format(host_name, location)):
            ret[item['volid']] = item
    return ret


def list_nodes(call=None):
    '''
    Return a list of the VMs that are managed by the provider

    CLI Example:

    .. code-block:: bash

        salt-cloud -Q my-proxmox-config
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    ret = {}
    for vm_name, vm_details in get_resources_vms(includeConfig=True).items():
        log.debug('VM_Name: {0}'.format(vm_name))
        log.debug('vm_details: {0}'.format(vm_details))

        # Limit resultset on what Salt-cloud demands:
        ret[vm_name] = {}
        ret[vm_name]['id'] = str(vm_details['vmid'])
        ret[vm_name]['image'] = str(vm_details['vmid'])
        ret[vm_name]['size'] = str(vm_details['disk'])
        ret[vm_name]['state'] = str(vm_details['status'])

        # Figure out which is which to put it in the right column
        private_ips = []
        public_ips = []

        if 'ip_address' in vm_details['config'] and vm_details['config']['ip_address'] != '-':
            ips = vm_details['config']['ip_address'].split(' ')
            for ip_ in ips:
                if IP(ip_).iptype() == 'PRIVATE':
                    private_ips.append(str(ip_))
                else:
                    public_ips.append(str(ip_))

        ret[vm_name]['private_ips'] = private_ips
        ret[vm_name]['public_ips'] = public_ips

    return ret


def list_nodes_full(call=None):
    '''
    Return a list of the VMs that are on the provider

    CLI Example:

    .. code-block:: bash

        salt-cloud -F my-proxmox-config
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    return get_resources_vms(includeConfig=True)


def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields

    CLI Example:

    .. code-block:: bash

        salt-cloud -S my-proxmox-config
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(), __opts__['query.selection'], call,
    )


def create(vm_):
    '''
    Create a single VM from a data dict

    CLI Example:

    .. code-block:: bash

        salt-cloud -p proxmox-ubuntu vmhostname
    '''
    ret = {}

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

    try:
        data = create_node(vm_)
    except Exception as exc:
        log.error(
            'Error creating {0} on PROXMOX\n\n'
            'The following exception was thrown when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_['name'], str(exc)
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return False

    ret['creation_data'] = data
    name = vm_['name']        # hostname which we know
    vmid = data['vmid']       # vmid which we have received
    host = data['node']       # host which we have received
    nodeType = data['technology']  # VM tech (Qemu / OpenVZ)

    # Determine which IP to use in order of preference:
    if 'ip_address' in vm_:
        ip_address = str(vm_['ip_address'])
    elif 'public_ips' in data:
        ip_address = str(data['public_ips'][0])  # first IP
    elif 'private_ips' in data:
        ip_address = str(data['private_ips'][0])  # first IP
    else:
        raise SaltCloudExecutionFailure  # err.. not a good idea i reckon

    log.debug('Using IP address {0}'.format(ip_address))

    # wait until the vm has been created so we can start it
    if not wait_for_created(data['upid'], timeout=300):
        return {'Error': 'Unable to create {0}, command timed out'.format(name)}

    # VM has been created. Starting..
    if not start(name, vmid, call='action'):
        log.error('Node {0} ({1}) failed to start!'.format(name, vmid))
        raise SaltCloudExecutionFailure

    # Wait until the VM has fully started
    log.debug('Waiting for state "running" for vm {0} on {1}'.format(vmid, host))
    if not wait_for_state(vmid, 'running'):
        return {'Error': 'Unable to start {0}, command timed out'.format(name)}

    ssh_username = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__, default='root'
    )
    ssh_password = config.get_cloud_config_value(
        'password', vm_, __opts__,
    )

    ret['ip_address'] = ip_address
    ret['username'] = ssh_username
    ret['password'] = ssh_password

    # Check whether we need to deploy and are on OpenVZ rather than KVM which
    # does not (yet) provide support for automatic provisioning
    if config.get_cloud_config_value('deploy', vm_, __opts__) is True and config.get_cloud_config_value('technology', vm_, __opts__) == 'openvz':
        deploy_script = script(vm_)
        deploy_kwargs = {
            'opts': __opts__,
            'host': ip_address,
            'username': ssh_username,
            'password': ssh_password,
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
            'sudo': config.get_cloud_config_value(
                'sudo', vm_, __opts__, default=(ssh_username != 'root')
            ),
            'sudo_password': config.get_cloud_config_value(
                'sudo_password', vm_, __opts__, default=None
            ),
            'tty': config.get_cloud_config_value(
                'tty', vm_, __opts__, default=False
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

        win_installer = config.get_cloud_config_value(
            'win_installer', vm_, __opts__)
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

        # Store what was used to the deploy the VM
        ret['deploy_kwargs'] = deploy_kwargs

        salt.utils.cloud.fire_event(
            'event',
            'executing deploy script',
            'salt/cloud/{0}/deploying'.format(vm_['name']),
            {'kwargs': event_kwargs},
            transport=__opts__['transport']
        )

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
    # END Install Salt role(s)

    # Report success!
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


def create_node(vm_):
    '''
    Build and submit the requestdata to create a new node
    '''
    newnode = {}

    if 'technology' not in vm_:
        vm_['technology'] = 'openvz'  # default virt tech if none is given

    if vm_['technology'] not in ['qemu', 'openvz']:
        # Wrong VM type given
        raise SaltCloudExecutionFailure

    if 'host' not in vm_:
        # Use globally configured/default location
        vm_['host'] = config.get_cloud_config_value(
            'default_host', get_configured_provider(), __opts__, search_global=False
        )

    if vm_['host'] is None:
        # No location given for the profile
        log.error('No host given to create this VM on')
        raise SaltCloudExecutionFailure

    # Required by both OpenVZ and Qemu (KVM)
    vmhost = vm_['host']
    newnode['vmid'] = _get_next_vmid()

    for prop in ('cpuunits', 'description', 'memory', 'onboot'):
        if prop in vm_:  # if the property is set, use it for the VM request
            newnode[prop] = vm_[prop]

    if vm_['technology'] == 'openvz':
        # OpenVZ related settings, using non-default names:
        newnode['hostname'] = vm_['name']
        newnode['ostemplate'] = vm_['image']

        # optional VZ settings
        for prop in ('cpus', 'disk', 'ip_address', 'nameserver', 'password', 'swap', 'poolid'):
            if prop in vm_:  # if the property is set, use it for the VM request
                newnode[prop] = vm_[prop]
    elif vm_['technology'] == 'qemu':
        # optional Qemu settings
        for prop in ('acpi', 'cores', 'cpu', 'pool'):
            if prop in vm_:  # if the property is set, use it for the VM request
                newnode[prop] = vm_[prop]

    # The node is ready. Lets request it to be added
    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': newnode},
    )

    log.debug('Preparing to generate a node using these parameters: {0} '.format(
              newnode))
    node = query('post', 'nodes/{0}/{1}'.format(vmhost, vm_['technology']), newnode)
    return _parse_proxmox_upid(node, vm_)


def show_instance(name, call=None):
    '''
    Show the details from Proxmox concerning an instance
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

    nodes = list_nodes_full()
    salt.utils.cloud.cache_node(nodes[name], __active_provider_name__, __opts__)
    return nodes[name]


def get_vmconfig(vmid, node=None, node_type='openvz'):
    '''
    Get VM configuration
    '''
    if node is None:
        # We need to figure out which node this VM is on.
        for host_name, host_details in avail_locations().items():
            for item in query('get', 'nodes/{0}/{1}'.format(host_name, node_type)):
                if item['vmid'] == vmid:
                    node = host_name

    # If we reached this point, we have all the information we need
    data = query('get', 'nodes/{0}/{1}/{2}/config'.format(node, node_type, vmid))

    return data


def wait_for_created(upid, timeout=300):
    '''
    Wait until a the vm has been created successfully
    '''
    start_time = time.time()
    info = _lookup_proxmox_task(upid)
    if not info:
        log.error('wait_for_created: No task information '
                  'retrieved based on given criteria.')
        raise SaltCloudExecutionFailure

    while True:
        if 'status' in info and info['status'] == 'OK':
            log.debug('Host has been created!')
            return True
        time.sleep(3)  # Little more patience, we're not in a hurry
        if time.time() - start_time > timeout:
            log.debug('Timeout reached while waiting for host to be created')
            return False
        info = _lookup_proxmox_task(upid)


def wait_for_state(vmid, state, timeout=300):
    '''
    Wait until a specific state has been reached on a node
    '''
    start_time = time.time()
    node = get_vm_status(vmid=vmid)
    if not node:
        log.error('wait_for_state: No VM retrieved based on given criteria.')
        raise SaltCloudExecutionFailure

    while True:
        if node['status'] == state:
            log.debug('Host {0} is now in "{1}" state!'.format(
                node['name'], state
            ))
            return True
        time.sleep(1)
        if time.time() - start_time > timeout:
            log.debug('Timeout reached while waiting for {0} to '
                      'become {1}'.format(node['name'], state))
            return False
        node = get_vm_status(vmid=vmid)
        log.debug('State for {0} is: "{1}" instead of "{2}"'.format(
                  node['name'], node['status'], state))


def destroy(name, call=None):
    '''
    Destroy a node.

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
        transport=__opts__['transport']
    )

    vmobj = _getVmByName(name)
    if vmobj is not None:
        # stop the vm
        if get_vm_status(vmid=vmobj['vmid'])['status'] != 'stopped':
            stop(name, vmobj['vmid'], 'action')

        # wait until stopped
        if not wait_for_state(vmobj['vmid'], 'stopped'):
            return {'Error': 'Unable to stop {0}, command timed out'.format(name)}

        query('delete', 'nodes/{0}/{1}'.format(
            vmobj['node'], vmobj['id']
        ))
        salt.utils.cloud.fire_event(
            'event',
            'destroyed instance',
            'salt/cloud/{0}/destroyed'.format(name),
            {'name': name},
            transport=__opts__['transport']
        )
        if __opts__.get('update_cachedir', False) is True:
            salt.utils.cloud.delete_minion_cachedir(name, __active_provider_name__.split(':')[0], __opts__)

        return {'Destroyed': '{0} was destroyed.'.format(name)}


def set_vm_status(status, name=None, vmid=None):
    '''
    Convenience function for setting VM status
    '''
    log.debug('Set status to {0} for {1} ({2})'.format(status, name, vmid))

    if vmid is not None:
        log.debug('set_vm_status: via ID - VMID {0} ({1}): {2}'.format(
                  vmid, name, status))
        vmobj = _getVmById(vmid)
    else:
        log.debug('set_vm_status: via name - VMID {0} ({1}): {2}'.format(
                  vmid, name, status))
        vmobj = _getVmByName(name)

    if not vmobj or 'node' not in vmobj or 'type' not in vmobj or 'vmid' not in vmobj:
        log.error('Unable to set status {0} for {1} ({2})'.format(
                  status, name, vmid))
        raise SaltCloudExecutionTimeout

    log.debug("VM_STATUS: Has desired info ({0}). Setting status..".format(vmobj))
    data = query('post', 'nodes/{0}/{1}/{2}/status/{3}'.format(
                 vmobj['node'], vmobj['type'], vmobj['vmid'], status))

    result = _parse_proxmox_upid(data, vmobj)

    if result is not False and result is not None:
        log.debug('Set_vm_status action result: {0}'.format(result))
        return True

    return False


def get_vm_status(vmid=None, name=None):
    '''
    Get the status for a VM, either via the ID or the hostname
    '''
    if vmid is not None:
        log.debug('get_vm_status: VMID {0}'.format(vmid))
        vmobj = _getVmById(vmid)
    elif name is not None:
        log.debug('get_vm_status: name {0}'.format(name))
        vmobj = _getVmByName(name)
    else:
        log.debug("get_vm_status: No ID or NAME given")
        raise SaltCloudExecutionFailure

    log.debug('VM found: {0}'.format(vmobj))

    if vmobj is not None and 'node' in vmobj:
        log.debug("VM_STATUS: Has desired info. Retrieving.. ({0})".format(
                  vmobj['name']))
        data = query('get', 'nodes/{0}/{1}/{2}/status/current'.format(
                     vmobj['node'], vmobj['type'], vmobj['vmid']))
        return data

    log.error('VM or requested status not found..')
    return False


def start(name, vmid=None, call=None):
    '''
    Start a node.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a start mymachine
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The start action must be called with -a or --action.'
        )

    log.debug('Start: {0} ({1}) = Start'.format(name, vmid))
    if not set_vm_status('start', name, vmid=vmid):
        log.error('Unable to bring VM {0} ({1}) up..'.format(name, vmid))
        raise SaltCloudExecutionFailure

    # xxx: TBD: Check here whether the status was actually changed to 'started'

    return {'Started': '{0} was started.'.format(name)}


def stop(name, vmid=None, call=None):
    '''
    Stop a node ("pulling the plug").

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop mymachine
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The stop action must be called with -a or --action.'
        )

    if not set_vm_status('stop', name, vmid=vmid):
        log.error('Unable to bring VM {0} ({1}) down..'.format(name, vmid))
        raise SaltCloudExecutionFailure

    # xxx: TBD: Check here whether the status was actually changed to 'stopped'

    return {'Stopped': '{0} was stopped.'.format(name)}


def shutdown(name=None, vmid=None, call=None):
    '''
    Shutdown a node via ACPI.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a shutdown mymachine
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The shutdown action must be called with -a or --action.'
        )

    if not set_vm_status('shutdown', name, vmid=vmid):
        log.error('Unable to shut VM {0} ({1}) down..'.format(name, vmid))
        raise SaltCloudExecutionFailure

    # xxx: TBD: Check here whether the status was actually changed to 'stopped'

    return {'Shutdown': '{0} was shutdown.'.format(name)}
