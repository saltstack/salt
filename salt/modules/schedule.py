# -*- coding: utf-8 -*-
'''
Module for manging the Salt schedule on a minion

.. versionadded:: Helium

'''

# Import Python libs
import os
import yaml

import salt.utils

__proxyenabled__ = ['*']

import logging
log = logging.getLogger(__name__)

__func_alias__ = {
    'list_': 'list',
    'reload_': 'reload'
}

SCHEDULE_CONF = [
        'function',
        'splay',
        'range',
        'when',
        'returner',
        'jid_include',
        'args',
        'kwargs',
        '_seconds',
        'seconds',
        'minutes',
        'hours',
        'days',
        'enabled'
        ]


def list_(show_all=False):
    '''
    List the jobs currently scheduled on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.list

        salt '*' schedule.list show_all=True
    '''

    schedule = __opts__['schedule'].copy()
    if 'schedule' in __pillar__:
        schedule.update(__pillar__['schedule'])

    for job in schedule.keys():
        if job == 'enabled':
            continue

        # Default jobs added by salt begin with __
        # by default hide them unless show_all is True.
        if job.startswith('__') and not show_all:
            del schedule[job]
            continue

        for item in schedule[job].keys():
            if item not in SCHEDULE_CONF:
                del schedule[job][item]
                continue
            if schedule[job][item] == 'true':
                schedule[job][item] = True
            if schedule[job][item] == 'false':
                schedule[job][item] = False

        if '_seconds' in schedule[job].keys():
            schedule[job]['seconds'] = schedule[job]['_seconds']
            del schedule[job]['_seconds']

    if schedule:
        tmp = {'schedule': schedule}
        yaml_out = yaml.safe_dump(tmp, default_flow_style=False)
        return yaml_out
    else:
        return None


def purge():
    '''
    Purge all the jobs currently scheduled on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.purge
    '''

    ret = {'comment': [],
           'result': True}

    schedule = __opts__['schedule'].copy()
    if 'schedule' in __pillar__:
        schedule.update(__pillar__['schedule'])

    for name in schedule.keys():
        if name == 'enabled':
            continue
        if name.startswith('__'):
            continue

        out = __salt__['event.fire']({'name': name, 'func': 'delete'}, 'manage_schedule')
        if out:
            ret['comment'].append('Deleted job: {0} from schedule.'.format(name))
        else:
            ret['comment'].append('Failed to delete job {0} from schedule.'.format(name))
            ret['result'] = False
    return ret


def delete(name):
    '''
    Delete a job from the minion's schedule

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.delete job1
    '''

    ret = {'comment': [],
           'result': True}

    if not name:
        ret['comment'] = 'Job name is required.'
        ret['result'] = False

    if name in __opts__['schedule']:
        out = __salt__['event.fire']({'name': name, 'func': 'delete'}, 'manage_schedule')
        if out:
            ret['comment'] = 'Deleted Job {0} from schedule.'.format(name)
        else:
            ret['comment'] = 'Failed to delete job {0} from schedule.'.format(name)
            ret['result'] = False
    elif 'schedule' in __pillar__ and name in __pillar__['schedule']:
        log.debug('found job in pillar')
        out = __salt__['event.fire']({'name': name, 'where': 'pillar', 'func': 'delete'}, 'manage_schedule')
        if out:
            ret['comment'] = 'Deleted Job {0} from schedule.'.format(name)
        else:
            ret['comment'] = 'Failed to delete job {0} from schedule.'.format(name)
            ret['result'] = False
    else:
        ret['comment'] = 'Job {0} does not exist.'.format(name)
        ret['result'] = False
    return ret


def add(name, **kwargs):
    '''
    Add a job to the schedule

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.add job1 function='test.ping' seconds=3600
    '''

    ret = {'comment': [],
           'result': True}

    current_schedule = __opts__['schedule'].copy()
    if 'schedule' in __pillar__:
        current_schedule.update(__pillar__['schedule'])

    if name in current_schedule:
        ret['comment'] = 'Job {0} already exists in schedule.'.format(name)
        ret['result'] = True
        return ret

    if not name:
        ret['comment'] = 'Job name is required.'
        ret['result'] = False

    schedule = {}
    schedule[name] = {'function': kwargs['function']}

    time_conflict = False
    for item in ['seconds', 'minutes', 'hours', 'days']:
        if item in kwargs and 'when' in kwargs:
            time_conflict = True

    if time_conflict:
        return 'Error: Unable to use "seconds", "minutes", "hours", or "days" with "when" option.'

    for item in ['seconds', 'minutes', 'hours', 'days']:
        if item in kwargs:
            schedule[name][item] = kwargs[item]

    if 'job_args' in kwargs:
        schedule[name]['args'] = kwargs['job_args']

    if 'job_kwargs' in kwargs:
        schedule[name]['kwargs'] = kwargs['job_kwargs']

    for item in ['splay', 'range', 'when', 'returner', 'jid_include']:
        if item in kwargs:
            schedule[name][item] = kwargs[item]

    out = __salt__['event.fire']({'name': name, 'schedule': schedule, 'func': 'add'}, 'manage_schedule')
    if out:
        ret['comment'] = 'Added job: {0} to schedule.'.format(name)
    else:
        ret['comment'] = 'Failed to modify job {0} to schedule.'.format(name)
        ret['result'] = False
    return ret


