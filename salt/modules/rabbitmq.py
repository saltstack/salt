"""
Module to provide RabbitMQ compatibility to Salt.
Todo: A lot, need to add cluster support, logging, and minion configuration
data.
"""

import logging
import os
import random
import re
import string

import salt.utils.itertools
import salt.utils.json
import salt.utils.path
import salt.utils.platform
import salt.utils.user
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.utils.versions import LooseVersion as _LooseVersion

log = logging.getLogger(__name__)

RABBITMQCTL = None
RABBITMQ_PLUGINS = None


def __virtual__():
    """
    Verify RabbitMQ is installed.
    """
    global RABBITMQCTL
    global RABBITMQ_PLUGINS

    if salt.utils.platform.is_windows():
        import winreg

        key = None
        try:
            key = winreg.OpenKeyEx(
                winreg.HKEY_LOCAL_MACHINE,
                "SOFTWARE\\VMware, Inc.\\RabbitMQ Server",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_32KEY,
            )
            (dir_path, value_type) = winreg.QueryValueEx(key, "Install_Dir")
            if value_type != winreg.REG_SZ:
                raise TypeError(
                    "Invalid RabbitMQ Server directory type: {}".format(value_type)
                )
            if not os.path.isdir(dir_path):
                raise OSError("RabbitMQ directory not found: {}".format(dir_path))
            subdir_match = ""
            for name in os.listdir(dir_path):
                if name.startswith("rabbitmq_server-"):
                    subdir_path = os.path.join(dir_path, name)
                    # Get the matching entry that is last in ASCII order.
                    if os.path.isdir(subdir_path) and subdir_path > subdir_match:
                        subdir_match = subdir_path
            if not subdir_match:
                raise OSError(
                    '"rabbitmq_server-*" subdirectory not found in: {}'.format(dir_path)
                )
            RABBITMQCTL = os.path.join(subdir_match, "sbin", "rabbitmqctl.bat")
            RABBITMQ_PLUGINS = os.path.join(
                subdir_match, "sbin", "rabbitmq-plugins.bat"
            )
        except Exception:  # pylint: disable=broad-except
            pass
        finally:
            if key is not None:
                winreg.CloseKey(key)
    else:
        RABBITMQCTL = salt.utils.path.which("rabbitmqctl")
        RABBITMQ_PLUGINS = salt.utils.path.which("rabbitmq-plugins")

    if not RABBITMQCTL:
        return (False, "Module rabbitmq: module only works when RabbitMQ is installed")
    return True


def _check_response(response):
    if isinstance(response, dict):
        if response["retcode"] != 0 or response["stderr"]:
            raise CommandExecutionError(
                "RabbitMQ command failed: {}".format(response["stderr"])
            )
    else:
        if "Error" in response:
            raise CommandExecutionError("RabbitMQ command failed: {}".format(response))


def _format_response(response, msg):
    if isinstance(response, dict):
        if response["retcode"] != 0 or response["stderr"]:
            raise CommandExecutionError(
                "RabbitMQ command failed: {}".format(response["stderr"])
            )
        else:
            response = response["stdout"]
    else:
        if "Error" in response:
            raise CommandExecutionError("RabbitMQ command failed: {}".format(response))
    return {msg: response}


def _get_rabbitmq_plugin():
    """
    Returns the rabbitmq-plugin command path if we're running an OS that
    doesn't put it in the standard /usr/bin or /usr/local/bin
    This works by taking the rabbitmq-server version and looking for where it
    seems to be hidden in /usr/lib.
    """
    global RABBITMQ_PLUGINS

    if RABBITMQ_PLUGINS is None:
        version = __salt__["pkg.version"]("rabbitmq-server").split("-")[0]
        RABBITMQ_PLUGINS = (
            "/usr/lib/rabbitmq/lib/rabbitmq_server-{}/sbin/rabbitmq-plugins".format(
                version
            )
        )

    return RABBITMQ_PLUGINS


