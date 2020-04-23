# -*- coding: utf-8 -*-
"""
Kamatera Cloud Module
=========================

The Kamatera cloud module is used to control access to the Kamatera cloud.

USe of this module requires an API key and secret which you can by visiting
https://console.kamatera.com and adding a new key under API Keys.

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.

    my-kamatera-config:
      driver: kamatera
      api_client_id: xxxxxxxxxxxxx
      api_secret: yyyyyyyyyyyyyyyyyyyyyy

"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import pprint
import time
import datetime

# Import Salt Libs
import salt.config as config
from salt.exceptions import SaltCloudException, SaltCloudSystemExit

# Get logging started
log = logging.getLogger(__name__)


__virtualname__ = 'kamatera'


# Only load in this module if the Kamatera configurations are in place
def __virtual__():
    """
    Check for Linode configs.
    """
    if get_configured_provider() is False:
        return False

    return __virtualname__


def get_configured_provider():
    """
    Return the first configured instance.
    """
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ('api_client_id', 'api_secret',)
    )


def avail_images(call=None):
    """
    Return available Kamatera images for a given location.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-images my-kamatera-config --location=EU
        salt-cloud -f avail_images my-kamatera-config --location=EU
    """
    if call == 'action':
        raise SaltCloudException('The avail_images function must be called with -f or --function.')
    elif not __opts__.get('location'):
        raise SaltCloudException('A location must be specified using --location=LOCATION')
    else:
        return {
            image['id']: image['name']
            for image in _request('service/server?images=1&datacenter=%s' % __opts__['location'])
        }


def avail_sizes(call=None):
    """
    Return available Kamatera CPU types for a given location.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-sizes my-kamatera-config --location=EU
        salt-cloud -f avail_sizes my-kamatera-config --location=EU
    """
    if call == 'action':
        raise SaltCloudException('The avail_sizes function must be called with -f or --function.')
    elif not __opts__.get('location'):
        raise SaltCloudException('A location must be specified using --location=LOCATION')
    else:
        return {
            cpuType['id']: {
                k: (
                    str(v) if k in ['ramMB', 'cpuCores'] else v
                ) for k, v in cpuType.items()
                if k != 'id'
            }
            for cpuType in _request('service/server?capabilities=1&datacenter=%s' % __opts__['location'])['cpuTypes']
        }


def avail_server_options(kwargs=None, call=None):
    """
    Return available Kamatera server options for a given location.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f avail_server_options my-kamatera-config --location=EU
    """
    if call != 'function':
        raise SaltCloudException('The avail_server_options function must be called with -f or --function.')
    elif not __opts__.get('location'):
        raise SaltCloudException('A location must be specified using --location=LOCATION')
    else:
        return {
            k: (str(v) if k == 'diskSizeGB' else v)
            for k, v in _request('service/server?capabilities=1&datacenter=%s' % __opts__['location']).items()
            if k not in ['cpuTypes', 'defaultMonthlyTrafficPackage']
        }


def avail_locations(call=None):
    """
    Return available Kamatera datacenter locations.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-locations my-kamatera-config
        salt-cloud -f avail_locations my-kamatera-config
    """
    if call == 'action':
        raise SaltCloudException(
            'The avail_locations function must be called with -f or --function.'
        )
    else:
        return {
            datacenter.pop('id'): '%s, %s (%s)' % (datacenter['subCategory'], datacenter['name'], datacenter['category'])
            for datacenter in _request('service/server?datacenter=1')
        }


def create(vm_):
    """
    Create a single Kamatera server.
    """
    name = vm_['name']
    profile = vm_.get('profile')
    if (not profile or not config.is_profile_configured(
        __opts__, __active_provider_name__ or 'kamatera', vm_['profile'], vm_=vm_)
    ):
        return False

    __utils__['cloud.fire_event'](
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(name),
        args=__utils__['cloud.filter_event']('creating', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )
    log.info('Creating Cloud VM %s', name)

    def _getval(key, default=None):
        val = config.get_cloud_config_value(key, vm_, __opts__, default=None)
        if not val and default is None:
            raise SaltCloudException('missing required profile option: %s' % key)
        else:
            return val or default

    request_data = {
        "name": name,
        "password": _getval('password', '__generate__'),
        "passwordValidate": _getval('password', '__generate__'),
        'ssh-key': _getval('ssh_pub_key', ''),
        "datacenter": _getval('location'),
        "image": _getval('image'),
        "cpu": '%s%s' % (_getval('cpu_cores'), _getval('cpu_type')),
        "ram": _getval('ram_mb'),
        "disk": ' '.join([
            'size=%d' % disksize for disksize
            in [_getval('disk_size_gb')] + _getval('extra_disk_sizes_gb', [])
        ]),
        "dailybackup": 'yes' if _getval('daily_backup', False) else 'no',
        "managed": 'yes' if _getval('managed', False) else 'no',
        "network": ' '.join([','.join([
            '%s=%s' % (k, v) for k, v
            in network.items()]) for network in _getval('networks', [{'name': 'wan', 'ip': 'auto'}])]),
        "quantity": 1,
        "billingcycle": _getval('billing_cycle', 'hourly'),
        "monthlypackage": _getval('monthly_traffic_package', ''),
        "poweronaftercreate": 'yes'
    }
    response = _request('service/server', 'POST', request_data)
    if not _getval('password', ''):
        command_ids = response['commandIds']
        generated_password = response['password']
    else:
        command_ids = response
        generated_password = None
    if len(command_ids) != 1:
        raise SaltCloudException('invalid Kamatera response')
    command_id = command_ids[0]

    __utils__['cloud.fire_event'](
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(name),
        args=__utils__['cloud.filter_event']('requesting', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    command = _wait_command(command_id, _getval)
    create_log = command['log']
    try:
        created_at = datetime.datetime.strptime(command['completed'], '%Y-%m-%d %H:%M:%S')
    except Exception:
        created_at = None
    name_lines = [line for line in create_log.split("\n") if line.startswith('Name: ')]
    if len(name_lines) != 1:
        raise SaltCloudException('invalid create log: ' + create_log)
    created_name = name_lines[0].replace('Name: ', '')
    tmp_servers = _list_servers(name_regex=created_name)
    if len(tmp_servers) != 1:
        raise SaltCloudException('invalid list servers response')
    server = tmp_servers[0]
    server['extra']['create_command'] = command
    server['extra']['created_at'] = created_at
    server['extra']['generated_password'] = generated_password
    public_ips = []
    private_ips = []
    for network in server['networks']:
        if network.get('network').startswith('wan-'):
            public_ips += network.get('ips', [])
        else:
            private_ips += network.get('ips', [])
    data = dict(
        image=_getval('image'),
        name=server['name'],
        size='%s%s-%smb-%sgb' % (server['cpu_cores'], server['cpu_type'], server['ram_mb'], server['disk_size_gb']),
        state=server['state'],
        private_ips=private_ips,
        public_ips=public_ips
    )
    # Pass the correct IP address to the bootstrap ssh_host key
    vm_['ssh_host'] = data['public_ips'][0]
    # If a password wasn't supplied in the profile or provider config, set it now.
    vm_['password'] = _getval('password', generated_password)
    # Make public_ips and private_ips available to the bootstrap script.
    vm_['public_ips'] = public_ips
    vm_['private_ips'] = private_ips

    # Send event that the instance has booted.
    __utils__['cloud.fire_event'](
        'event',
        'waiting for ssh',
        'salt/cloud/{0}/waiting_for_ssh'.format(name),
        sock_dir=__opts__['sock_dir'],
        args={'ip_address': vm_['ssh_host']},
        transport=__opts__['transport']
    )

    # Bootstrap!
    ret = __utils__['cloud.bootstrap'](vm_, __opts__)
    ret.update(data)

    log.info('Created Cloud VM \'%s\'', name)
    log.debug('\'%s\' VM creation details:\n%s', name, pprint.pformat(data))
    __utils__['cloud.fire_event'](
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(name),
        args=__utils__['cloud.filter_event']('created', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    return ret


def destroy(name, call=None):
    """
    Destroys a Kamatera server by name.

    name
        The name of server to be be destroyed.

    CLI Example:

    .. code-block:: bash

        salt-cloud -d server_name
    """
    if call == 'function':
        raise SaltCloudException(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )

    __utils__['cloud.fire_event'](
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )
    return _server_operation(name, "terminate")


def list_nodes(call=None, full=False, name_regex=None):
    """
    Returns a list of servers, keeping only a brief listing.

    CLI Example:

    .. code-block:: bash

        salt-cloud -Q
        salt-cloud --query
        salt-cloud -f list_nodes my-kamatera-config
    """
    if call == 'action':
        raise SaltCloudException(
            'The list_nodes function must be called with -f or --function.'
        )
    ret = {}
    for server_res in _list_servers(name_regex=name_regex):
        public_ips, private_ips, networks = [], [], []
        for network in server_res.pop("networks"):
            networks.append(network["network"])
            if network["network"].startswith("wan-"):
                public_ips += network["ips"]
            else:
                private_ips += network["ips"]
        name = server_res.pop("name")
        server = {
            "id": server_res.pop("id"),
            "image": "",
            "size": "%s%s-%smb-%sgb" % (server_res.pop("cpu_cores"), server_res.pop("cpu_type"), server_res.pop("ram_mb"), server_res.pop("disk_size_gb")),
            "state": server_res.pop("state"),
            "private_ips": private_ips,
            "public_ips": public_ips,
        }
        if full:
            server_res["networks"] = networks
            for k, v in server_res.pop("extra", {}).items():
                server_res[k] = v
            server["extra"] = server_res
        ret[name] = server
    return ret


def list_nodes_full(call=None):
    """
    List Kamatera servers, with all available information.

    CLI Example:

    .. code-block:: bash

        salt-cloud -F
        salt-cloud --full-query
        salt-cloud -f list_nodes_full my-kamatera-config
    """
    if call == 'action':
        raise SaltCloudException(
            'The list_nodes_full function must be called with -f or --function.'
        )
    return list_nodes(full=True)


def list_nodes_min(call=None):
    """
    Return a list of the VMs that are on the provider. Only a list of VM names and
    their state is returned. This is the minimum amount of information needed to
    check for existing VMs.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_nodes_min my-kamatera-config
        salt-cloud --function list_nodes_min my-kamatera-config
    """
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_min function must be called with -f or --function.'
        )
    ret = {}
    for server in _request("/service/servers"):
        ret[server['name']] = server
    return ret


def list_nodes_select(call=None):
    """
    Return a list of the servers that are on the provider, with select fields
    """
    return __utils__['cloud.list_nodes_select'](
        list_nodes_full(), __opts__['query.selection'], call,
    )


def reboot(name, call=None):
    """
    Reboot a Kamatera server.

    .. versionadded:: 2015.8.0

    name
        The name of the server to reboot.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reboot server_name
    """
    if call != 'action':
        raise SaltCloudException(
            'The show_instance action must be called with -a or --action.'
        )
    return _server_operation(name, 'reboot')


def start(name, call=None):
    """
    Start a Kamatera server.

    .. versionadded:: 2015.8.0

    name
        The name of the server to start.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a start server_name
    """
    if call != 'action':
        raise SaltCloudException(
            'The show_instance action must be called with -a or --action.'
        )
    return _server_operation(name, 'poweron')


def stop(name, call=None):
    """
    Stop a Kamatera server.

    .. versionadded:: 2015.8.0

    name
        The name of the server to stop.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop server_name
    """
    if call != 'action':
        raise SaltCloudException(
            'The show_instance action must be called with -a or --action.'
        )
    return _server_operation(name, 'poweroff')


def show_instance(name, call=None):
    """
    Displays details about a specific Kamatera server

    .. versionadded:: 2015.8.0

    name
        Server name

    CLI Example:

    .. code-block:: bash

        salt-cloud -a show_instance server_name
    """
    if call != 'action':
        raise SaltCloudException(
            'The show_instance action must be called with -a or --action.'
        )
    return list_nodes(full=True, name_regex=name)[name]


def _request(path, method='GET', request_data=None):
    """Make a web call to the Kamatera API."""
    vm_ = get_configured_provider()
    api_client_id = config.get_cloud_config_value(
        'api_client_id', vm_, __opts__, search_global=False,
    )
    api_secret = config.get_cloud_config_value(
        'api_secret', vm_, __opts__, search_global=False,
    )
    api_url = config.get_cloud_config_value(
        'api_url', vm_, __opts__, search_global=False, default='https://cloudcli.cloudwm.com',
    )
    url = api_url.strip('/') + '/' + path.strip('/')
    headers = dict(AuthClientId=api_client_id, AuthSecret=api_secret, Accept='application/json')
    headers['Content-Type'] = 'application/json'
    headers['X-CLOUDCLI-STATUSINJSON'] = 'true'
    result = __utils__['http.query'](
        url,
        method,
        data=__utils__['json.dumps'](request_data) if request_data is not None else None,
        header_dict=headers,
        decode=True,
        decode_type='json',
        text=True,
        status=True,
        opts=__opts__,
    )
    if result['status'] != 200 or result.get('error') or not result.get('dict'):
        if result.get("res"):
            logging.error(result["res"])
        raise SaltCloudException(result.get('error') or 'Unexpected response from Kamatera API')
    elif result['dict']['status'] != 200:
        try:
            message = result['dict']['response'].pop('message')
        except Exception:
            message = 'Unexpected response from Kamatera API (status=%s)' % result['dict']['status']
        logging.error(result['dict']['response'])
        raise SaltCloudException(message)
    else:
        return result['dict']['response']


def _get_command_status(command_id):
    """Get a Kamatera command status"""
    response = _request('/service/queue?id=' + str(command_id))
    if len(response) != 1:
        raise SaltCloudException('invalid response for command id ' + str(command_id))
    return response[0]


def _wait_command(command_id, _getval=None):
    """Wait for Kamatera command to complete and return the status"""
    if not _getval:
        _getval = lambda key, default: config.get_cloud_config_value(key, {}, __opts__, default)
    wait_poll_interval_seconds = _getval('wait_poll_interval_seconds', 2)
    wait_timeout_seconds = _getval('wait_timeout_seconds', 600)
    start_time = datetime.datetime.now()
    time.sleep(wait_poll_interval_seconds)
    while True:
        max_time = start_time + datetime.timedelta(seconds=wait_timeout_seconds)
        if max_time < datetime.datetime.now():
            raise SaltCloudException('Timeout waiting for command (timeout_seconds=%s, command_id=%s)' % (str(wait_timeout_seconds), str(command_id)))
        time.sleep(wait_poll_interval_seconds)
        command = _get_command_status(command_id)
        status = command.get('status')
        if status == 'complete':
            return command
        elif status == 'error':
            raise SaltCloudException('Command failed: ' + command.get('log'))


def _list_servers(name_regex=None, names=None):
    """list Kamatera servers base on regex of server names or specific list of names"""
    request_data = {'allow-no-servers': True}
    if names:
        servers = []
        for name in names:
            for server in _list_servers(name_regex=name):
                servers.append(server)
        return servers
    else:
        if not name_regex:
            name_regex = '.*'
        request_data['name'] = name_regex
        res = _request('/service/server/info', method='POST', request_data=request_data)
        return list(map(_get_server, res))


def _get_server(server):
    """get Kamatera server details in a standard structure"""
    server_cpu = server.pop('cpu')
    server_disk_sizes = server.pop('diskSizes')
    res_server = dict(
        id=server.pop('id'),
        name=server.pop('name'),
        state='running' if server.pop('power') == 'on' else 'stopped',
        datacenter=server.pop('datacenter'),
        cpu_type=server_cpu[-1],
        cpu_cores=int(server_cpu[:-1]),
        ram_mb=int(server.pop('ram')),
        disk_size_gb=int(server_disk_sizes[0]),
        extra_disk_sizes_gb=list(map(int, server_disk_sizes[1:])),
        networks=server.pop('networks'),
        daily_backup=server.pop('backup') == "1",
        managed=server.pop('managed') == "1",
        billing_cycle=server.pop('billing'),
        monthly_traffic_package=server.pop('traffic'),
        price_monthly_on=server.pop('priceMonthlyOn'),
        price_hourly_on=server.pop('priceHourlyOn'),
        price_hourly_off=server.pop('priceHourlyOff')
    )
    res_server['extra'] = server
    return res_server


def _server_operation(name, operation):
    """Run custom operations on the server"""
    state = _list_servers(name)[0]["state"]
    if operation != "terminate" and state not in ["stopped", "running"]:
        raise SaltCloudException("Invalid state for %s operation: %s" % (operation, state))
    if (
        (operation == "poweron" and state == "stopped")
        or (operation == "poweroff" and state == "running")
        or (operation == "reboot" and state == "running")
        or operation == "terminate"
    ):
        request_data = {'name': name}
        if operation == 'terminate':
            request_data['force'] = True
        command_id = _request('/service/server/%s' % operation, 'POST', request_data)[0]
        _wait_command(command_id)
        state = "destroyed" if operation == "terminate" else _list_servers(name)[0]["state"]
    return {
        "state": state,
        "action": {"poweron": "start", "poweroff": "stop", "terminate": "destroy"}.get(operation, operation),
        "success": (
            ((operation == "reboot" or operation == "poweron") and state == "running")
            or (operation == "poweroff" and state == "stopped")
            or operation == "terminate"
        )
    }
