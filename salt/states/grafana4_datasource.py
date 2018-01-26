# -*- coding: utf-8 -*-
'''
Manage Grafana v4.0 data sources

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

    Ensure influxdb data source is present:
      grafana_datasource.present:
        - name: influxdb
        - type: influxdb
        - url: http://localhost:8086
        - access: proxy
        - basic_auth: true
        - basic_auth_user: myuser
        - basic_auth_password: mypass
        - is_default: true
'''
from __future__ import absolute_import, print_function, unicode_literals

from salt.ext.six import string_types
from salt.utils.dictdiffer import deep_diff


def __virtual__():
    '''Only load if grafana4 module is available'''
    return 'grafana4.get_datasource' in __salt__


def present(name,
            type,
            url,
            access=None,
            user=None,
            password=None,
            database=None,
            basic_auth=None,
            basic_auth_user=None,
            basic_auth_password=None,
            tls_auth=None,
            json_data=None,
            is_default=None,
            with_credentials=None,
            type_logo_url=None,
            orgname=None,
            profile='grafana'):
    '''
    Ensure that a data source is present.

    name
        Name of the data source.

    type
        Type of the datasource ('graphite', 'influxdb' etc.).

    access
        Use proxy or direct. Default: proxy

    url
        The URL to the data source API.

    user
        Optional - user to authenticate with the data source.

    password
        Optional - password to authenticate with the data source.

    database
        Optional - database to use with the data source.

    basic_auth
        Optional - set to True to use HTTP basic auth to authenticate with the
        data source.

    basic_auth_user
        Optional - HTTP basic auth username.

    basic_auth_password
        Optional - HTTP basic auth password.

    json_data
        Optional - additional json data to post (eg. "timeInterval").

    is_default
        Optional - set data source as default.

    with_credentials
        Optional - Whether credentials such as cookies or auth headers should
        be sent with cross-site requests.

    type_logo_url
        Optional - Logo to use for this datasource.

    orgname
        Name of the organization in which the data source should be present.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.
    '''
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)

    ret = {'name': name, 'result': None, 'comment': None, 'changes': None}
    datasource = __salt__['grafana4.get_datasource'](name, orgname, profile)
    data = _get_json_data(
        name=name,
        type=type,
        url=url,
        access=access,
        user=user,
        password=password,
        database=database,
        basicAuth=basic_auth,
        basicAuthUser=basic_auth_user,
        basicAuthPassword=basic_auth_password,
        tlsAuth=tls_auth,
        jsonData=json_data,
        isDefault=is_default,
        withCredentials=with_credentials,
        typeLogoUrl=type_logo_url,
        defaults=datasource)

    if not datasource:
        __salt__['grafana4.create_datasource'](profile=profile, **data)
        datasource = __salt__['grafana4.get_datasource'](name, profile=profile)
        ret['result'] = True
        ret['comment'] = 'New data source {0} added'.format(name)
        ret['changes'] = data
        return ret

    # At this stage, the datasource exists; however, the object provided by
    # Grafana may lack some null keys compared to our "data" dict:
    for key in data:
        if key not in datasource:
            datasource[key] = None

    if data == datasource:
        ret['changes'] = None
        ret['comment'] = 'Data source {0} already up-to-date'.format(name)
        return ret

    __salt__['grafana4.update_datasource'](
        datasource['id'], profile=profile, **data)
    ret['result'] = True
    ret['changes'] = deep_diff(datasource, data, ignore=['id', 'orgId'])
    ret['comment'] = 'Data source {0} updated'.format(name)
    return ret


def absent(name, orgname=None, profile='grafana'):
    '''
    Ensure that a data source is present.

    name
        Name of the data source to remove.

    orgname
        Name of the organization from which the data source should be absent.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.
    '''
    if isinstance(profile, string_types):
        profile = __salt__['config.option'](profile)

    ret = {'name': name, 'result': None, 'comment': None, 'changes': {}}
    datasource = __salt__['grafana4.get_datasource'](name, orgname, profile)

    if not datasource:
        ret['result'] = True
        ret['comment'] = 'Data source {0} already absent'.format(name)
        return ret

    __salt__['grafana4.delete_datasource'](datasource['id'], profile=profile)

    ret['result'] = True
    ret['changes'][name] = 'Absent'
    ret['comment'] = 'Data source {0} was deleted'.format(name)

    return ret


def _get_json_data(defaults=None, **kwargs):
    if defaults is None:
        defaults = {}
    for k, v in kwargs.items():
        if v is None:
            kwargs[k] = defaults.get(k)
    return kwargs
