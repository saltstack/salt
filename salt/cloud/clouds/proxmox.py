# -*- coding: utf-8 -*-
'''
Proxmox Cloud Module
======================

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

:maintainer: Frank Klaassen <frank@cloudright.nl>
:maturity: new
:depends: json >= 2.0.9      
:depends: requests >= 2.2.1
:depends: IPy >= 0.81
'''

# Import python libs
import copy
import time
import pprint
import urllib
import urllib2
import logging

# Import salt libs
import salt.utils
from salt._compat import ElementTree as ET

# Import salt cloud libs
import salt.utils.cloud
import salt.config as config
from salt.cloud.exceptions import (
    SaltCloudNotFound,
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout
)

# Get logging started
log = logging.getLogger(__name__)

# Only load in this module if the PROXMOX configurations are in place
def __virtual__():
    '''
    Check for PROXMOX configurations
    '''
    if get_configured_provider() is False:
        log.debug(
            'There is no Proxmox cloud provider configuration available. '
            'Not loading module.'
        )
        return False

    log.debug('Loading Proxmox cloud module')    
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

#############################################################################################################
import requests
import json
from IPy import IP

url = None
ticket = None
csrf = None

def __authenticate():
    global url, ticket, csrf
    url = config.get_cloud_config_value(
        'url', get_configured_provider(), __opts__, search_global=False
    )
    username=config.get_cloud_config_value(
        'user', get_configured_provider(), __opts__, search_global=False
    ),
    passwd=config.get_cloud_config_value(
        'password', get_configured_provider(), __opts__, search_global=False
    )

    connect_data = { "username":username, "password":passwd }
    full_url = "https://%s:8006/api2/json/access/ticket" % (url)

    returned_data = requests.post(full_url,verify=False,data=connect_data).json()

    ticket = {'PVEAuthCookie':returned_data['data']['ticket']}
    csrf = str( returned_data['data']['CSRFPreventionToken'] )


def query(conn_type, option, post_data=None):
    if ticket is None or csrf is None or url is None:
        log.debug('Not authenticated yet, doing that now..')
        __authenticate()

    full_url = "https://%s:8006/api2/json/%s" % (url,option)

    log.debug("%s: %s (%s)\n" % (conn_type, full_url, post_data))

    httpheaders = {'Accept':'application/json','Content-Type':'application/x-www-form-urlencoded', 'User-Agent': 'salt-cloud-proxmox'}

    if conn_type == "post":
        httpheaders['CSRFPreventionToken'] = csrf
        response = requests.post(full_url, verify=False, 
                                      data = post_data, 
                                      cookies = ticket,
                                      headers = httpheaders)
    elif conn_type == "put":
        httpheaders['CSRFPreventionToken'] = csrf
        response = requests.put(full_url, verify=False, 
                                      data = post_data, 
                                      cookies = ticket,
                                      headers = httpheaders)
    elif conn_type == "delete":
        httpheaders['CSRFPreventionToken'] = csrf
        response = requests.delete(full_url, verify=False, 
                                      data = post_data, 
                                      cookies = ticket,
                                      headers = httpheaders)
    elif conn_type == "get":
        response = requests.get (full_url, verify=False, 
                                      cookies = ticket)

    response.raise_for_status()

    try:
        returned_data = response.json()
        if 'data' not in returned_data:
            raise RuntimeError
        log.debug('Received: %s' % returned_data)
        return returned_data['data']
    except:
        print("Error in trying to process JSON")
        print(response)

#############################################################################################################
def __getVmByName(name,allDetails=False):    
    # First try OpenVZ
    log.debug('__getVmByName: %s - OpenVZ?' % name)
    nodes = list_nodes(nodeType='openvz',fullInfo=False)
    if nodes and name in nodes:
        return nodes[name]

    # Not found. Try Qemu (KVM)
    log.debug('__getVmByName: %s - KVM?' % name)
    nodes = list_nodes(nodeType='qemu',fullInfo=False)
    if nodes and name in nodes:
        return nodes[name]
        
    log.debug('__getVmByName: %s. Neither' % name)
    return False

