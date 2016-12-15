# -*- coding: utf-8 -*-
'''
Module for working with the Grafana v4 API

:depends: requests

:configuration: This module can be used by specifying the name of a
    configuration profile in the minion config, minion pillar, or master
    config.

    For example:

    .. code-block:: yaml

        grafana:
            grafana_url: http://grafana.localhost
            grafana_user: admin
            grafana_password: admin
            grafana_timeout: 3
'''
from __future__ import absolute_import

try:
    import requests
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

from salt.ext.six import string_types


__virtualname__ = 'grafana4'


def __virtual__():
    '''
    Only load if requests is installed
    '''
    if HAS_LIBS:
        return __virtualname__
    else:
        return False, 'The "{0}" module could not be loaded: ' \
                      '"requests" is not installed.'.format(__virtualname__)


def _get_headers(profile):
    headers = {'Content-type': 'application/json'}
    if profile.get('grafana_token', False):
        headers['Authorization'] = 'Bearer {0}'.format(
            profile['grafana_token'])
    return headers


def _get_auth(profile):
    if profile.get('grafana_token', False):
        return None
    return requests.auth.HTTPBasicAuth(
        profile['grafana_user'],
        profile['grafana_password']
    )


def get_users(profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    response = requests.get(
        '{0}/api/users'.format(profile['grafana_url']),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_user(login, profile='grafana'):
    data = get_users(profile)
    for user in data:
        if user['login'] == login:
            return user
    return None


def get_user_data(userid, profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    response = requests.get(
        '{0}/api/users/{1}'.format(profile['grafana_url'], userid),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def create_user(profile='grafana', **kwargs):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    response = requests.post(
        '{0}/api/admin/users'.format(profile['grafana_url']),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def update_user(userid, profile='grafana', **kwargs):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    response = requests.put(
        '{0}/api/users/{1}'.format(profile['grafana_url'], userid),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def update_user_password(userid, profile='grafana', **kwargs):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    response = requests.put(
        '{0}/api/admin/users/{1}/password'.format(
            profile['grafana_url'], userid),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def update_user_permissions(userid, profile='grafana', **kwargs):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    response = requests.put(
        '{0}/api/admin/users/{1}/permissions'.format(
            profile['grafana_url'], userid),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def delete_user(userid, profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    response = requests.delete(
        '{0}/api/admin/users/{1}'.format(profile['grafana_url'], userid),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_user_orgs(userid, profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    response = requests.get(
        '{0}/api/users/{1}/orgs'.format(profile['grafana_url'], userid),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def delete_user_org(userid, orgid, profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    response = requests.delete(
        '{0}/api/orgs/{1}/users/{2}'.format(
            profile['grafana_url'], orgid, userid),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_orgs(profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    response = requests.get(
        '{0}/api/orgs'.format(profile['grafana_url']),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_org(name, profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    response = requests.get(
        '{0}/api/orgs/name/{1}'.format(profile['grafana_url'], name),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def switch_org(orgname, profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    org = get_org(orgname, profile)
    response = requests.post(
        '{0}/api/user/using/{1}'.format(profile['grafana_url'], org['id']),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return org


def get_org_users(orgname=None, profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.get(
        '{0}/api/org/users'.format(profile['grafana_url']),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def create_org_users(orgname=None, profile='grafana', **kwargs):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.post(
        '{0}/api/org/users'.format(profile['grafana_url']),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def update_org_users(userid, orgname=None, profile='grafana', **kwargs):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.patch(
        '{0}/api/org/users/{1}'.format(profile['grafana_url'], userid),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def delete_org_users(userid, orgname=None, profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.delete(
        '{0}/api/org/users/{1}'.format(profile['grafana_url'], userid),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_org_address(orgname=None, profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.get(
        '{0}/api/org/address'.format(profile['grafana_url']),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def update_org_address(orgname=None, profile='grafana', **kwargs):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.put(
        '{0}/api/org/address'.format(profile['grafana_url']),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_org_prefs(orgname=None, profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.get(
        '{0}/api/org/preferences'.format(profile['grafana_url']),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def update_org_prefs(orgname=None, profile='grafana', **kwargs):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.put(
        '{0}/api/org/preferences'.format(profile['grafana_url']),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def create_org(profile='grafana', **kwargs):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    response = requests.post(
        '{0}/api/orgs'.format(profile['grafana_url']),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def update_org(orgid, profile='grafana', **kwargs):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    response = requests.put(
        '{0}/api/orgs/{1}'.format(profile['grafana_url'], orgid),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def delete_org(orgid, profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    response = requests.delete(
        '{0}/api/orgs/{1}'.format(profile['grafana_url'], orgid),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_datasources(orgname=None, profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.get(
        '{0}/api/datasources'.format(profile['grafana_url']),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_datasource(name, orgname=None, profile='grafana'):
    data = get_datasources(orgname=orgname, profile=profile)
    for datasource in data:
        if datasource['name'] == name:
            return datasource
    return None


def create_datasource(orgname=None, profile='grafana', **kwargs):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.post(
        '{0}/api/datasources'.format(profile['grafana_url']),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def update_datasource(datasourceid, orgname=None, profile='grafana', **kwargs):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    response = requests.put(
        '{0}/api/datasources/{1}'.format(profile['grafana_url'], datasourceid),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return {}  # temporary fix for https://github.com/grafana/grafana/issues/6869
    return response.json()


def delete_datasource(datasourceid, orgname=None, profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    response = requests.delete(
        '{0}/api/datasources/{1}'.format(profile['grafana_url'], datasourceid),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_dashboard(slug, orgname=None, profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.get(
        '{0}/api/dashboards/db/{1}'.format(profile['grafana_url'], slug),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    data = response.json()
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        import pdb; pdb.set_trace()
        response.raise_for_status()
    return data.get('dashboard')


def delete_dashboard(slug, orgname=None, profile='grafana'):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.delete(
        '{0}/api/dashboards/db/{1}'.format(profile['grafana_url'], slug),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def create_update_dashboard(orgname=None, profile='grafana', **kwargs):
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.post(
        "{0}/api/dashboards/db".format(profile.get('grafana_url')),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get('grafana_timeout', 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()
