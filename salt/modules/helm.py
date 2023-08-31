"""
Interface with Helm

:depends: pyhelm_ Python package

.. _pyhelm: https://pypi.org/project/pyhelm/

.. note::
    This module use the helm-cli. The helm-cli binary have to be present in your Salt-Minion path.

Helm-CLI vs Salt-Modules
------------------------

This module is a wrapper of the helm binary.
All helm v3.0 command are implemented.

To install a chart with the helm-cli:

.. code-block:: bash

    helm install grafana stable/grafana --wait --values /path/to/values.yaml


To install a chart with the Salt-Module:

.. code-block:: bash

    salt '*' helm.install grafana stable/grafana values='/path/to/values.yaml' flags="['wait']"


Detailed Function Documentation
-------------------------------
"""


import copy
import logging
import re

from salt.exceptions import CommandExecutionError
from salt.serializers import json

log = logging.getLogger(__name__)

# Don't shadow built-in's.
__func_alias__ = {
    "help_": "help",
    "list_": "list",
}


def _prepare_cmd(binary="helm", commands=None, flags=None, kvflags=None):
    """

    :param binary:
    :param commands:
    :param flags:
    :param kvflags:
    :return:
    """
    if commands is None:
        commands = []
    if flags is None:
        flags = []
    else:
        flags = copy.deepcopy(flags)
    if kvflags is None:
        kvflags = {}
    else:
        kvflags = copy.deepcopy(kvflags)

    cmd = (binary,)

    for command in commands:
        cmd += (command,)

    for arg in flags:
        if not re.search(r"^--.*", arg):
            arg = "--" + arg
        cmd += (arg,)

    for key, val in kvflags.items():
        if not re.search(r"^--.*", key):
            key = "--" + key
        if key == "--set" and isinstance(val, list):
            for set_val in val:
                cmd += (
                    key,
                    set_val,
                )
        else:
            cmd += (
                key,
                val,
            )

    return cmd


def _exec_cmd(commands=None, flags=None, kvflags=None):
    """

    :param commands:
    :param flags:
    :param kvflags:
    :return:
    """
    cmd = _prepare_cmd(commands=commands, flags=flags, kvflags=kvflags)
    cmd_string = " ".join(cmd)

    try:
        result = __salt__["cmd.run_all"](cmd=cmd)
        result.update({"cmd": cmd_string})
    except CommandExecutionError as err:
        result = {"retcode": -1, "stdout": "", "stderr": err, "cmd": cmd_string}
        log.error(result)

    return result


def _exec_true_return(commands=None, flags=None, kvflags=None):
    """

    :param commands:
    :param flags:
    :param kvflags:
    :return:
    """
    cmd_result = _exec_cmd(commands=commands, flags=flags, kvflags=kvflags)
    if cmd_result.get("retcode", -1) == 0:
        result = True
    else:
        result = cmd_result.get("stderr", "")
    return result


def _exec_string_return(commands=None, flags=None, kvflags=None):
    """

    :param commands:
    :param flags:
    :param kvflags:
    :return:
    """
    cmd_result = _exec_cmd(commands=commands, flags=flags, kvflags=kvflags)
    if cmd_result.get("retcode", -1) == 0:
        result = cmd_result.get("stdout", "")
    else:
        result = cmd_result.get("stderr", "")
    return result


def _exec_dict_return(commands=None, flags=None, kvflags=None):
    """

    :param commands:
    :param flags:
    :param kvflags:
    :return:
    """
    if kvflags is None:
        kvflags = {}
    if not ("output" in kvflags.keys() or "--output" in kvflags.keys()):
        kvflags.update({"output": "json"})
    cmd_result = _exec_cmd(commands=commands, flags=flags, kvflags=kvflags)
    if cmd_result.get("retcode", -1) == 0:
        if kvflags.get("output") == "json" or kvflags.get("--output") == "json":
            result = json.deserialize(cmd_result.get("stdout", ""))
        else:
            result = cmd_result.get("stdout", "")
    else:
        result = cmd_result.get("stderr", "")
    return result


def completion(shell, flags=None, kvflags=None):
    """
    Generate auto-completions script for Helm for the specified shell (bash or zsh).
    Return the shell auto-completion content.

    shell
        (string) One of ['bash', 'zsh'].

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.completion bash

    """
    return _exec_string_return(
        commands=["completion", shell], flags=flags, kvflags=kvflags
    )