def __getVmById(vmid, nodeType=None):
    for host in avail_locations():
        #node = host['node']
        node = host # include full node details in the response
        if nodeType is not None: #If the nodetype is given we only retrieve data for that one
            log.debug('__getVmById: %s / %s' % (vmid,nodeType,))
            data = query('get','nodes/%s/%s/%s/status/current' % (node['node'], nodeType, vmid,))
            if data:
                data['node'] = node
                data['vmid'] = vmid
                return data 
        else: #otherwise we'll have to loop trough all available virtualisation systems offered
            for nodeType in ['openvz', 'qemu']:
                log.debug('__getVmById loop: %s / %s' % (vmid,nodeType,))
                data = query('get','nodes/%s/%s/%s/status/current' % (node['node'], nodeType, vmid,))
                if data:
                    data['node'] = node
                    data['vmid'] = vmid
                    return data 
    return None

def __get_next_vmid():
    return int( query('get','cluster/nextid') )

def __get_resources( typeFilter=None ):
    log.debug('Getting resources.. (filter: %s)' % type)
    resources = query('get', 'cluster/resources' )

    if resources and typeFilter is not None:
        return resources

    # Filtering required
    ret = []
    for resource in resources:
        if resource['type'] == typeFilter:
            ret.append( resource )

    return ret

def __parse_proxmox_upid( node, vm_=None):
    ret = {}
    
    upid = node

    # Parse node response
    node = node.split(':')
    if node[0] == 'UPID':
        ret['node']         = str( node[1] )
        ret['pid']          = str( node[2] )
        ret['pstart']       = str( node[3] )
        ret['starttime']    = str( node[4] )
        ret['type']         = str( node[5] )
        ret['vmid']         = str( node[6] )
        ret['user']         = str( node[7] )
        ret['upid']         = str( upid ) # include the upid again in case we'll need it again

        if vm_ is not None and 'technology' in vm_:
            ret['technology']   = str( vm_['technology'] )

    return ret

def __get_creation_info( upid ):
    log.debug('Getting creation status for upid: %s' % (upid,))    
    tasks = query('get', 'cluster/tasks' )

    if tasks:
        for task in tasks:
            if task['upid'] == upid:
                log.debug('Found upid task: %s' % (task,))    
                return task

    return False

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
    Return a list of the hypervisors (nodes) which this ProxmoxPVE machine manages
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_locations function must be called with '
            '-f or --function, or with the --list-locations option'
        )

    return query('get','nodes')

def avail_images(call=None,location='local',type='vztpl'):
    '''
    Return a list of the images that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    ret = {}
    for host in avail_locations():
        for item in query('get','nodes/%s/storage/%s/content' % (host['node'],location)):
            ret[item['volid']] = item
    return ret

def list_nodes(call=None,nodeType=None,fullInfo=True,allDetails=False):
    '''
    Return a list of the VMs that are managed by the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    ret = {}
    for host in avail_locations():
        if nodeType is not None: #If the nodetype is given we only retrieve data for that one
            for vm in query('get','nodes/%s/%s' % (host['node'], nodeType,)):
                name = vm['name']
                ret[name] = __nodeResponse(vm, host, nodeType, fullInfo, allDetails)
        else: #otherwise we'll have to loop trough all available virtualisation systems offered
            for nodeType in ['openvz', 'qemu']:
                for vm in query('get','nodes/%s/%s' % (host['node'], nodeType,)):
                    name = vm['name']
                    ret[name] = __nodeResponse(vm, host, nodeType, fullInfo, allDetails)

    return ret