def _safe_output(line):
    """
    Looks for rabbitmqctl warning, or general formatting, strings that aren't
    intended to be parsed as output.
    Returns a boolean whether the line can be parsed as rabbitmqctl output.
    """
    return not any(
        [
            line.startswith("Listing") and line.endswith("..."),
            line.startswith("Listing") and "\t" not in line,
            "...done" in line,
            line.startswith("WARNING:"),
            len(line) == 0,
        ]
    )


def _strip_listing_to_done(output_list):
    """
    Conditionally remove non-relevant first and last line,
    "Listing ..." - "...done".
    outputlist: rabbitmq command output split by newline
    return value: list, conditionally modified, may be empty.
    """
    return [line for line in output_list if _safe_output(line)]


def _output_to_dict(cmdoutput, values_mapper=None):
    """
    Convert rabbitmqctl output to a dict of data
    cmdoutput: string output of rabbitmqctl commands
    values_mapper: function object to process the values part of each line
    """
    if isinstance(cmdoutput, dict):
        if cmdoutput["retcode"] != 0 or cmdoutput["stderr"]:
            raise CommandExecutionError(
                "RabbitMQ command failed: {}".format(cmdoutput["stderr"])
            )
        cmdoutput = cmdoutput["stdout"]

    ret = {}
    if values_mapper is None:
        values_mapper = lambda string: string.split("\t")

    # remove first and last line: Listing ... - ...done
    data_rows = _strip_listing_to_done(cmdoutput.splitlines())

    for row in data_rows:
        try:
            key, values = row.split("\t", 1)
        except ValueError:
            # If we have reached this far, we've hit an edge case where the row
            # only has one item: the key. The key doesn't have any values, so we
            # set it to an empty string to preserve rabbitmq reporting behavior.
            # e.g. A user's permission string for '/' is set to ['', '', ''],
            # Rabbitmq reports this only as '/' from the rabbitmqctl command.
            log.debug(
                "Could not find any values for key '%s'. "
                "Setting to '%s' to an empty string.",
                row,
                row,
            )
            ret[row] = ""
            continue
        ret[key] = values_mapper(values)
    return ret


def _output_to_list(cmdoutput):
    """
    Convert rabbitmqctl output to a list of strings (assuming whitespace-delimited output).
    Ignores output lines that shouldn't be parsed, like warnings.
    cmdoutput: string output of rabbitmqctl commands
    """
    return [
        item
        for line in cmdoutput.splitlines()
        if _safe_output(line)
        for item in line.split()
    ]


def _output_lines_to_list(cmdoutput):
    """
    Convert rabbitmqctl output to a list of strings (assuming newline-delimited output).
    Ignores output lines that shouldn't be parsed, like warnings.
    cmdoutput: string output of rabbitmqctl commands
    """
    return [line.strip() for line in cmdoutput.splitlines() if _safe_output(line)]


def list_users(runas=None):
    """
    Return a list of users based off of rabbitmqctl user_list.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_users
    """
    # Windows runas currently requires a password.
    # Due to this, don't use a default value for
    # runas in Windows.
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "list_users", "-q"],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )

    # func to get tags from string such as "[admin, monitoring]"
    func = (
        lambda string: [x.strip() for x in string[1:-1].split(",")]
        if "," in string
        else [x for x in string[1:-1].split(" ")]
    )
    return _output_to_dict(res, func)


def list_vhosts(runas=None):
    """
    Return a list of vhost based on rabbitmqctl list_vhosts.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_vhosts
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "list_vhosts", "-q"],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )
    _check_response(res)
    return _output_to_list(res["stdout"])


def list_upstreams(runas=None):
    """
    Returns a dict of upstreams based on rabbitmqctl list_parameters.

    :param str runas: The name of the user to run this command as.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_upstreams

    .. versionadded:: 3000
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    ret = {}
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "list_parameters", "-q"],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )
    for raw_line in res["stdout"].split("\n"):
        if _safe_output(raw_line):
            (_, name, definition) = raw_line.split("\t")
            ret[name] = definition
    return ret


def user_exists(name, runas=None):
    """
    Return whether the user exists based on rabbitmqctl list_users.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.user_exists rabbit_user
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    return name in list_users(runas=runas)


def vhost_exists(name, runas=None):
    """
    Return whether the vhost exists based on rabbitmqctl list_vhosts.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.vhost_exists rabbit_host
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    return name in list_vhosts(runas=runas)


