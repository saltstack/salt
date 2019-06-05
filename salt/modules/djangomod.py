# -*- coding: utf-8 -*-
'''
Manage Django sites
'''


# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt libs
import salt.utils.path
import salt.exceptions

# Import 3rd-party libs
from salt.ext import six

# Define the module's virtual name
__virtualname__ = 'django'


def __virtual__():
    return __virtualname__


def _get_django_admin(bin_env):
    '''
    Return the django admin
    '''
    if not bin_env:
        if salt.utils.path.which('django-admin.py'):
            return 'django-admin.py'
        elif salt.utils.path.which('django-admin'):
            return 'django-admin'
        else:
            raise salt.exceptions.CommandExecutionError(
                    "django-admin or django-admin.py not found on PATH")

    # try to get django-admin.py bin from env
    if os.path.exists(os.path.join(bin_env, 'bin', 'django-admin.py')):
        return os.path.join(bin_env, 'bin', 'django-admin.py')
    return bin_env


def command(settings_module,
            command,
            bin_env=None,
            pythonpath=None,
            env=None,
            *args, **kwargs):
    '''
    Run arbitrary django management command

    CLI Example:

    .. code-block:: bash

        salt '*' django.command <settings_module> <command>
    '''
    dja = _get_django_admin(bin_env)
    cmd = '{0} {1} --settings={2}'.format(dja, command, settings_module)

    if pythonpath:
        cmd = '{0} --pythonpath={1}'.format(cmd, pythonpath)

    for arg in args:
        cmd = '{0} --{1}'.format(cmd, arg)

    for key, value in six.iteritems(kwargs):
        if not key.startswith('__'):
            cmd = '{0} --{1}={2}'.format(cmd, key, value)
    return __salt__['cmd.run'](cmd, env=env, python_shell=False)


def syncdb(settings_module,
           bin_env=None,
           migrate=False,
           database=None,
           pythonpath=None,
           env=None,
           noinput=True):
    '''
    Run syncdb

    Execute the Django-Admin syncdb command, if South is available on the
    minion the ``migrate`` option can be passed as ``True`` calling the
    migrations to run after the syncdb completes

    CLI Example:

    .. code-block:: bash

        salt '*' django.syncdb <settings_module>
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
                   env,
                   *args, **kwargs)


def createsuperuser(settings_module,
                    username,
                    email,
                    bin_env=None,
                    database=None,
                    pythonpath=None,
                    env=None):
    '''
    Create a super user for the database.
    This function defaults to use the ``--noinput`` flag which prevents the
    creation of a password for the superuser.

    CLI Example:

    .. code-block:: bash

        salt '*' django.createsuperuser <settings_module> user user@example.com
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
                   env,
                   *args, **kwargs)


def loaddata(settings_module,
             fixtures,
             bin_env=None,
             database=None,
             pythonpath=None,
             env=None):
    '''
    Load fixture data

    Fixtures:
        comma separated list of fixtures to load

    CLI Example:

    .. code-block:: bash

        salt '*' django.loaddata <settings_module> <comma delimited list of fixtures>

    '''
    args = []
    kwargs = {}
    if database:
        kwargs['database'] = database

    cmd = '{0} {1}'.format('loaddata', ' '.join(fixtures.split(',')))

    return command(settings_module,
                   cmd,
                   bin_env,
                   pythonpath,
                   env,
                   *args, **kwargs)


def collectstatic(settings_module,
                  bin_env=None,
                  no_post_process=False,
                  ignore=None,
                  dry_run=False,
                  clear=False,
                  link=False,
                  no_default_ignore=False,
                  pythonpath=None,
                  env=None):
    '''
    Collect static files from each of your applications into a single location
    that can easily be served in production.

    CLI Example:

    .. code-block:: bash

        salt '*' django.collectstatic <settings_module>
    '''
    args = ['noinput']
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
                   env,
                   *args, **kwargs)