def __nodeResponse(vm, host, nodeType,fullInfo=True,allDetails=False):
    ret = {}

    if fullInfo is False:
        log.debug("Basic info requested for node")
        ret = vm
        ret['node'] = host
    else:
        log.debug("Full info requested for node")
        node = get_vmconfig(vm['vmid'], host['node'], nodeType)

        ret = {
            'id': str(vm['vmid']),
            'image': str(node['ostemplate']),
            'size': str(node['disk']),
            'state': str(vm['status']),
        }

        # Figure out which is which to put it in the right column
        private_ips = []
        public_ips  = []

        if 'ip_address' in node and node['ip_address'] != '-':
            ips = node['ip_address'].split(' ')
            for ip in ips:
                if IP(ip).iptype() == 'PRIVATE':
                    private_ips.append( str(ip) )
                else:
                    public_ips.append( str(ip) )
            
        ret['private_ips']  = private_ips
        ret['public_ips']   = public_ips
        ret['node'] = host

        if allDetails is True:
            # Include more details            
            log.debug("More details requested for node")

            # Grab basic vm infos
            for prop in ('netout', 'netin', 'type', 'diskread', 'diskwrite'):
                ret[prop] = str( vm[prop] )

            # Grab detailed node infos
            for prop in ('cpuunits', 'cpus', 'memory', 'swap'):
                ret[prop] = str( node[prop] )

    return ret

def list_nodes_full(call=None,nodeType=None):
    # todo: append more information we might be able to use here.
    nodes = list_nodes(call,nodeType,True,True)

    return nodes

def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(), __opts__['query.selection'], call,
    )    

def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    ret = {}
    deploy = config.get_cloud_config_value('deploy', vm_, __opts__)
    if deploy is True and salt.utils.which('sshpass') is None:
        raise SaltCloudSystemExit(
            'Cannot deploy salt in a VM if the \'sshpass\' binary is not '
            'present on the system.'
        )

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
    #log.debug('VM Data: %s' % vm_)

    try:
        data = create_node(vm_)
    except Exception as exc:
        log.error(
            'Error creating {0} on PROXMOX\n\n'
            'The following exception was thrown when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_['name'], exc.message
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return False

    ret['creation_data'] = data
    name        = vm_['name']        # hostname which we know
    vmid        = data['vmid']       # vmid which we have received
    host        = data['node']       # host which we have received
    nodeType    = data['technology'] # VM tech (Qemu / OpenVZ)

    # wait until the vm has been created so we can start it
    if not wait_for_created(data['upid'], timeout=300):
        return {'Error': 'Unable to create {0}, command timed out'.format(name)}

    # VM has been created. Starting..
    if not start(name, vmid, call='action'):
        log.error('Node %s (%s) failed to start!' % (name, vmid,))
        raise SaltCloudExecutionFailure

    # Wait until the VM has fully started
    log.debug('Waiting for state "running" for vm %s (%s)' % (vmid, host,))
    if not wait_for_state(vmid, host, nodeType, 'running'):
        return {'Error': 'Unable to start {0}, command timed out'.format(name)}

    log.debug("!!! VM is running !!!")

    # Handle IPS
    if 'ip_address' in vm_:
        ip_address = str( vm_['ip_address'] )
    elif 'public_ips' in data:
        ip_address = str( data['public_ips'][0] ) # first IP
    elif 'private_ips' in data:
        ip_address = str( data['private_ips'][0] ) # first IP        
    else:
        raise SaltCloudExecutionFailure  #err.. not a good idea i reckon
    # END handle IP

    ### START Install Salt role(s)
    log.debug('Using IP address {0}'.format(ip_address))

    ssh_username = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__, default='root'
    )
    ssh_password = config.get_cloud_config_value(
        'password', vm_, __opts__
    )

    ret['ip_address'] = ip_address
    ret['username'] = ssh_username
    ret['password'] = ssh_password    

    if config.get_cloud_config_value('deploy', vm_, __opts__) is True:
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

         # No windows support
#        win_installer = config.get_cloud_config_value('win_installer', vm_, __opts__)
#        if win_installer:
#            deploy_kwargs['win_installer'] = win_installer
#            minion = salt.utils.cloud.minion_config(__opts__, vm_)
#            deploy_kwargs['master'] = minion['master']
#            deploy_kwargs['username'] = config.get_cloud_config_value(
#                'win_username', vm_, __opts__, default='Administrator'
#            )
#            deploy_kwargs['password'] = config.get_cloud_config_value(
#                'win_password', vm_, __opts__, default=''
#            )

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

        deployed = False
