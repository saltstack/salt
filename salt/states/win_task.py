# -*- coding: utf-8 -*-
# https://msdn.microsoft.com/en-us/library/windows/desktop/aa383608(v=vs.85).aspx
from __future__ import absolute_import, print_function, unicode_literals


# State Module for managing task scheduler on Windows.
# You can add or remove tasks.

# Import Python libs
import copy
import logging
import time

# Import salt libs
import salt.utils.data
import salt.utils.platform
import salt.utils.dateutils

# Import 3rd-party libs
try:
    import pywintypes
except ImportError:
    pass


ACTION_PARTS = {'Execute': ['cmd'],
                'Email': ['from', 'to', 'cc', 'server'],
                'Message': ['title', 'message']}

OPTIONAL_ACTION_PARTS = {'start_in': '',
                         'arguments': ''}

TRIGGER_PARTS = {'Event': ['subscription'],
                 'Once': [],
                 'Daily': ['days_interval'],
                 'Weekly': ['days_of_week', 'weeks_interval'],
                 'Monthly': ['months_of_year', 'days_of_month', 'last_day_of_month'],
                 'MonthlyDay': ['months_of_year', 'weeks_of_month', 'days_of_week'],
                 'OnIdle': [],
                 'OnTaskCreation': [],
                 'OnBoot': [],
                 'OnLogon': [],
                 'OnSessionChange': ['state_change']}

OPTIONAL_TRIGGER_PARTS = {'trigger_enabled': True,
                          'start_date': time.strftime('%Y-%m-%d'),
                          'start_time': time.strftime('%H:%M:%S'),
                          'end_date': None,
                          'end_time': "00:00:00",
                          'random_delay': False,
                          'repeat_interval': None,
                          'repeat_duration': None,
                          'repeat_stop_at_duration_end': False,
                          'execution_time_limit': '3 days',
                          'delay': False}

OPTIONAL_CONDITIONS_PARTS = {'ac_only': True,
                             'run_if_idle': False,
                             'run_if_network': False,
                             'start_when_available': False}

OPTIONAL_SETTINGS_PARTS = {'allow_demand_start': True,
                           'delete_after': False,
                           'execution_time_limit': '3 days',
                           'force_stop': True,
                           'multiple_instances': 'No New Instance',
                           'restart_interval': False,
                           'stop_if_on_batteries': True,
                           'wake_to_run': False}

TASK_PARTS = {'actions': {'parts': ACTION_PARTS, 'optional': OPTIONAL_ACTION_PARTS},
              'triggers': {'parts': TRIGGER_PARTS, 'optional': OPTIONAL_TRIGGER_PARTS},
              'conditions': {'parts': {}, 'optional': OPTIONAL_CONDITIONS_PARTS},
              'settings': {'parts': {}, 'optional': OPTIONAL_SETTINGS_PARTS}}

log = logging.getLogger(__name__)

__virtualname__ = 'task'


def __virtual__():
    '''
    Load only on minions running on Windows and with task Module loaded.
    '''
    if not salt.utils.platform.is_windows() or 'task.list_tasks' not in __salt__ or\
        'pywintypes' not in globals():
        return False, 'State win_task: state only works on Window systems with task loaded'
    return __virtualname__


def _get_state_data(name):
    r'''
    will return a new blank state dict.

    :param str name: name of task.

    :return new state data:
    :rtype dict:
    '''
    return {'name': name,
            'changes': {},
            'result': True,
            'comment': ''}


def _valid_location(location):
    r'''
    will test to see if task location is valid.

    :param str location: location of task.

    :return True if location is vaild, False if location is not valid:
    :rtype bool:
    '''
    try:
        __salt__['task.list_tasks'](location)
    except pywintypes.com_error:
        return False
    return True


def _get_task_state_data(name,
                         location):
    r'''
    will get the state of a task.

    :param str name: name of task

    :param str location: location of task.

    :return task state:
    :rtype dict:
    '''
    task_state = {'location_valid': False,
                  'task_found': False,
                  'task_info': {}}

    # if valid location then try to get more info on task
    if _valid_location(location):
        task_state['location_valid'] = True
        task_state['task_found'] = name in __salt__['task.list_tasks'](location)
        # if task was found then get actions and triggers info
        if task_state['task_found']:
            task_info = __salt__['task.info'](name, location)
            task_state['task_info'] = {key: task_info[key] for key in TASK_PARTS}

    return task_state


