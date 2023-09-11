"""
Interface with `grafana-cli`.
"""

import logging

import salt
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if grafana-cli exists on the system.
    """
    if salt.utils.path.which("grafana-cli") is None:
        return (
            False,
            "The grafana_cli execution module cannot be loaded: grafana-cli unavailable.",
        )
    else:
        return True


def _prepare_cmd(binary="grafana-cli", command=None, options=None, arguments=None):
    """
    Prepare a command to be run by Salt's cmd.run.

    :param str binary:
    :param str command:
    :param dict options:
    :param tuple arguments:
    """
    cmd = (binary,)

    if options is None:
        options = {}

    for option, value in options.items():
        if option == "plugins_dir" and value is not None:
            cmd += ("--pluginsDir", value)
        if option == "repo" and value is not None:
            cmd += ("--repo", value)

    if command is not None:
        cmd += (command,)

    if arguments is not None:
        cmd += arguments

    return cmd


def _run_cmd(command=None, options=None, arguments=None, user=None):
    """
    Run the grafana-cli command.

    :param str command:
    :param dict options:
    :param tuple arguments:
    :param str user:
    """
    cmd = _prepare_cmd(command=command, options=options, arguments=arguments)
    cmd_string = " ".join(cmd)

    try:
        result = __salt__["cmd.run_all"](cmd=cmd, runas=user)
        result.update({"cmd": cmd_string})
    except CommandExecutionError as err:
        result = {"retcode": 1, "stdout": err, "cmd": cmd_string}
        log.error(result)

    return result


def plugins_ls(plugins_dir=None, user=None):
    """
    Interface with `grafana-cli plugins ls`.

    :param str plugins_dir:
        Overrides the path to where your local Grafana instance stores plugins.

    :param str user:
        User name under which to run the grafana-cli command. By default, the command is run by the
        user under which the minion is running.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana_cli.plugins_ls
    """
    options = {"plugins_dir": plugins_dir}
    arguments = ("ls",)

    return _run_cmd(command="plugins", options=options, arguments=arguments, user=user)


def plugins_list_versions(name, repo=None, user=None):
    """
    Interface with `grafana-cli plugins list-versions`.

    :param str name:
        The ID of the plugin.

    :param str repo:
        Allows you to download and install or update plugins from a repository other than the
        default Grafana repo.

    :param str user:
        User name under which to run the grafana-cli command. By default, the command is run by the
        user under which the minion is running.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana_cli.plugins_list_versions foo
    """
    options = {"repo": repo}
    arguments = ("list-versions", name)

    return _run_cmd(command="plugins", options=options, arguments=arguments, user=user)


def plugins_get_latest_version(name, repo=None, user=None):
    """
    Get latest version of a plugin.

    :param str name:
        The ID of the plugin.

    :param str repo:
        Allows you to download and install or update plugins from a repository other than the
        default Grafana repo.

    :param str user:
        User name under which to run the grafana-cli command. By default, the command is run by the
        user under which the minion is running.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana_cli.plugins_get_latest_version foo
    """
    result = plugins_list_versions(name, repo=repo, user=user)

    if result["retcode"] != 0:
        return result

    latest_version = result["stdout"].split("\n")[0]

    return {"retcode": 0, "version": latest_version}


def plugins_get_status(name, plugins_dir=None, user=None):
    """
    Get the status of the plugin.

    :param str name:
        The ID of the plugin.

    :param str plugins_dir:
        Overrides the path to where your local Grafana instance stores plugins.

    :param str user:
        User name under which to run the grafana-cli command. By default, the command is run by the
        user under which the minion is running.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana_cli.plugins_get_status foo
    """
    result = plugins_ls(plugins_dir=plugins_dir, user=user)

    if result["retcode"] != 0:
        return result

    plugins = result["stdout"].split("\n")[1:]

    for plugin in plugins:
        plugin_name = plugin.split("@")[0].strip()
        plugin_version = plugin.split("@")[1].strip()

        if name == plugin_name:
            return {"retcode": 0, "installed": True, "version": plugin_version}

    return {"retcode": 0, "installed": False, "version": None}


def plugins_install_check(name, version=None, plugins_dir=None, repo=None, user=None):
    """
    Check if a plugin would be installed.

    :param str name:
        The ID of the plugin.

    :param str version:
        The version of the plugin.

    :param str plugins_dir:
        Overrides the path to where your local Grafana instance stores plugins.

    :param str repo:
        Allows you to download and install or update plugins from a repository other than the
        default Grafana repo.

    :param str user:
        User name under which to run the grafana-cli command. By default, the command is run by the
        user under which the minion is running.


    CLI Example:

    .. code-block:: bash

        salt '*' grafana_cli.plugins_install_check foo
    """
    get_status_result = plugins_get_status(name, plugins_dir=plugins_dir, user=user)

    if get_status_result["retcode"] != 0:
        return get_status_result

    latest_version_result = plugins_get_latest_version(name, repo=repo, user=user)

    if latest_version_result["retcode"] != 0:
        return latest_version_result

    is_installed = get_status_result["installed"]
    installed_version = get_status_result["version"]
    latest_version = latest_version_result["version"]

    ret = {"retcode": 0, "to_install": False, "old_version": None, "new_version": None}

    if is_installed:
        ret["old_version"] = installed_version

        if version is None:
            if installed_version != latest_version:
                ret["to_install"] = True
                ret["new_version"] = latest_version
        elif installed_version != version:
            ret["to_install"] = True
            ret["new_version"] = version
    else:
        ret["to_install"] = True

        if version is None:
            ret["new_version"] = latest_version
        else:
            ret["new_version"] = version

    return ret


def plugins_install(name, version=None, plugins_dir=None, repo=None, user=None):
    """
    Interface with `grafana-cli plugins install`.

    :param str name:
        The ID of the plugin.

    :param str version:
        The version of the plugin.

    :param str plugins_dir:
        Overrides the path to where your local Grafana instance stores plugins.

    :param str repo:
        Allows you to download and install or update plugins from a repository other than the
        default Grafana repo.

    :param str user:
        User name under which to run the grafana-cli command. By default, the command is run by the
        user under which the minion is running.

    CLI Example:

    .. code-block:: bash

        salt '*' grafana_cli.plugins_install foo version="2.2.0"
    """
    check_result = plugins_install_check(
        name, plugins_dir=plugins_dir, repo=repo, version=version, user=user
    )

    if check_result["retcode"] != 0:
        return check_result

    if not check_result["to_install"]:
        return {"retcode": 0, "result": False, "old": check_result["old_version"], "new": None}

    options = {
        "plugins_dir": plugins_dir,
        "repo": repo,
    }
    arguments = ("install", name, check_result["new_version"])

    result = _run_cmd(command="plugins", options=options, arguments=arguments, user=user)

    if result["retcode"] != 0:
        return result

    return {
        "retcode": 0,
        "result": True,
        "old": check_result["old_version"],
        "new": check_result["new_version"],
    }
