# -*- coding: utf-8 -*-
'''
Management of incron, the inotify cron
==============================================

The incron state module allows for user incrontabs to be cleanly managed.

Incron declarations require a number of parameters. The parameters needed
to be declared: ``path``, ``mask``, and ``cmd``. The ``user`` whose incrontab is to be edited
also needs to be defined.

When making changes to an existing incron job, the ``path`` declaration is the unique
factor, so if an existing cron that looks like this:

.. code-block:: yaml

    Watch for modifications in /home/user:
        incron.present:
            - user: root
            - path: /home/user
            - mask:
                - IN_MODIFY
            - cmd: 'echo "$$ $@"'

Is changed to this:

.. code-block:: yaml

    Watch for modifications and access in /home/user:
        incron.present:
            - user: root
            - path: /home/user
            - mask:
                - IN_MODIFY
                - IN_ACCESS
            - cmd: 'echo "$$ $@"'

Then the existing cron will be updated, but if the cron command is changed,
then a new cron job will be added to the user's crontab.

.. versionadded:: 0.17.0

'''


def _check_cron(user,
                path,
                mask,
                cmd):
    '''
    Return the changes
    '''
    arg_mask = mask.split(',')
    arg_mask.sort()

    lst = __salt__['incron.list_tab'](user)
    for cron in lst['crons']:
        if path == cron['path'] and cron['cmd'] == cmd:
            cron_mask = cron['mask'].split(',')
            cron_mask.sort()
            if cron_mask == arg_mask:
                return 'present'
            if any([x in cron_mask for x in arg_mask]):
                return 'update'
    return 'absent'


def _get_cron_info():
    '''
    Returns the proper group owner and path to the incron directory
    '''
    owner = 'root'
    if __grains__['os'] == 'FreeBSD':
        group = 'wheel'
        crontab_dir = '/var/spool/incron'
    elif __grains__['os'] == 'OpenBSD':
        group = 'crontab'
        crontab_dir = '/var/spool/incron'
    elif __grains__.get('os_family') == 'Solaris':
        group = 'root'
        crontab_dir = '/var/spool/incron'
    else:
        group = 'root'
        crontab_dir = '/var/spool/incron'
    return owner, group, crontab_dir


def present(name,
            path,
            mask,
            cmd,
            user='root'):
    '''
    Verifies that the specified incron job is present for the specified user.
    For more advanced information about what exactly can be set in the cron
    timing parameters, check your incron system's documentation. Most Unix-like
    systems' incron documentation can be found via the incrontab man page:
    ``man 5 incrontab``.

    name
        Unique comment describing the entry

    path
        The path that should be watched

    user
        The name of the user who's crontab needs to be modified, defaults to
        the root user

    mask
        The mask of events that should be monitored for

    cmd
        The cmd that should be executed

    '''
    mask = ',' . join(mask)

    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}
    if __opts__['test']:
        status = _check_cron(user,
                             path,
                             mask,
                             cmd)
        ret['result'] = None
        if status == 'absent':
            ret['comment'] = 'Incron {0} is set to be added'.format(name)
        elif status == 'present':
            ret['result'] = True
            ret['comment'] = 'Incron {0} already present'.format(name)
        elif status == 'update':
            ret['comment'] = 'Incron {0} is set to be updated'.format(name)
        return ret

    data = __salt__['incron.set_job'](user=user,
                                    path=path,
                                    mask=mask,
                                    cmd=cmd)
    if data == 'present':
        ret['comment'] = 'Incron {0} already present'.format(name)
        return ret

    if data == 'new':
        ret['comment'] = 'Incron {0} added to {1}\'s incrontab'.format(name, user)
        ret['changes'] = {user: name}
        return ret

    if data == 'updated':
        ret['comment'] = 'Incron {0} updated'.format(name)
        ret['changes'] = {user: name}
        return ret
    ret['comment'] = ('Incron {0} for user {1} failed to commit with error \n{2}'
                      .format(name, user, data))
    ret['result'] = False
    return ret


def absent(name,
           path,
           mask,
           cmd,
           user='root'):
    '''
    Verifies that the specified incron job is absent for the specified user; only
    the name is matched when removing a incron job.

    name
        Unique comment describing the entry

    path
        The path that should be watched

    user
        The name of the user who's crontab needs to be modified, defaults to
        the root user

    mask
        The mask of events that should be monitored for

    cmd
        The cmd that should be executed

    '''

    mask = ',' . join(mask)

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    if __opts__['test']:
        status = _check_cron(user,
                             path,
                             mask,
                             cmd)
        ret['result'] = None
        if status == 'absent':
            ret['result'] = True
            ret['comment'] = 'Incron {0} is absent'.format(name)
        elif status == 'present' or status == 'update':
            ret['comment'] = 'Incron {0} is set to be removed'.format(name)
        return ret

    data = __salt__['incron.rm_job'](user=user,
                                    path=path,
                                    mask=mask,
                                    cmd=cmd)
    if data == 'absent':
        ret['comment'] = "Incron {0} already absent".format(name)
        return ret
    if data == 'removed':
        ret['comment'] = ("Incron {0} removed from {1}'s crontab"
                          .format(name, user))
        ret['changes'] = {user: name}
        return ret
    ret['comment'] = ("Incron {0} for user {1} failed to commit with error {2}"
                      .format(name, user, data))
    ret['result'] = False
    return ret
