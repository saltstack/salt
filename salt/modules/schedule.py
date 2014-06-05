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
        'days'
        ]


def list():
    '''
    List the jobs currently scheduled on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.list
    '''

    schedule = __opts__['schedule']
    for job in schedule.keys():
        if job.startswith('_'):
            del schedule[job]
            continue

        for item in schedule[job].keys():
            if not item in SCHEDULE_CONF:
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

    schedule = __opts__['schedule']
    for job in schedule.keys():
        if job.startswith('_'):
            continue

        out = __salt__['event.fire']({'job': job, 'func': 'delete'}, 'manage_schedule')
        if out:
            ret['comment'].append('Deleted job: {0} from schedule.'.format(job))
        else:
            ret['comment'].append('Failed to delete job {0} from schedule.'.format(job))
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
        out = __salt__['event.fire']({'job': name, 'func': 'delete'}, 'manage_schedule')
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

    if name in __opts__['schedule']:
        ret['comment'] = 'Job {0} already exists in schedule.'.format(name)
        ret['result'] = True
        return ret

    if not name:
        ret['comment'] = 'Job name is required.'
        ret['result'] = False

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

    if not name in __opts__['schedule']:
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

    out = __salt__['event.fire']({'name': name, 'schedule': schedule, 'func': 'modify'}, 'manage_schedule')
    if out:
        ret['comment'] = 'Modified job: {0} in schedule.'.format(name)
    else:
        ret['comment'] = 'Failed to modify job {0} in schedule.'.format(name)
        ret['result'] = False
    return ret


def save():
    '''

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.save
    '''

    ret = {'comment': [],
           'result': True}

    schedule = __opts__['schedule']
    for job in schedule.keys():
        if job.startswith('_'):
            del schedule[job]
            continue

        for item in schedule[job].keys():
            if not item in SCHEDULE_CONF:
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
        ret['comment'] = 'Schedule saved to {0}.'.format(sfn)
    except (IOError, OSError):
        ret['comment'] = 'Unable to write to schedule file at {0}. Check permissions.'.format(sfn)
        ret['result'] = False
    return ret