#        if win_installer:
#            deployed = salt.utils.cloud.deploy_windows(**deploy_kwargs)
#        else:
        deployed = salt.utils.cloud.deploy_script(**deploy_kwargs)

        if deployed:
            log.info('Salt installed on {0}'.format(vm_['name']))
        else:
            log.error(
                'Failed to start Salt on Cloud VM {0}'.format(
                    vm_['name']
                )
            )

    ### END Install Salt role(s)

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
        vm_['technology'] = 'openvz' # default virt tech if none is given

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
    vmhost                 = vm_['host']
    newnode['vmid']         = __get_next_vmid()

    for prop in ('cpuunits', 'description', 'memory', 'onboot'):
        if prop in vm_: # if the propery is set, use it for the VM request
            newnode[prop] = vm_[prop]

    if vm_['technology'] == 'openvz':
        # OpenVZ related settings, using non-default names:
        newnode['hostname']     = vm_['name']
        newnode['ostemplate']   = vm_['image']
        
        # optional VZ settings
        for prop in ('cpus', 'disk', 'ip_address', 'nameserver', 'password', 'swap', 'poolid'):
            if prop in vm_: # if the propery is set, use it for the VM request
                newnode[prop] = vm_[prop]
    elif vm_['technology'] == 'qemu':
        # optional Qemu settings
        for prop in ('acpi', 'cores', 'cpu', 'pool'):
            if prop in vm_: # if the propery is set, use it for the VM request
                newnode[prop] = vm_[prop]

    # The node is ready. Lets request it to be added
    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': newnode},
    )

    log.debug("Preparing to generate a node using these parameters: %s " % newnode )
    node = query('post','nodes/%s/%s' % (vmhost, vm_['technology']), newnode)
    return __parse_proxmox_upid( node, vm_ ) 

def show_instance(name, call=None, type=None):
    '''
    Show the details from Proxmox concerning an instance
    ''' 
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )        

    nodes = list_nodes_full()
    return nodes[name]

def get_vmconfig(vmid, node=None, nodeType='openvz'):
    '''
    Get VM configuration
    ''' 
    if node is None:
        # We need to figure out which node this VM is on.
        for host in avail_locations():
            for item in query('get','nodes/%s/%s' % (host['node'],nodeType)):
                if item['vmid'] == vmid:
                    node = host['node']

    if node is None:
        raise Exception

    # If we reached this point, we have all the information we need    
    data = query('get', 'nodes/%s/%s/%s/config' % (node,nodeType,vmid) )

    return data    

def wait_for_created(upid, timeout=300):
    '''
    Wait until a the vm has been created succesfully
    '''
    start_time = time.time()
    info = __get_creation_info(upid)
    if not info:
        raise SaltCloudExecutionFailure

    while True:
        if 'status' in info and info['status'] == 'OK':
            log.debug('Host has been created!')
            return True
        time.sleep(3) # Little more patience, we're not in a hurry
        if time.time() - start_time > timeout:
            log.debug('Timeout reached while waiting for host to be created')
            return False
        info = __get_creation_info( upid )

def wait_for_state(vmid, node, nodeType, state, timeout=300):
    '''
    Wait until a specific state has been reached on  a node
    '''
    start_time = time.time()
    node = get_vm_status( vmid=vmid, host=node, nodeType=nodeType )
    if not node:
        raise SaltCloudExecutionFailure

    while True:
        if node['status'] == state:
            log.debug('Host %s is now in "%s" state!' % (node['name'], state,))
            return True
        time.sleep(1)
        if time.time() - start_time > timeout:
            log.debug('Timeout reached while waiting for %s to become %s' % (node['name'], state,))
            return False
        node = get_vm_status( vmid=vmid, host=node, nodeType=nodeType )
        log.debug('State for %s is: "%s" instead of "%s"' % (node['name'], node['status'], state,))

