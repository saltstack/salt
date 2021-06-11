# -*- coding: utf-8 -*-
"""
Aptly Debian repository manager.

.. versionadded:: 2018.3.0
"""
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import re

import salt.utils.json
import salt.utils.path
import salt.utils.stringutils
from salt.exceptions import SaltInvocationError

# Import salt libs
from salt.ext import six

_DEFAULT_CONFIG_PATH = "/etc/aptly.conf"
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "aptly"


def __virtual__():
    """
    Only works on systems with the aptly binary in the system path.
    """
    if salt.utils.path.which("aptly"):
        return __virtualname__
    return (False, "The aptly binaries required cannot be found or are not installed.")


def _cmd_run(cmd):
    """
    Run the aptly command.

    :return: The string output of the command.
    :rtype: str
    """
    cmd.insert(0, "aptly")
    cmd_ret = __salt__["cmd.run_all"](cmd, ignore_retcode=True)

    if cmd_ret["retcode"] != 0:
        log.debug("Unable to execute command: %s\nError: %s", cmd, cmd_ret["stderr"])

    return cmd_ret["stdout"]


def _format_repo_args(
    comment=None, component=None, distribution=None, uploaders_file=None, saltenv="base"
):
    """
    Format the common arguments for creating or editing a repository.

    :param str comment: The description of the repository.
    :param str component: The default component to use when publishing.
    :param str distribution: The default distribution to use when publishing.
    :param str uploaders_file: The repository upload restrictions config.
    :param str saltenv: The environment the file resides in.

    :return: A list of the arguments formatted as aptly arguments.
    :rtype: list
    """
    ret = list()
    cached_uploaders_path = None
    settings = {
        "comment": comment,
        "component": component,
        "distribution": distribution,
    }

    if uploaders_file:
        cached_uploaders_path = __salt__["cp.cache_file"](uploaders_file, saltenv)

        if not cached_uploaders_path:
            log.error("Unable to get cached copy of file: %s", uploaders_file)
            return False

    for setting in settings:
        if settings[setting] is not None:
            ret.append("-{}={}".format(setting, settings[setting]))

    if cached_uploaders_path:
        ret.append("-uploaders-file={}".format(cached_uploaders_path))

    return ret


def _validate_config(config_path):
    """
    Validate that the configuration file exists and is readable.

    :param str config_path: The path to the configuration file for the aptly instance.

    :return: None
    :rtype: None
    """
    log.debug("Checking configuration file: %s", config_path)

    if not os.path.isfile(config_path):
        message = "Unable to get configuration file: {}".format(config_path)
        log.error(message)
        raise SaltInvocationError(message)


def get_config(config_path=_DEFAULT_CONFIG_PATH):
    """
    Get the configuration data.

    :param str config_path: The path to the configuration file for the aptly instance.

    :return: A dictionary containing the configuration data.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' aptly.get_config
    """
    _validate_config(config_path)

    cmd = ["config", "show", "-config={}".format(config_path)]

    cmd_ret = _cmd_run(cmd)

    return salt.utils.json.loads(cmd_ret)


def list_repos(config_path=_DEFAULT_CONFIG_PATH, with_packages=False):
    """
    List all of the repos.

    :param str config_path: The path to the configuration file for the aptly instance.
    :param bool with_packages: Return a list of packages in the repo.

    :return: A dictionary of the repositories.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' aptly.list_repos
    """
    _validate_config(config_path)

    ret = dict()
    cmd = ["repo", "list", "-config={}".format(config_path), "-raw=true"]

    cmd_ret = _cmd_run(cmd)
    repos = [line.strip() for line in cmd_ret.splitlines()]

    log.debug("Found repositories: %s", len(repos))

    for name in repos:
        ret[name] = get_repo(
            name=name, config_path=config_path, with_packages=with_packages
        )
    return ret


def get_repo(name, config_path=_DEFAULT_CONFIG_PATH, with_packages=False):
    """
    Get the details of the repository.

    :param str name: The name of the repository.
    :param str config_path: The path to the configuration file for the aptly instance.
    :param bool with_packages: Return a list of packages in the repo.

    :return: A dictionary containing information about the repository.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' aptly.get_repo name="test-repo"
    """
    _validate_config(config_path)
    with_packages = six.text_type(bool(with_packages)).lower()

    ret = dict()
    cmd = [
        "repo",
        "show",
        "-config={}".format(config_path),
        "-with-packages={}".format(with_packages),
        name,
    ]

    cmd_ret = _cmd_run(cmd)

    for line in cmd_ret.splitlines():
        try:
            # Extract the settings and their values, and attempt to format
            # them to match their equivalent setting names.
            items = line.split(":")
            key = items[0].lower().replace("default", "").strip()
            key = " ".join(key.split()).replace(" ", "_")
            ret[key] = salt.utils.stringutils.to_none(
                salt.utils.stringutils.to_num(items[1].strip())
            )
        except (AttributeError, IndexError):
            # If the line doesn't have the separator or is otherwise invalid, skip it.
            log.debug("Skipping line: %s", line)

    if ret:
        log.debug("Found repository: %s", name)
    else:
        log.debug("Unable to find repository: %s", name)
    return ret


