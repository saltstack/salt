# -*- coding: utf-8 -*-
"""
Generate Pillar data from Django models through the Django ORM

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
          project_path: /path/to/project/
          settings_module: my_application.settings
          env_file: /path/to/env/file.sh
          # Optional: If your project is not using the system python,
          # add your virtualenv path below.
          env: /path/to/virtualenv/

          django_app:

            # Required: the app that is included in INSTALLED_APPS
            my_application.clients:

              # Required: the model name
              Client:

                # Required: model field to use as the key in the rendered
                # Pillar. Must be unique; must also be included in the
                # ``fields`` list below.
                name: shortname

                # Optional:
                # See Django's QuerySet documentation for how to use .filter()
                filter:  {'kw': 'args'}

                # Required: a list of field names
                # List items will be used as arguments to the .values() method.
                # See Django's QuerySet documentation for how to use .values()
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

As another example, data from multiple database tables can be fetched using
Django's regular lookup syntax. Note, using ManyToManyFields will not currently
work since the return from values() changes if a ManyToMany is present.

.. code-block:: yaml

    ext_pillar:
      - django_orm:
          pillar_name: djangotutorial
          project_path: /path/to/mysite
          settings_module: mysite.settings

          django_app:
            mysite.polls:
              Choices:
                name: poll__question
                fields:
                  - poll__question
                  - poll__id
                  - choice_text
                  - votes

Module Documentation
====================
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import sys

import salt.exceptions
import salt.utils.stringutils
from salt.ext import six

HAS_VIRTUALENV = False

try:
    import virtualenv

    HAS_VIRTUALENV = True
except ImportError:
    pass

log = logging.getLogger(__name__)


def __virtual__():
    """
    Always load
    """
    return True


def ext_pillar(
    minion_id,  # pylint: disable=W0613
    pillar,  # pylint: disable=W0613
    pillar_name,
    project_path,
    settings_module,
    django_app,
    env=None,
    env_file=None,
    *args,  # pylint: disable=W0613
    **kwargs
):  # pylint: disable=W0613
    """
    Connect to a Django database through the ORM and retrieve model fields

    :type pillar_name: str
    :param pillar_name: The name of the pillar to be returned

    :type project_path: str
    :param project_path: The full path to your Django project (the directory
        manage.py is in)

    :type settings_module: str
    :param settings_module: The settings module for your project. This can be
        found in your manage.py file

    :type django_app: str
    :param django_app: A dictionary containing your apps, models, and fields

    :type env: str
    :param env: The full path to the virtualenv for your Django project

    :type env_file: str
    :param env_file: An optional bash file that sets up your environment. The
        file is run in a subprocess and the changed variables are then added
    """

    if not os.path.isdir(project_path):
        log.error("Django project dir: '%s' not a directory!", project_path)
        return {}
    if HAS_VIRTUALENV and env is not None and os.path.isdir(env):
        for path in virtualenv.path_locations(env):
            if not os.path.isdir(path):
                log.error("Virtualenv %s not a directory!", path)
                return {}
        # load the virtualenv first
        sys.path.insert(
            0, os.path.join(virtualenv.path_locations(env)[1], "site-packages")
        )

    # load the django project
    sys.path.append(project_path)

    os.environ["DJANGO_SETTINGS_MODULE"] = settings_module

    if env_file is not None:
        import subprocess

        base_env = {}
        proc = subprocess.Popen(["bash", "-c", "env"], stdout=subprocess.PIPE)
        for line in proc.stdout:
            (key, _, value) = salt.utils.stringutils.to_str(line).partition("=")
            base_env[key] = value

        command = ["bash", "-c", "source {0} && env".format(env_file)]
        proc = subprocess.Popen(command, stdout=subprocess.PIPE)

        for line in proc.stdout:
            (key, _, value) = salt.utils.stringutils.to_str(line).partition("=")
            # only add a key if it is different or doesn't already exist
            if key not in base_env or base_env[key] != value:
                os.environ[key] = value.rstrip("\n")
                log.debug(
                    "Adding %s = %s to Django environment", key, value.rstrip("\n")
                )

    try:
        # pylint: disable=no-name-in-module
        from django.db.models.loading import get_model

        # pylint: enable=no-name-in-module

        django_pillar = {}

        for proj_app, models in six.iteritems(django_app):
            _, _, app = proj_app.rpartition(".")
            django_pillar[app] = {}
            for model_name, model_meta in six.iteritems(models):
                model_orm = get_model(app, model_name)
                if model_orm is None:
                    raise salt.exceptions.SaltException(
                        "Django model '{0}' not found in app '{1}'.".format(
                            app, model_name
                        )
                    )

                pillar_for_model = django_pillar[app][model_orm.__name__] = {}

                name_field = model_meta["name"]
                fields = model_meta["fields"]

                if "filter" in model_meta:
                    qs = model_orm.objects.filter(**model_meta["filter"]).values(
                        *fields
                    )
                else:
                    qs = model_orm.objects.values(*fields)

                for model in qs:
                    # Check that the human-friendly name given is valid (will
                    # be able to pick up a value from the query) and unique
                    # (since we're using it as the key in a dictionary)
                    if name_field not in model:
                        raise salt.exceptions.SaltException(
                            "Name '{0}' not found in returned fields.".format(
                                name_field
                            )
                        )

                    if model[name_field] in pillar_for_model:
                        raise salt.exceptions.SaltException(
                            "Value for '{0}' is not unique: {0}".format(
                                model[name_field]
                            )
                        )

                    pillar_for_model[model[name_field]] = model

        return {pillar_name: django_pillar}
    except ImportError as e:
        log.error("Failed to import library: %s", e)
        return {}
    except Exception as e:  # pylint: disable=broad-except
        log.error("Failed on Error: %s", e)
        log.debug("django_orm traceback", exc_info=True)
        return {}
