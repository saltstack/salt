# -*- coding: utf-8 -*-
"""
Kapacitor execution module.

:configuration: This module accepts connection configuration details either as
    parameters or as configuration settings in /etc/salt/minion on the relevant
    minions::

        kapacitor.host: 'localhost'
        kapacitor.port: 9092

    .. versionadded:: 2016.11.0

    Also protocol and SSL settings could be configured::

        kapacitor.unsafe_ssl: 'false'
        kapacitor.protocol: 'http'

    .. versionadded:: 2019.2.0

    This data can also be passed into pillar. Options passed into opts will
    overwrite options passed into pillar.

"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging as logger

import salt.utils.http
import salt.utils.json
import salt.utils.path

# Import Salt lobs
from salt.ext import six
from salt.utils.decorators import memoize

# Setup the logger
log = logger.getLogger(__name__)


def __virtual__():
    return "kapacitor" if salt.utils.path.which("kapacitor") else False


@memoize
def version():
    """
    Get the kapacitor version.
    """
    version = __salt__["pkg.version"]("kapacitor")
    if not version:
        version = six.string_types(
            __salt__["config.option"]("kapacitor.version", "latest")
        )
    return version


def _get_url():
    """
    Get the kapacitor URL.
    """
    protocol = __salt__["config.option"]("kapacitor.protocol", "http")
    host = __salt__["config.option"]("kapacitor.host", "localhost")
    port = __salt__["config.option"]("kapacitor.port", 9092)

    return "{0}://{1}:{2}".format(protocol, host, port)


def get_task(name):
    """
    Get a dict of data on a task.

    name
        Name of the task to get information about.

    CLI Example:

    .. code-block:: bash

        salt '*' kapacitor.get_task cpu
    """
    url = _get_url()

    if version() < "0.13":
        task_url = "{0}/task?name={1}".format(url, name)
    else:
        task_url = "{0}/kapacitor/v1/tasks/{1}?skip-format=true".format(url, name)

    response = salt.utils.http.query(task_url, status=True)

    if response["status"] == 404:
        return None

    data = salt.utils.json.loads(response["body"])

    if version() < "0.13":
        return {
            "script": data["TICKscript"],
            "type": data["Type"],
            "dbrps": data["DBRPs"],
            "enabled": data["Enabled"],
        }

    return {
        "script": data["script"],
        "type": data["type"],
        "dbrps": data["dbrps"],
        "enabled": data["status"] == "enabled",
    }


def _run_cmd(cmd):
    """
    Run a Kapacitor task and return a dictionary of info.
    """
    ret = {}
    env_vars = {
        "KAPACITOR_URL": _get_url(),
        "KAPACITOR_UNSAFE_SSL": __salt__["config.option"](
            "kapacitor.unsafe_ssl", "false"
        ),
    }
    result = __salt__["cmd.run_all"](cmd, env=env_vars)

    if result.get("stdout"):
        ret["stdout"] = result["stdout"]
    if result.get("stderr"):
        ret["stderr"] = result["stderr"]
    ret["success"] = result["retcode"] == 0

    return ret


def define_task(
    name,
    tick_script,
    task_type="stream",
    database=None,
    retention_policy="default",
    dbrps=None,
):
    """
    Define a task. Serves as both create/update.

    name
        Name of the task.

    tick_script
        Path to the TICK script for the task. Can be a salt:// source.

    task_type
        Task type. Defaults to 'stream'

    dbrps
        A list of databases and retention policies in "dbname"."rpname" format
        to fetch data from. For backward compatibility, the value of
        'database' and 'retention_policy' will be merged as part of dbrps.

        .. versionadded:: 2019.2.0

    database
        Which database to fetch data from.

    retention_policy
        Which retention policy to fetch data from. Defaults to 'default'.

    CLI Example:

    .. code-block:: bash

        salt '*' kapacitor.define_task cpu salt://kapacitor/cpu.tick database=telegraf
    """
    if not database and not dbrps:
        log.error("Providing database name or dbrps is mandatory.")
        return False

    if version() < "0.13":
        cmd = "kapacitor define -name {0}".format(name)
    else:
        cmd = "kapacitor define {0}".format(name)

    if tick_script.startswith("salt://"):
        tick_script = __salt__["cp.cache_file"](tick_script, __env__)

    cmd += " -tick {0}".format(tick_script)

    if task_type:
        cmd += " -type {0}".format(task_type)

    if not dbrps:
        dbrps = []

    if database and retention_policy:
        dbrp = "{0}.{1}".format(database, retention_policy)
        dbrps.append(dbrp)

    if dbrps:
        for dbrp in dbrps:
            cmd += " -dbrp {0}".format(dbrp)

    return _run_cmd(cmd)


def delete_task(name):
    """
    Delete a kapacitor task.

    name
        Name of the task to delete.

    CLI Example:

    .. code-block:: bash

        salt '*' kapacitor.delete_task cpu
    """
    return _run_cmd("kapacitor delete tasks {0}".format(name))


def enable_task(name):
    """
    Enable a kapacitor task.

    name
        Name of the task to enable.

    CLI Example:

    .. code-block:: bash

        salt '*' kapacitor.enable_task cpu
    """
    return _run_cmd("kapacitor enable {0}".format(name))


def disable_task(name):
    """
    Disable a kapacitor task.

    name
        Name of the task to disable.

    CLI Example:

    .. code-block:: bash

        salt '*' kapacitor.disable_task cpu
    """
    return _run_cmd("kapacitor disable {0}".format(name))
