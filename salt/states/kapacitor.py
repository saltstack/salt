# -*- coding: utf-8 -*-
'''
Kapacitor state module.

:configuration: This module accepts connection configuration details either as
    parameters or as configuration settings in /etc/salt/minion on the relevant
    minions::

        kapacitor.host: 'localhost'
        kapacitor.port: 9092

    This data can also be passed into pillar. Options passed into opts will
    overwrite options passed into pillar.

.. versionadded:: Carbon
'''

from __future__ import absolute_import

import difflib
import logging

import salt.utils

LOG = logging.getLogger(__name__)


def __virtual__():
    return 'kapacitor' if 'kapacitor.get_task' in __salt__ else False


def task_present(name,
                 tick_script,
                 task_type='stream',
                 database=None,
                 retention_policy='default',
                 enable=True):
    '''
    Ensure that a task is present and up-to-date in Kapacitor.

    name
        Name of the task.

    tick_script
        Path to the TICK script for the task. Can be a salt:// source.

    task_type
        Task type. Defaults to 'stream'

    database
        Which database to fetch data from. Defaults to None, which will use the
        default database in InfluxDB.

    retention_policy
        Which retention policy to fetch data from. Defaults to 'default'.

    enable
        Whether to enable the task or not. Defaults to True.
    '''
    comments = []
    changes = []
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    task = __salt__['kapacitor.get_task'](name)
    old_script = task['TICKscript'] if task else ''

    if tick_script.startswith('salt://'):
        script_path = __salt__['cp.cache_file'](tick_script, __env__)
    else:
        script_path = tick_script

    with salt.utils.fopen(script_path, 'r') as file:
        new_script = file.read()

    if old_script == new_script:
        comments.append('Task script is already up-to-date')
    else:
        if __opts__['test']:
            ret['result'] = None
            comments.append('Task would have been updated')
        else:
            result = __salt__['kapacitor.define_task'](name, script_path,
                task_type=task_type, database=database,
                retention_policy=retention_policy)
            if not result:
                ret['result'] = False
                comments.append('Could not define task')
                ret['comment'] = '\n'.join(comments)
                return ret
        ret['changes']['TICKscript diff'] = '\n'.join(difflib.unified_diff(
            old_script.splitlines(),
            new_script.splitlines(),
        ))
        comments.append('Task script updated')

    if enable:
        if task and task['Enabled']:
            comments.append('Task is already enabled')
        else:
            if __opts__['test']:
                ret['result'] = None
                comments.append('Task would have been enabled')
            else:
                result = __salt__['kapacitor.enable_task'](name)
                if not result:
                    ret['result'] = False
                    comments.append('Could not enable task')
                    ret['comment'] = '\n'.join(comments)
                    return ret
                comments.append('Task was enabled')
            ret['changes']['enabled'] = {'old': False, 'new': True}
    else:
        if task and not task['Enabled']:
            comments.append('Task is already disabled')
        else:
            if __opts__['test']:
                ret['result'] = None
                comments.append('Task would have been disabled')
            else:
                result = __salt__['kapacitor.disable_task'](name)
                if not result:
                    ret['result'] = False
                    comments.append('Could not disable task')
                    ret['comment'] = '\n'.join(comments)
                    return ret
                comments.append('Task was disabled')
            ret['changes']['enabled'] = {'old': True, 'new': False}

    ret['comment'] = '\n'.join(comments)
    return ret


def task_absent(name):
    '''
    Ensure that a task is absent from Kapacitor.

    name
        Name of the task.
    '''

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    task = __salt__['kapacitor.get_task'](name)

    if task:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Task would have been deleted'
        else:
            __salt__['kapacitor.delete_task'](name)
            ret['comment'] = 'Task was deleted'
        ret['changes'][name] = 'deleted'
    else:
        ret['comment'] = 'Task does not exist'

    return ret
