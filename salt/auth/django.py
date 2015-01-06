# -*- coding: utf-8 -*-
'''
Provide authentication using Django Web Framework

Django authentication depends on the presence of the django
framework in the PYTHONPATH, the django project's settings.py file being in
the PYTHONPATH and accessible via the DJANGO_SETTINGS_MODULE environment
variable.  This can be hard to debug.

django auth can be defined like any other eauth module:

external_auth:
  django:
    fred:
      - .*
      - '@runner'

This will authenticate Fred via django and allow him to run any
execution module and all runners.

The details of the django auth can also be located inside the django database.  The
relevant entry in the models.py file would look like this:

class SaltExternalAuthModel(models.Model):

  user_fk = models.ForeignKey(auth.User)
  minion_matcher = models.CharField()
  minion_fn = models.CharField()

Then, in the master's config file the external_auth clause should look like

external_auth:
  django:
    ^model: <fully-qualified reference to model class>

When a user attempts to authenticate via Django, Salt will import the package
indicated via the keyword '^model'.  That model must have the fields
indicated above, though the model DOES NOT have to be named 'SaltExternalAuthModel'.

:depends:   - Django Web Framework
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs

log = logging.getLogger(__name__)

try:
    import django
    import django.conf
    import django.contrib.auth
    HAS_DJANGO = True
except Exception as exc:
    # If Django is installed and is not detected, uncomment
    # the following line to display additional information
    #log.warning('Could not load Django auth module. Found exception: {0}'.format(exc))
    HAS_DJANGO = False

django_auth_class = None


def django_auth_setup():
    '''
    Prepare the connection to the Django authentication framework
    '''
    global django_auth_class

    if django_auth_class is not None:
        return

    # Versions 1.7 and later of Django don't pull models until
    # they are needed.  When using framework facilities outside the
    # web application container we need to run django.setup() to
    # get the model definitions cached.
    if '^model' in __opts__['external_auth']['django']:
        django_model_fullname = __opts__['external_auth']['django']['^model']
        django_model_name = django_model_fullname.split('.')[-1]
        django_module_name = '.'.join(django_model_fullname.split('.')[0:-1])

        __import__(django_module_name, globals(), locals(), 'SaltExternalAuthModel')
        django_auth_class_str = 'django_auth_module.{0}'.format(django_model_name)
        django_auth_class = eval(django_auth_class_str)  # pylint: disable=W0123

    if django.VERSION >= (1, 7):
        django.setup()


def auth(username, password):
    '''
    Simple Django auth
    '''

    django_auth_setup()
    user = django.contrib.auth.authenticate(username=username, password=password)
    if user is not None:
        if user.is_active:
            log.debug('Django authentication successful')

            auth_dict_from_db = retrieve_auth_entries(username)[username]
            if auth_dict_from_db is not None:
                __opts__['external_auth']['django'][username] = auth_dict_from_db

            return True
        else:
            log.debug('Django authentication: the password is valid but the account is disabled.')

    return False


def retrieve_auth_entries(u=None):
    '''

    :param u: Username to filter for
    :return: Dictionary that can be slotted into the __opts__ structure for eauth that designates the
             user and his or her ACL

    username     minion_or_fn_matcher     minion_fn
    fred                                  test.ping
    fred         server1                  network.interfaces
    fred         server1                  raid.list
    fred         server2                  .*
    guru         .*
    smartadmin   server1                  .*

    Should result in
    fred:
      - test.ping
      - server1:
          - network.interfaces
          - raid.list
      - server2:
          - .*
    guru:
      - .*
    smartadmin:
      - server1:
        - .*

    '''
    django_auth_setup()

    if u is None:
        db_records = django_auth_class.objects.all()
    else:
        db_records = django_auth_class.objects.filter(user_fk__username=u)
    auth_dict = {}

    for a in db_records:
        if a.user_fk.username not in auth_dict:
            auth_dict[a.user_fk.username] = []

        if not a.minion_or_fn_matcher and a.minion_fn:
            auth_dict[a.user_fk.username].append(a.minion_fn)
        elif a.minion_or_fn_matcher and not a.minion_fn:
            auth_dict[a.user_fk.username].append(a.minion_or_fn_matcher)
        else:
            found = False
            for d in auth_dict[a.user_fk.username]:
                if isinstance(d, dict):
                    if a.minion_or_fn_matcher in d.keys():
                        auth_dict[a.user_fk.username][a.minion_or_fn_matcher].append(a.minion_fn)
                        found = True
            if not found:
                auth_dict[a.user_fk.username].append({a.minion_or_fn_matcher: [a.minion_fn]})

    log.debug('django auth_dict is {0}'.format(repr(auth_dict)))
    return auth_dict
