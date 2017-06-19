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

If you intend to use salt-cloud commands to query, reboot, or disconnect minions, it
needs to do salt-api calls to your Salt master. Your configuration might be similar to:...

.. code-block:: yaml

    # file /etc/salt/cloud.providers.d/saltify_provider.conf
    my-saltify-config:
      driver: saltify
      # The salt-api user password can be stored in your keyring
      # don't forget to set the password by running something like:
      # salt-call sdb.set 'sdb://salt-cloud-keyring/password' 'xyz1234'
      eauth: pam
      username: sdb://osenv/USER
      password: sdb://salt-cloud-keyring/password

Which in turn implies that you have enabled both sdb and pam.
Your minion (and master) configuration might include something like:...

.. code-block:: yaml

    # file /etc/salt/minion.d/salt-api.conf
    osenv:
      driver: env
    salt-cloud-keyring:
      driver: keyring
      service: system
    external_auth:  # give full remote control to group "sudo"
      pam:
        sudo%:
          - .*
          - '@wheel'
          - '@runner'
          - '@jobs'
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.utils
import salt.config as config
import salt.netapi
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
               'eauth': vm_['eauth']
               }
    except IndexError:
        raise SaltCloudException(
            'Configuration must define salt-api "username", "password" and "eauth"')
    return ret


def list_nodes():
    '''
    List the nodes which have salt-cloud:driver:saltify grains.
    '''
    nodes = list_nodes_full()
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
                'name': grains['fqdn'],
                'private_ips': private_ips,
                'public_ips': public_ips,
                'salt-cloud': grains['salt-cloud'],
                'state': 'running'
            }
        else:
            ret[name] = {  # according to the grain target selection, this node must have once been saltify-ed
                'id': name,
                'salt-cloud': {'profile': '', 'driver': 'saltify', 'provider': ''},
                'state': 'unknown'
            }
    return ret


def list_nodes_full():
    '''
    List the nodes, ask all 'saltify' minions, return dict of grains.
    '''
    local = salt.netapi.NetapiClient(__opts__)
    cmd = {'client':'local',
           'tgt': 'salt-cloud:driver:saltify',
           'fun': 'grains.items',
           'arg': '',
           'tgt_type': 'grain'
           }
    cmd.update(_get_connection_info())
    ret = local.run(cmd)
    for grains in ret.values(): # clean up some hyperverbose grains -- everything is too much
        try:
            del grains['cpu_flags'], grains['disks'], grains['pythonpath'], grains['dns'], grains['gpus']
        except (KeyError, TypeError):
            pass
    return ret


def list_nodes_select(call=None):
    ''' Return a list of the minions that have salt-cloud grains, with
    select fields.
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full('function'), __opts__['query.selection'], call,
    )


def reboot(name, call=None):
    '''
    Reboot a saltify minion.

    .. versionadded:: xxx

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
    cmd = {'client':'local',
           'tgt': name,
           'fun': 'system.reboot',
           'arg': '',
           }
    cmd.update(_get_connection_info())
    ret = local.run(cmd)

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

    CLI Example:
    .. code-block:: bash

        salt-cloud --destroy mymachine
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
        transport=__opts__['transport']
    )

    local = salt.netapi.NetapiClient(__opts__)
    cmd = {'client':'local',
           'tgt': name,
           'fun': 'system.shutdown',
           'arg': '',
           }
    cmd.update(_get_connection_info())
    ret = local.run(cmd)

    __utils__['cloud.fire_event'](
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    return ret
