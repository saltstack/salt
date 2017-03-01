# -*- coding: utf-8 -*-
'''
Manage Grafana v4.0 orgs

.. versionadded:: Nitrogen

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
      grafana_org: grafana
      grafana_password: qwertyuiop
      grafana_url: 'https://url.com'

.. code-block:: yaml

    Ensure foobar org is present:
      grafana4_org.present:
        - name: foobar
        - theme:  ""
        - home_dashboard_id: 0
        - timezone: "utc"
        - address1: ""
        - address2: ""
        - city: ""
        - zip_code: ""
        - state: ""
        - country: ""
'''
from __future__ import absolute_import

from salt.ext.six import string_types
from salt.utils import dictupdate
from salt.utils.dictdiffer import deep_diff
from requests.exceptions import HTTPError


def __virtual__():
    '''Only load if grafana4 module is available'''
    return 'grafana4.get_org' in __salt__


def present(name,
            users=None,
            theme=None,
            home_dashboard_id=None,
            timezone=None,
            address1=None,
            address2=None,
            city=None,
            zip_code=None,
            address_state=None,
            country=None,
            profile='grafana'):
    '''
    Ensure that an organization is present.

    name
        Name of the org.

    users
        Optional - Dict of user/role associated with the org. Example:
        users:
          foo: Viewer
          bar: Editor

    theme
        Optional - Selected theme for the org.

    home_dashboard_id
        Optional - Home dashboard for the org.

    timezone
        Optional - Timezone for the org (one of: "browser", "utc", or "").

    address1
        Optional - address1 of the org.

    address2
        Optional - address2 of the org.

    city
        Optional - city of the org.

    zip_code
        Optional - zip_code of the org.

    address_state
        Optional - state of the org.

    country
        Optional - country of the org.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.
    '''
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)

    ret = {'name': name, 'result': None, 'comment': None, 'changes': {}}
    create = False
    try:
        org = __salt__['grafana4.get_org'](name, profile)
    except HTTPError as e:
        if e.response.status_code == 404:
            create = True
        else:
            raise

    if create:
        __salt__['grafana4.create_org'](profile=profile, name=name)
        org = __salt__['grafana4.get_org'](name, profile)
        ret['changes'] = org
        ret['comment'] = 'New org {0} added'.format(name)

    data = _get_json_data(address1=address1, address2=address2,
        city=city, zipCode=zip_code, state=address_state, country=country,
        defaults=org['address'])
    if data != org['address']:
        __salt__['grafana4.update_org_address'](name, profile=profile, **data)
        if create:
            dictupdate.update(ret['changes']['address'], data)
        else:
            dictupdate.update(ret['changes'], deep_diff(org['address'], data))

    prefs = __salt__['grafana4.get_org_prefs'](name, profile=profile)
    data = _get_json_data(theme=theme, homeDashboardId=home_dashboard_id,
        timezone=timezone, defaults=prefs)
    if data != prefs:
        __salt__['grafana4.update_org_prefs'](name, profile=profile, **data)
        if create:
            dictupdate.update(ret['changes'], data)
        else:
            dictupdate.update(ret['changes'], deep_diff(prefs, data))

    if users:
        db_users = {}
        for item in __salt__['grafana4.get_org_users'](name, profile=profile):
            db_users[item['login']] = {
                'userId': item['userId'],
                'role': item['role'],
                }
        for username, role in users.items():
            if username in db_users:
                if role is False:
                    __salt__['grafana4.delete_org_user'](
                        db_users[username]['userId'], profile=profile)
                elif role != db_users[username]['role']:
                    __salt__['grafana4.update_org_user'](
                        db_users[username]['userId'], loginOrEmail=username,
                        role=role, profile=profile)
            elif role:
                __salt__['grafana4.create_org_user'](
                    loginOrEmail=username, role=role, profile=profile)

        new_db_users = {}
        for item in __salt__['grafana4.get_org_users'](name, profile=profile):
            new_db_users[item['login']] = {
                'userId': item['userId'],
                'role': item['role'],
                }
        if create:
            dictupdate.update(ret['changes'], new_db_users)
        else:
            dictupdate.update(ret['changes'], deep_diff(db_users, new_db_users))

    ret['result'] = True
    if not create:
        if ret['changes']:
            ret['comment'] = 'Org {0} updated'.format(name)
        else:
            ret['changes'] = None
            ret['comment'] = 'Org {0} already up-to-date'.format(name)

    return ret


def absent(name, profile='grafana'):
    '''
    Ensure that a org is present.

    name
        Name of the org to remove.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.
    '''
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)

    ret = {'name': name, 'result': None, 'comment': None, 'changes': {}}
    org = __salt__['grafana4.get_org'](name, profile)

    if not org:
        ret['result'] = True
        ret['comment'] = 'Org {0} already absent'.format(name)
        return ret

    __salt__['grafana4.delete_org'](org['id'], profile=profile)

    ret['result'] = True
    ret['changes'][name] = 'Absent'
    ret['comment'] = 'Org {0} was deleted'.format(name)

    return ret


def _get_json_data(defaults=None, **kwargs):
    if defaults is None:
        defaults = {}
    for k, v in kwargs.items():
        if v is None:
            kwargs[k] = defaults.get(k)
    return kwargs
