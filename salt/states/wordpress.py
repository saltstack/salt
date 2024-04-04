"""
This state module is used to manage Wordpress installations

:depends: wp binary from http://wp-cli.org/
"""


def __virtual__():
    if "wordpress.show_plugin" in __salt__:
        return True
    return (False, "wordpress module could not be loaded")


def installed(name, user, admin_user, admin_password, admin_email, title, url):
    """
    Run the initial setup of wordpress

    name
        path to the wordpress installation

    user
        user that owns the files for the wordpress installation

    admin_user
        username for wordpress website administrator user

    admin_password
        password for wordpress website administrator user

    admin_email
        email for wordpress website administrator user

    title
        title for the wordpress website

    url
        url for the wordpress website

    .. code-block:: yaml

        /var/www/html:
          wordpress.installed:
            - title: Daniel's Awesome Blog
            - user: apache
            - admin_user: dwallace
            - admin_email: dwallace@example.com
            - admin_password: password123
            - url: https://blog.dwallace.com
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": False}

    check = __salt__["wordpress.is_installed"](name, user)

    if check:
        ret["result"] = True
        ret["comment"] = f"Wordpress is already installed: {name}"
        return ret
    elif __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Wordpress will be installed: {name}"
        return ret

    resp = __salt__["wordpress.install"](
        name, user, admin_user, admin_password, admin_email, title, url
    )
    if resp:
        ret["result"] = True
        ret["comment"] = f"Wordpress Installed: {name}"
        ret["changes"] = {"new": resp}
    else:
        ret["comment"] = f"Failed to install wordpress: {name}"

    return ret


def activated(name, path, user):
    """
    Activate wordpress plugins

    name
        name of plugin to activate

    path
        path to wordpress installation

    user
        user who should own the files in the wordpress installation

    .. code-block:: yaml

        HyperDB:
          wordpress.activated:
            - path: /var/www/html
            - user: apache
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": False}

    check = __salt__["wordpress.show_plugin"](name, path, user)

    if check["status"] == "active":
        ret["result"] = True
        ret["comment"] = f"Plugin already activated: {name}"
        return ret
    elif __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Plugin will be activated: {name}"
        return ret

    resp = __salt__["wordpress.activate"](name, path, user)
    if resp is True:
        ret["result"] = True
        ret["comment"] = f"Plugin activated: {name}"
        ret["changes"] = {
            "old": check,
            "new": __salt__["wordpress.show_plugin"](name, path, user),
        }
    elif resp is None:
        ret["result"] = True
        ret["comment"] = f"Plugin already activated: {name}"
        ret["changes"] = {
            "old": check,
            "new": __salt__["wordpress.show_plugin"](name, path, user),
        }
    else:
        ret["comment"] = f"Plugin failed to activate: {name}"

    return ret


def deactivated(name, path, user):
    """
    Deactivate wordpress plugins

    name
        name of plugin to deactivate

    path
        path to wordpress installation

    user
        user who should own the files in the wordpress installation

    .. code-block:: yaml

        HyperDB:
          wordpress.deactivated:
            - path: /var/www/html
            - user: apache
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": False}

    check = __salt__["wordpress.show_plugin"](name, path, user)

    if check["status"] == "inactive":
        ret["result"] = True
        ret["comment"] = f"Plugin already deactivated: {name}"
        return ret
    elif __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Plugin will be deactivated: {name}"
        return ret

    resp = __salt__["wordpress.deactivate"](name, path, user)
    if resp is True:
        ret["result"] = True
        ret["comment"] = f"Plugin deactivated: {name}"
        ret["changes"] = {
            "old": check,
            "new": __salt__["wordpress.show_plugin"](name, path, user),
        }
    elif resp is None:
        ret["result"] = True
        ret["comment"] = f"Plugin already deactivated: {name}"
        ret["changes"] = {
            "old": check,
            "new": __salt__["wordpress.show_plugin"](name, path, user),
        }
    else:
        ret["comment"] = f"Plugin failed to deactivate: {name}"

    return ret
