# -*- coding: utf-8 -*-
'''
Manage RabbitMQ Plugins
=======================

.. versionadded:: 2014.1.0

Example:

.. code-block:: yaml

    some_plugin:
        rabbitmq_plugin.enabled: []
'''
from __future__ import absolute_import

# Import python libs
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if RabbitMQ is installed.
    '''
    if __salt__['cmd.has_exec']('rabbitmqctl'):
        return True
    return False


def enabled(name, runas=None):
    '''
    Ensure the RabbitMQ plugin is enabled.

    name
        The name of the plugin
    runas
        The user to run the rabbitmq-plugin command as
    '''

    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    result = {}

    if __salt__['rabbitmq.plugin_is_enabled'](name, runas=runas):
        ret['comment'] = 'Plugin {0} is already enabled'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Plugin {0} is set to be enabled'.format(name)
    else:
        result = __salt__['rabbitmq.enable_plugin'](name, runas=runas)

    if 'Error' in result:
        ret['result'] = False
        ret['comment'] = result['Error']
    elif 'Enabled' in result:
        ret['comment'] = result['Enabled']
        ret['changes'] = {'old': '', 'new': name}

    return ret


def disabled(name, runas=None):
    '''
    Ensure the RabbitMQ plugin is disabled.

    name
        The name of the plugin
    runas
        The user to run the rabbitmq-plugin command as
    '''

    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    result = {}

    if not __salt__['rabbitmq.plugin_is_enabled'](name, runas=runas):
        ret['comment'] = 'Plugin {0} is not enabled'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Plugin {0} is set to be disabled'.format(name)
    else:
        result = __salt__['rabbitmq.disable_plugin'](name, runas=runas)

    if 'Error' in result:
        ret['result'] = False
        ret['comment'] = result['Error']
    elif 'Disabled' in result:
        ret['comment'] = result['Disabled']
        ret['changes'] = {'new': '', 'old': name}

    return ret