def destroy(name, call=None):
    '''
    Destroy a node.

    CLI Example::

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

    vm = __getVmByName(name)
    if vm is not None:
        query('delete','nodes/%s/%s' % (vm['host'],vm['type'], vm['id']))
        salt.utils.cloud.fire_event(
            'event',
            'destroyed instance',
            'salt/cloud/{0}/destroyed'.format(name),
            {'name': name},
            transport=__opts__['transport']
        )

        return {'Destroyed': '{0} was destroyed.'.format(name)}        

# Convenience function for setting VM status
def set_vm_status(status, name=None, vmid=None):
    log.debug('Set status to %s for %s (%s)' % (status,name,vmid,))

    if vmid is not None:
        log.debug('set_vm_status: via id - VMID %s (%s): %s' % (vmid, name, status,))
        vm = __getVmById(vmid)
    else:
        log.debug('set_vm_status: via name - VMID %s (%s): %s' % (vmid, name, status,))
        vm = __getVmByName(name)
    
    log.debug("set_vm_status VM: %s" % vm)

#    if vm is None or vm['node'] is None:
    if vm is None or 'node' not in vm or 'node' not in vm['node']:
        log.error('VM is: %s or node not in vm:' % vm)
        raise SaltCloudExecutionTimeout

    log.debug("VM_STATUS: Has desired info. Setting status..") 
    data = query('post', 'nodes/%s/%s/%s/status/%s' % (vm['node']['node'], vm['type'], vm['vmid'], status) )    

    result = __parse_proxmox_upid( data, vm )

    if result is not False and result is not None:
        log.debug('Set_vm_status action result: %s' % result)        
        return True

    return False

def get_vm_status(vmid=None, name=None, host=None, nodeType=None):

    if vmid is not None:
        log.debug('get_vm_status: VMID %s' % vmid)
        vm = __getVmById(vmid)
    elif name is not None:
        log.debug('get_vm_status: name %s' % name)
        vm = __getVmByName(name)
    else:
        log.debug("get_vm_status: No ID or NAME given")
        raise SaltCloudExecutionFailure

    log.debug('VM found: %s' % vm)
    
    if vm is not None and 'node' in vm and 'node' in vm['node']:
        log.debug("VM_STATUS: Has desired info. Retrieving.. (%s)" % vm['name'])
        data = query('get', 'nodes/%s/%s/%s/status/current' % (vm['node']['node'],vm['type'],vm['vmid']) )    
        return data

    log.error('VM or requested status not found..')
    return False

def start(name, vmid=None, call=None):
    '''
    Start a node.

    CLI Example::

        salt-cloud -a start mymachine
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The start action must be called with -a or --action.'
        )

    log.debug('Start: %s (%s) = Start' % (name,vmid,))
    if not set_vm_status('start', name, vmid=vmid):
        log.error('Unable to bring vm %s (%s) up..' % (name, vmid))
        raise SaltCloudExecutionFailure

    return {'Started': '{0} was started.'.format(name)}

def stop(name, vmid=None, call=None):
    '''
    Stop a node ("pulling the plug").

    CLI Example::

        salt-cloud -a stop mymachine
    ''' 
    if call != 'action':
        raise SaltCloudSystemExit(
            'The stop action must be called with -a or --action.'
        )

    if not set_vm_status('stop', name, vmid=vmid):
        log.error('Unable to bring vm %s (%s) down..' % (name, vmid))
        raise SaltCloudExecutionFailure

    return {'Stopped': '{0} was stopped.'.format(name)}

def shutdown(name=None, vmid=None, call=None):
    '''
    Shutdown a node via ACPI.

    CLI Example::

        salt-cloud -a shutdown mymachine
    ''' 
    if call != 'action':
        raise SaltCloudSystemExit(
            'The shutdown action must be called with -a or --action.'
        )

    if not set_vm_status('shutdown', name, vmid=vmid):
        log.error('Unable to shut vm %s (%s) down..' % (name, vmid))
        raise SaltCloudExecutionFailure

    return {'Shutdown': '{0} was shutdown.'.format(name)}
