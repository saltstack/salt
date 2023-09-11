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