def upstream_exists(name, runas=None):
    """
    Return whether the upstreamexists based on rabbitmqctl list_parameters.

    :param str name: The name of the upstream to check for.
    :param str runas: The name of the user to run the command as.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.upstream_exists rabbit_upstream

    .. versionadded:: 3000
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    return name in list_upstreams(runas=runas)


def add_user(name, password=None, runas=None):
    """
    Add a rabbitMQ user via rabbitmqctl user_add <user> <password>

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.add_user rabbit_user password
    """
    clear_pw = False

    if password is None:
        # Generate a random, temporary password. RabbitMQ requires one.
        clear_pw = True
        password = "".join(
            random.SystemRandom().choice(string.ascii_uppercase + string.digits)
            for x in range(15)
        )

    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()

    if salt.utils.platform.is_windows():
        # On Windows, if the password contains a special character
        # such as '|', normal execution will fail. For example:
        # cmd: rabbitmq.add_user abc "asdf|def"
        # stderr: 'def' is not recognized as an internal or external
        #         command,\r\noperable program or batch file.
        # Work around this by using a shell and a quoted command.
        python_shell = True
        cmd = '"{}" add_user "{}" "{}"'.format(RABBITMQCTL, name, password)
    else:
        python_shell = False
        cmd = [RABBITMQCTL, "add_user", name, password]

    res = __salt__["cmd.run_all"](
        cmd,
        reset_system_locale=False,
        output_loglevel="quiet",
        runas=runas,
        python_shell=python_shell,
    )

    if clear_pw:
        # Now, Clear the random password from the account, if necessary
        try:
            clear_password(name, runas)
        except Exception:  # pylint: disable=broad-except
            # Clearing the password failed. We should try to cleanup
            # and rerun and error.
            delete_user(name, runas)
            raise

    msg = "Added"
    return _format_response(res, msg)


def delete_user(name, runas=None):
    """
    Deletes a user via rabbitmqctl delete_user.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.delete_user rabbit_user
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "delete_user", name],
        reset_system_locale=False,
        python_shell=False,
        runas=runas,
    )
    msg = "Deleted"

    return _format_response(res, msg)


def change_password(name, password, runas=None):
    """
    Changes a user's password.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.change_password rabbit_user password
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    if salt.utils.platform.is_windows():
        # On Windows, if the password contains a special character
        # such as '|', normal execution will fail. For example:
        # cmd: rabbitmq.add_user abc "asdf|def"
        # stderr: 'def' is not recognized as an internal or external
        #         command,\r\noperable program or batch file.
        # Work around this by using a shell and a quoted command.
        python_shell = True
        cmd = '"{}" change_password "{}" "{}"'.format(RABBITMQCTL, name, password)
    else:
        python_shell = False
        cmd = [RABBITMQCTL, "change_password", name, password]
    res = __salt__["cmd.run_all"](
        cmd,
        reset_system_locale=False,
        runas=runas,
        output_loglevel="quiet",
        python_shell=python_shell,
    )
    msg = "Password Changed"

    return _format_response(res, msg)


def clear_password(name, runas=None):
    """
    Removes a user's password.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.clear_password rabbit_user
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "clear_password", name],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )
    msg = "Password Cleared"

    return _format_response(res, msg)


