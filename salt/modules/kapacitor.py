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

import logging as logger

import salt.utils.http
import salt.utils.json
import salt.utils.path

# Import Salt lobs
from salt.utils.decorators import memoize

# Setup the logger
log = logger.getLogger(__name__)


def __virtual__():
    if salt.utils.path.which("kapacitor"):
        return "kapacitor"
    else:
        return (False, "Missing dependency: kapacitor")


@memoize
def version():
    """
    Get the kapacitor version.
    """
    version = __salt__["pkg.version"]("kapacitor")
    if not version:
        version = str(__salt__["config.option"]("kapacitor.version", "latest"))
    return version


def _get_url():
    """
    Get the kapacitor URL.
    """
    protocol = __salt__["config.option"]("kapacitor.protocol", "http")
    host = __salt__["config.option"]("kapacitor.host", "localhost")
    port = __salt__["config.option"]("kapacitor.port", 9092)

    return f"{protocol}://{host}:{port}"


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
        task_url = f"{url}/task?name={name}"
    else:
        task_url = f"{url}/kapacitor/v1/tasks/{name}?skip-format=true"

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
        cmd = f"kapacitor define -name {name}"
    else:
        cmd = f"kapacitor define {name}"

    if tick_script.startswith("salt://"):
        tick_script = __salt__["cp.cache_file"](tick_script, __env__)

    cmd += f" -tick {tick_script}"

    if task_type:
        cmd += f" -type {task_type}"

    if not dbrps:
        dbrps = []

    if database and retention_policy:
        dbrp = f"{database}.{retention_policy}"
        dbrps.append(dbrp)

    if dbrps:
        for dbrp in dbrps:
            cmd += f" -dbrp {dbrp}"

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
    return _run_cmd(f"kapacitor delete tasks {name}")


def enable_task(name):
    """
    Enable a kapacitor task.

    name
        Name of the task to enable.

    CLI Example:

    .. code-block:: bash

        salt '*' kapacitor.enable_task cpu
    """
    return _run_cmd(f"kapacitor enable {name}")


def disable_task(name):
    """
    Disable a kapacitor task.

    name
        Name of the task to disable.

    CLI Example:

    .. code-block:: bash

        salt '*' kapacitor.disable_task cpu
    """
    return _run_cmd(f"kapacitor disable {name}")
