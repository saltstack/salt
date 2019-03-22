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

.. versionadded:: 2016.11.0
'''


from __future__ import absolute_import, print_function, unicode_literals
import difflib

import salt.utils.files
import salt.utils.stringutils


def __virtual__():
    return 'kapacitor' if 'kapacitor.version' in __salt__ else False


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
    old_script = task['script'] if task else ''

    if tick_script.startswith('salt://'):
        script_path = __salt__['cp.cache_file'](tick_script, __env__)
    else:
        script_path = tick_script

    with salt.utils.files.fopen(script_path, 'r') as file:
        new_script = salt.utils.stringutils.to_unicode(file.read()).replace('\t', '    ')

    is_up_to_date = task and (
        old_script == new_script and
        task_type == task['type'] and
        task['dbrps'] == [{'db': database, 'rp': retention_policy}]
    )

    if is_up_to_date:
        comments.append('Task script is already up-to-date')
    else:
        if __opts__['test']:
            ret['result'] = None
            comments.append('Task would have been updated')
        else:
            result = __salt__['kapacitor.define_task'](
                name,
                script_path,
                task_type=task_type,
                database=database,
                retention_policy=retention_policy
            )
            ret['result'] = result['success']
            if not ret['result']:
                comments.append('Could not define task')
                if result.get('stderr'):
                    comments.append(result['stderr'])
                ret['comment'] = '\n'.join(comments)
                return ret

        if old_script != new_script:
            ret['changes']['TICKscript diff'] = '\n'.join(difflib.unified_diff(
                old_script.splitlines(),
                new_script.splitlines(),
            ))
            comments.append('Task script updated')

        if not task or task['type'] != task_type:
            ret['changes']['type'] = task_type
            comments.append('Task type updated')

        if not task or task['dbrps'][0]['db'] != database:
            ret['changes']['db'] = database
            comments.append('Task database updated')

        if not task or task['dbrps'][0]['rp'] != retention_policy:
            ret['changes']['rp'] = retention_policy
            comments.append('Task retention policy updated')

    if enable:
        if task and task['enabled']:
            comments.append('Task is already enabled')
        else:
            if __opts__['test']:
                ret['result'] = None
                comments.append('Task would have been enabled')
            else:
                result = __salt__['kapacitor.enable_task'](name)
                ret['result'] = result['success']
                if not ret['result']:
                    comments.append('Could not enable task')
                    if result.get('stderr'):
                        comments.append(result['stderr'])
                    ret['comment'] = '\n'.join(comments)
                    return ret
                comments.append('Task was enabled')
            ret['changes']['enabled'] = {'old': False, 'new': True}
    else:
        if task and not task['enabled']:
            comments.append('Task is already disabled')
        else:
            if __opts__['test']:
                ret['result'] = None
                comments.append('Task would have been disabled')
            else:
                result = __salt__['kapacitor.disable_task'](name)
                ret['result'] = result['success']
                if not ret['result']:
                    comments.append('Could not disable task')
                    if result.get('stderr'):
                        comments.append(result['stderr'])
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
            result = __salt__['kapacitor.delete_task'](name)
            ret['result'] = result['success']
            if not ret['result']:
                ret['comment'] = 'Could not disable task'
                if result.get('stderr'):
                    ret['comment'] += '\n' + result['stderr']
                return ret
            ret['comment'] = 'Task was deleted'
        ret['changes'][name] = 'deleted'
    else:
        ret['comment'] = 'Task does not exist'

    return ret