def check_password(name, password, runas=None):
    """
    .. versionadded:: 2016.3.0

    Checks if a user's password is valid.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.check_password rabbit_user password
    """
    # try to get the rabbitmq-version - adapted from _get_rabbitmq_plugin

    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()

    try:
        res = __salt__["cmd.run"](
            [RABBITMQCTL, "status"],
            reset_system_locale=False,
            runas=runas,
            python_shell=False,
        )
        # Check regex against older RabbitMQ version status output
        old_server_version = re.search(r'\{rabbit,"RabbitMQ","(.+)"\}', res)
        # Check regex against newer RabbitMQ version status output
        server_version = re.search(r"RabbitMQ version:\s*(.+)", res)

        if server_version is None and old_server_version is None:
            raise ValueError

        if old_server_version:
            server_version = old_server_version
        server_version = server_version.group(1).split("-")[0]
        version = [int(i) for i in server_version.split(".")]

    except ValueError:
        version = (0, 0, 0)
    if len(version) < 3:
        version = (0, 0, 0)

    # rabbitmq introduced a native api to check a username and password in version 3.5.7.
    if tuple(version) >= (3, 5, 7):
        if salt.utils.platform.is_windows():
            # On Windows, if the password contains a special character
            # such as '|', normal execution will fail. For example:
            # cmd: rabbitmq.add_user abc "asdf|def"
            # stderr: 'def' is not recognized as an internal or external
            #         command,\r\noperable program or batch file.
            # Work around this by using a shell and a quoted command.
            python_shell = True
            cmd = '"{}" authenticate_user "{}" "{}"'.format(RABBITMQCTL, name, password)
        else:
            python_shell = False
            cmd = [RABBITMQCTL, "authenticate_user", name, password]

        res = __salt__["cmd.run_all"](
            cmd,
            reset_system_locale=False,
            runas=runas,
            output_loglevel="quiet",
            python_shell=python_shell,
        )

        if res["retcode"] != 0 or res["stderr"]:
            return False
        return True

    cmd = (
        "rabbit_auth_backend_internal:check_user_login"
        '(<<"{}">>, [{{password, <<"{}">>}}]).'.format(
            name.replace('"', '\\"'), password.replace('"', '\\"')
        )
    )

    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "eval", cmd],
        reset_system_locale=False,
        runas=runas,
        output_loglevel="quiet",
        python_shell=False,
    )
    msg = "password-check"

    _response = _format_response(res, msg)
    _key = next(iter(_response))

    if "invalid credentials" in _response[_key]:
        return False

    return True


def add_vhost(vhost, runas=None):
    """
    Adds a vhost via rabbitmqctl add_vhost.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq add_vhost '<vhost_name>'
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "add_vhost", vhost],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )

    msg = "Added"
    return _format_response(res, msg)


def delete_vhost(vhost, runas=None):
    """
    Deletes a vhost rabbitmqctl delete_vhost.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.delete_vhost '<vhost_name>'
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "delete_vhost", vhost],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )
    msg = "Deleted"
    return _format_response(res, msg)


def set_permissions(vhost, user, conf=".*", write=".*", read=".*", runas=None):
    """
    Sets permissions for vhost via rabbitmqctl set_permissions

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.set_permissions myvhost myuser
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "set_permissions", "-p", vhost, user, conf, write, read],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )
    msg = "Permissions Set"
    return _format_response(res, msg)


def list_permissions(vhost, runas=None):
    """
    Lists permissions for vhost via rabbitmqctl list_permissions

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_permissions /myvhost
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "list_permissions", "--formatter=json", "-p", vhost],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )

    perms = salt.utils.json.loads(res["stdout"])
    perms_dict = {}
    for perm in perms:
        user = perm["user"]
        perms_dict[user] = perm
        del perms_dict[user]["user"]
    return perms_dict


def list_user_permissions(name, runas=None):
    """
    List permissions for a user via rabbitmqctl list_user_permissions

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_user_permissions user
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "list_user_permissions", name, "--formatter=json"],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )

    perms = salt.utils.json.loads(res["stdout"])
    perms_dict = {}
    for perm in perms:
        vhost = perm["vhost"]
        perms_dict[vhost] = perm
        del perms_dict[vhost]["vhost"]
    return perms_dict


def set_user_tags(name, tags, runas=None):
    """Add user tags via rabbitmqctl set_user_tags

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.set_user_tags myadmin administrator
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()

    if not isinstance(tags, (list, tuple)):
        tags = [tags]

    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "set_user_tags", name] + list(tags),
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )
    msg = "Tag(s) set"
    return _format_response(res, msg)


def status(runas=None):
    """
    return rabbitmq status

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.status
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "status"],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )
    _check_response(res)
    return res["stdout"]


def cluster_status(runas=None):
    """
    return rabbitmq cluster_status

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.cluster_status
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "cluster_status"],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )
    _check_response(res)
    return res["stdout"]


