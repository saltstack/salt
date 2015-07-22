# -*- coding: utf-8 -*-
'''
Module for managing the Salt schedule on a minion

.. versionadded:: 2014.7.0

'''
from __future__ import absolute_import

# Import Python libs
import copy as pycopy
import difflib
import os
import yaml

import salt.utils
import salt.utils.odict
import salt.ext.six as six

__proxyenabled__ = ['*']

import logging
log = logging.getLogger(__name__)

__func_alias__ = {
    'list_': 'list',
    'reload_': 'reload'
}

SCHEDULE_CONF = [
        'name',
        'maxrunning',
        'function',
        'splay',
        'range',
        'when',
        'once',
        'once_fmt',
        'returner',
        'jid_include',
        'args',
        'kwargs',
        '_seconds',
        'seconds',
        'minutes',
        'hours',
        'days',
        'enabled',
        'return_job',
        'metadata',
        'cron'
]


def list_(show_all=False, return_yaml=True):
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

    for job in schedule.keys():  # iterate over a copy since we will mutate it
        if job == 'enabled':
            continue

        # Default jobs added by salt begin with __
        # by default hide them unless show_all is True.
        if job.startswith('__') and not show_all:
            del schedule[job]
            continue

        for item in pycopy.copy(schedule[job]):
            if item not in SCHEDULE_CONF:
                del schedule[job][item]
                continue
            if schedule[job][item] == 'true':
                schedule[job][item] = True
            if schedule[job][item] == 'false':
                schedule[job][item] = False

        if '_seconds' in schedule[job]:
            schedule[job]['seconds'] = schedule[job]['_seconds']
            del schedule[job]['_seconds']

    if schedule:
        if return_yaml:
            tmp = {'schedule': schedule}
            yaml_out = yaml.safe_dump(tmp, default_flow_style=False)
            return yaml_out
        else:
            return schedule
    else:
        return {'schedule': {}}


def is_enabled(name):
    '''
    List a Job only if its enabled

    .. versionadded:: 2015.5.3

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.is_enabled name=job_name
    '''

    current_schedule = __salt__['schedule.list'](show_all=False, return_yaml=False)
    if name in current_schedule:
        return current_schedule[name]
    else:
        return {}


def purge(**kwargs):
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

    for name in schedule:
        if name == 'enabled':
            continue
        if name.startswith('__'):
            continue

        if 'test' in kwargs and kwargs['test']:
            ret['comment'].append('Job: {0} would be deleted from schedule.'.format(name))
        else:
            out = __salt__['event.fire']({'name': name, 'func': 'delete'}, 'manage_schedule')
            if out:
                ret['comment'].append('Deleted job: {0} from schedule.'.format(name))
            else:
                ret['comment'].append('Failed to delete job {0} from schedule.'.format(name))
                ret['result'] = False
    return ret


def delete(name, **kwargs):
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
        if 'test' in kwargs and kwargs['test']:
            ret['comment'] = 'Job: {0} would be deleted from schedule.'.format(name)
        else:
            out = __salt__['event.fire']({'name': name, 'func': 'delete'}, 'manage_schedule')
            if out:
                ret['comment'] = 'Deleted Job {0} from schedule.'.format(name)
            else:
                ret['comment'] = 'Failed to delete job {0} from schedule.'.format(name)
                ret['result'] = False
    elif 'schedule' in __pillar__ and name in __pillar__['schedule']:
        if 'test' in kwargs and kwargs['test']:
            ret['comment'] = 'Job: {0} would be deleted from schedule.'.format(name)
        else:
            out = __salt__['event.fire']({'name': name, 'where': 'pillar', 'func': 'delete'}, 'manage_schedule')
            if out:
                ret['comment'] = 'Deleted Job {0} from schedule. Minions may need a refreshed pillar. Run saltutil.refresh_pillar.'.format(name)
            else:
                ret['comment'] = 'Failed to delete job {0} from schedule.'.format(name)
                ret['result'] = False
    else:
        ret['comment'] = 'Job {0} does not exist.'.format(name)
        ret['result'] = False
    return ret


