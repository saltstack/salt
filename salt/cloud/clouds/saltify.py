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
import salt.config as config
from salt.exceptions import SaltCloudException

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


def list_nodes():
    '''
    Because this module is not specific to any cloud providers, there will be
    no nodes to list.
    '''
    return {}


def list_nodes_full():
    '''
    Because this module is not specific to any cloud providers, there will be
    no nodes to list.
    '''
    return {}


def list_nodes_select():
    '''
    Because this module is not specific to any cloud providers, there will be
    no nodes to list.
    '''
    return {}


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
