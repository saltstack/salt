# -*- coding: utf-8 -*-
'''
Vagrant Module
==============

The Vagrant module is designed to "vagrant up" a virtual machine as a
Salt minion.

Use of this module requires some configuration in cloud profile and provider
files as described in the
:ref:`Gettting Started with Vagrant <getting-started-with-vagrant>` documentation.
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.utils
import salt.config as config
import salt.netapi
import salt.ext.six as six
if six.PY3:
    import ipaddress
else:
    import salt.ext.ipaddress as ipaddress
from salt.exceptions import SaltCloudException, SaltCloudSystemExit

# Get logging started
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Needs no special configuration
    '''
    return True


def _get_connection_info():
    '''
    Return connection information for the passed VM data
    '''
    vm_ = get_configured_provider()

    try:
        ret = {'username': config.get_cloud_config_value(
                    'username', vm_, __opts__, default=None),
               'password': config.get_cloud_config_value(
                    'password', vm_, __opts__, default=None),
               'eauth': config.get_cloud_config_value(
                    'eauth', vm_, __opts__, default=''),
               }
    except IndexError:
        raise SaltCloudException(
            'Configuration must define salt-api "username", "password" and "eauth"')
    return ret


def avail_locations(call=None):
    '''
    This function returns a list of locations available.
    salt-cloud --list-locations my-cloud-provider
    [ vagrant will always returns an empty dictionary ]
    '''

    return {}


def avail_images(call=None):
    '''This function returns a list of images available for this cloud provider.
     vagrant will return a list of profiles.
     salt-cloud --list-images my-cloud-provider
    '''
    vm_ = get_configured_provider()
    return {'Profiles': [profile for profile in vm_['profiles']]}


def avail_sizes(call=None):
    '''
    This function returns a list of sizes available for this cloud provider.
    salt-cloud --list-sizes my-cloud-provider
    [ vagrant always returns an empty dictionary ]
    '''
    return {}


def list_nodes(call=None):
    '''
    List the nodes which have salt-cloud:driver:vagrant grains.
    salt-cloud -Q
    '''
    nodes = _list_nodes_full(call)
    return _build_required_items(nodes)


def _build_required_items(nodes):
    ret = {}
    for name, grains in nodes.items():
        if grains:
            private_ips = []
            public_ips = []
            ips = grains['ipv4'] + grains['ipv6']
            for adrs in ips:
                ip_ = ipaddress.ip_address(adrs)
                if not ip_.is_loopback:
                    if ip_.is_private:
                        private_ips.append(adrs)
                    else:
                        public_ips.append(adrs)

            ret[name] = {
                'id': grains['id'],
                'image': grains['salt-cloud']['profile'],
                'private_ips': private_ips,
                'public_ips': public_ips,
                'size': '',
                'state': 'running'
            }

    return ret


def list_nodes_full(call=None):
    '''
    List the nodes, ask all 'vagrant' minions, return dict of grains (enhanced).
    '''
    ret = _list_nodes_full(call)

    for key, grains in ret.items():  # clean up some hyperverbose grains -- everything is too much
        try:
            del grains['cpu_flags'], grains['disks'], grains['pythonpath'], grains['dns'], grains['gpus']
        except KeyError:
            pass  # ignore absence of things we are eliminating
        except TypeError:
            del ret[key]  # eliminate all reference to unexpected (None) values.

    reqs = _build_required_items(ret)
    for name in ret:
        ret[name].update(reqs[name])
    return ret


def _list_nodes_full(call=None):
    '''
    List the nodes, ask all 'vagrant' minions, return dict of grains.
    '''
    local = salt.netapi.NetapiClient(__opts__)
    cmd = {'client': 'local',
           'tgt': 'salt-cloud:driver:vagrant',
           'fun': 'grains.items',
           'arg': '',
           'tgt_type': 'grain',
           }
    cmd.update(_get_connection_info())

    log.debug('Vagrant driver sending netapi command=', repr(cmd))
    return local.run(cmd)