def modify(name, **kwargs):
    '''
    Modify an existing job in the schedule

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.modify job1 function='test.ping' seconds=3600
    '''

    ret = {'comment': [],
           'result': True}

    current_schedule = __opts__['schedule'].copy()
    if 'schedule' in __pillar__:
        current_schedule.update(__pillar__['schedule'])

    if name not in current_schedule:
        ret['comment'] = 'Job {0} does not exist in schedule.'.format(name)
        ret['result'] = False
        return ret

    schedule = {'function': kwargs['function']}

    time_conflict = False
    for item in ['seconds', 'minutes', 'hours', 'days']:
        if item in kwargs and 'when' in kwargs:
            time_conflict = True

    if time_conflict:
        return 'Error: Unable to use "seconds", "minutes", "hours", or "days" with "when" option.'

    for item in ['seconds', 'minutes', 'hours', 'days']:
        if item in kwargs:
            schedule[item] = kwargs[item]

    if 'job_args' in kwargs:
        schedule['args'] = kwargs['job_args']

    if 'job_kwargs' in kwargs:
        schedule['kwargs'] = kwargs['job_kwargs']

    for item in ['splay', 'range', 'when', 'returner', 'jid_include']:
        if item in kwargs:
            schedule[item] = kwargs[item]

    if name in __opts__['schedule']:
        out = __salt__['event.fire']({'name': name, 'schedule': schedule, 'func': 'modify'}, 'manage_schedule')
        if out:
            ret['comment'] = 'Modified job: {0} in schedule.'.format(name)
        else:
            ret['comment'] = 'Failed to modify job {0} in schedule.'.format(name)
            ret['result'] = False
    elif 'schedule' in __pillar__ and name in __pillar__['schedule']:
        out = __salt__['event.fire']({'name': name, 'schedule': schedule, 'where': 'pillar', 'func': 'modify'}, 'manage_schedule')
        if out:
            ret['comment'] = 'Modified job: {0} in schedule.'.format(name)
        else:
            ret['comment'] = 'Failed to modify job {0} in schedule.'.format(name)
            ret['result'] = False
    return ret


def run_job(name, force=False):
    '''
    Run a scheduled job on the minion immediately

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.run_job job1

        salt '*' schedule.run_job job1 force=True
        Force the job to run even if it is disabled.
    '''

    ret = {'comment': [],
           'result': True}

    if not name:
        ret['comment'] = 'Job name is required.'
        ret['result'] = False

    if name in __opts__['schedule']:
        data = __opts__['schedule'][name]
        if 'enabled' in data and not data['enabled'] and not force:
            ret['comment'] = 'Job {0} is disabled.'.format(name)
        else:
            out = __salt__['event.fire']({'name': name, 'func': 'run_job'}, 'manage_schedule')
            if out:
                ret['comment'] = 'Scheduling Job {0} on minion.'.format(name)
            else:
                ret['comment'] = 'Failed to run job {0} on minion.'.format(name)
                ret['result'] = False
    elif 'schedule' in __pillar__ and name in __pillar__['schedule']:
        data = __pillar__['schedule'][name]
        if 'enabled' in data and not data['enabled'] and not force:
            ret['comment'] = 'Job {0} is disabled.'.format(name)
        else:
            out = __salt__['event.fire']({'name': name, 'where': 'pillar', 'func': 'run_job'}, 'manage_schedule')
            if out:
                ret['comment'] = 'Scheduling Job {0} on minion.'.format(name)
            else:
                ret['comment'] = 'Failed to run job {0} on minion.'.format(name)
                ret['result'] = False
    else:
        ret['comment'] = 'Job {0} does not exist.'.format(name)
        ret['result'] = False
    return ret


def enable_job(name):
    '''
    Enable a job in the minion's schedule

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.enable_job job1
    '''

    ret = {'comment': [],
           'result': True}

    if not name:
        ret['comment'] = 'Job name is required.'
        ret['result'] = False

    if name in __opts__['schedule']:
        out = __salt__['event.fire']({'name': name, 'func': 'enable_job'}, 'manage_schedule')
        if out:
            ret['comment'] = 'Enabled Job {0} in schedule.'.format(name)
        else:
            ret['comment'] = 'Failed to enable job {0} from schedule.'.format(name)
            ret['result'] = False
    elif 'schedule' in __pillar__ and name in __pillar__['schedule']:
        out = __salt__['event.fire']({'name': name, 'where': 'pillar', 'func': 'enable_job'}, 'manage_schedule')
        if out:
            ret['comment'] = 'Enabled Job {0} in schedule.'.format(name)
        else:
            ret['comment'] = 'Failed to enable job {0} from schedule.'.format(name)
            ret['result'] = False
    else:
        ret['comment'] = 'Job {0} does not exist.'.format(name)
        ret['result'] = False
    return ret


