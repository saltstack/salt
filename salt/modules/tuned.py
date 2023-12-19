"""
Interface to Red Hat tuned-adm module

:maintainer:    Syed Ali <alicsyed@gmail.com>
:maturity:      new
:depends:       tuned-adm
:platform:      Linux
"""

import re

import salt.utils.path

TUNED_OFF_RETURN_NAME = "No current active profile."

__func_alias__ = {
    "list_": "list",
}

__virtualname__ = "tuned"


def __virtual__():
    """
    Check to see if tuned-adm binary is installed on the system

    """
    tuned_adm = salt.utils.path.which("tuned-adm")
    if not tuned_adm:
        return (
            False,
            "The tuned execution module failed to load: the tuned-adm binary is not in"
            " the path.",
        )
    return __virtualname__


def list_():
    """
    List the profiles available

    CLI Example:

    .. code-block:: bash

        salt '*' tuned.list
    """

    result = __salt__["cmd.run"]("tuned-adm list").splitlines()
    # Remove "Available profiles:"
    result.pop(0)
    # Cut off any warnings
    try:
        result = result[: result.index("** COLLECTED WARNINGS **") - 1]
    except ValueError:
        pass
    # Remove "Current active profile:.*"
    result.pop()
    # Output can be : " - <profile name> - <description>" (v2.7.1)
    # or " - <profile name> " (v2.4.1)
    result = [i.split("- ")[1].strip() for i in result]
    return result


def active():
    """
    Return current active profile in stdout key if retcode is 0, otherwise raw result

    CLI Example:

    .. code-block:: bash

        salt '*' tuned.active
    """

    # determine the active profile
    result = __salt__["cmd.run_all"]("tuned-adm active", ignore_retcode=True)
    if result["retcode"] == 0:
        pattern = re.compile(
            r"""(?P<stmt>Current active profile:) (?P<profile>\w+.*)"""
        )
        match = re.match(pattern, result["stdout"])
        if match:
            result["stdout"] = "{}".format(match.group("profile"))
    return result


def off():
    """
    Turn off all profiles

    CLI Example:

    .. code-block:: bash

        salt '*' tuned.off
    """

    # turn off all profiles
    return __salt__["cmd.run_all"]("tuned-adm off")


def profile(profile_name):
    """
    Activate specified profile

    CLI Example:

    .. code-block:: bash

        salt '*' tuned.profile virtual-guest
    """

    # run tuned-adm with the profile specified, upon success replace stdout with the profile_name
    result = __salt__["cmd.run_all"](
        f"tuned-adm profile {profile_name}", ignore_retcode=True
    )
    if result["retcode"] == 0:
        result["stdout"] = profile_name
    return result
