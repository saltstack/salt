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

# Import python libs
import os

# Import salt libs
import salt._compat
import salt.utils
from salt.modules.cron import (
    _needs_change,
    _cron_matched,
    SALT_CRON_NO_IDENTIFIER
)


def _check_cron(user,
                cmd,
                minute=None,
                hour=None,
                daymonth=None,
                month=None,
                dayweek=None,
                comment=None,
                identifier=None):
    '''
    Return the changes
    '''
    if minute is not None:
        minute = str(minute).lower()
    if hour is not None:
        hour = str(hour).lower()
    if daymonth is not None:
        daymonth = str(daymonth).lower()
    if month is not None:
        month = str(month).lower()
    if dayweek is not None:
        dayweek = str(dayweek).lower()
    lst = __salt__['cron.list_tab'](user)
    for cron in lst['crons']:
        if _cron_matched(cron, cmd, identifier):
            if any([_needs_change(x, y) for x, y in
                    ((cron['minute'], minute), (cron['hour'], hour),
                     (cron['daymonth'], daymonth), (cron['month'], month),
                     (cron['dayweek'], dayweek), (cron['comment'], comment))]):
                return 'update'
            return 'present'
    return 'absent'


def _check_cron_env(user,
                    name,
                    value=None):
    '''
    Return the environment changes
    '''
    if value is None:
        value = ""  # Matching value set in salt.modules.cron._render_tab
    lst = __salt__['cron.list_tab'](user)
    for env in lst['env']:
        if name == env['name']:
            if value != env['value']:
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
    elif __grains__['os_family'] == 'Solaris':
        group = 'root'
        crontab_dir = '/var/spool/cron/crontabs'
    elif __grains__['os'] == 'MacOS':
        group = 'wheel'
        crontab_dir = '/usr/lib/cron/tabs'
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
            comment=None,
            identifier=None):
    '''
    Verifies that the specified cron job is present for the specified user.
    For more advanced information about what exactly can be set in the cron
    timing parameters, check your cron system's documentation. Most Unix-like
    systems' cron documentation can be found via the crontab man page:
    ``man 5 crontab``.

    name
        The command that should be executed by the cron job.

    user
        The name of the user whose crontab needs to be modified, defaults to
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
        The information to be set in the day of week section. Default is ``*``

    comment
        User comment to be added on line previous the cron job

    identifier
        Custom-defined identifier for tracking the cron line for future crontab
        edits. This defaults to the state id
    '''
    name = ' '.join(name.strip().split())
    if not identifier:
        identifier = SALT_CRON_NO_IDENTIFIER
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}
    if __opts__['test']:
        status = _check_cron(user,
                             cmd=name,
                             minute=minute,
                             hour=hour,
                             daymonth=daymonth,
                             month=month,
                             dayweek=dayweek,
                             comment=comment,
                             identifier=identifier)
        ret['result'] = None
        if status == 'absent':
            ret['comment'] = 'Cron {0} is set to be added'.format(name)
        elif status == 'present':
            ret['result'] = True
            ret['comment'] = 'Cron {0} already present'.format(name)
        elif status == 'update':
            ret['comment'] = 'Cron {0} is set to be updated'.format(name)
        return ret

    data = __salt__['cron.set_job'](user=user,
                                    minute=minute,
                                    hour=hour,
                                    daymonth=daymonth,
                                    month=month,
                                    dayweek=dayweek,
                                    cmd=name,
                                    comment=comment,
                                    identifier=identifier)
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
           identifier=None,
           **kwargs):
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

    name = ' '.join(name.strip().split())
    if not identifier:
        identifier = SALT_CRON_NO_IDENTIFIER
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    if __opts__['test']:
        status = _check_cron(user, name)
        ret['result'] = None
        if status == 'absent':
            ret['result'] = True
            ret['comment'] = 'Cron {0} is absent'.format(name)
        elif status == 'present' or status == 'update':
            ret['comment'] = 'Cron {0} is set to be removed'.format(name)
        return ret

    data = __salt__['cron.rm_job'](user, name, identifier=identifier)
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
        hosted on either the salt master server, or on an HTTP or FTP server.
        For files hosted on the salt file server, if the file is located on
        the master in the directory named spam, and is called eggs, the source
        string is salt://spam/eggs.

        If the file is hosted on a HTTP or FTP server then the source_hash
        argument is also required

    source_hash
        This can be either a file which contains a source hash string for
        the source, or a source hash string. The source hash string is the
        hash algorithm followed by the hash of the file:
        md5=e138491e9d5b97023cea823fe17bac22

    user
        The user to whom the crontab should be assigned. This defaults to
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
    mode = __salt__['config.manage_mode']('0600')
    owner, group, crontab_dir = _get_cron_info()

    cron_path = salt.utils.mkstemp()
    with salt.utils.fopen(cron_path, 'w+') as fp_:
        fp_.write(__salt__['cron.raw_cron'](user))

    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    # Avoid variable naming confusion in below module calls, since ID
    # declaration for this state will be a source URI.
    source = name

    if isinstance(env, salt._compat.string_types):
        msg = (
            'Passing a salt environment should be done using \'saltenv\' not '
            '\'env\'. This warning will go away in Salt Boron and this '
            'will be the default and expected behaviour. Please update your '
            'state files.'
        )
        salt.utils.warn_until('Boron', msg)
        ret.setdefault('warnings', []).append(msg)
        # No need to set __env__ = env since that's done in the state machinery

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
                                             context,
                                             defaults,
                                             __env__,
                                             **kwargs
                                             )
        ret['result'], ret['comment'] = fcm
        os.unlink(cron_path)
        return ret

    # If the source is a list then find which file exists
    source, source_hash = __salt__['file.source_list'](source,
                                                       source_hash,
                                                       __env__)

    # Gather the source file from the server
    try:
        sfn, source_sum, comment = __salt__['file.get_managed'](
            cron_path,
            template,
            source,
            source_hash,
            owner,
            group,
            mode,
            __env__,
            context,
            defaults,
            **kwargs
        )
    except Exception as exc:
        ret['result'] = False
        ret['changes'] = {}
        ret['comment'] = 'Unable to manage file: {0}'.format(exc)
        return ret

    if comment:
        ret['comment'] = comment
        ret['result'] = False
        os.unlink(cron_path)
        return ret

    try:
        ret = __salt__['file.manage_file'](
            cron_path,
            sfn,
            ret,
            source,
            source_sum,
            owner,
            group,
            mode,
            __env__,
            backup
        )
    except Exception as exc:
        ret['result'] = False
        ret['changes'] = {}
        ret['comment'] = 'Unable to manage file: {0}'.format(exc)
        return ret

    if ret['changes']:
        ret['changes'] = {'diff': ret['changes']['diff']}
        ret['comment'] = 'Crontab for user {0} was updated'.format(user)
    elif ret['result']:
        ret['comment'] = 'Crontab for user {0} is in the correct ' \
                         'state'.format(user)

    cron_ret = __salt__['cron.write_cron_file_verbose'](user, cron_path)
    if cron_ret['retcode']:
        ret['comment'] = 'Unable to update user {0} crontab {1}.' \
                         ' Error: {2}'.format(user, cron_path, cron_ret['stderr'])
        ret['result'] = False

    os.unlink(cron_path)
    return ret