def create(name, flags=None, kvflags=None):
    """
    Creates a chart directory along with the common files and directories used in a chart.
    Return True if succeed, else the error message.

    name
        (string) The chart name to create.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.create NAME

    """
    return _exec_true_return(commands=["create", name], flags=flags, kvflags=kvflags)


def dependency_build(chart, flags=None, kvflags=None):
    """
    Build out the charts/ directory from the Chart.lock file.
    Return True if succeed, else the error message.

    chart
        (string) The chart name to build dependency.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.dependency_build CHART

    """
    return _exec_true_return(
        commands=["dependency", "build", chart], flags=flags, kvflags=kvflags
    )


def dependency_list(chart, flags=None, kvflags=None):
    """
    List all of the dependencies declared in a chart.
    Return chart dependencies if succeed, else the error message.

    chart
        (string) The chart name to list dependency.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.dependency_list CHART

    """
    return _exec_string_return(
        commands=["dependency", "list", chart], flags=flags, kvflags=kvflags
    )


def dependency_update(chart, flags=None, kvflags=None):
    """
    Update the on-disk dependencies to mirror Chart.yaml.
    Return True if succeed, else the error message.

    chart
        (string) The chart name to update dependency.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.dependency_update CHART

    """
    return _exec_true_return(
        commands=["dependency", "update", chart], flags=flags, kvflags=kvflags
    )


def env(flags=None, kvflags=None):
    """
    Prints out all the environment information in use by Helm.
    Return Helm environments variables if succeed, else the error message.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.env

    """
    return _exec_string_return(commands=["env"], flags=flags, kvflags=kvflags)


def get_all(release, flags=None, kvflags=None):
    """
    Prints a human readable collection of information about the notes, hooks, supplied values, and generated manifest file of the given release.
    Return release information if succeed, else the error message.

    release
        (string) Release name to get information from.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.get_all RELEASE

    """
    return _exec_string_return(
        commands=["get", "all", release], flags=flags, kvflags=kvflags
    )


def get_hooks(release, flags=None, kvflags=None):
    """
    Prints a human readable collection of information about the hooks of the given release.
    Return release hooks information if succeed, else the error message.

    release
        (string) Release name to get hooks information from.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.get_hooks RELEASE

    """
    return _exec_string_return(
        commands=["get", "hooks", release], flags=flags, kvflags=kvflags
    )


def get_manifest(release, flags=None, kvflags=None):
    """
    Prints a human readable collection of information about the manifest of the given release.
    Return release manifest information if succeed, else the error message.

    release
        (string) Release name to get manifest information from.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.get_manifest RELEASE

    """
    return _exec_string_return(
        commands=["get", "manifest", release], flags=flags, kvflags=kvflags
    )


def get_notes(release, flags=None, kvflags=None):
    """
    Prints a human readable collection of information about the notes of the given release.
    Return release notes information if succeed, else the error message.

    release
        (string) Release name to get notes information from.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.get_notes RELEASE

    """
    return _exec_string_return(
        commands=["get", "notes", release], flags=flags, kvflags=kvflags
    )


def get_values(release, flags=None, kvflags=None):
    """
    Prints a human readable collection of information about the values of the given release.
    Return release values information if succeed, else the error message.

    release
        (string) Release name to get values information from.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.get_values RELEASE

        # In YAML format
        salt '*' helm.get_values RELEASE kvflags="{'output': 'yaml'}"

    """
    return _exec_dict_return(
        commands=["get", "values", release], flags=flags, kvflags=kvflags
    )


def help_(command, flags=None, kvflags=None):
    """
    Provides help for any command in the application.
    Return the full help if succeed, else the error message.

    command
        (string) Command to get help. ex: 'get'

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.help COMMAND

    """
    return _exec_string_return(commands=["help", command], flags=flags, kvflags=kvflags)


def history(release, flags=None, kvflags=None):
    """
    Prints historical revisions for a given release.
    Return release historic if succeed, else the error message.

    release
        (string) Release name to get history from.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.history RELEASE

        # In YAML format
        salt '*' helm.history RELEASE kvflags="{'output': 'yaml'}"

    """
    return _exec_dict_return(
        commands=["history", release], flags=flags, kvflags=kvflags
    )