def new_repo(
    name,
    config_path=_DEFAULT_CONFIG_PATH,
    comment=None,
    component=None,
    distribution=None,
    uploaders_file=None,
    from_snapshot=None,
    saltenv="base",
):
    """
    Create the new repository.

    :param str name: The name of the repository.
    :param str config_path: The path to the configuration file for the aptly instance.
    :param str comment: The description of the repository.
    :param str component: The default component to use when publishing.
    :param str distribution: The default distribution to use when publishing.
    :param str uploaders_file: The repository upload restrictions config.
    :param str from_snapshot: The snapshot to initialize the repository contents from.
    :param str saltenv: The environment the file resides in.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' aptly.new_repo name="test-repo" comment="Test main repo" component="main" distribution="trusty"
    """
    _validate_config(config_path)

    current_repo = __salt__["aptly.get_repo"](name=name, config_path=config_path)

    if current_repo:
        log.debug("Repository already exists: %s", name)
        return True

    cmd = ["repo", "create", "-config={}".format(config_path)]
    repo_params = _format_repo_args(
        comment=comment,
        component=component,
        distribution=distribution,
        uploaders_file=uploaders_file,
        saltenv=saltenv,
    )
    cmd.extend(repo_params)
    cmd.append(name)

    if from_snapshot:
        cmd.extend(["from", "snapshot", from_snapshot])

    _cmd_run(cmd)
    repo = __salt__["aptly.get_repo"](name=name, config_path=config_path)

    if repo:
        log.debug("Created repo: %s", name)
        return True
    log.error("Unable to create repo: %s", name)
    return False


def set_repo(
    name,
    config_path=_DEFAULT_CONFIG_PATH,
    comment=None,
    component=None,
    distribution=None,
    uploaders_file=None,
    saltenv="base",
):
    """
    Configure the repository settings.

    :param str name: The name of the repository.
    :param str config_path: The path to the configuration file for the aptly instance.
    :param str comment: The description of the repository.
    :param str component: The default component to use when publishing.
    :param str distribution: The default distribution to use when publishing.
    :param str uploaders_file: The repository upload restrictions config.
    :param str from_snapshot: The snapshot to initialize the repository contents from.
    :param str saltenv: The environment the file resides in.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' aptly.set_repo name="test-repo" comment="Test universe repo" component="universe" distribution="xenial"
    """
    _validate_config(config_path)

    failed_settings = dict()

    # Only check for settings that were passed in and skip the rest.
    settings = {
        "comment": comment,
        "component": component,
        "distribution": distribution,
    }

    for setting in list(settings):
        if settings[setting] is None:
            settings.pop(setting, None)

    current_settings = __salt__["aptly.get_repo"](name=name, config_path=config_path)

    if not current_settings:
        log.error("Unable to get repo: %s", name)
        return False

    # Discard any additional settings that get_repo gives
    # us that are not present in the provided arguments.
    for current_setting in list(current_settings):
        if current_setting not in settings:
            current_settings.pop(current_setting, None)

    # Check the existing repo settings to see if they already have the desired values.
    if settings == current_settings:
        log.debug("Settings already have the desired values for repository: %s", name)
        return True

    cmd = ["repo", "edit", "-config={}".format(config_path)]

    repo_params = _format_repo_args(
        comment=comment,
        component=component,
        distribution=distribution,
        uploaders_file=uploaders_file,
        saltenv=saltenv,
    )
    cmd.extend(repo_params)
    cmd.append(name)

    _cmd_run(cmd)
    new_settings = __salt__["aptly.get_repo"](name=name, config_path=config_path)

    # Check the new repo settings to see if they have the desired values.
    for setting in settings:
        if settings[setting] != new_settings[setting]:
            failed_settings.update({setting: settings[setting]})

    if failed_settings:
        log.error("Unable to change settings for the repository: %s", name)
        return False
    log.debug(
        "Settings successfully changed to the desired values for repository: %s", name
    )
    return True


