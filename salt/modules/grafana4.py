"""
Module for working with the Grafana v4 API

.. versionadded:: 2017.7.0

:depends: requests

:configuration: This module requires a configuration profile to be configured
    in the minion config, minion pillar, or master config.
    The module will use the 'grafana' key by default, if defined.

    For example:

    .. code-block:: yaml

        grafana:
            grafana_url: http://grafana.localhost
            grafana_user: admin
            grafana_password: admin
            grafana_timeout: 3
"""

try:
    import requests

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False


__virtualname__ = "grafana4"


def __virtual__():
    """
    Only load if requests is installed
    """
    if HAS_LIBS:
        return __virtualname__
    else:
        return (
            False,
            'The "{}" module could not be loaded: "requests" is not installed.'.format(
                __virtualname__
            ),
        )


def _get_headers(profile):
    headers = {"Content-type": "application/json"}
    if profile.get("grafana_token", False):
        headers["Authorization"] = "Bearer {}".format(profile["grafana_token"])
    return headers


def _get_auth(profile):
    if profile.get("grafana_token", False):
        return None
    return requests.auth.HTTPBasicAuth(
        profile["grafana_user"], profile["grafana_password"]
    )


def get_users(profile="grafana"):
    """
    List all users.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.get_users
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    response = requests.get(
        "{}/api/users".format(profile["grafana_url"]),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_user(login, profile="grafana"):
    """
    Show a single user.

    login
        Login of the user.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.get_user <login>
    """
    data = get_users(profile)
    for user in data:
        if user["login"] == login:
            return user
    return None


def get_user_data(userid, profile="grafana"):
    """
    Get user data.

    userid
        Id of the user.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.get_user_data <user_id>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    response = requests.get(
        "{}/api/users/{}".format(profile["grafana_url"], userid),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def create_user(profile="grafana", **kwargs):
    """
    Create a new user.

    login
        Login of the new user.

    password
        Password of the new user.

    email
        Email of the new user.

    name
        Optional - Full name of the new user.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.create_user login=<login> password=<password> email=<email>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    response = requests.post(
        "{}/api/admin/users".format(profile["grafana_url"]),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def update_user(userid, profile="grafana", **kwargs):
    """
    Update an existing user.

    userid
        Id of the user.

    login
        Optional - Login of the user.

    email
        Optional - Email of the user.

    name
        Optional - Full name of the user.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.update_user <user_id> login=<login> email=<email>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    response = requests.put(
        "{}/api/users/{}".format(profile["grafana_url"], userid),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def update_user_password(userid, profile="grafana", **kwargs):
    """
    Update a user password.

    userid
        Id of the user.

    password
        New password of the user.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.update_user_password <user_id> password=<password>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    response = requests.put(
        "{}/api/admin/users/{}/password".format(profile["grafana_url"], userid),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def update_user_permissions(userid, profile="grafana", **kwargs):
    """
    Update a user password.

    userid
        Id of the user.

    isGrafanaAdmin
        Whether user is a Grafana admin.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.update_user_permissions <user_id> isGrafanaAdmin=<true|false>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    response = requests.put(
        "{}/api/admin/users/{}/permissions".format(profile["grafana_url"], userid),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def delete_user(userid, profile="grafana"):
    """
    Delete a user.

    userid
        Id of the user.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.delete_user <user_id>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    response = requests.delete(
        "{}/api/admin/users/{}".format(profile["grafana_url"], userid),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_user_orgs(userid, profile="grafana"):
    """
    Get the list of organisations a user belong to.

    userid
        Id of the user.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.get_user_orgs <user_id>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    response = requests.get(
        "{}/api/users/{}/orgs".format(profile["grafana_url"], userid),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def delete_user_org(userid, orgid, profile="grafana"):
    """
    Remove a user from an organization.

    userid
        Id of the user.

    orgid
        Id of the organization.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.delete_user_org <user_id> <org_id>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    response = requests.delete(
        "{}/api/orgs/{}/users/{}".format(profile["grafana_url"], orgid, userid),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_orgs(profile="grafana"):
    """
    List all organizations.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.get_orgs
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    response = requests.get(
        "{}/api/orgs".format(profile["grafana_url"]),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_org(name, profile="grafana"):
    """
    Show a single organization.

    name
        Name of the organization.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.get_org <name>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    response = requests.get(
        "{}/api/orgs/name/{}".format(profile["grafana_url"], name),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def switch_org(orgname, profile="grafana"):
    """
    Switch the current organization.

    name
        Name of the organization to switch to.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.switch_org <name>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    org = get_org(orgname, profile)
    response = requests.post(
        "{}/api/user/using/{}".format(profile["grafana_url"], org["id"]),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return org


def get_org_users(orgname=None, profile="grafana"):
    """
    Get the list of users that belong to the organization.

    orgname
        Name of the organization.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.get_org_users <orgname>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.get(
        "{}/api/org/users".format(profile["grafana_url"]),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def create_org_user(orgname=None, profile="grafana", **kwargs):
    """
    Add user to the organization.

    loginOrEmail
        Login or email of the user.

    role
        Role of the user for this organization. Should be one of:
            - Admin
            - Editor
            - Read Only Editor
            - Viewer

    orgname
        Name of the organization in which users are added.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.create_org_user <orgname> loginOrEmail=<loginOrEmail> role=<role>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.post(
        "{}/api/org/users".format(profile["grafana_url"]),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def update_org_user(userid, orgname=None, profile="grafana", **kwargs):
    """
    Update user role in the organization.

    userid
        Id of the user.

    loginOrEmail
        Login or email of the user.

    role
        Role of the user for this organization. Should be one of:
            - Admin
            - Editor
            - Read Only Editor
            - Viewer

    orgname
        Name of the organization in which users are updated.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.update_org_user <user_id> <orgname> loginOrEmail=<loginOrEmail> role=<role>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.patch(
        "{}/api/org/users/{}".format(profile["grafana_url"], userid),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def delete_org_user(userid, orgname=None, profile="grafana"):
    """
    Remove user from the organization.

    userid
        Id of the user.

    orgname
        Name of the organization in which users are updated.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.delete_org_user <user_id> <orgname>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.delete(
        "{}/api/org/users/{}".format(profile["grafana_url"], userid),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_org_address(orgname=None, profile="grafana"):
    """
    Get the organization address.

    orgname
        Name of the organization in which users are updated.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.get_org_address <orgname>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.get(
        "{}/api/org/address".format(profile["grafana_url"]),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def update_org_address(orgname=None, profile="grafana", **kwargs):
    """
    Update the organization address.

    orgname
        Name of the organization in which users are updated.

    address1
        Optional - address1 of the org.

    address2
        Optional - address2 of the org.

    city
        Optional - city of the org.

    zip_code
        Optional - zip_code of the org.

    state
        Optional - state of the org.

    country
        Optional - country of the org.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.update_org_address <orgname> country=<country>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.put(
        "{}/api/org/address".format(profile["grafana_url"]),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_org_prefs(orgname=None, profile="grafana"):
    """
    Get the organization preferences.

    orgname
        Name of the organization in which users are updated.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.get_org_prefs <orgname>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.get(
        "{}/api/org/preferences".format(profile["grafana_url"]),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def update_org_prefs(orgname=None, profile="grafana", **kwargs):
    """
    Update the organization preferences.

    orgname
        Name of the organization in which users are updated.

    theme
        Selected theme for the org.

    homeDashboardId
        Home dashboard for the org.

    timezone
        Timezone for the org (one of: "browser", "utc", or "").

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.update_org_prefs <orgname> theme=<theme> timezone=<timezone>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.put(
        "{}/api/org/preferences".format(profile["grafana_url"]),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def create_org(profile="grafana", **kwargs):
    """
    Create a new organization.

    name
        Name of the organization.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.create_org <name>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    response = requests.post(
        "{}/api/orgs".format(profile["grafana_url"]),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def update_org(orgid, profile="grafana", **kwargs):
    """
    Update an existing organization.

    orgid
        Id of the organization.

    name
        New name of the organization.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.update_org <org_id> name=<name>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    response = requests.put(
        "{}/api/orgs/{}".format(profile["grafana_url"], orgid),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def delete_org(orgid, profile="grafana"):
    """
    Delete an organization.

    orgid
        Id of the organization.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.delete_org <org_id>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    response = requests.delete(
        "{}/api/orgs/{}".format(profile["grafana_url"], orgid),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_datasources(orgname=None, profile="grafana"):
    """
    List all datasources in an organisation.

    orgname
        Name of the organization.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.get_datasources <orgname>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.get(
        "{}/api/datasources".format(profile["grafana_url"]),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_datasource(name, orgname=None, profile="grafana"):
    """
    Show a single datasource in an organisation.

    name
        Name of the datasource.

    orgname
        Name of the organization.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.get_datasource <name> <orgname>
    """
    data = get_datasources(orgname=orgname, profile=profile)
    for datasource in data:
        if datasource["name"] == name:
            return datasource
    return None


def create_datasource(orgname=None, profile="grafana", **kwargs):
    """
    Create a new datasource in an organisation.

    name
        Name of the data source.

    type
        Type of the datasource ('graphite', 'influxdb' etc.).

    access
        Use proxy or direct.

    url
        The URL to the data source API.

    user
        Optional - user to authenticate with the data source.

    password
        Optional - password to authenticate with the data source.

    database
        Optional - database to use with the data source.

    basicAuth
        Optional - set to True to use HTTP basic auth to authenticate with the
        data source.

    basicAuthUser
        Optional - HTTP basic auth username.

    basicAuthPassword
        Optional - HTTP basic auth password.

    jsonData
        Optional - additional json data to post (eg. "timeInterval").

    isDefault
        Optional - set data source as default.

    withCredentials
        Optional - Whether credentials such as cookies or auth headers should
        be sent with cross-site requests.

    typeLogoUrl
        Optional - Logo to use for this datasource.

    orgname
        Name of the organization in which the data source should be created.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.create_datasource

    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.post(
        "{}/api/datasources".format(profile["grafana_url"]),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def update_datasource(datasourceid, orgname=None, profile="grafana", **kwargs):
    """
    Update a datasource.

    datasourceid
        Id of the datasource.

    name
        Name of the data source.

    type
        Type of the datasource ('graphite', 'influxdb' etc.).

    access
        Use proxy or direct.

    url
        The URL to the data source API.

    user
        Optional - user to authenticate with the data source.

    password
        Optional - password to authenticate with the data source.

    database
        Optional - database to use with the data source.

    basicAuth
        Optional - set to True to use HTTP basic auth to authenticate with the
        data source.

    basicAuthUser
        Optional - HTTP basic auth username.

    basicAuthPassword
        Optional - HTTP basic auth password.

    jsonData
        Optional - additional json data to post (eg. "timeInterval").

    isDefault
        Optional - set data source as default.

    withCredentials
        Optional - Whether credentials such as cookies or auth headers should
        be sent with cross-site requests.

    typeLogoUrl
        Optional - Logo to use for this datasource.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.update_datasource <datasourceid>

    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    response = requests.put(
        "{}/api/datasources/{}".format(profile["grafana_url"], datasourceid),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    # temporary fix for https://github.com/grafana/grafana/issues/6869
    # return response.json()
    return {}


def delete_datasource(datasourceid, orgname=None, profile="grafana"):
    """
    Delete a datasource.

    datasourceid
        Id of the datasource.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.delete_datasource <datasource_id>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    response = requests.delete(
        "{}/api/datasources/{}".format(profile["grafana_url"], datasourceid),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def get_dashboard(slug, orgname=None, profile="grafana"):
    """
    Get a dashboard.

    slug
        Slug (name) of the dashboard.

    orgname
        Name of the organization.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.get_dashboard <slug>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.get(
        "{}/api/dashboards/db/{}".format(profile["grafana_url"], slug),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    data = response.json()
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        response.raise_for_status()
    return data.get("dashboard")


def delete_dashboard(slug, orgname=None, profile="grafana"):
    """
    Delete a dashboard.

    slug
        Slug (name) of the dashboard.

    orgname
        Name of the organization.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.delete_dashboard <slug>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.delete(
        "{}/api/dashboards/db/{}".format(profile["grafana_url"], slug),
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()


def create_update_dashboard(orgname=None, profile="grafana", **kwargs):
    """
    Create or update a dashboard.

    dashboard
        A dict that defines the dashboard to create/update.

    overwrite
        Whether the dashboard should be overwritten if already existing.

    orgname
        Name of the organization.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana4.create_update_dashboard dashboard=<dashboard> overwrite=True orgname=<orgname>
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)
    if orgname:
        switch_org(orgname, profile)
    response = requests.post(
        "{}/api/dashboards/db".format(profile.get("grafana_url")),
        json=kwargs,
        auth=_get_auth(profile),
        headers=_get_headers(profile),
        timeout=profile.get("grafana_timeout", 3),
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return response.json()
