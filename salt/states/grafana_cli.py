"""
Manage Grafana using grafana-cli.
"""


def __virtual__():
    """
    Only load if grafana_cli is available.
    """
    if "grafana_cli.plugins_ls" not in __salt__:
        return (False, "grafana_cli module could not be loaded")
    else:
        return True


def plugin_installed(
    name, version=None, plugins=None, plugins_dir=None, repo=None, user=None
):
    """
    Ensure that a plugin is installed, and that it is in the correct version (if specified).

    :param str name:
        The ID of the plugin to be installed. This parameter is ignored if ``plugins`` is used.

    :param str version:
        Install a specific version of a plugin. This option is ignored if ``plugins`` is used.

        Example:

        ... code-block:: yaml

            myplugin:
              grafana_cli.plugin_installed:
                - version: 2.2.0

    :param list plugins:
        A list of plugins to install. Version numbers can be specified.
        All plugins listed under ``plugins`` will be installed via a single command.

        Example:

        ... code-block:: yaml

            myplugins:
              grafana-cli.plugin_installed:
                - plugins:
                  - foo
                  - bar: 1.3.0
                  - baz

    :param str plugins_dir:
        Overrides the path to where your local Grafana instance stores plugins.

    :param str repo:
        Allows you to download and install or update plugins from a repository other than the
        default Grafana repo.

    :param str user:
        User name under which to run the grafana-cli command. By default, the command is run by the
        user under which the minion is running.
    """
    if isinstance(plugins, list) and len(plugins) == 0:
        return {
            "name": name,
            "result": True,
            "changes": {},
            "comment": "No plugins to install provided",
        }

    if plugins is None:
        plugins = [{"name": name, "version": version}]

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    changes = {}
    messages = []
    newly_installed = []
    already_installed = []

    for plugin in plugins:
        if isinstance(plugin, str):
            plugin = {"name": plugin, "version": None}

        result = __salt__["grafana_cli.plugins_install_check"](
            plugin["name"], plugins_dir=plugins_dir, repo=repo, user=user, version=plugin["version"]
        )

        if result["retcode"] != 0:
            ret["result"] = False
            messages.append(result["stdout"])
            break

        if not result["to_install"]:
            already_installed.append(plugin["name"])
            continue

        changes[plugin["name"]] = "{0} -> {1}".format(result["old_version"], result["new_version"])

        if __opts__["test"]:
            ret["result"] = None
            newly_installed.append(plugin["name"])
            continue

        result = __salt__["grafana_cli.plugins_install"](
            plugin["name"], plugins_dir=plugins_dir, repo=repo, user=user, version=plugin["version"]
        )

        if result["retcode"] != 0:
            ret["result"] = False
            messages.append(result["stdout"])
            break

        result = __salt__["grafana_cli.plugins_install_check"](
            plugin["name"], plugins_dir=plugins_dir, repo=repo, user=user, version=plugin["version"]
        )

        if result["retcode"] != 0:
            ret["result"] = False
            messages.append(result["stdout"])
            break

        if not result["to_install"]:
            newly_installed.append(plugin["name"])
        else:
            ret["result"] = False
            messages.append("{0} failed to install".format(plugin["name"]))
            break

    ret["changes"] = changes

    if len(newly_installed) > 0:
        newly_installed.sort()

        if __opts__["test"]:
            ret["comment"] += "The following plugins would be installed:\n"
        else:
            ret["comment"] += "The following plugins have been installed:\n"

        for x in newly_installed:
            ret["comment"] += "  - {0}\n".format(x)

    if len(already_installed) > 0:
        already_installed.sort()

        ret["comment"] += "The following plugins are already installed:\n"

        for x in already_installed:
            ret["comment"] += "  - {0}\n".format(x)

    if len(messages) > 0:
        ret["comment"] += "Messages:\n"
        ret["comment"] += "\n".join(messages)

    return ret


def plugin_removed(name, plugins=None, plugins_dir=None, user=None):
    """
    Verify that a plugin is not installed, calling grafana_cli.plugins_remove if necessary.

    :param str name:
        The ID of the plugin to be removed. This parameter is ignored if ``plugins`` is used.

    :param list plugins:
        A list of plugins to remove.
        All plugins listed under ``plugins`` will be removed via a single command.

        Example:

        ... code-block:: yaml

            myplugins:
              grafana-cli.plugin_removed:
                - plugins:
                  - foo
                  - bar
                  - baz

    :param str plugins_dir:
        Overrides the path to where your local Grafana instance stores plugins.

    :param str user:
        User name under which to run the grafana-cli command. By default, the command is run by the
        user under which the minion is running.
    """
    if isinstance(plugins, list) and len(plugins) == 0:
        return {
            "name": name,
            "result": True,
            "changes": {},
            "comment": "No plugins to remove provided",
        }

    if plugins is None:
        plugins = [name]

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    changes = {}
    messages = []
    newly_removed = []
    already_removed = []

    for plugin in plugins:
        result = __salt__["grafana_cli.plugins_get_status"](
            plugin, plugins_dir=plugins_dir, user=user
        )

        if result["retcode"] != 0:
            ret["result"] = False
            messages.append(result["stdout"])
            break

        if not result["installed"]:
            already_removed.append(plugin)
            continue

        changes[plugin] = "{0} -> None".format(result["version"])

        if __opts__["test"]:
            ret["result"] = None
            newly_removed.append(plugin)
            continue

        result = __salt__["grafana_cli.plugins_remove"](plugin, plugins_dir=plugins_dir, user=user)

        if result["retcode"] != 0:
            ret["result"] = False
            messages.append(result["stdout"])
            break

        result = __salt__["grafana_cli.plugins_get_status"](
            plugin, plugins_dir=plugins_dir, user=user
        )

        if result["retcode"] != 0:
            ret["result"] = False
            messages.append(result["stdout"])
            break

        if not result["installed"]:
            newly_removed.append(plugin)
        else:
            ret["result"] = False
            messages.append("{0} failed to remove".format(plugin))
            break

    ret["changes"] = changes

    if len(newly_removed) > 0:
        newly_removed.sort()

        if __opts__["test"]:
            ret["comment"] += "The following plugins would be removed:\n"
        else:
            ret["comment"] += "The following plugins have been removed:\n"

        for x in newly_removed:
            ret["comment"] += "  - {0}\n".format(x)

    if len(already_removed) > 0:
        already_removed.sort()

        ret["comment"] += "The following plugins are already removed:\n"

        for x in already_removed:
            ret["comment"] += "  - {0}\n".format(x)

    if len(messages) > 0:
        ret["comment"] += "Messages:\n"
        ret["comment"] += "\n".join(messages)

    return ret