def build_schedule_item(name, **kwargs):
    '''
    Build a schedule job

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.build_schedule_item job1 function='test.ping' seconds=3600
    '''

    ret = {'comment': [],
           'result': True}

    if not name:
        ret['comment'] = 'Job name is required.'
        ret['result'] = False
        return ret

    schedule = {}
    schedule[name] = salt.utils.odict.OrderedDict()
    schedule[name]['function'] = kwargs['function']

    time_conflict = False
    for item in ['seconds', 'minutes', 'hours', 'days']:
        if item in kwargs and 'when' in kwargs:
            time_conflict = True

        if item in kwargs and 'cron' in kwargs:
            time_conflict = True

    if time_conflict:
        ret['result'] = False
        ret['comment'] = 'Unable to use "seconds", "minutes", "hours", or "days" with "when" or "cron" options.'
        return ret

    if 'when' in kwargs and 'cron' in kwargs:
        ret['result'] = False
        ret['comment'] = 'Unable to use "when" and "cron" options together.  Ignoring.'
        return ret

    for item in ['seconds', 'minutes', 'hours', 'days']:
        if item in kwargs:
            schedule[name][item] = kwargs[item]

    if 'return_job' in kwargs:
        schedule[name]['return_job'] = kwargs['return_job']

    if 'metadata' in kwargs:
        schedule[name]['metadata'] = kwargs['metadata']

    if 'job_args' in kwargs:
        schedule[name]['args'] = kwargs['job_args']

    if 'job_kwargs' in kwargs:
        schedule[name]['kwargs'] = kwargs['job_kwargs']

    if 'maxrunning' in kwargs:
        schedule[name]['maxrunning'] = kwargs['maxrunning']
    else:
        schedule[name]['maxrunning'] = 1

    if 'name' in kwargs:
        schedule[name]['name'] = kwargs['name']
    else:
        schedule[name]['name'] = name

    if 'jid_include' not in kwargs or kwargs['jid_include']:
        schedule[name]['jid_include'] = True

    if 'splay' in kwargs:
        if isinstance(kwargs['splay'], dict):
            # Ensure ordering of start and end arguments
            schedule[name]['splay'] = salt.utils.odict.OrderedDict()
            schedule[name]['splay']['start'] = kwargs['splay']['start']
            schedule[name]['splay']['end'] = kwargs['splay']['end']
        else:
            schedule[name]['splay'] = kwargs['splay']

    for item in ['range', 'when', 'once', 'once_fmt', 'cron', 'returner',
            'return_config']:
        if item in kwargs:
            schedule[name][item] = kwargs[item]

    return schedule[name]


def add(name, **kwargs):
    '''
    Add a job to the schedule

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.add job1 function='test.ping' seconds=3600
        # If function have some arguments, use job_args
        salt '*' schedule.add job2 function='cmd.run' job_args="['date >> /tmp/date.log']" seconds=60
    '''

    ret = {'comment': [],
           'result': True}

    current_schedule = __opts__['schedule'].copy()
    if 'schedule' in __pillar__:
        current_schedule.update(__pillar__['schedule'])

    if name in current_schedule:
        ret['comment'] = 'Job {0} already exists in schedule.'.format(name)
        ret['result'] = False
        return ret

    if not name:
        ret['comment'] = 'Job name is required.'
        ret['result'] = False

    time_conflict = False
    for item in ['seconds', 'minutes', 'hours', 'days']:
        if item in kwargs and 'when' in kwargs:
            time_conflict = True
        if item in kwargs and 'cron' in kwargs:
            time_conflict = True

    if time_conflict:
        ret['result'] = False
        ret['comment'] = 'Error: Unable to use "seconds", "minutes", "hours", or "days" with "when" or "cron" options.'
        return ret

    if 'when' in kwargs and 'cron' in kwargs:
        ret['result'] = False
        ret['comment'] = 'Unable to use "when" and "cron" options together.  Ignoring.'
        return ret

    _new = build_schedule_item(name, **kwargs)

    schedule = {}
    schedule[name] = _new

    if 'test' in kwargs and kwargs['test']:
        ret['comment'] = 'Job: {0} would be added to schedule.'.format(name)
    else:
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

    ret = {'comment': '',
           'changes': {},
           'result': True}

    time_conflict = False
    for item in ['seconds', 'minutes', 'hours', 'days']:
        if item in kwargs and 'when' in kwargs:
            time_conflict = True

        if item in kwargs and 'cron' in kwargs:
            time_conflict = True

    if time_conflict:
        ret['result'] = False
        ret['comment'] = 'Error: Unable to use "seconds", "minutes", "hours", or "days" with "when" option.'
        return ret

    if 'when' in kwargs and 'cron' in kwargs:
        ret['result'] = False
        ret['comment'] = 'Unable to use "when" and "cron" options together.  Ignoring.'
        return ret

    current_schedule = __opts__['schedule'].copy()
    if 'schedule' in __pillar__:
        current_schedule.update(__pillar__['schedule'])

    if name not in current_schedule:
        ret['comment'] = 'Job {0} does not exist in schedule.'.format(name)
        ret['result'] = False
        return ret

    _current = current_schedule[name]
    if '_seconds' in _current:
        _current['seconds'] = _current['_seconds']
        del _current['_seconds']

    _new = build_schedule_item(name, **kwargs)
    if _new == _current:
        ret['comment'] = 'Job {0} in correct state'.format(name)
        return ret

    _current_lines = ['{0}:{1}\n'.format(key, value)
                      for (key, value) in sorted(_current.items())]
    _new_lines = ['{0}:{1}\n'.format(key, value)
                  for (key, value) in sorted(_new.items())]
    _diff = difflib.unified_diff(_current_lines, _new_lines)

    ret['changes']['diff'] = ''.join(_diff)

    if name in __opts__['schedule']:
        if 'test' in kwargs and kwargs['test']:
            ret['comment'] = 'Job: {0} would be modified in schedule.'.format(name)
        else:
            out = __salt__['event.fire']({'name': name, 'schedule': _new, 'func': 'modify'}, 'manage_schedule')
            if out:
                ret['comment'] = 'Modified job: {0} in schedule.'.format(name)
            else:
                ret['comment'] = 'Failed to modify job {0} in schedule.'.format(name)
                ret['result'] = False
    elif 'schedule' in __pillar__ and name in __pillar__['schedule']:
        if 'test' in kwargs and kwargs['test']:
            ret['comment'] = 'Job: {0} would be modified in schedule.'.format(name)
        else:
            out = __salt__['event.fire']({'name': name, 'schedule': _new, 'where': 'pillar', 'func': 'modify'}, 'manage_schedule')
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