def install(
    release,
    chart,
    values=None,
    version=None,
    namespace=None,
    set=None,
    flags=None,
    kvflags=None,
):
    """
    Installs a chart archive.
    Return True if succeed, else the error message.

    release
        (string) Release name to get values information from.

    chart
        (string) Chart name to install.

    values
        (string) Absolute path to the values.yaml file.

    version
        (string) The exact chart version to install. If this is not specified, the latest version is installed.

    namespace
        (string) The namespace scope for this request.

    set
        (string or list) Set a values on the command line.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.install RELEASE CHART

        # With values file.
        salt '*' helm.install RELEASE CHART values='/path/to/values.yaml'

    """
    if values:
        if kvflags:
            kvflags.update({"values": values})
        else:
            kvflags = {"values": values}
    if version:
        if kvflags:
            kvflags.update({"version": version})
        else:
            kvflags = {"version": version}
    if namespace:
        if kvflags:
            kvflags.update({"namespace": namespace})
        else:
            kvflags = {"namespace": namespace}
    if set:
        if kvflags:
            kvflags.update({"set": set})
        else:
            kvflags = {"set": set}
    return _exec_true_return(
        commands=["install", release, chart], flags=flags, kvflags=kvflags
    )


def lint(path, values=None, namespace=None, set=None, flags=None, kvflags=None):
    """
    Takes a path to a chart and runs a series of tests to verify that the chart is well-formed.
    Return True if succeed, else the error message.

    path
        (string) The path to the chart to lint.

    values
        (string) Absolute path to the values.yaml file.

    namespace
        (string) The namespace scope for this request.

    set
        (string or list) Set a values on the command line.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.lint PATH

    """
    if values:
        if kvflags:
            kvflags.update({"values": values})
        else:
            kvflags = {"values": values}
    if namespace:
        if kvflags:
            kvflags.update({"namespace": namespace})
        else:
            kvflags = {"namespace": namespace}
    if set:
        if kvflags:
            kvflags.update({"set": set})
        else:
            kvflags = {"set": set}
    return _exec_true_return(commands=["lint", path], flags=flags, kvflags=kvflags)


def list_(namespace=None, flags=None, kvflags=None):
    """
    Lists all of the releases. By default, it lists only releases that are deployed or failed.
    Return the list of release if succeed, else the error message.

    namespace
        (string) The namespace scope for this request.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.list

        # In YAML format
        salt '*' helm.list kvflags="{'output': 'yaml'}"

    """
    if namespace:
        if kvflags:
            kvflags.update({"namespace": namespace})
        else:
            kvflags = {"namespace": namespace}
    return _exec_dict_return(commands=["list"], flags=flags, kvflags=kvflags)


def package(chart, flags=None, kvflags=None):
    """
    Packages a chart into a versioned chart archive file. If a path is given, this will look at that path for a chart
    (which must contain a Chart.yaml file) and then package that directory.
    Return True if succeed, else the error message.

    chart
        (string) Chart name to package. Can be an absolute path.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.package CHART

        # With destination path.
        salt '*' helm.package CHART kvflags="{'destination': '/path/to/the/package'}"

    """
    return _exec_true_return(commands=["package", chart], flags=flags, kvflags=kvflags)


def plugin_install(path, flags=None, kvflags=None):
    """
    Install a Helm plugin from a url to a VCS repo or a local path.
    Return True if succeed, else the error message.

    path
        (string) Path to the local plugin. Can be an url.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.plugin_install PATH

    """
    return _exec_true_return(
        commands=["plugin", "install", path], flags=flags, kvflags=kvflags
    )


def plugin_list(flags=None, kvflags=None):
    """
    List installed Helm plugins.
    Return the plugin list if succeed, else the error message.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.plugin_list

    """
    return _exec_string_return(
        commands=["plugin", "list"], flags=flags, kvflags=kvflags
    )


def plugin_uninstall(plugin, flags=None, kvflags=None):
    """
    Uninstall a Helm plugin.
    Return True if succeed, else the error message.

    plugin
        (string) The plugin to uninstall.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.plugin_uninstall PLUGIN

    """
    return _exec_true_return(
        commands=["plugin", "uninstall", plugin], flags=flags, kvflags=kvflags
    )


def plugin_update(plugin, flags=None, kvflags=None):
    """
    Update a Helm plugin.
    Return True if succeed, else the error message.

    plugin
        (string) The plugin to update.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.plugin_update PLUGIN

    """
    return _exec_true_return(
        commands=["plugin", "update", plugin], flags=flags, kvflags=kvflags
    )


