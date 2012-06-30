'''
Manage Django sites
'''

import os


def _get_django_admin(bin_env):
    '''
    Return the django admin
    '''
    if not bin_env:
        da = 'django-admin.py'
    else:
        # try to get django-admin.py bin from env
        if os.path.exists(os.path.join(bin_env, 'bin', 'django-admin.py')):
            da = os.path.join(bin_env, 'bin', 'django-admin.py')
        else:
            da = bin_env
    return da


def command(settings_module,
            command,
            bin_env=None,
            pythonpath=None,
            *args, **kwargs):
    '''
    Run arbitrary django management command
    '''
    da = _get_django_admin(bin_env)
    cmd = '{0} {1} --settings={2}'.format(da, command, settings_module)

    if pythonpath:
        cmd = '{0} --pythonpath={1}'.format(cmd, pythonpath)

    for arg in args:
        cmd = '{0} --{1}'.format(cmd, arg)

    for key, value in kwargs.items():
        if not key.startswith('__'):
            cmd = '{0} --{1}={2}'.format(cmd, key, value)
    return __salt__['cmd.run'](cmd)


def syncdb(settings_module,
           bin_env=None,
           migrate=False,
           database=None,
           pythonpath=None,
           noinput=True):
    '''
    Run syncdb

    Execute the Django-Admin syncdb command, if South is available on the
    minion the ``migrate`` option can be passed as ``True`` calling the
    migrations to run after the syncdb completes

    CLI Example::

        salt '*' django.syncdb settings.py
    '''
    args = []
    kwargs = {}
    if migrate:
        args.append('migrate')
    if database:
        kwargs['database'] = database
    if noinput:
        args.append('noinput')

    return command(settings_module,
                  'syncdb',
                   bin_env,
                   pythonpath,
                   *args, **kwargs)


def createsuperuser(settings_module,
                    username,
                    email,
                    bin_env=None,
                    database=None,
                    pythonpath=None):
    '''
    Create a super user for the database.
    This function defaults to use the ``--noinput`` flag which prevents the
    creation of a password for the superuser.

    CLI Example::

        salt '*' django.createsuperuser settings.py user user@example.com
    '''
    args = ['noinput']
    kwargs = dict(
        email=email,
        username=username,
    )
    if database:
        kwargs['database'] = database
    return command(settings_module,
                   'createsuperuser',
                   bin_env,
                   pythonpath,
                   *args, **kwargs)


def loaddata(settings_module,
             fixtures,
             bin_env=None,
             database=None,
             pythonpath=None):
    '''
    Load fixture data

    Fixtures:
        comma separated list of fixtures to load

    CLI Example::

        salt '*' django.loaddata settings.py <comma delimited list of fixtures>

    '''
    da = _get_django_admin(bin_env)
    cmd = '{0} loaddata --settings={1} {2}'.format(
        da, settings_module, ' '.join(fixtures.split(',')))
    if database:
        cmd = '{0} --database={1}'.format(cmd, database)
    if pythonpath:
        cmd = '{0} --pythonpath={1}'.format(cmd, pythonpath)
    return __salt__['cmd.run'](cmd)


def collectstatic(settings_module,
                  bin_env=None,
                  no_post_process=False,
                  ignore=None,
                  dry_run=False,
                  clear=False,
                  link=False,
                  no_default_ignore=False,
                  pythonpath=None):
    '''
    Collect static files from each of your applications into a single location
    that can easily be served in production.

    CLI Example::

        salt '*' django.collectstatic settings.py
    '''
    args = []
    kwargs = {}
    if no_post_process:
        args.append('no-post-process')
    if ignore:
        kwargs['ignore'] = ignore
    if dry_run:
        args.append('dry-run')
    if clear:
        args.append('clear')
    if link:
        args.append('link')
    if no_default_ignore:
        args.append('no-default-ignore')

    return command(settings_module,
                   'collectstatic',
                   bin_env,
                   pythonpath,
                   *args, **kwargs)
