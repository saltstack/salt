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
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.utils

# Import salt cloud libs
import salt.utils.cloud
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
    log.info('Provisioning existing machine {0}'.format(vm_['name']))

    ret = salt.utils.cloud.bootstrap(vm_, __opts__)

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