def pull(pkg, flags=None, kvflags=None):
    """
    Retrieve a package from a package repository, and download it locally.
    Return True if succeed, else the error message.

    pkg
        (string) The package to pull. Can be url or repo/chartname.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.pull PKG

        # With destination path to write the chart.
        salt '*' helm.pull PKG kvflags="{'destination': '/path/to/the/chart'}"

    """
    return _exec_true_return(commands=["pull", pkg], flags=flags, kvflags=kvflags)


def repo_add(name, url, namespace=None, flags=None, kvflags=None):
    """
    Add a chart repository.
    Return True if succeed, else the error message.

    name
        (string) The local name of the repository to install. Have to be unique.

    url
        (string) The url to the repository.

    namespace
        (string) The namespace scope for this request.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.repo_add NAME URL

    """
    if namespace:
        if kvflags:
            kvflags.update({"namespace": namespace})
        else:
            kvflags = {"namespace": namespace}
    return _exec_true_return(
        commands=["repo", "add", name, url], flags=flags, kvflags=kvflags
    )


def repo_index(directory, namespace=None, flags=None, kvflags=None):
    """
    Read the current directory and generate an index file based on the charts found.
    Return True if succeed, else the error message.

    directory
        (string) The path to the index.

    namespace
        (string) The namespace scope for this request.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.index DIRECTORY

    """
    if namespace:
        if kvflags:
            kvflags.update({"namespace": namespace})
        else:
            kvflags = {"namespace": namespace}
    return _exec_true_return(
        commands=["repo", "index", directory], flags=flags, kvflags=kvflags
    )


def repo_list(namespace=None, flags=None, kvflags=None):
    """
    List a chart repository.
    Return the repository list if succeed, else the error message.

    namespace
        (string) The namespace scope for this request.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.repo_list

        # In YAML format
        salt '*' helm.repo_list kvflags="{'output': 'yaml'}"

    """
    if namespace:
        if kvflags:
            kvflags.update({"namespace": namespace})
        else:
            kvflags = {"namespace": namespace}
    return _exec_dict_return(commands=["repo", "list"], flags=flags, kvflags=kvflags)


def repo_remove(name, namespace=None, flags=None, kvflags=None):
    """
    Remove a chart repository.
    Return True if succeed, else the error message.

    name
        (string) The local name of the repository to remove.

    namespace
        (string) The namespace scope for this request.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.repo_remove NAME

    """
    if namespace:
        if kvflags:
            kvflags.update({"namespace": namespace})
        else:
            kvflags = {"namespace": namespace}
    return _exec_true_return(
        commands=["repo", "remove", name], flags=flags, kvflags=kvflags
    )


def repo_update(namespace=None, flags=None, kvflags=None):
    """
    Update all charts repository.
    Return True if succeed, else the error message.

    namespace
        (string) The namespace scope for this request.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.repo_update

    """
    if namespace:
        if kvflags:
            kvflags.update({"namespace": namespace})
        else:
            kvflags = {"namespace": namespace}
    return _exec_true_return(commands=["repo", "update"], flags=flags, kvflags=kvflags)


def repo_manage(
    present=None, absent=None, prune=False, namespace=None, flags=None, kvflags=None
):
    """
    Manage charts repository.
    Return the summery of all actions.

    present
        (list) List of repository to be present. It's a list of dict: [{'name': 'local_name', 'url': 'repository_url'}]

    absent
        (list) List of local name repository to be absent.

    prune
        (boolean - default: False) If True, all repository already present but not in the present list would be removed.

    namespace
        (string) The namespace scope for this request.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.repo_manage present="[{'name': 'LOCAL_NAME', 'url': 'REPO_URL'}]" absent="['LOCAL_NAME']"

    """
    if present is None:
        present = []
    else:
        present = copy.deepcopy(present)
    if absent is None:
        absent = []
    else:
        absent = copy.deepcopy(absent)
    if namespace:
        if kvflags:
            kvflags.update({"namespace": namespace})
        else:
            kvflags = {"namespace": namespace}

    repos_present = repo_list(namespace=namespace, flags=flags, kvflags=kvflags)
    if not isinstance(repos_present, list):
        repos_present = []
    result = {"present": [], "added": [], "absent": [], "removed": [], "failed": []}

    for repo in present:
        if not (
            isinstance(repo, dict) and "name" in repo.keys() and "url" in repo.keys()
        ):
            raise CommandExecutionError(
                "Parameter present have to be formatted like "
                "[{'name': '<myRepoName>', 'url': '<myRepoUrl>'}]"
            )

        already_present = False
        for (index, repo_present) in enumerate(repos_present):
            if repo.get("name") == repo_present.get("name") and repo.get(
                "url"
            ) == repo_present.get("url"):
                result["present"].append(repo)
                repos_present.pop(index)
                already_present = True
                break

        if not already_present:
            repo_add_status = repo_add(
                repo.get("name"),
                repo.get("url"),
                namespace=namespace,
                flags=flags,
                kvflags=kvflags,
            )
            if isinstance(repo_add_status, bool) and repo_add_status:
                result["added"].append(repo)
            else:
                result["failed"].append(repo)

    for repo in repos_present:
        if prune:
            absent.append(repo.get("name"))
        elif not repo.get("name") in absent:
            result["present"].append(repo)

    for name in absent:
        remove_status = repo_remove(name, namespace=namespace)
        if isinstance(remove_status, bool) and remove_status:
            result["removed"].append(name)
        else:
            result["absent"].append(name)

    return result