def join_cluster(host, user="rabbit", ram_node=None, runas=None):
    """
    Join a rabbit cluster

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.join_cluster rabbit.example.com rabbit
    """
    cmd = [RABBITMQCTL, "join_cluster"]
    if ram_node:
        cmd.append("--ram")
    cmd.append("{}@{}".format(user, host))

    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    stop_app(runas)
    res = __salt__["cmd.run_all"](
        cmd, reset_system_locale=False, runas=runas, python_shell=False
    )
    start_app(runas)

    return _format_response(res, "Join")


def stop_app(runas=None):
    """
    Stops the RabbitMQ application, leaving the Erlang node running.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.stop_app
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "stop_app"],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )
    _check_response(res)
    return res["stdout"]


def start_app(runas=None):
    """
    Start the RabbitMQ application.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.start_app
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "start_app"],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )
    _check_response(res)
    return res["stdout"]


def reset(runas=None):
    """
    Return a RabbitMQ node to its virgin state

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.reset
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "reset"],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )
    _check_response(res)
    return res["stdout"]


def force_reset(runas=None):
    """
    Forcefully Return a RabbitMQ node to its virgin state

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.force_reset
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "force_reset"],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )
    _check_response(res)
    return res["stdout"]


def list_queues(runas=None, *args):
    """
    Returns queue details of the / virtual host

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_queues messages consumers
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    cmd = [RABBITMQCTL, "list_queues", "-q"]
    cmd.extend(args)
    res = __salt__["cmd.run_all"](
        cmd, reset_system_locale=False, runas=runas, python_shell=False
    )
    _check_response(res)
    return _output_to_dict(res["stdout"])


def list_queues_vhost(vhost, runas=None, *args):
    """
    Returns queue details of specified virtual host. This command will consider
    first parameter as the vhost name and rest will be treated as
    queueinfoitem. For getting details on vhost ``/``, use :mod:`list_queues
    <salt.modules.rabbitmq.list_queues>` instead).

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_queues messages consumers
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    cmd = [RABBITMQCTL, "list_queues", "-q", "-p", vhost]
    cmd.extend(args)
    res = __salt__["cmd.run_all"](
        cmd, reset_system_locale=False, runas=runas, python_shell=False
    )
    _check_response(res)
    return _output_to_dict(res["stdout"])


def list_policies(vhost="/", runas=None):
    """
    Return a dictionary of policies nested by vhost and name
    based on the data returned from rabbitmqctl list_policies.

    Reference: http://www.rabbitmq.com/ha.html

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_policies
    """
    ret = {}
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "list_policies", "-q", "-p", vhost],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )
    _check_response(res)
    output = res["stdout"]

    if __grains__["os_family"] != "FreeBSD":
        version = __salt__["pkg.version"]("rabbitmq-server").split("-")[0]
    else:
        version = __salt__["pkg.version"]("rabbitmq").split("-")[0]

    for line in _output_lines_to_list(output):
        parts = line.split("\t")

        if len(parts) not in (5, 6):
            continue

        vhost, name = parts[0], parts[1]
        if vhost not in ret:
            ret[vhost] = {}
        ret[vhost][name] = {}

        if _LooseVersion(version) >= _LooseVersion("3.7"):
            # in version 3.7 the position of apply_to and pattern has been
            # switched
            ret[vhost][name]["pattern"] = parts[2]
            ret[vhost][name]["apply_to"] = parts[3]
            ret[vhost][name]["definition"] = parts[4]
            ret[vhost][name]["priority"] = parts[5]
        else:
            # How many fields are there? - 'apply_to' was inserted in position
            # 2 at some point
            # and in version 3.7 the position of apply_to and pattern has been
            # switched
            offset = len(parts) - 5
            if len(parts) == 6:
                ret[vhost][name]["apply_to"] = parts[2]
            ret[vhost][name].update(
                {
                    "pattern": parts[offset + 2],
                    "definition": parts[offset + 3],
                    "priority": parts[offset + 4],
                }
            )

    return ret


