
"""
Manage Django sites
"""

import os

def _get_django_admin(bin_env):
    if not bin_env:
        da = 'django-admin.py'
    else:
        # try to get pip bin from env
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
    """
    run arbitrary django management command
    """
    da = _get_django_admin(bin_env)
    cmd = "{0} {1} --settings={2}".format(da, command, settings_module)

    if pythonpath:
        cmd = "{0} --pythonpath={1}".format(cmd, pythonpath)

    for arg in args:
        cmd = "{0} --{1}".format(cmd, arg)

    for key, value in kwargs.iteritems():
        if not key.startswith("__"):
            cmd = '{0} --{1}={2}'.format(cmd, key, value)

    return __salt__['cmd.run'](cmd)


def syncdb(settings_module,
           bin_env=None,
           migrate=False,
           database=None,
           pythonpath=None):
    """
    run syncdb

    if you have south installed, you can pass in the optional
    ``migrate`` kwarg and run the migrations after the syncdb
    finishes.
    """
    da = _get_django_admin(bin_env)
    cmd = "{0} syncdb --settings={1}".format(da, settings_module)
    if migrate:
        cmd = "{0} --migrate".format(cmd)
    if database:
        cmd = "{0} --database={1}".format(cmd, database)
    if pythonpath:
        cmd = "{0} --pythonpath={1}".format(cmd, pythonpath)
    return __salt__['cmd.run'](cmd)


def createsuperuser(settings_module,
                    username,
                    email,
                    bin_env=None,
                    database=None,
                    pythonpath=None):
    """
    create a super user for the database.
    this defaults to use the ``--noinput`` flag which will
    not create a password for the superuser.
    """
    da = _get_django_admin(bin_env)
    cmd = "{0} createsuperuser --settings={1} --noinput --email='{2}' --username={3}".format(
            da, settings_module, email, username)
    if database:
        cmd = "{0} --database={1}".format(cmd, database)
    if pythonpath:
        cmd = "{0} --pythonpath={1}".format(cmd, pythonpath)
    return __salt__['cmd.run'](cmd)


def loaddata(settings_module,
             fixtures,
             bin_env=None,
             database=None,
             pythonpath=None):
    """
    load fixture data

    fixtures:
        comma separated list of fixtures to load

    """
    da = _get_django_admin(bin_env)
    cmd = "{0} loaddata --settings={1} {2}".format(
        da, settings_module, " ".join(fixtures.split(",")))
    if database:
        cmd = "{0} --database={1}".format(cmd, database)
    if pythonpath:
        cmd = "{0} --pythonpath={1}".format(cmd, pythonpath)
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
    da = _get_django_admin(bin_env)
    cmd = "{0} collectstatic --settings={1} --noinput".format(
            da, settings_module)
    if no_post_process:
        cmd = "{0} --no-post-process".format(cmd)
    if ignore:
        cmd = "{0} --ignore=".format(cmd, ignore)
    if dry_run:
        cmd = "{0} --dry-run".format(cmd)
    if clear:
        cmd = "{0} --clear".format(cmd)
    if link:
        cmd = "{0} --link".format(cmd)
    if no_default_ignore:
        cmd = "{0} --no-default-ignore".format(cmd)
    if pythonpath:
        cmd = "{0} --pythonpath={1}".format(cmd, pythonpath)

    return __salt__['cmd.run'](cmd)
