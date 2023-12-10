"""
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
"""

import salt.utils.dictupdate as dictupdate
from salt.utils.dictdiffer import deep_diff


def __virtual__():
    """Only load if grafana4 module is available"""
    if "grafana4.get_user" in __salt__:
        return True
    return (False, "grafana4 module could not be loaded")


def present(
    name, password, email, is_admin=False, fullname=None, theme=None, profile="grafana"
):
    """
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
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)

    ret = {"name": name, "result": None, "comment": None, "changes": {}}
    user = __salt__["grafana4.get_user"](name, profile)
    create = not user

    if create:
        if __opts__["test"]:
            ret["comment"] = "User {} will be created".format(name)
            return ret
        __salt__["grafana4.create_user"](
            login=name, password=password, email=email, name=fullname, profile=profile
        )
        user = __salt__["grafana4.get_user"](name, profile)
        ret["changes"]["new"] = user

    user_data = __salt__["grafana4.get_user_data"](user["id"], profile=profile)
    data = _get_json_data(
        login=name, email=email, name=fullname, theme=theme, defaults=user_data
    )
    if data != _get_json_data(
        login=None, email=None, name=None, theme=None, defaults=user_data
    ):
        if __opts__["test"]:
            ret["comment"] = "User {} will be updated".format(name)
            return ret
        __salt__["grafana4.update_user"](user["id"], profile=profile, **data)
        dictupdate.update(
            ret["changes"],
            deep_diff(user_data, __salt__["grafana4.get_user_data"](user["id"])),
        )

    if user["isAdmin"] != is_admin:
        if __opts__["test"]:
            ret["comment"] = "User {} isAdmin status will be updated".format(name)
            return ret
        __salt__["grafana4.update_user_permissions"](
            user["id"], isGrafanaAdmin=is_admin, profile=profile
        )
        dictupdate.update(
            ret["changes"],
            deep_diff(user, __salt__["grafana4.get_user"](name, profile)),
        )

    ret["result"] = True
    if create:
        ret["changes"] = ret["changes"]["new"]
        ret["comment"] = "New user {} added".format(name)
    else:
        if ret["changes"]:
            ret["comment"] = "User {} updated".format(name)
        else:
            ret["changes"] = {}
            ret["comment"] = "User {} already up-to-date".format(name)

    return ret


def absent(name, profile="grafana"):
    """
    Ensure that a user is present.

    name
        Name of the user to remove.

    profile
        Configuration profile used to connect to the Grafana instance.
        Default is 'grafana'.
    """
    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)

    ret = {"name": name, "result": None, "comment": None, "changes": {}}
    user = __salt__["grafana4.get_user"](name, profile)

    if user:
        if __opts__["test"]:
            ret["comment"] = "User {} will be deleted".format(name)
            return ret
        orgs = __salt__["grafana4.get_user_orgs"](user["id"], profile=profile)
        __salt__["grafana4.delete_user"](user["id"], profile=profile)
        for org in orgs:
            if org["name"] == user["email"]:
                # Remove entire Org in the case where auto_assign_org=false:
                # When set to false, new users will automatically cause a new
                # organization to be created for that new user (the org name
                # will be the email)
                __salt__["grafana4.delete_org"](org["orgId"], profile=profile)
            else:
                __salt__["grafana4.delete_user_org"](
                    user["id"], org["orgId"], profile=profile
                )
    else:
        ret["result"] = True
        ret["comment"] = "User {} already absent".format(name)
        return ret

    ret["result"] = True
    ret["changes"][name] = "Absent"
    ret["comment"] = "User {} was deleted".format(name)
    return ret


def _get_json_data(defaults=None, **kwargs):
    if defaults is None:
        defaults = {}
    for k, v in kwargs.items():
        if v is None:
            kwargs[k] = defaults.get(k)
    return kwargs
