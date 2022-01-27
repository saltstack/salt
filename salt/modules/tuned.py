"""
Interface to Red Hat tuned-adm module

:maintainer:    Syed Ali <alicsyed@gmail.com>
:maturity:      new
:depends:       tuned-adm
:platform:      Linux
"""


import re

import salt.utils.path

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
    Return current active profile

    CLI Example:

    .. code-block:: bash

        salt '*' tuned.active
    """

    # turn off all profiles
    result = __salt__["cmd.run_all"]("tuned-adm active", ignore_retcode=True)
    if result["retcode"] != 0:
        return "none"
    pattern = re.compile(r"""(?P<stmt>Current active profile:) (?P<profile>\w+.*)""")
    match = re.match(pattern, result["stdout"])
    return "{}".format(match.group("profile"))


def off():
    """
    Turn off all profiles

    CLI Example:

    .. code-block:: bash

        salt '*' tuned.off
    """

    # turn off all profiles
    result = __salt__["cmd.retcode"]("tuned-adm off")
    if int(result) != 0:
        return False
    return True


def profile(profile_name):
    """
    Activate specified profile

    CLI Example:

    .. code-block:: bash

        salt '*' tuned.profile virtual-guest
    """

    # run tuned-adm with the profile specified
    result = __salt__["cmd.retcode"]("tuned-adm profile {}".format(profile_name))
    if int(result) != 0:
        return False
    return "{}".format(profile_name)
