'''
Management of cron, the Unix command scheduler.
===============================================

The cron state module allows for user crontabs to be cleanly managed.

Cron declarations require a number of parameters. The timing parameters, need
to be declared, minute, hour, daymonth, month and dayweek. The  user who's
crontab is to be edited also needs to be defined.

By default the timing arguments are all ``*`` and the user is root. When
making changes to an existing cron job the name declaration is the unique
factor, so if and existing cron that looks like this:

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
'''


def _check_cron(cmd, user, minute, hour, dom, month, dow):
    '''
    Return the changes
    '''
    lst = __salt__['cron.list_tab'](user)
    for cron in lst['crons']:
        if cmd == cron['cmd']:
            if not minute == cron['min'] or \
                    not hour == cron['hour'] or \
                    not dom == cron['daymonth'] or \
                    not month == cron['month'] or \
                    not dow == cron['dayweek']:
                return 'update'
            return 'present'
    return 'absent'


def present(name,
        user='root',
        minute='*',
        hour='*',
        daymonth='*',
        month='*',
        dayweek='*',
        ):
    '''
    Verifies that the specified cron job is present for the specified user.
    For more advanced information about what exactly can be set in the cron
    timing parameters check your cron system's documentation. Most Unix-like
    systems' cron documentation can be found via the crontab man page:
    ``man 5 crontab``.

    name
        The command that should be executed by the cron job.

    user
        The name of the user who's crontab needs to be modified, defaults to
        the root user

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
        The information to be set in the day of day of week section. Default is
        ``*``
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}
    if __opts__['test']:
        status = _check_cron(
                name,
                user,
                minute,
                hour,
                daymonth,
                month,
                dayweek)
        ret['result'] = None
        if status == 'absent':
            ret['comment'] = 'Cron {0} is set to be added'.format(name)
        elif status == 'present':
            ret['result'] = True
            ret['comment'] = 'Cron {0} already present'.format(name)
        elif status == 'update':
            ret['comment'] = 'Cron {0} is set to be updated'.format(name)
        return ret

    data = __salt__['cron.set_job'](
            dom=daymonth,
            dow=dayweek,
            hour=hour,
            minute=minute,
            month=month,
            cmd=name,
            user=user
            )
    if data == 'present':
        ret['comment'] = 'Cron {0} already present'.format(name)
        return ret

    if data == 'new':
        ret['comment'] = 'Cron {0} added to {1}\'s crontab'.format(name, user)
        ret['changes'] = {user: name}
        return ret

    if data == 'updated':
        ret['comment'] = 'Cron {0} updated'.format(name, user)
        ret['changes'] = {user: name}
        return ret
    ret['comment'] = ('Cron {0} for user {1} failed to commit with error \n{2}'
                      .format(name, user, data))
    ret['result'] = False
    return ret


def absent(name,
        user='root',
        minute='*',
        hour='*',
        daymonth='*',
        month='*',
        dayweek='*',
        ):
    '''
    Verifies that the specified cron job is absent for the specified user, only
    the name is matched when removing a cron job.

    name
        The command that should be absent in the user crontab.

    user
        The name of the user who's crontab needs to be modified, defaults to
        the root user

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
        The information to be set in the day of day of week section. Default is
        ``*``
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    if __opts__['test']:
        status = _check_cron(
                name,
                user,
                minute,
                hour,
                daymonth,
                month,
                dayweek)
        ret['result'] = None
        if status == 'absent':
            ret['result'] = True
            ret['comment'] = 'Cron {0} is absent'.format(name)
        elif status == 'present' or status == 'update':
            ret['comment'] = 'Cron {0} is set to be removed'.format(name)
        return ret

    data = __salt__['cron.rm_job'](
            user,
            minute,
            hour,
            daymonth,
            month,
            dayweek,
            name,
            )
    if data == 'absent':
        ret['comment'] = "Cron {0} already absent".format(name)
        return ret
    if data == 'removed':
        ret['comment'] = ("Cron {0} removed from {1}'s crontab"
                          .format(name, user))
        ret['changes'] = {user: name}
        return ret
    ret['comment'] = ("Cron {0} for user {1} failed to commit with error {2}"
                      .format(name, user, data))
    ret['result'] = False
    return ret