def env_present(name,
                value=None,
                user='root'):
    '''
    Verifies that the specified environment variable is present in the crontab
    for the specified user.

    name
        The name of the environment variable to set in the user crontab

    user
        The name of the user whose crontab needs to be modified, defaults to
        the root user

    value
        The value to set for the given environment variable
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}
    if __opts__['test']:
        status = _check_cron_env(user, name, value=value)
        ret['result'] = None
        if status == 'absent':
            ret['comment'] = 'Cron env {0} is set to be added'.format(name)
        elif status == 'present':
            ret['result'] = True
            ret['comment'] = 'Cron env {0} already present'.format(name)
        elif status == 'update':
            ret['comment'] = 'Cron env {0} is set to be updated'.format(name)
        return ret

    data = __salt__['cron.set_env'](user, name, value=value)
    if data == 'present':
        ret['comment'] = 'Cron env {0} already present'.format(name)
        return ret

    if data == 'new':
        ret['comment'] = 'Cron env {0} added to {1}\'s crontab'.format(name, user)
        ret['changes'] = {user: name}
        return ret

    if data == 'updated':
        ret['comment'] = 'Cron env {0} updated'.format(name, user)
        ret['changes'] = {user: name}
        return ret
    ret['comment'] = ('Cron env {0} for user {1} failed to commit with error \n{2}'
                      .format(name, user, data))
    ret['result'] = False
    return ret


def env_absent(name,
               user='root'):
    '''
    Verifies that the specified environment variable is absent from the crontab
    for the specified user

    name
        The name of the environment variable to remove from the user crontab

    user
        The name of the user whose crontab needs to be modified, defaults to
        the root user
    '''

    name = ' '.join(name.strip().split())
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    if __opts__['test']:
        status = _check_cron_env(user, name)
        ret['result'] = None
        if status == 'absent':
            ret['result'] = True
            ret['comment'] = 'Cron env {0} is absent'.format(name)
        elif status == 'present' or status == 'update':
            ret['comment'] = 'Cron env {0} is set to be removed'.format(name)
        return ret

    data = __salt__['cron.rm_env'](user, name)
    if data == 'absent':
        ret['comment'] = "Cron env {0} already absent".format(name)
        return ret
    if data == 'removed':
        ret['comment'] = ("Cron env {0} removed from {1}'s crontab"
                          .format(name, user))
        ret['changes'] = {user: name}
        return ret
    ret['comment'] = ("Cron env {0} for user {1} failed to commit with error {2}"
                      .format(name, user, data))
    ret['result'] = False
    return ret
