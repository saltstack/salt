"""
Installation of PHP Extensions Using pecl
=========================================

These states manage the installed pecl extensions. Note that php-pear must be
installed for these states to be available, so pecl states should include a
requisite to a pkg.installed state for the package which provides pecl
(``php-pear`` in most cases). Example:

.. code-block:: yaml

    php-pear:
      pkg.installed

    mongo:
      pecl.installed:
        - require:
          - pkg: php-pear
"""


def __virtual__():
    """
    Only load if the pecl module is available in __salt__
    """
    if "pecl.list" in __salt__:
        return "pecl"
    return (False, "pecl module could not be loaded")


def installed(
    name, version=None, defaults=False, force=False, preferred_state="stable"
):
    """
    .. versionadded:: 0.17.0

    Make sure that a pecl extension is installed.

    name
        The pecl extension name to install

    version
        The pecl extension version to install. This option may be
        ignored to install the latest stable version.

    defaults
        Use default answers for extensions such as pecl_http which ask
        questions before installation. Without this option, the pecl.installed
        state will hang indefinitely when trying to install these extensions.

    force
        Whether to force the installed version or not

    preferred_state
        The pecl extension state to install
    """
    # Check to see if we have a designated version
    if not isinstance(version, str) and version is not None:
        version = str(version)

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    if "/" in name:
        channel, package = name.split("/")
    else:
        channel = None
        package = name
    installed_pecls = __salt__["pecl.list"](channel)

    if package in installed_pecls:
        # The package is only installed if version is absent or matches
        if (
            version is None or version in installed_pecls[package]
        ) and preferred_state in installed_pecls[package]:
            ret["result"] = True
            ret["comment"] = f"Pecl extension {name} is already installed."
            return ret

    if version is not None:
        # Modify the name to include the version and proceed.
        name = f"{name}-{version}"

    if __opts__["test"]:
        ret["comment"] = f"Pecl extension {name} would have been installed"
        return ret
    if __salt__["pecl.install"](
        name, defaults=defaults, force=force, preferred_state=preferred_state
    ):
        ret["result"] = True
        ret["changes"][name] = "Installed"
        ret["comment"] = f"Pecl extension {name} was successfully installed"
    else:
        ret["result"] = False
        ret["comment"] = f"Could not install pecl extension {name}."

    return ret


def removed(name):
    """
    Make sure that a pecl extension is not installed.

    name
        The pecl extension name to uninstall
    """
    ret = {"name": name, "result": None, "comment": "", "changes": {}}
    if name not in __salt__["pecl.list"]():
        ret["result"] = True
        ret["comment"] = f"Pecl extension {name} is not installed."
        return ret

    if __opts__["test"]:
        ret["comment"] = f"Pecl extension {name} would have been removed"
        return ret
    if __salt__["pecl.uninstall"](name):
        ret["result"] = True
        ret["changes"][name] = "Removed"
        ret["comment"] = f"Pecl extension {name} was successfully removed."
    else:
        ret["result"] = False
        ret["comment"] = f"Could not remove pecl extension {name}."
    return ret
