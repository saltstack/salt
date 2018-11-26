# -*- coding: utf-8 -*-
'''
Manage Grafana v4.0 users

.. versionadded:: 2017.7.0

:configuration: This state requires a configuration profile to be configured
    in the minion config, minion pillar, or master config. The module will use
    the 'grafana' key by default, if defined.

    Example configuration using basic authentication:

    .. code-block:: yaml

        grafana:
          grafana_url: http://grafana.localhost
          grafana_user: admin
          grafana_password: admin
          grafana_timeout: 3

    Example configuration using token based authentication:

    .. code-block:: yaml

        grafana:
          grafana_url: http://grafana.localhost
          grafana_token: token
          grafana_timeout: 3

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
from requests.exceptions import HTTPError


def __virtual__():
    '''Only load if grafana4 module is available'''
    return 'grafana4.get_user' in __salt__


def present(name,
            password,
            email=None,
            is_admin=False,
            fullname=None,
            theme=None,
            default_organization=None,
            organizations=None,
            profile='grafana'):
    '''
    Ensure that a user is present.

    name
        Name of the user.

    password
        Password of the user.

    email
        Optional - Email of the user.

    is_admin
        Optional - Set user as admin user. Default: False

    fullname
        Optional - Full name of the user.

    theme
        Optional - Selected theme of the user.

    default_organization
        Optional - Set user's default organization

    organizations
        Optional - List of viewer member organizations or pairs of organization and role that the user belongs to.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.


    Here is an example for using default_organization and organizations
    parameters. The user will be added as a viewer to ReadonlyOrg, as an editor
    to TestOrg and as an admin to AdminOrg. When she logs on, TestOrg will be
    the default. The state will fail if any organisation is unknown or invalid
    roles are defined.

    .. code-block:: yaml

        add_grafana_test_user:
          grafana4_user.present:
            - name: test
            - password: 1234567890
            - fullname: 'Test User'
            - default_organization: TestOrg
            - organizations:
              - ReadonlyOrg
              - TestOrg: Editor
              - Staging: Admin
    '''
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)

    ret = {'name': name, 'result': None, 'comment': None, 'changes': {}}
    user = __salt__['grafana4.get_user'](name, profile)
    create = not user

    if create:
        if __opts__['test']:
            ret['comment'] = 'User {0} will be created'.format(name)
            return ret
        __salt__['grafana4.create_user'](
            login=name,
            password=password,
            email=email,
            name=fullname,
            profile=profile)
        user = __salt__['grafana4.get_user'](name, profile)
        ret['changes']['new'] = user

    user_data = __salt__['grafana4.get_user_data'](user['id'], profile=profile)

    if default_organization:
        try:
            org_id = __salt__['grafana4.get_org'](default_organization, profile)['id']
        except HTTPError as e:
            ret['comment'] = 'Error while looking up user {}\'s default grafana org {}: {}'.format(
                    name, default_organization, e)
            ret['result'] = False
            return ret
    new_data = _get_json_data(login=name, email=email, name=fullname, theme=theme,
                            orgId=org_id if default_organization else None,
                            defaults=user_data)
    old_data = _get_json_data(login=None, email=None, name=None, theme=None,
                            orgId=None,
                            defaults=user_data)
    if organizations:
        ret = _update_user_organizations(name, user['id'], organizations, ret, profile)
        if 'result' in ret and ret['result'] is False:
            return ret

    if new_data != old_data:
        if __opts__['test']:
            ret['comment'] = 'User {0} will be updated'.format(name)
            dictupdate.update(ret['changes'], deep_diff(old_data, new_data))
            return ret
        __salt__['grafana4.update_user'](user['id'], profile=profile, orgid=org_id, **new_data)
        dictupdate.update(
            ret['changes'], deep_diff(
                user_data, __salt__['grafana4.get_user_data'](user['id'])))

    if user['isAdmin'] != is_admin:
        if __opts__['test']:
            ret['comment'] = 'User {0} isAdmin status will be updated'.format(
                    name)
            return ret
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
            ret['changes'] = {}
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
        if __opts__['test']:
            ret['comment'] = 'User {0} will be deleted'.format(name)
            return ret
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


def _update_user_organizations(user_name, user_id, organizations, ret, profile):
    for org in organizations.items():
        org_name, org_role = org if isinstance(org, tuple) and len(org) == 2 else (org, 'Viewer')
        try:
            org_users = __salt__['grafana4.get_org_users'](org_name, profile)
        except HTTPError as e:
            ret['comment'] = 'Error while looking up user {}\'s grafana org {}: {}'.format(
                    user_name, org_name, e)
            ret['result'] = False
            return ret
        user_found = False
        for org_user in org_users:
            if org_user['userId'] == user_id:
                if org_user['role'] != org_role:
                    try:
                        __salt__['grafana4.update_org_user'](user_id,
                                orgname=org_name, profile=profile, role=org_role)
                    except HTTPError as e:
                        ret['comment'] = 'Error while setting role {} for user {} in grafana org {}: {}'.format(
                                org_role, user_name, org_name, e)
                        ret['result'] = False
                        return ret
                    ret['changes'][org_name] = org_role
                user_found = True
                break
        if not user_found:
            ret['changes'][org_name] = org_role
            __salt__['grafana4.create_org_user'](orgname=org_name,
                    profile=profile, role=org_role, loginOrEmail=user_name)
    return ret