def disable_job(name):
    '''
    Disable a job in the minion's schedule

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.disable_job job1
    '''

    ret = {'comment': [],
           'result': True}

    if not name:
        ret['comment'] = 'Job name is required.'
        ret['result'] = False

    if name in __opts__['schedule']:
        out = __salt__['event.fire']({'name': name, 'func': 'disable_job'}, 'manage_schedule')
        if out:
            ret['comment'] = 'Disabled Job {0} in schedule.'.format(name)
        else:
            ret['comment'] = 'Failed to disable job {0} from schedule.'.format(name)
            ret['result'] = False
    elif 'schedule' in __pillar__ and name in __pillar__['schedule']:
        out = __salt__['event.fire']({'name': name, 'where': 'pillar', 'func': 'disable_job'}, 'manage_schedule')
        if out:
            ret['comment'] = 'Disabled Job {0} in schedule.'.format(name)
        else:
            ret['comment'] = 'Failed to disable job {0} from schedule.'.format(name)
            ret['result'] = False
    else:
        ret['comment'] = 'Job {0} does not exist.'.format(name)
        ret['result'] = False
    return ret


def save():
    '''
    Save all scheduled jobs on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.save
    '''

    ret = {'comment': [],
           'result': True}

    schedule = __opts__['schedule']
    for job in schedule.keys():
        if job == 'enabled':
            continue
        if job.startswith('_'):
            del schedule[job]
            continue

        for item in schedule[job].keys():
            if item not in SCHEDULE_CONF:
                del schedule[job][item]
                continue
            if schedule[job][item] == 'true':
                schedule[job][item] = True
            if schedule[job][item] == 'false':
                schedule[job][item] = False

        if '_seconds' in schedule[job].keys():
            schedule[job]['seconds'] = schedule[job]['_seconds']
            del schedule[job]['_seconds']

    # move this file into an configurable opt
    sfn = '{0}/{1}/schedule.conf'.format(__opts__['config_dir'], os.path.dirname(__opts__['default_include']))
    if schedule:
        tmp = {'schedule': schedule}
        yaml_out = yaml.safe_dump(tmp, default_flow_style=False)
    else:
        yaml_out = ''

    try:
        with salt.utils.fopen(sfn, 'w+') as fp_:
            fp_.write(yaml_out)
        ret['comment'] = 'Schedule (non-pillar items) saved to {0}.'.format(sfn)
    except (IOError, OSError):
        ret['comment'] = 'Unable to write to schedule file at {0}. Check permissions.'.format(sfn)
        ret['result'] = False
    return ret


def enable():
    '''
    Enable all scheduled jobs on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.enable
    '''

    ret = {'comment': [],
           'result': True}

    out = __salt__['event.fire']({'func': 'enable'}, 'manage_schedule')
    if out:
        ret['comment'] = 'Enabled schedule on minion.'
    else:
        ret['comment'] = 'Failed to enable schedule on minion.'
        ret['result'] = False
    return ret


def disable():
    '''
    Disable all scheduled jobs on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.disable
    '''

    ret = {'comment': [],
           'result': True}

    out = __salt__['event.fire']({'func': 'disable'}, 'manage_schedule')
    if out:
        ret['comment'] = 'Disabled schedule on minion.'
    else:
        ret['comment'] = 'Failed to disable schedule on minion.'
        ret['result'] = False
    return ret


def reload_():
    '''
    Reload saved scheduled jobs on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.reload
    '''

    ret = {'comment': [],
           'result': True}

    # If there a schedule defined in pillar, refresh it.
    if 'schedule' in __pillar__:
        out = __salt__['event.fire']({}, 'pillar_refresh')
        if out:
            ret['comment'].append('Reloaded schedule from pillar on minion.')
        else:
            ret['comment'].append('Failed to reload schedule from pillar on minion.')
            ret['result'] = False

    # move this file into an configurable opt
    sfn = '{0}/{1}/schedule.conf'.format(__opts__['config_dir'], os.path.dirname(__opts__['default_include']))
    if os.path.isfile(sfn):
        with salt.utils.fopen(sfn, 'rb') as fp_:
            try:
                schedule = yaml.safe_load(fp_.read())
            except Exception as e:
                ret['comment'].append('Unable to read existing schedule file: {0}'.format(e))

        if 'schedule' in schedule and schedule['schedule']:
            out = __salt__['event.fire']({'func': 'reload', 'schedule': schedule}, 'manage_schedule')
            if out:
                ret['comment'].append('Reloaded schedule on minion from schedule.conf.')
            else:
                ret['comment'].append('Failed to reload schedule on minion from schedule.conf.')
                ret['result'] = False
        else:
            ret['comment'].append('Failed to reload schedule on minion.  Saved file is empty or invalid.')
            ret['result'] = False
    return ret