def enable_job(name, **kwargs):
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
        if 'test' in __opts__ and __opts__['test']:
            ret['comment'] = 'Job: {0} would be enabled in schedule.'.format(name)
        else:
            out = __salt__['event.fire']({'name': name, 'func': 'enable_job'}, 'manage_schedule')
            if out:
                ret['comment'] = 'Enabled Job {0} in schedule.'.format(name)
            else:
                ret['comment'] = 'Failed to enable job {0} from schedule.'.format(name)
                ret['result'] = False
    elif 'schedule' in __pillar__ and name in __pillar__['schedule']:
        if 'test' in kwargs and kwargs['test']:
            ret['comment'].append('Job: {0} would be enabled in schedule.'.format(name))
        else:
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


def disable_job(name, **kwargs):
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
        if 'test' in kwargs and kwargs['test']:
            ret['comment'] = 'Job: {0} would be disabled in schedule.'.format(name)
        else:
            out = __salt__['event.fire']({'name': name, 'func': 'disable_job'}, 'manage_schedule')
            if out:
                ret['comment'] = 'Disabled Job {0} in schedule.'.format(name)
            else:
                ret['comment'] = 'Failed to disable job {0} from schedule.'.format(name)
                ret['result'] = False
    elif 'schedule' in __pillar__ and name in __pillar__['schedule']:
        if 'test' in kwargs and kwargs['test']:
            ret['comment'].append('Job: {0} would be disabled in schedule.'.format(name))
        else:
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

    schedule = list_(return_yaml=False)

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


def enable(**kwargs):
    '''
    Enable all scheduled jobs on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.enable
    '''

    ret = {'comment': [],
           'result': True}

    if 'test' in kwargs and kwargs['test']:
        ret['comment'] = 'Schedule would be enabled.'
    else:
        out = __salt__['event.fire']({'func': 'enable'}, 'manage_schedule')
        if out:
            ret['comment'] = 'Enabled schedule on minion.'
        else:
            ret['comment'] = 'Failed to enable schedule on minion.'
            ret['result'] = False
    return ret


def disable(**kwargs):
    '''
    Disable all scheduled jobs on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.disable
    '''

    ret = {'comment': [],
           'result': True}

    if 'test' in kwargs and kwargs['test']:
        ret['comment'] = 'Schedule would be disabled.'
    else:
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

        if schedule:
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
        else:
            ret['comment'].append('Failed to reload schedule on minion.  Saved file is empty or invalid.')
            ret['result'] = False
    return ret


