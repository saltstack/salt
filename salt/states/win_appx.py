"""
Manage Microsoft Store apps on Windows. Removing an app with this modules will
deprovision the app from the online Windows image.

.. versionadded:: 3007.0
"""

import fnmatch
import logging

import salt.utils.data
import salt.utils.platform

log = logging.getLogger(__name__)
__virtualname__ = "appx"


def __virtual__():
    """
    Only work on Windows where the DISM module is available
    """
    if not salt.utils.platform.is_windows():
        return False, "Appx state: Only available on Windows"

    pwsh_info = __salt__["cmd.shell_info"](shell="powershell", list_modules=False)
    if not pwsh_info["installed"]:
        return False, "Appx state: PowerShell not available"

    return __virtualname__


def absent(name, query, include_store=False, frameworks=False, deprovision_only=False):
    """
    Removes Microsoft Store packages from the system. If the package is part of
    a bundle, the entire bundle will be removed.

    This function removes the package for all users on the system. It also
    deprovisions the package so that it isn't re-installed by later system
    updates. To only deprovision a package and not remove it for all users, set
    ``deprovision_only=True``.

    Args:

        query (str):
            The query string to use to select the packages to be removed. If the
            string matches multiple packages, they will all be removed. Here are
            some example strings:

            | string          | description |
            | --------------- | ----------- |
            | ``*teams*``     | Remove Microsoft Teams |
            | ``*zune*``      | Remove Windows Media Player and Zune Video |
            | ``*zuneMusic*`` | Only remove Windows Media Player |
            | ``*xbox*``      | Remove all xBox packages, there are 5 by default
            | ``*``           | Remove everything but the Microsoft Store, unless ``include_store=True`` |

            .. note::
                Use the ``appx.list`` function to make sure your query is
                returning what you expect. Then use the same query to remove
                those packages

        include_store (bool):
            Include the Microsoft Store in the results of the query to be
            removed. Use this with caution. It is difficult to reinstall the
            Microsoft Store once it has been removed with this function. Default
            is ``False``

        frameworks (bool):
            Include frameworks in the results of the query to be removed.
            Default is ``False``

        deprovision_only (bool):
            Only deprovision the package. The package will be removed from the
            current user and added to the list of deprovisioned packages. The
            package will not be re-installed in future system updates. New users
            of the system will not have the package installed. However, the
            package will still be installed for existing users. Default is
            ``False``

    Returns:
        bool: ``True`` if successful, ``None`` if no packages found

    Raises:
        CommandExecutionError: On errors encountered removing the package

    CLI Example:

    .. code-block:: yaml

        remove_candy_crush:
          appx.absent:
            - query: "*candy*"
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    old = __salt__["appx.list"](include_store=include_store, frameworks=frameworks)
    matches = fnmatch.filter(old, query)
    if not matches:
        ret["comment"] = f"No apps found matching query: {query}"
        return ret

    if __opts__["test"]:
        comment = ["The following apps will be removed:"]
        comment.extend(matches)
        ret["comment"] = "\n- ".join(comment)
        ret["result"] = None
        return ret

    # Install the capability
    status = __salt__["appx.remove"](
        query,
        include_store=include_store,
        frameworks=frameworks,
        deprovision_only=deprovision_only,
    )

    if status is None:
        ret["comment"] = f"No apps found matching query: {query}"
        ret["result"] = False

    new = __salt__["appx.list"](include_store=include_store, frameworks=frameworks)
    changes = salt.utils.data.compare_lists(old, new)

    if changes:
        ret["comment"] = f"Removed apps matching query: {query}"
        ret["changes"] = changes

    return ret