def _get_arguments(arguments_given,
                   key_arguments,
                   arguments_need_it,
                   optional_arguments):
    block = {}
    # check if key arguments are present
    for key in key_arguments:
        if key not in arguments_given:
            return 'Missing key argument {0}'.format(repr(key))
        block[key] = arguments_given[key]

        # check is key item valid
        if block[key] not in arguments_need_it:
            return '{0} item {1} is not in key item list {2}'.format(repr(key), repr(block[key]), list(arguments_need_it))

        # check is key2 present
        for key2 in arguments_need_it[block[key]]:
            if key2 not in arguments_given:
                return 'Missing {0} argument'.format(key2)
            block[key2] = arguments_given[key2]

    # add optional arguments if their not present
    for key in optional_arguments:
        if key in arguments_given:
            block[key] = arguments_given[key]
        else:
            block[key] = optional_arguments[key]

    return block


def _task_state_prediction_bandage(state):
    r'''
    A bandage to format and add arguments to a task state.
    This is so task states can be compared.

    :param dict state: task state
    :return task state:
    :rtype dict:
    '''

    # add 'enabled = True' to all triggers
    # this is because triggers will add this argument after their made
    if 'triggers' in state['task_info']:
        for trigger in state['task_info']['triggers']:
            trigger['enabled'] = True

    # format dates
    for trigger in state['task_info']['triggers']:
        for key in ['start_date', 'end_data']:
            if key in trigger:
                # if except is triggered don't format the date
                try:
                    div = [d for d in ['-', '/'] if d in trigger[key]][0]
                    part1, part2, part3 = trigger[key].split(div)
                    if len(part1) == 4:
                        year, month, day = part1, part2, part3
                    else:
                        month, day, year = part1, part2, part3
                        if len(year) != 4:
                            year = time.strftime('%Y')[:2] + year

                    trigger[key] = salt.utils.dateutils.strftime("{0}-{1}-{2}".format(year, month, day), '%Y-%m-%d')
                except IndexError:
                    pass
                except ValueError:
                    pass

    # format times
    for trigger in state['task_info']['triggers']:
        for key in ['start_time', 'end_time']:
            if key in trigger:
                try:
                    trigger[key] = salt.utils.dateutils.strftime(trigger[key], '%H:%M:%S')
                except ValueError:
                    pass

    return state


def _get_task_state_prediction(state,
                              new_task):
    r'''
        predicts what a the new task will look like

    :param dict state:
    :param dict new_task:
    :return task state:
    :rtype dict:
    '''

    new_state = copy.deepcopy(state)

    # if location not valid state can't be made
    if state['location_valid']:
        new_state['task_found'] = True
        new_state['task_info'] = {'actions': [new_task['action']],
                                  'triggers': [new_task['trigger']],
                                  'conditions': new_task['conditions'],
                                  'settings': new_task['settings']}

        action_keys = set()
        trigger_keys = set()
        if state['task_found']:
            # get all the arguments used by actions
            for action in state['task_info']['actions']:
                action_keys = action_keys.union(set(action))

            # get all the arguments used by triggers
            for trigger in state['task_info']['triggers']:
                trigger_keys = trigger_keys.union(set(trigger))

        # get setup for the for loop below
        arguments_filter = [[new_state['task_info']['actions'], action_keys, TASK_PARTS['actions']['optional']],
                            [new_state['task_info']['triggers'], trigger_keys, TASK_PARTS['triggers']['optional']]]

        # removes any optional arguments that are equal to the default and is not used by the state
        for argument_list, safe_keys, optional_keys in arguments_filter:
            for dic in argument_list:
                for key in list(dic):
                    if key not in safe_keys and key in optional_keys:
                        if dic[key] == optional_keys[key]:
                            del dic[key]

        # removes add on arguments from triggers
        # this is because task info does not give this info
        argument_add_on = set(sum([TRIGGER_PARTS[key] for key in TRIGGER_PARTS], []))
        for trigger in new_state['task_info']['triggers']:
            for key in list(trigger):
                if key in argument_add_on:
                    del trigger[key]

    return _task_state_prediction_bandage(new_state)