def set_policy(
    vhost, name, pattern, definition, priority=None, runas=None, apply_to=None
):
    """
    Set a policy based on rabbitmqctl set_policy.

    Reference: http://www.rabbitmq.com/ha.html

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.set_policy / HA '.*' '{"ha-mode":"all"}'
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    if isinstance(definition, dict):
        definition = salt.utils.json.dumps(definition)
    if not isinstance(definition, str):
        raise SaltInvocationError(
            "The 'definition' argument must be a dictionary or JSON string"
        )
    cmd = [RABBITMQCTL, "set_policy", "-p", vhost]
    if priority:
        cmd.extend(["--priority", priority])
    if apply_to:
        cmd.extend(["--apply-to", apply_to])
    cmd.extend([name, pattern, definition])
    res = __salt__["cmd.run_all"](
        cmd, reset_system_locale=False, runas=runas, python_shell=False
    )
    log.debug("Set policy: %s", res["stdout"])
    return _format_response(res, "Set")


def delete_policy(vhost, name, runas=None):
    """
    Delete a policy based on rabbitmqctl clear_policy.

    Reference: http://www.rabbitmq.com/ha.html

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.delete_policy / HA
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "clear_policy", "-p", vhost, name],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )
    log.debug("Delete policy: %s", res["stdout"])
    return _format_response(res, "Deleted")


def policy_exists(vhost, name, runas=None):
    """
    Return whether the policy exists based on rabbitmqctl list_policies.

    Reference: http://www.rabbitmq.com/ha.html

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.policy_exists / HA
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    policies = list_policies(runas=runas)
    return bool(vhost in policies and name in policies[vhost])


def list_available_plugins(runas=None):
    """
    Returns a list of the names of all available plugins (enabled and disabled).

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_available_plugins
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    cmd = [_get_rabbitmq_plugin(), "list", "-m"]
    ret = __salt__["cmd.run_all"](
        cmd, reset_system_locale=False, runas=runas, python_shell=False
    )
    _check_response(ret)
    return _output_to_list(ret["stdout"])


def list_enabled_plugins(runas=None):
    """
    Returns a list of the names of the enabled plugins.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_enabled_plugins
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    cmd = [_get_rabbitmq_plugin(), "list", "-m", "-e"]
    ret = __salt__["cmd.run_all"](
        cmd, reset_system_locale=False, runas=runas, python_shell=False
    )
    _check_response(ret)
    return _output_to_list(ret["stdout"])


def plugin_is_enabled(name, runas=None):
    """
    Return whether the plugin is enabled.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.plugin_is_enabled rabbitmq_plugin_name
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    return name in list_enabled_plugins(runas)


def enable_plugin(name, runas=None):
    """
    Enable a RabbitMQ plugin via the rabbitmq-plugins command.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.enable_plugin foo
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    cmd = [_get_rabbitmq_plugin(), "enable", name]
    ret = __salt__["cmd.run_all"](
        cmd, reset_system_locale=False, runas=runas, python_shell=False
    )
    return _format_response(ret, "Enabled")


def disable_plugin(name, runas=None):
    """
    Disable a RabbitMQ plugin via the rabbitmq-plugins command.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.disable_plugin foo
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    cmd = [_get_rabbitmq_plugin(), "disable", name]
    ret = __salt__["cmd.run_all"](
        cmd, reset_system_locale=False, runas=runas, python_shell=False
    )
    return _format_response(ret, "Disabled")


