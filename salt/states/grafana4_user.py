# -*- coding: utf-8 -*-
'''
Manage Grafana v4.0 users

.. versionadded:: 2017.7.0

Token auth setup

.. code-block:: yaml

    grafana_version: 4
    grafana:
      grafana_timeout: 5
      grafana_token: qwertyuiop
      grafana_url: 'https://url.com'

Basic auth setup

.. code-block:: yaml

    grafana_version: 4
    grafana:
      grafana_timeout: 5
      grafana_user: grafana
      grafana_password: qwertyuiop
      grafana_url: 'https://url.com'

.. code-block:: yaml

    Ensure foobar user is present:
      grafana4_user.present:
        - name: foobar
        - password: mypass
        - email: "foobar@localhost"
        - fullname: Foo Bar
        - is_admin: true
'''
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.dictupdate as dictupdate
from salt.utils.dictdiffer import deep_diff

# Import 3rd-party libs
from salt.ext.six import string_types


def __virtual__():
    '''Only load if grafana4 module is available'''
    return 'grafana4.get_user' in __salt__


def present(name,
            password,
            email,
            is_admin=False,
            fullname=None,
            theme=None,
            profile='grafana'):
    '''
    Ensure that a user is present.

    name
        Name of the user.

    password
        Password of the user.

    email
        Email of the user.

    is_admin
        Optional - Set user as admin user. Default: False

    fullname
        Optional - Full name of the user.

    theme
        Optional - Selected theme of the user.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.
    '''
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)

    ret = {'name': name, 'result': None, 'comment': None, 'changes': {}}
    user = __salt__['grafana4.get_user'](name, profile)
    create = not user

    if create:
        __salt__['grafana4.create_user'](
            login=name,
            password=password,
            email=email,
            name=fullname,
            profile=profile)
        user = __salt__['grafana4.get_user'](name, profile)
        ret['changes']['new'] = user

    user_data = __salt__['grafana4.get_user_data'](user['id'])
    data = _get_json_data(login=name, email=email, name=fullname, theme=theme,
                          defaults=user_data)
    if data != _get_json_data(login=None, email=None, name=None, theme=None,
                              defaults=user_data):
        __salt__['grafana4.update_user'](user['id'], profile=profile, **data)
        dictupdate.update(
            ret['changes'], deep_diff(
                user_data, __salt__['grafana4.get_user_data'](user['id'])))

    if user['isAdmin'] != is_admin:
        __salt__['grafana4.update_user_permissions'](
            user['id'], isGrafanaAdmin=is_admin, profile=profile)
        dictupdate.update(ret['changes'], deep_diff(
            user, __salt__['grafana4.get_user'](name, profile)))

    ret['result'] = True
    if create:
        ret['changes'] = ret['changes']['new']
        ret['comment'] = 'New user {0} added'.format(name)
    else:
        if ret['changes']:
            ret['comment'] = 'User {0} updated'.format(name)
        else:
            ret['changes'] = None
            ret['comment'] = 'User {0} already up-to-date'.format(name)

    return ret


def absent(name, profile='grafana'):
    '''
    Ensure that a user is present.

    name
        Name of the user to remove.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.
    '''
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)

    ret = {'name': name, 'result': None, 'comment': None, 'changes': {}}
    user = __salt__['grafana4.get_user'](name, profile)

    if user:
        orgs = __salt__['grafana4.get_user_orgs'](user['id'], profile=profile)
        __salt__['grafana4.delete_user'](user['id'], profile=profile)
        for org in orgs:
            if org['name'] == user['email']:
                # Remove entire Org in the case where auto_assign_org=false:
                # When set to false, new users will automatically cause a new
                # organization to be created for that new user (the org name
                # will be the email)
                __salt__['grafana4.delete_org'](org['orgId'], profile=profile)
            else:
                __salt__['grafana4.delete_user_org'](
                    user['id'], org['orgId'], profile=profile)
    else:
        ret['result'] = True
        ret['comment'] = 'User {0} already absent'.format(name)
        return ret

    ret['result'] = True
    ret['changes'][name] = 'Absent'
    ret['comment'] = 'User {0} was deleted'.format(name)
    return ret


def _get_json_data(defaults=None, **kwargs):
    if defaults is None:
        defaults = {}
    for k, v in kwargs.items():
        if v is None:
            kwargs[k] = defaults.get(k)
    return kwargs
