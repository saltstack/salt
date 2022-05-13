"""
Manage Django sites
"""


import os

import salt.exceptions
import salt.utils.path

# Define the module's virtual name
__virtualname__ = "django"


def __virtual__():
    return __virtualname__


def _get_django_admin(bin_env):
    """
    Return the django admin
    """
    if not bin_env:
        if salt.utils.path.which("django-admin.py"):
            return "django-admin.py"
        elif salt.utils.path.which("django-admin"):
            return "django-admin"
        else:
            raise salt.exceptions.CommandExecutionError(
                "django-admin or django-admin.py not found on PATH"
            )

    # try to get django-admin.py bin from env
    if os.path.exists(os.path.join(bin_env, "bin", "django-admin.py")):
        return os.path.join(bin_env, "bin", "django-admin.py")
    return bin_env


def command(
    settings_module,
    command,
    bin_env=None,
    pythonpath=None,
    env=None,
    runas=None,
    *args,
    **kwargs
):
    """
    Run arbitrary django management command

    CLI Example:

    .. code-block:: bash

        salt '*' django.command <settings_module> <command>
    """
    dja = _get_django_admin(bin_env)
    cmd = "{} {} --settings={}".format(dja, command, settings_module)

    if pythonpath:
        cmd = "{} --pythonpath={}".format(cmd, pythonpath)

    for arg in args:
        cmd = "{} --{}".format(cmd, arg)

    for key, value in kwargs.items():
        if not key.startswith("__"):
            cmd = "{} --{}={}".format(cmd, key, value)
    return __salt__["cmd.run"](cmd, env=env, runas=runas, python_shell=False)


def syncdb(
    settings_module,
    bin_env=None,
    migrate=False,
    database=None,
    pythonpath=None,
    env=None,
    noinput=True,
    runas=None,
):
    """
    Run syncdb

    Execute the Django-Admin syncdb command, if South is available on the
    minion the ``migrate`` option can be passed as ``True`` calling the
    migrations to run after the syncdb completes

    NOTE: The syncdb command was deprecated in Django 1.7 and removed in Django 1.9.
    For Django versions 1.9 or higher use the `migrate` command instead.

    CLI Example:

    .. code-block:: bash

        salt '*' django.syncdb <settings_module>
    """
    args = []
    kwargs = {}
    if migrate:
        args.append("migrate")
    if database:
        kwargs["database"] = database
    if noinput:
        args.append("noinput")

    return command(
        settings_module, "syncdb", bin_env, pythonpath, env, runas, *args, **kwargs
    )


def migrate(
    settings_module,
    app_label=None,
    migration_name=None,
    bin_env=None,
    database=None,
    pythonpath=None,
    env=None,
    noinput=True,
    runas=None,
):
    """
    Run migrate

    Execute the Django-Admin migrate command (requires Django 1.7 or higher).

    .. versionadded:: 3000

    settings_module
        Specifies the settings module to use.
        The settings module should be in Python package syntax, e.g. mysite.settings.
        If this isn’t provided, django-admin will use the DJANGO_SETTINGS_MODULE
        environment variable.

    app_label
        Specific app to run migrations for, instead of all apps.
        This may involve running other apps’ migrations too, due to dependencies.

    migration_name
        Named migration to be applied to a specific app.
        Brings the database schema to a state where the named migration is applied,
        but no later migrations in the same app are applied. This may involve
        unapplying migrations if you have previously migrated past the named migration.
        Use the name zero to unapply all migrations for an app.

    bin_env
        Path to pip (or to a virtualenv). This can be used to specify the path
        to the pip to use when more than one Python release is installed (e.g.
        ``/usr/bin/pip-2.7`` or ``/usr/bin/pip-2.6``. If a directory path is
        specified, it is assumed to be a virtualenv.

    database
        Database to migrate. Defaults to 'default'.

    pythonpath
        Adds the given filesystem path to the Python import search path.
        If this isn’t provided, django-admin will use the PYTHONPATH environment variable.

    env
        A list of environment variables to be set prior to execution.

        Example:

        .. code-block:: yaml

            module.run:
              - name: django.migrate
              - settings_module: my_django_app.settings
              - env:
                - DATABASE_USER: 'mydbuser'

    noinput
        Suppresses all user prompts. Defaults to True.

    runas
        The user name to run the command as.

    CLI Example:

    .. code-block:: bash

        salt '*' django.migrate <settings_module>
        salt '*' django.migrate <settings_module> <app_label>
        salt '*' django.migrate <settings_module> <app_label> <migration_name>
    """
    args = []
    kwargs = {}
    if database:
        kwargs["database"] = database
    if noinput:
        args.append("noinput")

    if app_label and migration_name:
        cmd = "migrate {} {}".format(app_label, migration_name)
    elif app_label:
        cmd = "migrate {}".format(app_label)
    else:
        cmd = "migrate"

    return command(
        settings_module, cmd, bin_env, pythonpath, env, runas, *args, **kwargs
    )


def createsuperuser(
    settings_module,
    username,
    email,
    bin_env=None,
    database=None,
    pythonpath=None,
    env=None,
    runas=None,
):
    """
    Create a super user for the database.
    This function defaults to use the ``--noinput`` flag which prevents the
    creation of a password for the superuser.

    CLI Example:

    .. code-block:: bash

        salt '*' django.createsuperuser <settings_module> user user@example.com
    """
    args = ["noinput"]
    kwargs = dict(
        email=email,
        username=username,
    )
    if database:
        kwargs["database"] = database
    return command(
        settings_module,
        "createsuperuser",
        bin_env,
        pythonpath,
        env,
        runas,
        *args,
        **kwargs
    )


def loaddata(
    settings_module, fixtures, bin_env=None, database=None, pythonpath=None, env=None
):
    """
    Load fixture data

    Fixtures:
        comma separated list of fixtures to load

    CLI Example:

    .. code-block:: bash

        salt '*' django.loaddata <settings_module> <comma delimited list of fixtures>

    """
    args = []
    kwargs = {}
    if database:
        kwargs["database"] = database

    cmd = "{} {}".format("loaddata", " ".join(fixtures.split(",")))

    return command(settings_module, cmd, bin_env, pythonpath, env, *args, **kwargs)


def collectstatic(
    settings_module,
    bin_env=None,
    no_post_process=False,
    ignore=None,
    dry_run=False,
    clear=False,
    link=False,
    no_default_ignore=False,
    pythonpath=None,
    env=None,
    runas=None,
):
    """
    Collect static files from each of your applications into a single location
    that can easily be served in production.

    CLI Example:

    .. code-block:: bash

        salt '*' django.collectstatic <settings_module>
    """
    args = ["noinput"]
    kwargs = {}
    if no_post_process:
        args.append("no-post-process")
    if ignore:
        kwargs["ignore"] = ignore
    if dry_run:
        args.append("dry-run")
    if clear:
        args.append("clear")
    if link:
        args.append("link")
    if no_default_ignore:
        args.append("no-default-ignore")

    return command(
        settings_module,
        "collectstatic",
        bin_env,
        pythonpath,
        env,
        runas,
        *args,
        **kwargs
    )
