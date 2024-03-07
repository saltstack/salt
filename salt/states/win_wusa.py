"""
Microsoft Updates (KB) Management

This module provides the ability to enforce KB installations from files (.msu),
without WSUS or Windows Update

.. versionadded:: 2018.3.4
"""

import logging

import salt.utils.platform
import salt.utils.url
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)


# Define the module's virtual name
__virtualname__ = "wusa"


def __virtual__():
    """
    Load only on Windows
    """
    if not salt.utils.platform.is_windows():
        return False, "Only available on Windows systems"

    return __virtualname__


def installed(name, source):
    """
    Ensure an update is installed on the minion

    Args:

        name(str):
            Name of the Windows KB ("KB123456")

        source (str):
            Source of .msu file corresponding to the KB

    Example:

    .. code-block:: yaml

        KB123456:
          wusa.installed:
            - source: salt://kb123456.msu
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    # Input validation
    if not name:
        raise SaltInvocationError('Must specify a KB "name"')
    if not source:
        raise SaltInvocationError('Must specify a "source" file to install')

    # Is the KB already installed
    if __salt__["wusa.is_installed"](name):
        ret["result"] = True
        ret["comment"] = f"{name} already installed"
        return ret

    # Check for test=True
    if __opts__["test"] is True:
        ret["result"] = None
        ret["comment"] = f"{name} would be installed"
        ret["result"] = None
        return ret

    # Cache the file
    cached_source_path = __salt__["cp.cache_file"](path=source, saltenv=__env__)
    if not cached_source_path:
        msg = 'Unable to cache {} from saltenv "{}"'.format(
            salt.utils.url.redact_http_basic_auth(source), __env__
        )
        ret["comment"] = msg
        return ret

    # Install the KB

    additional_comment = ""

    try:
        __salt__["wusa.install"](cached_source_path)
    except CommandExecutionError as exc:
        additional_comment = exc.message

    # Verify successful install
    if __salt__["wusa.is_installed"](name):
        ret["comment"] = f"{name} was installed. {additional_comment}"
        ret["changes"] = {"old": False, "new": True}
        ret["result"] = True
    else:
        ret["comment"] = f"{name} failed to install. {additional_comment}"

    return ret


def uninstalled(name):
    """
    Ensure an update is uninstalled from the minion

    Args:

        name(str):
            Name of the Windows KB ("KB123456")

    Example:

    .. code-block:: yaml

        KB123456:
          wusa.uninstalled
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    # Is the KB already uninstalled
    if not __salt__["wusa.is_installed"](name):
        ret["result"] = True
        ret["comment"] = f"{name} already uninstalled"
        return ret

    # Check for test=True
    if __opts__["test"] is True:
        ret["result"] = None
        ret["comment"] = f"{name} would be uninstalled"
        ret["result"] = None
        return ret

    # Uninstall the KB
    __salt__["wusa.uninstall"](name)

    # Verify successful uninstall
    if not __salt__["wusa.is_installed"](name):
        ret["comment"] = f"{name} was uninstalled"
        ret["changes"] = {"old": True, "new": False}
        ret["result"] = True
    else:
        ret["comment"] = f"{name} failed to uninstall"

    return ret
