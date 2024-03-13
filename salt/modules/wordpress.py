"""
This module is used to manage Wordpress installations

:depends: wp binary from http://wp-cli.org/
"""

# Import Python Modules

import collections

# Import Salt Modules
import salt.utils.path

Plugin = collections.namedtuple("Plugin", "name status update versino")


def __virtual__():
    if salt.utils.path.which("wp"):
        return True
    return (False, "Missing dependency: wp")


def _get_plugins(stuff):
    return Plugin(stuff)


def list_plugins(path, user):
    """
    List plugins in an installed wordpress path

    path
        path to wordpress install location

    user
        user to run the command as

    CLI Example:

    .. code-block:: bash

        salt '*' wordpress.list_plugins /var/www/html apache
    """
    ret = []
    resp = __salt__["cmd.shell"](f"wp --path={path} plugin list", runas=user)
    for line in resp.split("\n")[1:]:
        ret.append(line.split("\t"))
    return [plugin.__dict__ for plugin in map(_get_plugins, ret)]


def show_plugin(name, path, user):
    """
    Show a plugin in a wordpress install and check if it is installed

    name
        Wordpress plugin name

    path
        path to wordpress install location

    user
        user to run the command as

    CLI Example:

    .. code-block:: bash

        salt '*' wordpress.show_plugin HyperDB /var/www/html apache
    """
    ret = {"name": name}
    resp = __salt__["cmd.shell"](
        f"wp --path={path} plugin status {name}", runas=user
    ).split("\n")
    for line in resp:
        if "Status" in line:
            ret["status"] = line.split(" ")[-1].lower()
        elif "Version" in line:
            ret["version"] = line.split(" ")[-1].lower()
    return ret


def activate(name, path, user):
    """
    Activate a wordpress plugin

    name
        Wordpress plugin name

    path
        path to wordpress install location

    user
        user to run the command as

    CLI Example:

    .. code-block:: bash

        salt '*' wordpress.activate HyperDB /var/www/html apache
    """
    check = show_plugin(name, path, user)
    if check["status"] == "active":
        # already active
        return None
    resp = __salt__["cmd.shell"](f"wp --path={path} plugin activate {name}", runas=user)
    if "Success" in resp:
        return True
    elif show_plugin(name, path, user)["status"] == "active":
        return True
    return False


def deactivate(name, path, user):
    """
    Deactivate a wordpress plugin

    name
        Wordpress plugin name

    path
        path to wordpress install location

    user
        user to run the command as

    CLI Example:

    .. code-block:: bash

        salt '*' wordpress.deactivate HyperDB /var/www/html apache
    """
    check = show_plugin(name, path, user)
    if check["status"] == "inactive":
        # already inactive
        return None
    resp = __salt__["cmd.shell"](
        f"wp --path={path} plugin deactivate {name}", runas=user
    )
    if "Success" in resp:
        return True
    elif show_plugin(name, path, user)["status"] == "inactive":
        return True
    return False


def is_installed(path, user=None):
    """
    Check if wordpress is installed and setup

    path
        path to wordpress install location

    user
        user to run the command as

    CLI Example:

    .. code-block:: bash

        salt '*' wordpress.is_installed /var/www/html apache
    """
    retcode = __salt__["cmd.retcode"](f"wp --path={path} core is-installed", runas=user)
    if retcode == 0:
        return True
    return False


def install(path, user, admin_user, admin_password, admin_email, title, url):
    """
    Run the initial setup functions for a wordpress install

    path
        path to wordpress install location

    user
        user to run the command as

    admin_user
        Username for the Administrative user for the wordpress install

    admin_password
        Initial Password for the Administrative user for the wordpress install

    admin_email
        Email for the Administrative user for the wordpress install

    title
        Title of the wordpress website for the wordpress install

    url
        Url for the wordpress install

    CLI Example:

    .. code-block:: bash

        salt '*' wordpress.install /var/www/html apache dwallace password123 \
            dwallace@example.com "Daniel's Awesome Blog" https://blog.dwallace.com
    """
    retcode = __salt__["cmd.retcode"](
        'wp --path={} core install --title="{}" --admin_user={} '
        "--admin_password='{}' --admin_email={} --url={}".format(
            path, title, admin_user, admin_password, admin_email, url
        ),
        runas=user,
    )

    if retcode == 0:
        return True
    return False