def set_upstream(
    name,
    uri,
    prefetch_count=None,
    reconnect_delay=None,
    ack_mode=None,
    trust_user_id=None,
    exchange=None,
    max_hops=None,
    expires=None,
    message_ttl=None,
    ha_policy=None,
    queue=None,
    runas=None,
):
    """
    Configures an upstream via rabbitmqctl set_parameter. This can be an exchange-upstream,
    a queue-upstream or both.

    :param str name: The name of the upstream to configure.

    The following parameters apply to federated exchanges and federated queues:

    :param str uri: The AMQP URI(s) for the upstream.
    :param int prefetch_count: The maximum number of unacknowledged messages copied
        over a link at any one time. Default: 1000
    :param int reconnect_delay: The duration (in seconds) to wait before reconnecting
        to the broker after being disconnected. Default: 1
    :param str ack_mode: Determines how the link should acknowledge messages.
        If set to ``on-confirm`` (the default), messages are acknowledged to the
        upstream broker after they have been confirmed downstream. This handles
        network errors and broker failures without losing messages, and is the
        slowest option.
        If set to ``on-publish``, messages are acknowledged to the upstream broker
        after they have been published downstream. This handles network errors
        without losing messages, but may lose messages in the event of broker failures.
        If set to ``no-ack``, message acknowledgements are not used. This is the
        fastest option, but may lose messages in the event of network or broker failures.
    :param bool trust_user_id: Determines how federation should interact with the
        validated user-id feature. If set to true, federation will pass through
        any validated user-id from the upstream, even though it cannot validate
        it itself. If set to false or not set, it will clear any validated user-id
        it encounters. You should only set this to true if you trust the upstream
        server (and by extension, all its upstreams) not to forge user-ids.

    The following parameters apply to federated exchanges only:

    :param str exchange: The name of the upstream exchange. Default is to use the
        same name as the federated exchange.
    :param int max_hops: The maximum number of federation links that a message
        published to a federated exchange can traverse before it is discarded.
        Default is 1. Note that even if max-hops is set to a value greater than 1,
        messages will never visit the same node twice due to travelling in a loop.
        However, messages may still be duplicated if it is possible for them to
        travel from the source to the destination via multiple routes.
    :param int expires: The expiry time (in milliseconds) after which an upstream
        queue for a federated exchange may be deleted, if a connection to the upstream
        broker is lost. The default is 'none', meaning the queue should never expire.
        This setting controls how long the upstream queue will last before it is
        eligible for deletion if the connection is lost.
        This value is used to set the "x-expires" argument for the upstream queue.
    :param int message_ttl: The expiry time for messages in the upstream queue
        for a federated exchange (see expires), in milliseconds. Default is ``None``,
        meaning messages should never expire. This does not apply to federated queues.
        This value is used to set the "x-message-ttl" argument for the upstream queue.
    :param str ha_policy: Determines the "x-ha-policy" argument for the upstream
        queue for a federated exchange (see expires). This is only of interest
        when connecting to old brokers which determine queue HA mode using this
        argument. Default is ``None``, meaning the queue is not HA.

    The following parameter applies to federated queues only:

    :param str queue: The name of the upstream queue. Default is to use the same
        name as the federated queue.

    :param str runas: The name of the user to run the command as.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.set_upstream upstream_name ack_mode=on-confirm max_hops=1 \
            trust_user_id=True uri=amqp://hostname

    .. versionadded:: 3000
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    params = salt.utils.data.filter_falsey(
        {
            "uri": uri,
            "prefetch-count": prefetch_count,
            "reconnect-delay": reconnect_delay,
            "ack-mode": ack_mode,
            "trust-user-id": trust_user_id,
            "exchange": exchange,
            "max-hops": max_hops,
            "expires": expires,
            "message-ttl": message_ttl,
            "ha-policy": ha_policy,
            "queue": queue,
        }
    )
    res = __salt__["cmd.run_all"](
        [
            RABBITMQCTL,
            "set_parameter",
            "federation-upstream",
            name,
            salt.utils.json.dumps(params),
        ],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )
    _check_response(res)
    return True


def delete_upstream(name, runas=None):
    """
    Deletes an upstream via rabbitmqctl clear_parameter.

    :param str name: The name of the upstream to delete.
    :param str runas: The name of the user to run the command as.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.delete_upstream upstream_name

    .. versionadded:: 3000
    """
    if runas is None and not salt.utils.platform.is_windows():
        runas = salt.utils.user.get_user()
    res = __salt__["cmd.run_all"](
        [RABBITMQCTL, "clear_parameter", "federation-upstream", name],
        reset_system_locale=False,
        runas=runas,
        python_shell=False,
    )
    _check_response(res)
    return True
