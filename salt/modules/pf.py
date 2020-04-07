# -*- coding: utf-8 -*-
"""
Control the OpenBSD packet filter (PF).

:codeauthor: Jasper Lievisse Adriaanse <j@jasper.la>

.. versionadded:: 2019.2.0
"""

from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging
import re

# Import salt libs
import salt.utils.path
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only works on OpenBSD for now; other systems with pf (macOS, FreeBSD, etc)
    need to be tested before enabling them.
    """
    if __grains__["os"] == "OpenBSD" and salt.utils.path.which("pfctl"):
        return True

    return (
        False,
        "The pf execution module cannot be loaded: either the system is not OpenBSD or the pfctl binary was not found",
    )


def enable():
    """
    Enable the Packet Filter.

    CLI example:

    .. code-block:: bash

        salt '*' pf.enable
    """
    ret = {}
    result = __salt__["cmd.run_all"](
        "pfctl -e", output_loglevel="trace", python_shell=False
    )

    if result["retcode"] == 0:
        ret = {"comment": "pf enabled", "changes": True}
    else:
        # If pf was already enabled the return code is also non-zero.
        # Don't raise an exception in that case.
        if result["stderr"] == "pfctl: pf already enabled":
            ret = {"comment": "pf already enabled", "changes": False}
        else:
            raise CommandExecutionError(
                "Could not enable pf",
                info={"errors": [result["stderr"]], "changes": False},
            )

    return ret


def disable():
    """
    Disable the Packet Filter.

    CLI example:

    .. code-block:: bash

        salt '*' pf.disable
    """
    ret = {}
    result = __salt__["cmd.run_all"](
        "pfctl -d", output_loglevel="trace", python_shell=False
    )

    if result["retcode"] == 0:
        ret = {"comment": "pf disabled", "changes": True}
    else:
        # If pf was already disabled the return code is also non-zero.
        # Don't raise an exception in that case.
        if result["stderr"] == "pfctl: pf not enabled":
            ret = {"comment": "pf already disabled", "changes": False}
        else:
            raise CommandExecutionError(
                "Could not disable pf",
                info={"errors": [result["stderr"]], "changes": False},
            )

    return ret


def loglevel(level):
    """
    Set the debug level which limits the severity of log messages printed by ``pf(4)``.

    level:
        Log level. Should be one of the following: emerg, alert, crit, err, warning, notice,
        info or debug.

    CLI example:

    .. code-block:: bash

        salt '*' pf.loglevel emerg
    """
    # There's no way to getting the previous loglevel so imply we've
    # always made a change.
    ret = {"changes": True}

    all_levels = ["emerg", "alert", "crit", "err", "warning", "notice", "info", "debug"]
    if level not in all_levels:
        raise SaltInvocationError("Unknown loglevel: {0}".format(level))

    result = __salt__["cmd.run_all"](
        "pfctl -x {0}".format(level), output_loglevel="trace", python_shell=False
    )

    if result["retcode"] != 0:
        raise CommandExecutionError(
            "Problem encountered setting loglevel",
            info={"errors": [result["stderr"]], "changes": False},
        )

    return ret


def load(file="/etc/pf.conf", noop=False):
    """
    Load a ruleset from the specific file, overwriting the currently loaded ruleset.

    file:
        Full path to the file containing the ruleset.

    noop:
        Don't actually load the rules, just parse them.

    CLI example:

    .. code-block:: bash

        salt '*' pf.load /etc/pf.conf.d/lockdown.conf
    """
    # We cannot precisely determine if loading the ruleset implied
    # any changes so assume it always does.
    ret = {"changes": True}
    cmd = ["pfctl", "-f", file]

    if noop:
        ret["changes"] = False
        cmd.append("-n")

    result = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)

    if result["retcode"] != 0:
        raise CommandExecutionError(
            "Problem loading the ruleset from {0}".format(file),
            info={"errors": [result["stderr"]], "changes": False},
        )

    return ret


def flush(modifier):
    """
    Flush the specified packet filter parameters.

    modifier:
        Should be one of the following:

        - all
        - info
        - osfp
        - rules
        - sources
        - states
        - tables

        Please refer to the OpenBSD `pfctl(8) <https://man.openbsd.org/pfctl#T>`_
        documentation for a detailed explanation of each command.

    CLI example:

    .. code-block:: bash

        salt '*' pf.flush states
    """
    ret = {}

    all_modifiers = ["rules", "states", "info", "osfp", "all", "sources", "tables"]

    # Accept the following two modifiers to allow for a consistent interface between
    # pfctl(8) and Salt.
    capital_modifiers = ["Sources", "Tables"]
    all_modifiers += capital_modifiers
    if modifier.title() in capital_modifiers:
        modifier = modifier.title()

    if modifier not in all_modifiers:
        raise SaltInvocationError("Unknown modifier: {0}".format(modifier))

    cmd = "pfctl -v -F {0}".format(modifier)
    result = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)

    if result["retcode"] == 0:
        if re.match(r"^0.*", result["stderr"]):
            ret["changes"] = False
        else:
            ret["changes"] = True

        ret["comment"] = result["stderr"]
    else:
        raise CommandExecutionError(
            "Could not flush {0}".format(modifier),
            info={"errors": [result["stderr"]], "changes": False},
        )

    return ret


def table(command, table, **kwargs):
    """
    Apply a command on the specified table.

    table:
        Name of the table.

    command:
        Command to apply to the table. Supported commands are:

        - add
        - delete
        - expire
        - flush
        - kill
        - replace
        - show
        - test
        - zero

        Please refer to the OpenBSD `pfctl(8) <https://man.openbsd.org/pfctl#T>`_
        documentation for a detailed explanation of each command.

    CLI example:

    .. code-block:: bash

        salt '*' pf.table expire table=spam_hosts number=300
        salt '*' pf.table add table=local_hosts addresses='["127.0.0.1", "::1"]'
    """
    ret = {}

    all_commands = [
        "kill",
        "flush",
        "add",
        "delete",
        "expire",
        "replace",
        "show",
        "test",
        "zero",
    ]
    if command not in all_commands:
        raise SaltInvocationError("Unknown table command: {0}".format(command))

    cmd = ["pfctl", "-t", table, "-T", command]

    if command in ["add", "delete", "replace", "test"]:
        cmd += kwargs.get("addresses", [])
    elif command == "expire":
        number = kwargs.get("number", None)
        if not number:
            raise SaltInvocationError("need expire_number argument for expire command")
        else:
            cmd.append(number)

    result = __salt__["cmd.run_all"](cmd, output_level="trace", python_shell=False)

    if result["retcode"] == 0:
        if command == "show":
            ret = {"comment": result["stdout"].split()}
        elif command == "test":
            ret = {"comment": result["stderr"], "matches": True}
        else:
            if re.match(r"^(0.*|no changes)", result["stderr"]):
                ret["changes"] = False
            else:
                ret["changes"] = True

            ret["comment"] = result["stderr"]
    else:
        # 'test' returns a non-zero code if the address didn't match, even if
        # the command itself ran fine; also set 'matches' to False since not
        # everything matched.
        if command == "test" and re.match(
            r"^\d+/\d+ addresses match.$", result["stderr"]
        ):
            ret = {"comment": result["stderr"], "matches": False}
        else:
            raise CommandExecutionError(
                "Could not apply {0} on table {1}".format(command, table),
                info={"errors": [result["stderr"]], "changes": False},
            )

    return ret


def show(modifier):
    """
    Show filter parameters.

    modifier:
        Modifier to apply for filtering. Only a useful subset of what pfctl supports
        can be used with Salt.

        - rules
        - states
        - tables

    CLI example:

    .. code-block:: bash

        salt '*' pf.show rules
    """
    # By definition showing the parameters makes no changes.
    ret = {"changes": False}

    capital_modifiers = ["Tables"]
    all_modifiers = ["rules", "states", "tables"]
    all_modifiers += capital_modifiers
    if modifier.title() in capital_modifiers:
        modifier = modifier.title()

    if modifier not in all_modifiers:
        raise SaltInvocationError("Unknown modifier: {0}".format(modifier))

    cmd = "pfctl -s {0}".format(modifier)
    result = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)

    if result["retcode"] == 0:
        ret["comment"] = result["stdout"].split("\n")
    else:
        raise CommandExecutionError(
            "Could not show {0}".format(modifier),
            info={"errors": [result["stderr"]], "changes": False},
        )

    return ret
