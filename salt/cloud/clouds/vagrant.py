# -*- coding: utf-8 -*-
'''
Vagrant Cloud Driver
====================

The Vagrant cloud is designed to "vagrant up" a virtual machine as a
Salt minion.

Use of this module requires some configuration in cloud profile and provider
files as described in the
:ref:`Getting Started with Vagrant <getting-started-with-vagrant>` documentation.

.. versionadded:: 2018.3.0


'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os
import tempfile

# Import salt libs
import salt.utils
import salt.config as config
import salt.client
import salt.ext.six as six
if six.PY3:
    import ipaddress
else:
    import salt.ext.ipaddress as ipaddress
from salt.exceptions import SaltCloudException, SaltCloudSystemExit, \
    SaltInvocationError

# Get logging started
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Needs no special configuration
    '''
    return True


def avail_locations(call=None):
    r'''
    This function returns a list of locations available.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-locations my-cloud-provider

        # \[ vagrant will always returns an empty dictionary \]

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
    r'''
    This function returns a list of sizes available for this cloud provider.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-sizes my-cloud-provider

        # \[ vagrant always returns an empty dictionary \]

    '''
    return {}


def list_nodes(call=None):
    '''
    List the nodes which have salt-cloud:driver:vagrant grains.

    CLI Example:

    .. code-block:: bash

        salt-cloud -Q
    '''
    nodes = _list_nodes(call)
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

    CLI Example:

    .. code-block:: bash

        salt-call -F
    '''
    ret = _list_nodes(call)

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


def _list_nodes(call=None):
    '''
    List the nodes, ask all 'vagrant' minions, return dict of grains.
    '''
    local = salt.client.LocalClient()
    ret = local.cmd('salt-cloud:driver:vagrant', 'grains.items', '', tgt_type='grain')
    return ret


def list_nodes_select(call=None):
    '''
    Return a list of the minions that have salt-cloud grains, with
    select fields.
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full('function'), __opts__['query.selection'], call,
    )


def show_instance(name, call=None):
    '''
    List the a single node, return dict of grains.
    '''
    local = salt.client.LocalClient()
    ret = local.cmd(name, 'grains.items', '')
    reqs = _build_required_items(ret)
    ret[name].update(reqs[name])
    return ret


def _get_my_info(name):
    local = salt.client.LocalClient()
    return local.cmd(name, 'grains.get', ['salt-cloud'])


def create(vm_):
    '''
    Provision a single machine

    CLI Example:

    .. code-block:: bash

        salt-cloud -p my_profile new_node_1

    '''
    name = vm_['name']
    machine = config.get_cloud_config_value(
        'machine', vm_, __opts__, default='')
    vm_['machine'] = machine
    host = config.get_cloud_config_value(
        'host', vm_, __opts__, default=NotImplemented)
    vm_['cwd'] = config.get_cloud_config_value(
        'cwd', vm_, __opts__, default='/')
    vm_['runas'] = config.get_cloud_config_value(
        'vagrant_runas', vm_, __opts__, default=os.getenv('SUDO_USER'))
    vm_['timeout'] = config.get_cloud_config_value(
        'vagrant_up_timeout', vm_, __opts__, default=300)
    vm_['vagrant_provider'] = config.get_cloud_config_value(
        'vagrant_provider', vm_, __opts__, default='')
    vm_['grains'] = {'salt-cloud:vagrant': {'host': host, 'machine': machine}}

    log.info('sending \'vagrant.init %s machine=%s\' command to %s', name, machine, host)

    local = salt.client.LocalClient()
    ret = local.cmd(host, 'vagrant.init', [name], kwarg={'vm': vm_, 'start': True})
    log.info('response ==> %s', ret[host])

    network_mask = config.get_cloud_config_value(
        'network_mask', vm_, __opts__, default='')
    if 'ssh_host' not in vm_:
        ret = local.cmd(host,
                        'vagrant.get_ssh_config',
                        [name],
                        kwarg={'network_mask': network_mask,
                                'get_private_key': True})[host]
    with tempfile.NamedTemporaryFile() as pks:
        if 'private_key' not in vm_ and ret and ret.get('private_key', False):
            pks.write(ret['private_key'])
            pks.flush()
            log.debug('wrote private key to %s', pks.name)
            vm_['key_filename'] = pks.name
        if 'ssh_host' not in vm_:
            try:
                vm_.setdefault('ssh_username', ret['ssh_username'])
                if ret.get('ip_address'):
                    vm_['ssh_host'] = ret['ip_address']
                else:  # if probe failed or not used, use Vagrant's reported ssh info
                    vm_['ssh_host'] = ret['ssh_host']
                    vm_.setdefault('ssh_port', ret['ssh_port'])
            except (KeyError, TypeError):
                raise SaltInvocationError(
                    'Insufficient SSH addressing information for {}'.format(name))

        log.info('Provisioning machine %s as node %s using ssh %s',
                 machine, name, vm_['ssh_host'])
        ret = __utils__['cloud.bootstrap'](vm_, __opts__)
        return ret


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    ret = config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'vagrant',
        ''
        )
    return ret


# noinspection PyTypeChecker
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
    my_info = _get_my_info(name)
    if my_info:
        profile_name = my_info[name]['profile']
        profile = opts['profiles'][profile_name]
        host = profile['host']
        local = salt.client.LocalClient()
        ret = local.cmd(host, 'vagrant.destroy', [name])

        if ret[host]:
            __utils__['cloud.fire_event'](
                'event',
                'destroyed instance',
                'salt/cloud/{0}/destroyed'.format(name),
                args={'name': name},
                sock_dir=opts['sock_dir'],
                transport=opts['transport']
            )

            if opts.get('update_cachedir', False) is True:
                __utils__['cloud.delete_minion_cachedir'](
                    name, __active_provider_name__.split(':')[0], opts)

            return {'Destroyed': '{0} was destroyed.'.format(name)}
        else:
            return {'Error': 'Error destroying {}'.format(name)}
    else:
        return {'Error': 'No response from {}. Cannot destroy.'.format(name)}


# noinspection PyTypeChecker
def reboot(name, call=None):
    '''
    Reboot a vagrant minion.

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
    my_info = _get_my_info(name)
    profile_name = my_info[name]['profile']
    profile = __opts__['profiles'][profile_name]
    host = profile['host']
    local = salt.client.LocalClient()
    return local.cmd(host, 'vagrant.reboot', [name])
