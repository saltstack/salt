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

# Get logging started
log = logging.getLogger(__name__)


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
        log.info('Provisioning existing machine {0}'.format(vm_['name']))
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
    log.info('Testing logon credentials for {0}'.format(vm_['name']))

    win_installer = config.get_cloud_config_value(
        'win_installer', vm_, __opts__
    )

    if win_installer:

        # No support for Windows at this time
        return None

    else:
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

        return __utils__['cloud.wait_for_passwd'](**kwargs)
