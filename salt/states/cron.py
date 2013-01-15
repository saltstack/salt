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

# Import python libs
import os

# Import salt libs
from salt.utils import mkstemp


def _check_cron(cmd, user, minute, hour, dom, month, dow):
    '''
    Return the changes
    '''
    lst = __salt__['cron.list_tab'](user)
    for cron in lst['crons']:
        if cmd == cron['cmd']:
            if not str(minute) == cron['min'] or \
                    not str(hour) == cron['hour'] or \
                    not str(dom) == cron['daymonth'] or \
                    not str(month) == cron['month'] or \
                    not str(dow) == cron['dayweek']:
                return 'update'
            return 'present'
    return 'absent'


def _get_cron_info():
    '''
    Returns the proper group owner and path to the cron directory
    '''
    owner = 'root'
    if __grains__['os'] == 'FreeBSD':
        group = 'wheel'
        crontab_dir = '/var/cron/tabs'
    elif __grains__['os'] == 'OpenBSD':
        group = 'crontab'
        crontab_dir = '/var/cron/tabs'
    elif __grains__['os'] == 'Solaris':
        group = 'root'
        crontab_dir = '/var/spool/cron/crontabs'
    else:
        group = 'root'
        crontab_dir = '/var/spool/cron'
    return owner, group, crontab_dir


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
    name = ' '.join(name.strip().split())
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}
    if __opts__['test']:
        status = _check_cron(name,
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

    data = __salt__['cron.set_job'](dom=daymonth,
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
           dayweek='*'):
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
    name = ' '.join(name.strip().split())
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    if __opts__['test']:
        status = _check_cron(name,
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

    data = __salt__['cron.rm_job'](user,
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


def file(name,
         source_hash='',
         user='root',
         template=None,
         context=None,
         replace=True,
         defaults=None,
         env=None,
         backup='',
         **kwargs):
    '''
    Provides file.managed-like functionality (templating, etc.) for a pre-made
    crontab file, to be assigned to a given user.

    name
        The source file to be used as the crontab. This source file can be
        hosted on either the salt master server, or on an http or ftp server.
        For files hosted on the salt file server, if the file is located on
        the master in the directory named spam, and is called eggs, the source
        string is salt://spam/eggs.

        If the file is hosted on a http or ftp server then the source_hash
        argument is also required

    source_hash
        This can be either a file which contains a source hash string for
        the source, or a source hash string. The source hash string is the
        hash algorithm followed by the hash of the file:
        md5=e138491e9d5b97023cea823fe17bac22

    user
        The user to whome the crontab should be assigned. This defaults to
        root.

    template
        If this setting is applied then the named templating engine will be
        used to render the downloaded file. Currently, jinja and mako are
        supported.

    context
        Overrides default context variables passed to the template.

    replace
        If the crontab should be replaced, if False then this command will
        be ignored if a crontab exists for the specified user. Default is True.

    defaults
        Default context passed to the template.

    backup
        Overrides the default backup mode for the user's crontab.
    '''
    # Initial set up
    mode = __salt__['config.manage_mode'](600)
    owner, group, crontab_dir = _get_cron_info()

    cron_path = mkstemp()
    with open(cron_path, 'w+') as fp_:
        fp_.write(__salt__['cron.raw_cron'](user))

    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    # Avoid variable naming confusion in below module calls, since ID
    # delclaration for this state will be a source URI.
    source = name

    if env is None:
        env = kwargs.get('__env__', 'base')

    if not replace and os.stat(cron_path).st_size > 0:
        ret['comment'] = 'User {0} already has a crontab. No changes ' \
                         'made'.format(user)
        os.unlink(cron_path)
        return ret

    if __opts__['test']:
        fcm = __salt__['file.check_managed'](cron_path,
                                             source,
                                             source_hash,
                                             owner,
                                             group,
                                             mode,
                                             template,
                                             False,  # makedirs = False
                                             context,
                                             defaults,
                                             env,
                                             **kwargs
                                             )
        ret['result'], ret['comment'] = fcm
        os.unlink(cron_path)
        return ret

    # If the source is a list then find which file exists
    source, source_hash = __salt__['file.source_list'](source,
                                                       source_hash,
                                                       env)

    # Gather the source file from the server
    sfn, source_sum, comment = __salt__['file.get_managed'](cron_path,
                                                            template,
                                                            source,
                                                            source_hash,
                                                            owner,
                                                            group,
                                                            mode,
                                                            env,
                                                            context,
                                                            defaults,
                                                            **kwargs
                                                            )
    if comment:
        ret['comment'] = comment
        ret['result'] = False
        os.unlink(cron_path)
        return ret

    ret = __salt__['file.manage_file'](cron_path,
                                       sfn,
                                       ret,
                                       source,
                                       source_sum,
                                       owner,
                                       group,
                                       mode,
                                       env,
                                       backup)
    if not __salt__['cron.write_cron_file'](user, cron_path):
        ret['comment'] = 'Crontab file updated, but was unable to ' \
                         'update cron daemon'
        ret['result'] = False
    os.unlink(cron_path)
    return ret