def delete_repo(name, config_path=_DEFAULT_CONFIG_PATH, force=False):
    """
    Remove the repository.

    :param str name: The name of the repository.
    :param str config_path: The path to the configuration file for the aptly instance.
    :param bool force: Whether to remove the repository even if it is used as the source
        of an existing snapshot.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' aptly.delete_repo name="test-repo"
    """
    _validate_config(config_path)
    force = six.text_type(bool(force)).lower()

    current_repo = __salt__["aptly.get_repo"](name=name, config_path=config_path)

    if not current_repo:
        log.debug("Repository already absent: %s", name)
        return True

    cmd = [
        "repo",
        "drop",
        "-config={}".format(config_path),
        "-force={}".format(force),
        name,
    ]

    _cmd_run(cmd)
    repo = __salt__["aptly.get_repo"](name=name, config_path=config_path)

    if repo:
        log.error("Unable to remove repo: %s", name)
        return False
    log.debug("Removed repo: %s", name)
    return True


def list_mirrors(config_path=_DEFAULT_CONFIG_PATH):
    """
    Get a list of all the mirrors.

    :param str config_path: The path to the configuration file for the aptly instance.

    :return: A list of the mirror names.
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' aptly.list_mirrors
    """
    _validate_config(config_path)

    cmd = ["mirror", "list", "-config={}".format(config_path), "-raw=true"]

    cmd_ret = _cmd_run(cmd)
    ret = [line.strip() for line in cmd_ret.splitlines()]

    log.debug("Found mirrors: %s", len(ret))
    return ret


def list_published(config_path=_DEFAULT_CONFIG_PATH):
    """
    Get a list of all the published repositories.

    :param str config_path: The path to the configuration file for the aptly instance.

    :return: A list of the published repository names.
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' aptly.list_published
    """
    _validate_config(config_path)

    cmd = ["publish", "list", "-config={}".format(config_path), "-raw=true"]

    cmd_ret = _cmd_run(cmd)
    ret = [line.strip() for line in cmd_ret.splitlines()]

    log.debug("Found published repositories: %s", len(ret))
    return ret


def list_snapshots(config_path=_DEFAULT_CONFIG_PATH, sort_by_time=False):
    """
    Get a list of all the snapshots.

    :param str config_path: The path to the configuration file for the aptly instance.
    :param bool sort_by_time: Whether to sort by creation time instead of by name.

    :return: A list of the snapshot names.
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' aptly.list_snapshots
    """
    _validate_config(config_path)

    cmd = ["snapshot", "list", "-config={}".format(config_path), "-raw=true"]

    if sort_by_time:
        cmd.append("-sort=time")
    else:
        cmd.append("-sort=name")

    cmd_ret = _cmd_run(cmd)
    ret = [line.strip() for line in cmd_ret.splitlines()]

    log.debug("Found snapshots: %s", len(ret))
    return ret


def cleanup_db(config_path=_DEFAULT_CONFIG_PATH, dry_run=False):
    """
    Remove data regarding unreferenced packages and delete files in the package pool that
        are no longer being used by packages.

    :param bool dry_run: Report potential changes without making any changes.

    :return: A dictionary of the package keys and files that were removed.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' aptly.cleanup_db
    """
    _validate_config(config_path)
    dry_run = six.text_type(bool(dry_run)).lower()

    ret = {"deleted_keys": list(), "deleted_files": list()}

    cmd = [
        "db",
        "cleanup",
        "-config={}".format(config_path),
        "-dry-run={}".format(dry_run),
        "-verbose=true",
    ]

    cmd_ret = _cmd_run(cmd)

    type_pattern = r"^List\s+[\w\s]+(?P<package_type>(file|key)s)[\w\s]+:$"
    list_pattern = r"^\s+-\s+(?P<package>.*)$"
    current_block = None

    for line in cmd_ret.splitlines():
        if current_block:
            match = re.search(list_pattern, line)
            if match:
                package_type = "deleted_{}".format(current_block)
                ret[package_type].append(match.group("package"))
            else:
                current_block = None
        # Intentionally not using an else here, in case of a situation where
        # the next list header might be bordered by the previous list.
        if not current_block:
            match = re.search(type_pattern, line)
            if match:
                current_block = match.group("package_type")

    log.debug("Package keys identified for deletion: %s", len(ret["deleted_keys"]))
    log.debug("Package files identified for deletion: %s", len(ret["deleted_files"]))
    return ret