def rollback(release, revision, namespace=None, flags=None, kvflags=None):
    """
    Rolls back a release to a previous revision.
    To see release revision number, execute the history module.
    Return True if succeed, else the error message.

    release
        (string) The name of the release to managed.

    revision
        (string) The revision number to roll back to.

    namespace
        (string) The namespace scope for this request.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.rollback RELEASE REVISION

        # In dry-run mode.
        salt '*' helm.rollback RELEASE REVISION flags=['dry-run']

    """
    if namespace:
        if kvflags:
            kvflags.update({"namespace": namespace})
        else:
            kvflags = {"namespace": namespace}
    return _exec_true_return(
        commands=["rollback", release, revision], flags=flags, kvflags=kvflags
    )


def search_hub(keyword, flags=None, kvflags=None):
    """
    Search the Helm Hub or an instance of Monocular for Helm charts.
    Return the research result if succeed, else the error message.

    keyword
        (string) The keyword to search in the hub.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.search_hub KEYWORD

        # In YAML format
        salt '*' helm.search_hub KEYWORD kvflags="{'output': 'yaml'}"

    """
    return _exec_dict_return(
        commands=["search", "hub", keyword], flags=flags, kvflags=kvflags
    )


def search_repo(keyword, flags=None, kvflags=None):
    """
    Search reads through all of the repositories configured on the system, and looks for matches. Search of these
    repositories uses the metadata stored on the system.
    Return the research result if succeed, else the error message.

    keyword
        (string) The keyword to search in the repo.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.search_hub KEYWORD

        # In YAML format
        salt '*' helm.search_hub KEYWORD kvflags="{'output': 'yaml'}"

    """
    return _exec_dict_return(
        commands=["search", "repo", keyword], flags=flags, kvflags=kvflags
    )


def show_all(chart, flags=None, kvflags=None):
    """
    Inspects a chart (directory, file, or URL) and displays all its content (values.yaml, Charts.yaml, README).
    Return chart information if succeed, else the error message.

    chart
        (string) The chart to inspect.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.show_all CHART

    """
    return _exec_string_return(
        commands=["show", "all", chart], flags=flags, kvflags=kvflags
    )


def show_chart(chart, flags=None, kvflags=None):
    """
    Inspects a chart (directory, file, or URL) and displays the contents of the Charts.yaml file.
    Return chart information if succeed, else the error message.

    chart
        (string) The chart to inspect.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.show_chart CHART

    """
    return _exec_string_return(
        commands=["show", "chart", chart], flags=flags, kvflags=kvflags
    )


def show_readme(chart, flags=None, kvflags=None):
    """
    Inspects a chart (directory, file, or URL) and displays the contents of the README file.
    Return chart information if succeed, else the error message.

    chart
        (string) The chart to inspect.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.show_readme CHART

    """
    return _exec_string_return(
        commands=["show", "readme", chart], flags=flags, kvflags=kvflags
    )


def show_values(chart, flags=None, kvflags=None):
    """
    Inspects a chart (directory, file, or URL) and displays the contents of the values.yaml file.
    Return chart information if succeed, else the error message.

    chart
        (string) The chart to inspect.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.show_values CHART

    """
    return _exec_string_return(
        commands=["show", "values", chart], flags=flags, kvflags=kvflags
    )