def list_nodes_select(call=None):
    ''' Return a list of the minions that have salt-cloud grains, with
    select fields.
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full('function'), __opts__['query.selection'], call,
    )


def show_instance(name, call=None):
    '''
    List the a single node, return dict of grains.
    '''
    local = salt.netapi.NetapiClient(__opts__)
    cmd = {'client': 'local',
           'tgt': name,
           'fun': 'grains.items',
           'arg': '',
           'tgt_type': 'glob',
           }
    cmd.update(_get_connection_info())
    ret = local.run(cmd)
    ret.update(_build_required_items(ret))
    return ret


def create(vm_):
    '''
    Provision a single machine
    '''
    machine = config.get_cloud_config_value(
        'machine', vm_, __opts__, default='')
    host = config.get_cloud_config_value(
        'host', vm_, __opts__, default=NotImplemented)
    cwd = config.get_cloud_config_value(
        'cwd', vm_, __opts__, default='/')
    runas = config.get_cloud_config_value(
        'runas', vm_, __opts__, default=os.getenv('SUDO_USER'))
    up_timeout = config.get_cloud_config_value(
        'vagrant_up_timeout', vm_, __opts__, default=180)

    log.info('sending \'vagrant up %s\' command to %s', machine, host)

    local = salt.netapi.NetapiClient(__opts__)

    args = ['vagrant up {}'.format(machine)]
    kwargs = {'cwd': cwd, 'runas': runas, 'timeout': up_timeout, 'use_vt': True}

    cmd = {'client': 'local',
           'tgt': host,
           'fun': 'cmd.run',
           'arg': args,
           'kwarg': kwargs,
           'tgt_type': 'glob',
           }
    cmd.update(_get_connection_info())
    log.debug('Vagrant driver sending netapi command=%s',repr(cmd))
    ret = local.run(cmd)
    log.debug('response ==> %s', repr(ret))

    # NOTE: the minion's Vagrantfile is expected to contain a line like...
    #  config.vm.provision "shell", inline: "ifconfig", run: "always"
    ssh_config = {'bridged_address': None}  # define a default value in a new {}
    if not 'ssh_host' in vm_:
        for line in ret[host].split('\n'):
            try:
                found_address = ''
                tokens = line.strip().split()
                # the lines we are looking for appear like:
                #   "inet addr:10.124.31.185  Bcast:10.124.31.255  Mask:255.255.248.0"
                # theoretically, the last such address we find should be the right one
                if "inet" in tokens:
                    net = tokens.index("inet") + 1
                    splits = tokens[net].split(":")
                    if splits[0] == "addr":
                        found_address = splits[1]
                    else:
                        #  inet 10.2.156.13  netmask 255.255.255.254  broadcast 10.255.255.255
                        found_address = tokens[net]
                    if found_address.startswith('127.'):
                        continue
                    ssh_config['bridged_address'] = found_address
                elif "inet6" in tokens:
                    net = tokens.index("inet6") + 1
                    if tokens[net] == "addr:":
                        # inet6 addr: fe80::a00:27ff:fe04:7aac/64 Scope:Link
                        found_address = tokens[net + 1].split('/')[0]
                    else:
                        # inet6 2001:bc8:4400:2100::22:c0d  prefixlen 127  scopeid 0x0<global>
                        found_address =  tokens[net]
                    if found_address.startswith('fe80:'):
                        continue
                    if found_address.startswith('::1'):
                        continue
                    ssh_config['bridged_address'] = found_address
                        # NOTE: IPv6 address will be used if both 6 and 4 appear
            except (IndexError, AttributeError):
                pass
        log.info('Network bridge address detected as: %s', ssh_config['bridged_address'])

    log.info('requesting vagrant ssh-config for %s', machine)
    cmd['arg'] = ['vagrant ssh-config {}'.format(machine)]
    ret = local.run(cmd)  # ask Vagrant about the configuration it just created
    log.debug('response ==> %s', repr(ret))
    reply = ret[host]

    for line in reply.split('\n'):  # build a dictionary of the text reply
        tokens = line.strip().split()
        if len(tokens) == 2:
            ssh_config[tokens[0]] = tokens[1]
    log.debug('ssh_config=%s', repr(ssh_config))

    # retrieve the Vagrant private key from the host
    identity_file_name = ssh_config['IdentityFile']
    cmd['arg'] = ['cat {}'.format(identity_file_name)]
    cmd['kwarg'] = {'output': 'json'}
    log.info('retrieving Vagrant private key from %s', host)
    ret = local.run(cmd)
    log.trace('response ==> %s', ret)
    private_key = ret[host]
    with tempfile.NamedTemporaryFile() as pks:
        pks.write(private_key)
        pks.flush()
        log.trace('wrote private key %s to %s', private_key, pks.name)
        vm_.setdefault('key_filename', pks.name)
        vm_.setdefault('ssh_username', ssh_config['User'])
        if not 'ssh_host' in vm_:
            if ssh_config['bridged_address']:
                vm_['ssh_host'] = ssh_config['bridged_address']
            else: # do not use Vagrant's detected ssh port if probe worked
                vm_['ssh_host'] = ssh_config['HostName']
                vm_.setdefault('ssh_port', ssh_config['Port'])

        log.info('Provisioning machine %s as node %s', machine, vm_['name'])
        ret = __utils__['cloud.bootstrap'](vm_, __opts__)

    return ret


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    ret = config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'vagrant',
        ('api_username', 'api_password', 'api_eauth')
    )
    try:
        # configure return dictionary as appropriate for salt-api call
        ret['username'] = ret['api_username']
        ret['password'] = ret['api_password']
        ret['eauth'] = ret['api_eauth']
    except (KeyError, TypeError):
        raise SaltCloudException('Required configuration parameter missing.')
    return ret


# noinspection PyTypeChecker
def destroy(name, call=None):
    ''' Destroy a node.

    .. versionadded:: Oxygen

    CLI Example:
    .. code-block:: bash

        salt-cloud --destroy mymachine
    '''
    if call == 'function':
        raise SaltCloudSystemExit(
            'The destroy action must be called with -d, --destroy, '
            '-a, or --action.'
        )

    opts = __opts__

    __utils__['cloud.fire_event'](
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        args={'name': name},
        sock_dir=opts['sock_dir'],
        transport=opts['transport']
    )

    local = salt.netapi.NetapiClient(opts)
    cmd = {'client': 'local',
           'tgt': name,
           'fun': 'grains.get',
           'arg': ['salt-cloud'],
           }
    cmd.update(_get_connection_info())
    my_info = local.run(cmd)
    profile_name = my_info[name]['profile']
    profile = opts['profiles'][profile_name]
    machine = profile['machine']
    host = profile['host']
    cwd = profile['cwd']
    runas = profile['runas']
    log.info('sending \'vagrant destroy %s\' command to %s', machine, host)

    local = salt.netapi.NetapiClient(opts)

    args = ['vagrant destroy {} -f'.format(machine)]
    kwargs = {'cwd': cwd, 'runas': runas}
    cmd = {'client': 'local',
           'tgt': host,
           'fun': 'cmd.run',
           'arg': args,
           'kwarg': kwargs,
           'tgt_type': 'glob',
           }
    cmd.update(_get_connection_info())
    ret = local.run(cmd)
    log.debug('response ==>%s', ret)

    __utils__['cloud.fire_event'](
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        args={'name': name},
        sock_dir=opts['sock_dir'],
        transport=opts['transport']
    )

    if opts.get('update_cachedir', False) is True:
        __utils__['cloud.delete_minion_cachedir'](name, __active_provider_name__.split(':')[0], opts)

    return {'Destroyed': '{0} was destroyed.'.format(name)}


# noinspection PyTypeChecker
def reboot(name, call=None):
    '''
    Reboot a vagrant minion.

    .. versionadded:: Oxygen

    name
        The name of the VM to reboot.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reboot vm_name
    '''
    if call != 'action':
        raise SaltCloudException(
            'The reboot action must be called with -a or --action.'
        )

    local = salt.netapi.NetapiClient(__opts__)
    cmd = {'client': 'local',
           'tgt': name,
           'fun': 'grains.get',
           'arg': ['salt-cloud'],
           }
    cmd.update(_get_connection_info())
    vm_ = cmd['vm']
    my_info = local.run(cmd)
    try:
        vm_.update(my_info[name])  # get profile name to get config value
    except (IndexError, TypeError):
        pass
    profile_name = my_info[name]['profile']
    profile = vm_['profiles'][profile_name]
    machine = profile['machine']
    host = profile['host']
    cwd = config.get_cloud_config_value(
        'cwd', vm_, __opts__, default='/')
    runas = config.get_cloud_config_value(
        'runas', vm_, __opts__, default=os.getenv('SUDO_USER'))

    log.info('sending \'vagrant reload %s\' command to %s', machine, host)

    args = ['vagrant reload {}'.format(machine)]
    kwargs = {'cwd': cwd, 'runas': runas}
    cmd['tgt'] = host
    cmd['fun'] = 'cmd.run'
    cmd['arg'] = args
    cmd['kwarg'] = kwargs
    ret = local.run(cmd)
    log.debug('response ==>%s', ret)

    return ret
