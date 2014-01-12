# -*- coding: utf-8 -*-
'''
Saltify Module
==============
The Saltify module is designed to install Salt on a remote machine, virtual or
bare metal, using SSH. This module is useful for provisioning machines which
are already installed, but not Salted.

Use of this module requires no configuration in the main cloud configuration
file. However, profiles must still be configured, as described in the
:ref:`core config documentation <config_saltify>`.
'''

# Import python libs
import os
import copy
import logging

# Import salt libs
import salt.utils

# Import salt cloud libs
import salt.utils.cloud
import salt.config as config
from salt.cloud.exceptions import SaltCloudConfigError, SaltCloudSystemExit

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
    if config.get_cloud_config_value('deploy', vm_, __opts__) is False:
        return {
            'Error': {
                'No Deploy': '\'deploy\' is not enabled. Not deploying.'
            }
        }
    key_filename = config.get_cloud_config_value(
        'key_filename', vm_, __opts__, search_global=False, default=None
    )
    if key_filename is not None and not os.path.isfile(key_filename):
        raise SaltCloudConfigError(
            'The defined ssh_keyfile {0!r} does not exist'.format(
                key_filename
            )
        )

    if key_filename is None and salt.utils.which('sshpass') is None:
        raise SaltCloudSystemExit(
            'Cannot deploy salt in a VM if the \'ssh_keyfile\' setting '
            'is not set and \'sshpass\' binary is not present on the '
            'system for the password.'
        )

    ret = {}

    log.info('Provisioning existing machine {0}'.format(vm_['name']))

    ssh_username = config.get_cloud_config_value('ssh_username', vm_, __opts__)
    deploy_script = script(vm_)
    deploy_kwargs = {
        'host': vm_['ssh_host'],
        'username': ssh_username,
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
        'sudo': config.get_cloud_config_value(
            'sudo', vm_, __opts__, default=(ssh_username != 'root')
        ),
        'sudo_password': config.get_cloud_config_value(
            'sudo_password', vm_, __opts__, default=None
        ),
        'tty': config.get_cloud_config_value(
            'tty', vm_, __opts__, default=True
        ),
        'password': config.get_cloud_config_value(
            'password', vm_, __opts__, search_global=False
        ),
        'key_filename': key_filename,
        'script_args': config.get_cloud_config_value('script_args', vm_, __opts__),
        'script_env': config.get_cloud_config_value('script_env', vm_, __opts__),
        'minion_conf': salt.utils.cloud.minion_config(__opts__, vm_),
        'preseed_minion_keys': vm_.get('preseed_minion_keys', None),
        'display_ssh_output': config.get_cloud_config_value(
            'display_ssh_output', vm_, __opts__, default=True
        )
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

    win_installer = config.get_cloud_config_value('win_installer', vm_, __opts__)
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
    ret['deploy_kwargs'] = event_kwargs

    salt.utils.cloud.fire_event(
        'event',
        'executing deploy script',
        'salt/cloud/{0}/deploying'.format(vm_['name']),
        {'kwargs': event_kwargs},
    )

    deployed = False
    if win_installer:
        deployed = salt.utils.cloud.deploy_windows(**deploy_kwargs)
    else:
        deployed = salt.utils.cloud.deploy_script(**deploy_kwargs)

    if deployed:
        ret['deployed'] = deployed
        log.info('Salt installed on {0}'.format(vm_['name']))
        return ret

    log.error('Failed to start Salt on host {0}'.format(vm_['name']))
    return {
        'Error': {
            'Not Deployed': 'Failed to start Salt on host {0}'.format(
                vm_['name']
            )
        }
    }


def script(vm_):
    '''
    Return the script deployment object
    '''
    return salt.utils.cloud.os_script(
        config.get_cloud_config_value('script', vm_, __opts__),
        vm_,
        __opts__,
        salt.utils.cloud.salt_config_to_yaml(
            salt.utils.cloud.minion_config(__opts__, vm_)
        )
    )


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'saltify',
        ()
    )