def status(release, namespace=None, flags=None, kvflags=None):
    """
    Show the status of the release.
    Return the release status if succeed, else the error message.

    release
        (string) The release to status.

    namespace
        (string) The namespace scope for this request.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.status RELEASE

        # In YAML format
        salt '*' helm.status RELEASE kvflags="{'output': 'yaml'}"

    """
    if namespace:
        if kvflags:
            kvflags.update({"namespace": namespace})
        else:
            kvflags = {"namespace": namespace}
    return _exec_dict_return(commands=["status", release], flags=flags, kvflags=kvflags)


def template(
    name, chart, values=None, output_dir=None, set=None, flags=None, kvflags=None
):
    """
    Render chart templates locally and display the output.
    Return the chart renderer if succeed, else the error message.

    name
        (string) The template name.

    chart
        (string) The chart to template.

    values
        (string) Absolute path to the values.yaml file.

    output_dir
        (string) Absolute path to the output directory.

    set
        (string or list) Set a values on the command line.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.template NAME CHART

        # With values file.
        salt '*' helm.template NAME CHART values='/path/to/values.yaml' output_dir='path/to/output/dir'

    """
    if values:
        if kvflags:
            kvflags.update({"values": values})
        else:
            kvflags = {"values": values}
    if set:
        if kvflags:
            kvflags.update({"set": set})
        else:
            kvflags = {"set": set}
    if output_dir:
        kvflags.update({"output-dir": output_dir})
    return _exec_string_return(
        commands=["template", name, chart], flags=flags, kvflags=kvflags
    )


def test(release, flags=None, kvflags=None):
    """
    Runs the tests for a release.
    Return the test result if succeed, else the error message.

    release
        (string) The release name to test.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.test RELEASE

    """
    return _exec_string_return(commands=["test", release], flags=flags, kvflags=kvflags)


def uninstall(release, namespace=None, flags=None, kvflags=None):
    """
    Uninstall the release name.
    Return True if succeed, else the error message.

    release
        (string) The name of the release to managed.

    namespace
        (string) The namespace scope for this request.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.uninstall RELEASE

        # In dry-run mode.
        salt '*' helm.uninstall RELEASE flags=['dry-run']

    """
    if namespace:
        if kvflags:
            kvflags.update({"namespace": namespace})
        else:
            kvflags = {"namespace": namespace}
    return _exec_true_return(
        commands=["uninstall", release], flags=flags, kvflags=kvflags
    )


def upgrade(
    release,
    chart,
    values=None,
    version=None,
    namespace=None,
    set=None,
    flags=None,
    kvflags=None,
):
    """
    Upgrades a release to a new version of a chart.
    Return True if succeed, else the error message.

    release
        (string) The name of the release to managed.

    chart
        (string) The chart to managed.

    values
        (string) Absolute path to the values.yaml file.

    version
        (string) The exact chart version to install. If this is not specified, the latest version is installed.

    namespace
        (string) The namespace scope for this request.

    set
        (string or list) Set a values on the command line.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.upgrade RELEASE CHART

        # In dry-run mode.
        salt '*' helm.upgrade RELEASE CHART flags=['dry-run']

        # With values file.
        salt '*' helm.upgrade RELEASE CHART values='/path/to/values.yaml'

    """
    if values:
        if kvflags:
            kvflags.update({"values": values})
        else:
            kvflags = {"values": values}
    if version:
        if kvflags:
            kvflags.update({"version": version})
        else:
            kvflags = {"version": version}
    if namespace:
        if kvflags:
            kvflags.update({"namespace": namespace})
        else:
            kvflags = {"namespace": namespace}
    if set:
        if kvflags:
            kvflags.update({"set": set})
        else:
            kvflags = {"set": set}
    return _exec_true_return(
        commands=["upgrade", release, chart], flags=flags, kvflags=kvflags
    )


def verify(path, flags=None, kvflags=None):
    """
    Verify that the given chart has a valid provenance file.
    Return True if succeed, else the error message.

    path
        (string) The path to the chart file.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.verify PATH

    """
    return _exec_true_return(commands=["verify", path], flags=flags, kvflags=kvflags)


def version(flags=None, kvflags=None):
    """
    Show the version for Helm.
    Return version information if succeed, else the error message.

    flags
        (list) Flags in argument of the command without values. ex: ['help', '--help']

    kvflags
        (dict) Flags in argument of the command with values. ex: {'v': 2, '--v': 4}

    CLI Example:

    .. code-block:: bash

        salt '*' helm.version

    """
    return _exec_string_return(commands=["version"], flags=flags, kvflags=kvflags)
