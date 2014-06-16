# -*- coding: utf-8 -*-
'''
Management of cron, the Unix command scheduler
==============================================

Cron declarations require a number of parameters. The following are the
parameters used by Salt to define the various timing values for a cron job:

* ``minute``
* ``hour``
* ``daymonth``
* ``month``
* ``dayweek`` (0 to 6 are Sunday through Saturday, 7 can also be used for
  Sunday)

.. warning::

    Any timing arguments not specified take a value of ``*``. This means that
    setting ``hour`` to ``5``, while not defining the ``minute`` param, will
    result in Salt adding a job that will execute every minute between 5 and 6
    A.M.!

    Additionally, the default user for these states is ``root``. Therefore, if
    the cron job is for another user, it is necessary to specify that user with
    the ``user`` parameter.

A long time ago (before 2014.2), when making changes to an existing cron job,
the name declaration is the parameter used to uniquely identify the job,
so if an existing cron that looks like this:

.. code-block:: yaml

    date > /tmp/crontest:
      cron.present:
        - user: root
        - minute: 5

Is changed to this:

.. code-block:: yaml

    date > /tmp/crontest:
      cron.present:
        - user: root
        - minute: 7
        - hour: 2

Then the existing cron will be updated, but if the cron command is changed,
then a new cron job will be added to the user's crontab.

The current behavior is still relying on that mechanism, but you can also
specify an identifier to identify your crontabs:
.. versionadded:: 2014.2
.. code-block:: yaml

    date > /tmp/crontest:
      cron.present:
        - identifier: SUPERCRON
        - user: root
        - minute: 7
        - hour: 2

And, some months later, you modify it:
.. versionadded:: 2014.2
.. code-block:: yaml

    superscript > /tmp/crontest:
      cron.present:
        - identifier: SUPERCRON
        - user: root
        - minute: 3
        - hour: 4

The old **date > /tmp/crontest** will be replaced by
**superscript > /tmp/crontest**.

Additionally, Salt also supports running a cron every ``x minutes`` very similarly to the Unix
convention of using ``*/5`` to have a job run every five minutes. In Salt, this
looks like:

.. code-block:: yaml

    date > /tmp/crontest:
      cron.present:
        - user: root
        - minute: '*/5'

The job will now run every 5 minutes.

Additionally, the temporal parameters (minute, hour, etc.) can be randomized by
using ``random`` instead of using a specific value. For example, by using the
``random`` keyword in the ``minute`` parameter of a cron state, the same cron
job can be pushed to hundreds or thousands of hosts, and they would each use a
randomly-generated minute. This can be helpful when the cron job accesses a
network resource, and it is not desirable for all hosts to run the job
concurrently.

.. code-block:: yaml

    /path/to/cron/script:
      cron.present:
        - user: root
        - minute: random
        - hour: 2

.. versionadded:: 0.16.0

Since Salt assumes a value of ``*`` for unspecified temporal parameters, adding
a parameter to the state and setting it to ``random`` will change that value
from ``*`` to a randomized numeric value. However, if that field in the cron
entry on the minion already contains a numeric value, then using the ``random``
keyword will not modify it.
'''

import logging
log = logging.getLogger(__name__)


def present(name,
            **kwargs):
    '''
    Verifies that the specified cron job is present for the specified user.
    For more advanced information about what exactly can be set in the cron
    timing parameters, check your cron system's documentation. Most Unix-like
    systems' cron documentation can be found via the crontab man page:
    ``man 5 crontab``.

    name
        The command that should be executed by the cron job.

    minute
        The information to be set into the minute section, this can be any
        string supported by your cron system's the minute field. Default is
        ``*``

    hour
        The information to be set in the hour section. Default is ``*``

    daymonth
        The information to be set in the day of month section. Default is ``*``

    month
        The information to be set in the month section. Default is ``*``

    dayweek
        The information to be set in the day of week section. Default is ``*``

    comment
        User comment to be added on line previous the cron job

    identifier
        Custom-defined identifier for tracking the cron line for future crontab
        edits. This defaults to the state id
    '''

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': []}

    current_schedule = __salt__['schedule.list'](show_all=True, return_yaml=False)

    if name in current_schedule:
        new_item = __salt__['schedule.build_schedule_item'](name, **kwargs)
        if new_item == current_schedule[name]:
            ret['comment'].append('Job {0} in correct state'.format(name))
        else:
            result = __salt__['schedule.modify'](name, **kwargs)
            if not result['result']:
                ret['result'] = result['result']
                ret['comment'].append(result['comment'])
                return ret
            else:
                ret['comment'].append('Modifying job {0} in schedule'.format(name))
                ret['changes'] = result['changes']
    else:
        result = __salt__['schedule.add'](name, **kwargs)
        if not result['result']:
            ret['result'] = result['result']
            ret['comment'].append(result['comment'])
            return ret
        else:
            ret['comment'].append('Adding new job {0} to schedule'.format(name))

    ret['comment'] = '\n'.join(ret['comment'])
    return ret


def absent(name, **kwargs):
    '''
    Verifies that the specified cron job is absent for the specified user; only
    the name is matched when removing a cron job.

    name
        The command that should be absent in the user crontab.

    user
        The name of the user whose crontab needs to be modified, defaults to
        the root user

    identifier
        Custom-defined identifier for tracking the cron line for future crontab
        edits. This defaults to the state id
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
        result = __salt__['schedule.delete'](name)
        if not result['result']:
            ret['result'] = result['result']
            ret['comment'].append(result['comment'])
        else:
            ret['comment'].append('Removed job {0} from schedule'.format(name))
    else:
            ret['comment'].append('Job {0} not present in schedule'.format(name))

    ret['comment'] = '\n'.join(ret['comment'])
    return ret
