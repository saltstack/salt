# -*- coding: utf-8 -*-
'''
Management of the Salt scheduler
==============================================

.. code-block:: yaml

    job3:
      schedule.present:
        - function: test.ping
        - seconds: 3600
        - splay: 10

    This will schedule the command: test.ping every 3600 seconds
    (every hour) splaying the time between 0 and 10 seconds

    job2:
      schedule.present:
        - function: test.ping
        - seconds: 15
        - splay:
            - start: 10
            - end: 20

    This will schedule the command: test.ping every 3600 seconds
    (every hour) splaying the time between 10 and 20 seconds

    job1:
      schedule.present:
        - function: state.sls
        - job_args:
          - httpd
        - job_kwargs:
            test: True
        - when:
            - Monday 5:00pm
            - Tuesday 3:00pm
            - Wednesday 5:00pm
            - Thursday 3:00pm
            - Friday 5:00pm

    This will schedule the command: state.sls httpd test=True at 5pm on Monday,
    Wednesday and Friday, and 3pm on Tuesday and Thursday.  Requires that
    python-dateutil is installed on the minion.

    job1:
      schedule.present:
        - function: state.sls
        - job_args:
          - httpd
        - job_kwargs:
            test: True
        - cron: '*/5 * * * *'

    Scheduled jobs can also be specified using the format used by cron.  This will
    schedule the command: state.sls httpd test=True to run every 5 minutes.  Requires
    that python-croniter is installed on the minion.

    job1:
      schedule.present:
        - function: state.sls
        - args:
          - httpd
        - kwargs:
            test: True
        - when:
            - Monday 5:00pm
            - Tuesday 3:00pm
            - Wednesday 5:00pm
            - Thursday 3:00pm
            - Friday 5:00pm
        - returner: xmpp
        - return_config: xmpp_state_run

    This will schedule the command: state.sls httpd test=True at 5pm on Monday,
    Wednesday and Friday, and 3pm on Tuesday and Thursday.  Using the xmpp returner
    to return the results of the scheduled job, with the alternative configuration
    options found in the xmpp_state_run section.

'''


def present(name,
            **kwargs):
    '''
    Ensure a job is present in the schedule

    name
        The unique name that is given to the scheduled job.

    seconds
        The scheduled job will be executed after the specified
        number of seconds have passed.

    minutes
        The scheduled job will be executed after the specified
        number of minutes have passed.

    hours
        The scheduled job will be executed after the specified
        number of hours have passed.

    days
        The scheduled job will be executed after the specified
        number of days have passed.

    when
        This will schedule the job at the specified time(s).
        The when parameter must be a single value or a dictionary
        with the date string(s) using the dateutil format.
        Requires python-dateutil.

    cron
        This will schedule the job at the specified time(s)
        using the crontab format.
        Requires python-croniter.

    function
        The function that should be executed by the scheduled job.

    job_args
        The arguments that will be used by the scheduled job.

    job_kwargs
        The keyword arguments that will be used by the scheduled job.

    maxrunning
        Ensure that there are no more than N copies of a particular job running.

    jid_include
        Include the job into the job cache.

    splay
        The amount of time in seconds to splay a scheduled job.
        Can be specified as a single value in seconds or as a dictionary
        range with 'start' and 'end' values.

    range
        This will schedule the command within the range specified.
        The range parameter must be a dictionary with the date strings
        using the dateutil format. Requires python-dateutil.

    once
        This will schedule a job to run once on the specified date.

    once_fmt
        The default date format is ISO 8601 but can be overridden by
        also specifying the ``once_fmt`` option.

    enabled
        Whether the job should be enabled or disabled.  Value should be a boolean.

    return_job
        Whether to return information to the Salt master upon job completion.

    metadata
        Using the metadata parameter special values can be associated with
        a scheduled job.  These values are not used in the execution of the job,
        but can be used to search for specific jobs later if combined with the
        return_job parameter.  The metadata parameter must be specified as a
        dictionary, othewise it will be ignored.

    returner
        The returner to use to return the results of the scheduled job.

    return_config
        The alternative configuration to use for returner configuration options.

    '''

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': []}

    current_schedule = __salt__['schedule.list'](show_all=True, return_yaml=False)

    if name in current_schedule:
        new_item = __salt__['schedule.build_schedule_item'](name, **kwargs)

        # See if the new_item is valid
        if isinstance(new_item, dict):
            if 'result' in new_item and not new_item['result']:
                ret['result'] = new_item['result']
                ret['comment'] = new_item['comment']
                return ret

        if new_item == current_schedule[name]:
            ret['comment'].append('Job {0} in correct state'.format(name))
        else:
            if 'test' in __opts__ and __opts__['test']:
                kwargs['test'] = True
                result = __salt__['schedule.modify'](name, **kwargs)
                ret['comment'].append(result['comment'])
                ret['changes'] = result['changes']
            else:
                result = __salt__['schedule.modify'](name, **kwargs)
                if not result['result']:
                    ret['result'] = result['result']
                    ret['comment'] = result['comment']
                    return ret
                else:
                    ret['comment'].append('Modifying job {0} in schedule'.format(name))
                    ret['changes'] = result['changes']
    else:
        if 'test' in __opts__ and __opts__['test']:
            kwargs['test'] = True
            result = __salt__['schedule.add'](name, **kwargs)
            ret['comment'].append(result['comment'])
        else:
            result = __salt__['schedule.add'](name, **kwargs)
            if not result['result']:
                ret['result'] = result['result']
                ret['comment'] = result['comment']
                return ret
            else:
                ret['comment'].append('Adding new job {0} to schedule'.format(name))

    ret['comment'] = '\n'.join(ret['comment'])
    return ret


def absent(name, **kwargs):
    '''
    Ensure a job is absent from the schedule

    name
        The unique name that is given to the scheduled job.

    '''
    ### NOTE: The keyword arguments in **kwargs are ignored in this state, but
    ###       cannot be removed from the function definition, otherwise the use
    ###       of unsupported arguments will result in a traceback.

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': []}

    current_schedule = __salt__['schedule.list'](show_all=True, return_yaml=False)
    if name in current_schedule:
        if 'test' in __opts__ and __opts__['test']:
            kwargs['test'] = True
            result = __salt__['schedule.delete'](name, **kwargs)
            ret['comment'].append(result['comment'])
        else:
            result = __salt__['schedule.delete'](name, **kwargs)
            if not result['result']:
                ret['result'] = result['result']
                ret['comment'] = result['comment']
                return ret
            else:
                ret['comment'].append('Removed job {0} from schedule'.format(name))
    else:
        ret['comment'].append('Job {0} not present in schedule'.format(name))

    ret['comment'] = '\n'.join(ret['comment'])
    return ret
