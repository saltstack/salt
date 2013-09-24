# -*- coding: utf-8 -*-
'''
Generate pillar data from Django models through the Django ORM

:maintainer: Micah Hausler <micah.hausler@gmail.com>
:maturity: new


Configuring the django_orm ext_pillar
=====================================

To use this module, your Django project must be on the salt master server with
database access. This assumes you are using virtualenv with all the project's
requirements installed.

.. code-block:: yaml

    ext_pillar:
      - django_orm:
          pillar_name: my_application
          env: /path/to/virtualenv/
          project_path: /path/to/project/
          env_file: /path/to/env/file.sh
          settings_module: my_application.settings

          django_app:

            # Required: the app that is included in INSTALLED_APPS
            my_application.clients:

              # Required: the model name
              Client:

                # Required: model field to use as a name in the
                # rendered pillar, should be unique
                name: shortname

                # Optional:
                # See Django's QuerySet documentation for how to use .filter()
                filter:  {'kw': 'args'}

                # Required: a list of field names
                fields:
                  - field_1
                  - field_2


This would return pillar data that would look like

.. code-block:: yaml

    my_application:
      my_application.clients:
        Client:
          client_1:
            field_1: data_from_field_1
            field_2: data_from_field_2
          client_2:
            field_1: data_from_field_1
            field_2: data_from_field_2


Module Documentation
====================
'''

import logging
import os
import sys


HAS_VIRTUALENV = False

try:
    import virtualenv
    HAS_VIRTUALENV = True
except ImportError:
    pass

log = logging.getLogger(__name__)


def __virtual__():
    if not HAS_VIRTUALENV:
        log.warn('virtualenv not installed, please install first')
        return False
    return 'django_orm'


def ext_pillar(pillar,
               pillar_name,
               env,
               project_path,
               settings_module,
               django_app,
               env_file=None,
               *args,
               **kwargs):
    '''
    Connect to a Django database through the ORM and retrieve model fields

    Parameters:
        * `pillar_name`: The name of the pillar to be returned
        * `env`: The full path to the virtualenv for your Django project
        * `project_path`: The full path to your Django project (the directory
          manage.py is in.)
        * `settings_module`: The settings module for your project. This can be
          found in your manage.py file.
        * `django_app`: A dictionary containing your apps, models, and fields
        * `env_file`: A bash file that sets up your environment. The file is
          run in a subprocess and the changed variables are then added.
    '''

    if not os.path.isdir(project_path):
        log.error('Django project dir: \'{}\' not a directory!'.format(env))
        return {}
    for path in virtualenv.path_locations(env):
        if not os.path.isdir(path):
            log.error('Virtualenv {} not a directory!'.format(path))
            return {}

    # load the virtualenv
    sys.path.append(virtualenv.path_locations(env)[1] + '/site-packages/')
    # load the django project
    sys.path.append(project_path)

    os.environ['DJANGO_SETTINGS_MODULE'] = settings_module

    if env_file is not None:
        import subprocess

        base_env = {}
        proc = subprocess.Popen(['bash', '-c', 'env'], stdout=subprocess.PIPE)
        for line in proc.stdout:
            (key, _, value) = line.partition('=')
            base_env[key] = value

        command = ['bash', '-c', 'source {0} && env'.format(env_file)]
        proc = subprocess.Popen(command, stdout=subprocess.PIPE)

        for line in proc.stdout:
            (key, _, value) = line.partition('=')
            # only add a key if it is different or doesn't already exist
            if key not in base_env or base_env[key] != value:
                os.environ[key] = value.rstrip('\n')
                log.debug('Adding {} = {} to Django environment'.format(
                            key,
                            value.rstrip('\n')))

    try:
        import importlib

        django_pillar = {}

        for app, models in django_app.iteritems():
            django_pillar[app] = {}
            model_file = importlib.import_module(app + '.models')
            for model_name, model_meta in models.iteritems():
                model_orm = model_file.__dict__[model_name]
                django_pillar[app][model_orm.__name__] = {}

                fields = model_meta['fields']

                if 'filter' in model_meta.keys():
                    qs = model_orm.objects.filter(**model_meta['filter'])
                else:
                    qs = model_orm.objects.all()

                # Loop through records for the queryset
                for model in qs:
                    django_pillar[app][model_orm.__name__][
                            model.__dict__[
                                model_meta['name']
                            ]] = {}

                    for field in fields:
                        django_pillar[app][model_orm.__name__][
                                        model.__dict__[
                                            model_meta['name']
                                        ]][field] = model.__dict__[field]

        return {pillar_name: django_pillar}
    except ImportError, e:
        log.error('Failed to import library: {}'.format(e.message))
        return {}
    except Exception, e:
        log.error('Failed on Error: {}'.format(e.message))
        return {}