def move(name, target, **kwargs):
    '''
    Move scheduled job to another minion or minions.

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.move jobname target
    '''

    ret = {'comment': [],
           'result': True}

    if not name:
        ret['comment'] = 'Job name is required.'
        ret['result'] = False

    if name in __opts__['schedule']:
        if 'test' in kwargs and kwargs['test']:
            ret['comment'] = 'Job: {0} would be moved from schedule.'.format(name)
        else:
            schedule_opts = []
            for key, value in six.iteritems(__opts__['schedule'][name]):
                temp = '{0}={1}'.format(key, value)
                schedule_opts.append(temp)
            response = __salt__['publish.publish'](target, 'schedule.add', schedule_opts)

            # Get errors and list of affeced minions
            errors = []
            minions = []
            for minion in response:
                minions.append(minion)
                if not response[minion]:
                    errors.append(minion)

            # parse response
            if not response:
                ret['comment'] = 'no servers answered the published schedule.add command'
                return ret
            elif len(errors) > 0:
                ret['comment'] = 'the following minions return False'
                ret['minions'] = errors
                return ret
            else:
                delete(name)
                ret['result'] = True
                ret['comment'] = 'Moved Job {0} from schedule.'.format(name)
                ret['minions'] = minions
                return ret
    elif 'schedule' in __pillar__ and name in __pillar__['schedule']:
        if 'test' in kwargs and kwargs['test']:
            ret['comment'] = 'Job: {0} would be moved from schedule.'.format(name)
        else:
            schedule_opts = []
            for key, value in six.iteritems(__opts__['schedule'][name]):
                temp = '{0}={1}'.format(key, value)
                schedule_opts.append(temp)
            response = __salt__['publish.publish'](target, 'schedule.add', schedule_opts)

            # Get errors and list of affeced minions
            errors = []
            minions = []
            for minion in response:
                minions.append(minion)
                if not response[minion]:
                    errors.append(minion)

            # parse response
            if not response:
                ret['comment'] = 'no servers answered the published schedule.add command'
                return ret
            elif len(errors) > 0:
                ret['comment'] = 'the following minions return False'
                ret['minions'] = errors
                return ret
            else:
                delete(name, where='pillar')
                ret['result'] = True
                ret['comment'] = 'Moved Job {0} from schedule.'.format(name)
                ret['minions'] = minions
                return ret
    else:
        ret['comment'] = 'Job {0} does not exist.'.format(name)
        ret['result'] = False
    return ret


def copy(name, target, **kwargs):
    '''
    Copy scheduled job to another minion or minions.

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.copy jobname target
    '''

    ret = {'comment': [],
           'result': True}

    if not name:
        ret['comment'] = 'Job name is required.'
        ret['result'] = False

    if name in __opts__['schedule']:
        if 'test' in kwargs and kwargs['test']:
            ret['comment'] = 'Job: {0} would be copied.'.format(name)
        else:
            schedule_opts = []
            for key, value in six.iteritems(__opts__['schedule'][name]):
                temp = '{0}={1}'.format(key, value)
                schedule_opts.append(temp)
            response = __salt__['publish.publish'](target, 'schedule.add', schedule_opts)

            # Get errors and list of affeced minions
            errors = []
            minions = []
            for minion in response:
                minions.append(minion)
                if not response[minion]:
                    errors.append(minion)

            # parse response
            if not response:
                ret['comment'] = 'no servers answered the published schedule.add command'
                return ret
            elif len(errors) > 0:
                ret['comment'] = 'the following minions return False'
                ret['minions'] = errors
                return ret
            else:
                ret['result'] = True
                ret['comment'] = 'Copied Job {0} from schedule to minion(s).'.format(name)
                ret['minions'] = minions
                return ret
    elif 'schedule' in __pillar__ and name in __pillar__['schedule']:
        if 'test' in kwargs and kwargs['test']:
            ret['comment'] = 'Job: {0} would be moved from schedule.'.format(name)
        else:
            schedule_opts = []
            for key, value in six.iteritems(__opts__['schedule'][name]):
                temp = '{0}={1}'.format(key, value)
                schedule_opts.append(temp)
            response = __salt__['publish.publish'](target, 'schedule.add', schedule_opts)

            # Get errors and list of affeced minions
            errors = []
            minions = []
            for minion in response:
                minions.append(minion)
                if not response[minion]:
                    errors.append(minion)

            # parse response
            if not response:
                ret['comment'] = 'no servers answered the published schedule.add command'
                return ret
            elif len(errors) > 0:
                ret['comment'] = 'the following minions return False'
                ret['minions'] = errors
                return ret
            else:
                ret['result'] = True
                ret['comment'] = 'Copied Job {0} from schedule to minion(s).'.format(name)
                ret['minions'] = minions
                return ret
    else:
        ret['comment'] = 'Job {0} does not exist.'.format(name)
        ret['result'] = False
    return ret
