"""
Manage software from FreeBSD ports

.. versionadded:: 2014.1.0

.. note::

    It may be helpful to use a higher timeout when running a
    :mod:`ports.installed <salt.states.ports>` state, since compiling the port
    may exceed Salt's timeout.

    .. code-block:: bash

        salt -t 1200 '*' state.highstate
"""

import copy
import logging

# Needed by imported function _options_file_exists
import os  # pylint: disable=W0611
import sys

import salt.utils.data
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.modules.freebsdports import _normalize, _options_file_exists

log = logging.getLogger(__name__)


def __virtual__():
    if __grains__.get("os", "") == "FreeBSD" and "ports.install" in __salt__:
        return "ports"
    return (False, "ports module could not be loaded")


def _repack_options(options):
    """
    Repack the options data
    """
    return {
        str(x): _normalize(y)
        for x, y in salt.utils.data.repack_dictlist(options).items()
    }


def _get_option_list(options):
    """
    Returns the key/value pairs in the passed dict in a commaspace-delimited
    list in the format "key=value".
    """
    return ", ".join([f"{x}={y}" for x, y in options.items()])


def _build_option_string(options):
    """
    Common function to get a string to append to the end of the state comment
    """
    if options:
        return f"with the following build options: {_get_option_list(options)}"
    else:
        return "with the default build options"


def installed(name, options=None):
    """
    Verify that the desired port is installed, and that it was compiled with
    the desired options.

    options
        Make sure that the desired non-default options are set

        .. warning::

            Any build options not passed here assume the default values for the
            port, and are not just differences from the existing cached options
            from a previous ``make config``.

    Example usage:

    .. code-block:: yaml

        security/nmap:
          ports.installed:
            - options:
              - IPV6: off
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"{name} is already installed",
    }
    try:
        current_options = __salt__["ports.showconfig"](
            name, default=False, dict_return=True
        )
        default_options = __salt__["ports.showconfig"](
            name, default=True, dict_return=True
        )
        # unpack the options from the top-level return dict
        if current_options:
            current_options = current_options[next(iter(current_options))]
        if default_options:
            default_options = default_options[next(iter(default_options))]
    except (SaltInvocationError, CommandExecutionError) as exc:
        ret["result"] = False
        ret["comment"] = (
            "Unable to get configuration for {}. Port name may "
            "be invalid, or ports tree may need to be updated. "
            "Error message: {}".format(name, exc)
        )
        return ret

    options = _repack_options(options) if options is not None else {}
    desired_options = copy.deepcopy(default_options)
    desired_options.update(options)
    ports_pre = [
        x["origin"] for x in __salt__["pkg.list_pkgs"](with_origin=True).values()
    ]

    if current_options == desired_options and name in ports_pre:
        # Port is installed as desired
        if options:
            ret["comment"] += " " + _build_option_string(options)
        return ret

    if not default_options:
        if options:
            ret["result"] = False
            ret["comment"] = (
                "{} does not have any build options, yet options were specified".format(
                    name
                )
            )
            return ret
        else:
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"] = f"{name} will be installed"
                return ret
    else:
        bad_opts = [x for x in options if x not in default_options]
        if bad_opts:
            ret["result"] = False
            ret["comment"] = (
                "The following options are not available for {}: {}".format(
                    name, ", ".join(bad_opts)
                )
            )
            return ret

        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"{name} will be installed "
            ret["comment"] += _build_option_string(options)
            return ret

        if options:
            if not __salt__["ports.config"](name, reset=True, **options):
                ret["result"] = False
                ret["comment"] = f"Unable to set options for {name}"
                return ret
        else:
            __salt__["ports.rmconfig"](name)
            if _options_file_exists(name):
                ret["result"] = False
                ret["comment"] = f"Unable to clear options for {name}"
                return ret

    ret["changes"] = __salt__["ports.install"](name)
    ports_post = [
        x["origin"] for x in __salt__["pkg.list_pkgs"](with_origin=True).values()
    ]
    err = sys.modules[__salt__["test.ping"].__module__].__context__.pop(
        "ports.install_error", None
    )
    if err or name not in ports_post:
        ret["result"] = False
    if ret["result"]:
        ret["comment"] = f"Successfully installed {name}"
        if default_options:
            ret["comment"] += " " + _build_option_string(options)
    else:
        ret["comment"] = f"Failed to install {name}"
        if err:
            ret["comment"] += f". Error message:\n{err}"
    return ret