def present(name,
            location='\\',
            user_name='System',
            password=None,
            force=False,
            **kwargs):
    r'''
    Create a new task in the designated location. This function has many keyword
    arguments that are not listed here. For additional arguments see:

    - :py:func:`edit_task`
    - :py:func:`add_action`
    - :py:func:`add_trigger`

    :param str name: The name of the task. This will be displayed in the task
        scheduler.

    :param str location: A string value representing the location in which to
        create the task. Default is '\\' which is the root for the task
        scheduler (C:\Windows\System32\tasks).

    :param str user_name: The user account under which to run the task. To
        specify the 'System' account, use 'System'. The password will be
        ignored.

    :param str password: The password to use for authentication. This should set
        the task to run whether the user is logged in or not, but is currently
        not working.

    :param bool force: If the task exists, overwrite the existing task.

    :return dict state:
    :rtype dict:

    CLI Example:

        .. code-block::YAML

             test_win_task_present:
               task.present:
                 - name: salt
                 - location: ''
                 - force: True
                 - action_type: Execute
                 - cmd: 'del /Q /S C:\\Temp'
                 - trigger_type: Once
                 - start_date: 12-1-16
                 - start_time: 01:00

        .. code-block:: bash

            salt 'minion-id' state.apply <YAML file>
    '''

    ret = _get_state_data(name)
    before = _get_task_state_data(name, location)

    # if location not valid the task present will fail
    if not before['location_valid']:
        ret['result'] = False
        ret['comment'] = '{0} is not a valid file location'.format(repr(location))
        return ret

    # split up new task into all its parts
    new_task = {'action': _get_arguments(kwargs, ['action_type'],
                                         TASK_PARTS['actions']['parts'], TASK_PARTS['actions']['optional']),
                'trigger': _get_arguments(kwargs, ['trigger_type'],
                                          TASK_PARTS['triggers']['parts'], TASK_PARTS['triggers']['optional']),
                'conditions': _get_arguments(kwargs, [],
                                             TASK_PARTS['conditions']['parts'], TASK_PARTS['conditions']['optional']),
                'settings': _get_arguments(kwargs, [],
                                           TASK_PARTS['settings']['parts'], TASK_PARTS['settings']['optional'])}

    # if win os is higher than 7 then Email and Message action_type is not supported
    try:
        if int(__grains__['osversion'].split('.')[0]) >= 8 and new_task['action']['action_type'] in ['Email', 'Message']:
            log.warning('This OS %s does not support Email or Message action_type.', __grains__['osversion'])
    except ValueError:
        pass

    for key in new_task:
        # if string is returned then an error happened
        if isinstance(new_task[key], str):
            ret['comment'] = '{0}: {1}'.format(key, new_task[key])
            ret['result'] = False
            return ret

    if __opts__['test']:
        # if force is False and task is found then no changes will take place
        if not force and before['task_found']:
            ret['comment'] = '\'force=True\' will allow the new task to replace the old one'
            ret['result'] = False
            log.warning("force=False")
            return ret

        after = _get_task_state_prediction(before, new_task)
        ret['result'] = None
        # the task will not change
        if before == after:
            ret['result'] = True
            return ret

        ret['changes'] = salt.utils.data.compare_dicts(before, after)
        return ret

    # put all the arguments to kwargs
    for key in new_task:
        kwargs.update(new_task[key])

    # make task
    ret['result'] = __salt__['task.create_task'](name=name,
                                                 location=location,
                                                 user_name=user_name,
                                                 password=password,
                                                 force=force,
                                                 **kwargs)

    # if 'task.crate_task' returns a str then task did not change
    if isinstance(ret['result'], str):
        ret['comment'] = '\'force=True\' will allow the new task to replace the old one'
        ret['result'] = False
        log.warning("force=False")
        return ret

    after = _get_task_state_data(name, location)

    if after['task_info']['actions'][0]['action_type'] != kwargs['action_type']:
        ret['comment'] = 'failed to make action'
        ret['result'] = False
    elif after['task_info']['triggers'][0]['trigger_type'] != kwargs['trigger_type']:
        ret['comment'] = 'failed to make trigger'
        ret['result'] = False

    ret['changes'] = salt.utils.data.compare_dicts(before, after)
    return ret


def absent(name,
           location='\\'):
    r'''
    Delete a task from the task scheduler.

    :param str name: The name of the task to delete.

    :param str location: A string value representing the location of the task.
        Default is '\\' which is the root for the task scheduler
        (C:\Windows\System32\tasks).

    :return True if successful, False if unsuccessful:
    :rtype bool:

    CLI Example:

    .. code-block::YAML

         test_win_task_absent:
           task.absent:
             - name: salt
             - location: ''

    .. code-block:: bash

        salt 'minion-id' state.apply <YAML file>
    '''

    ret = _get_state_data(name)
    before = _get_task_state_data(name, location)

    # if location not valid the task present will fail
    if not before['location_valid']:
        ret['result'] = False
        ret['comment'] = '{0} is not a valid file location'.format(repr(location))
        return ret

    if __opts__['test']:
        # if task was not found then no changes
        if not before['task_found']:
            ret['result'] = True
            ret['changes'] = salt.utils.data.compare_dicts(before, before)
        else:
            # if task was found then changes will happen
            ret['result'] = None
            ret['changes'] = salt.utils.data.compare_dicts(before, {'location_valid': True,
                                                                    'task_found': False,
                                                                    'task_info': {}})
        return ret

    # if task was found then delete it
    if before['task_found']:
        # try to delete task
        ret['result'] = __salt__['task.delete_task'](name=name,
                                                     location=location)

    # if 'task.delete_task' returns a str then task was not deleted
    if isinstance(ret['result'], str):
        ret['result'] = False

    ret['changes'] = salt.utils.data.compare_dicts(before, _get_task_state_data(name, location))
    return ret
