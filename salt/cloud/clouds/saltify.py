# -*- coding: utf-8 -*-
'''
Saltify Module
==============

The Saltify module is designed to install Salt on a remote machine, virtual or
bare metal, using SSH. This module is useful for provisioning machines which
are already installed, but not Salted.

Use of this module requires some configuration in cloud profile and provider
files as described in the
:ref:`Gettting Started with Saltify <getting-started-with-saltify>` documentation.
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

try:
    from impacket.smbconnection import SessionError as smbSessionError
    from impacket.smb3 import SessionError as smb3SessionError
    HAS_IMPACKET = True
except ImportError:
    HAS_IMPACKET = False

try:
    from winrm.exceptions import WinRMTransportError
    from requests.exceptions import (
        ConnectionError, ConnectTimeout, ReadTimeout, SSLError,
        ProxyError, RetryError, InvalidSchema)
    HAS_WINRM = True
except ImportError:
    HAS_WINRM = False


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
        ret = {'username': vm_['username'],
               'password': vm_['password'],
               'eauth': vm_['eauth'],
               'vm': vm_,
               }
    except KeyError:
        raise SaltCloudException(
            'Configuration must define salt-api "username", "password" and "eauth"')
    return ret


def avail_locations(call=None):
    '''
    This function returns a list of locations available.

    .. code-block:: bash

        salt-cloud --list-locations my-cloud-provider

    [ saltify will always returns an empty dictionary ]
    '''

    return {}


def avail_images(call=None):
    '''
    This function returns a list of images available for this cloud provider.

    .. code-block:: bash

        salt-cloud --list-images saltify

    returns a list of available profiles.

    ..versionadded:: Oxygen

    '''
    vm_ = get_configured_provider()
    return {'Profiles': [profile for profile in vm_['profiles']]}


def avail_sizes(call=None):
    '''
    This function returns a list of sizes available for this cloud provider.

    .. code-block:: bash

        salt-cloud --list-sizes saltify

    [ saltify always returns an empty dictionary ]
    '''
    return {}


def list_nodes(call=None):
    '''
    List the nodes which have salt-cloud:driver:saltify grains.

    .. code-block:: bash

        salt-cloud -Q

    returns a list of dictionaries of defined standard fields.

    salt-api setup required for operation.

    ..versionadded:: Oxygen

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
    Lists complete information for all nodes.

    .. code-block:: bash

        salt-cloud -F

    returns a list of dictionaries.
    for 'saltify' minions, returns dict of grains (enhanced).
    salt-api setup required for operation.

    ..versionadded:: Oxygen
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
    List the nodes, ask all 'saltify' minions, return dict of grains.
    '''
    local = salt.netapi.NetapiClient(__opts__)
    cmd = {'client': 'local',
           'tgt': 'salt-cloud:driver:saltify',
           'fun': 'grains.items',
           'arg': '',
           'tgt_type': 'grain',
           }
    cmd.update(_get_connection_info())

    return local.run(cmd)


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
    local = salt.netapi.NetapiClient(__opts__)
    cmd = {'client': 'local',
           'tgt': 'name',
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
    deploy_config = config.get_cloud_config_value(
        'deploy', vm_, __opts__, default=False)

    if deploy_config:
        log.info('Provisioning existing machine %s', vm_['name'])
        ret = __utils__['cloud.bootstrap'](vm_, __opts__)
    else:
        ret = _verify(vm_)

    return ret


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'saltify',
        ()
    )


def _verify(vm_):
    '''
    Verify credentials for an exsiting system
    '''
    log.info('Verifying credentials for %s', vm_['name'])

    win_installer = config.get_cloud_config_value(
        'win_installer', vm_, __opts__)

    if win_installer:

        log.debug('Testing Windows authentication method for %s', vm_['name'])

        if not HAS_IMPACKET:
            log.error('Impacket library not found')
            return False

        # Test Windows connection
        kwargs = {
            'host': vm_['ssh_host'],
            'username': config.get_cloud_config_value(
                'win_username', vm_, __opts__, default='Administrator'),
            'password': config.get_cloud_config_value(
                'win_password', vm_, __opts__, default='')
        }

        # Test SMB connection
        try:
            log.debug('Testing SMB protocol for %s', vm_['name'])
            if __utils__['smb.get_conn'](**kwargs) is False:
                return False
        except (smbSessionError, smb3SessionError) as exc:
            log.error('Exception: %s', exc)
            return False

        # Test WinRM connection
        use_winrm = config.get_cloud_config_value(
            'use_winrm', vm_, __opts__, default=False)

        if use_winrm:
            log.debug('WinRM protocol requested for %s', vm_['name'])
            if not HAS_WINRM:
                log.error('WinRM library not found')
                return False

            kwargs['port'] = config.get_cloud_config_value(
                'winrm_port', vm_, __opts__, default=5986)
            kwargs['timeout'] = 10

            try:
                log.debug('Testing WinRM protocol for %s', vm_['name'])
                return __utils__['cloud.wait_for_winrm'](**kwargs) is not None
            except (ConnectionError, ConnectTimeout, ReadTimeout, SSLError,
                    ProxyError, RetryError, InvalidSchema, WinRMTransportError) as exc:
                log.error('Exception: %s', exc)
                return False

        return True

    else:

        log.debug('Testing SSH authentication method for %s', vm_['name'])

        # Test SSH connection
        kwargs = {
            'host': vm_['ssh_host'],
            'port': config.get_cloud_config_value(
                'ssh_port', vm_, __opts__, default=22
            ),
            'username': config.get_cloud_config_value(
                'ssh_username', vm_, __opts__, default='root'
            ),
            'password': config.get_cloud_config_value(
                'password', vm_, __opts__, search_global=False
            ),
            'key_filename': config.get_cloud_config_value(
                'key_filename', vm_, __opts__, search_global=False,
                default=config.get_cloud_config_value(
                    'ssh_keyfile', vm_, __opts__, search_global=False,
                    default=None
                )
            ),
            'gateway': vm_.get('gateway', None),
            'maxtries': 1
        }

        log.debug('Testing SSH protocol for %s', vm_['name'])
        try:
            return __utils__['cloud.wait_for_passwd'](**kwargs) is True
        except SaltCloudException as exc:
            log.error('Exception: %s', exc)
            return False


def destroy(name, call=None):
    ''' Destroy a node.

    .. versionadded:: Oxygen

    CLI Example:

    .. code-block:: bash

        salt-cloud --destroy mymachine

    salt-api setup required for operation.

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
    vm_ = cmd['vm']
    my_info = local.run(cmd)
    try:
        vm_.update(my_info[name])  # get profile name to get config value
    except (IndexError, TypeError):
        pass
    if config.get_cloud_config_value(
           'remove_config_on_destroy', vm_, opts, default=True
            ):
        cmd.update({'fun': 'service.disable', 'arg': ['salt-minion']})
        ret = local.run(cmd)  # prevent generating new keys on restart
        if ret and ret[name]:
            log.info('disabled salt-minion service on %s', name)
        cmd.update({'fun': 'config.get', 'arg': ['conf_file']})
        ret = local.run(cmd)
        if ret and ret[name]:
            confile = ret[name]
            cmd.update({'fun': 'file.remove', 'arg': [confile]})
            ret = local.run(cmd)
            if ret and ret[name]:
                log.info('removed minion %s configuration file %s',
                         name, confile)
        cmd.update({'fun': 'config.get', 'arg': ['pki_dir']})
        ret = local.run(cmd)
        if ret and ret[name]:
            pki_dir = ret[name]
            cmd.update({'fun': 'file.remove', 'arg': [pki_dir]})
            ret = local.run(cmd)
            if ret and ret[name]:
                log.info(
                    'removed minion %s key files in %s',
                    name,
                    pki_dir)

    if config.get_cloud_config_value(
        'shutdown_on_destroy', vm_, opts, default=False
        ):
        cmd.update({'fun': 'system.shutdown', 'arg': ''})
        ret = local.run(cmd)
        if ret and ret[name]:
            log.info('system.shutdown for minion %s successful', name)

    __utils__['cloud.fire_event'](
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        args={'name': name},
        sock_dir=opts['sock_dir'],
        transport=opts['transport']
    )

    return {'Destroyed': '{0} was destroyed.'.format(name)}


def reboot(name, call=None):
    '''
    Reboot a saltify minion.

    salt-api setup required for operation.

    ..versionadded:: Oxygen

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
           'fun': 'system.reboot',
           'arg': '',
           }
    cmd.update(_get_connection_info())
    ret = local.run(cmd)

    return ret
