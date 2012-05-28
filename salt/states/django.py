'''
Django Management
=============================

Run django management commands.

.. code-block:: yaml

    settings:
        django.syncdb:
            - bin_env: /var/www/env/
            - pythonpath: /var/www/mysite/
            - migrate: True
        django.collectstatic:
            - bin_env: /var/www/env/
            - pythonpath: /var/www/mysite/
            - clear: True
'''


def syncdb(name,
           bin_env=None,
           migrate=False,
           database=None,
           pythonpath=None):
    '''
    Run syncdb operations.

    name
        The name of the settings module
    bin_env
        Path to a python virtual environment.
    pythonpath
        Path from which python will execute.
    migrate
        Run migrations on database. Requires South.
    database
        Specifies the name of the database to run on.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    output = __salt__['django.syncdb'](name,
                              bin_env=bin_env,
                              migrate=migrate,
                              database=database,
                              pythonpath=pythonpath)
    ret['changes']['output'] = output
    return ret


def collectstatic(name,
                  bin_env=None,
                  no_post_process=False,
                  ignore=None,
                  dry_run=False,
                  clear=False,
                  link=False,
                  no_default_ignore=False,
                  pythonpath=None):
    '''
    Run the collectstatic commands

    name
        The name of the settings module
    bin_env
        Path to a python virtual environment.
    pythonpath
        Path from which python will execute.
    no_post_process
        Do not run post_process. Only applies Django>= 1.4
    ignore
        Ignores files or directories matching these glob patterns.
    dry_run
        Display what collectstatic would act on without performing the action.
    clear
        Clear existing files before copying. Only in Django>=1.4
    link
        Create symlinks instead of copying
    no_default_ignore
        Don't ignore common private patterns
    pythonpath
        Directory to run django-admin.py process from.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    output = __salt__['django.collectstatic'](name,
                                              bin_env=bin_env,
                                              no_post_process=no_post_process,
                                              ignore=ignore,
                                              dry_run=dry_run,
                                              clear=clear,
                                              link=link,
                                              no_default_ignore=no_default_ignore,
                                              pythonpath=pythonpath)
    ret['changes']['output'] = output
    return ret
