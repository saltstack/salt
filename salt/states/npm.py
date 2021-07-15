"""
Installation of NPM Packages
============================

These states manage the installed packages for node.js using the Node Package
Manager (npm). Note that npm must be installed for these states to be
available, so npm states should include a requisite to a pkg.installed state
for the package which provides npm (simply ``npm`` in most cases). Example:

.. code-block:: yaml

    npm:
      pkg.installed

    yaml:
      npm.installed:
        - require:
          - pkg: npm
"""


import re

from salt.exceptions import CommandExecutionError, CommandNotFoundError


def __virtual__():
    """
    Only load if the npm module is available in __salt__
    """
    return (
        "npm" if "npm.list" in __salt__ else False,
        "'npm' binary not found on system",
    )


def installed(
    name, pkgs=None, dir=None, user=None, force_reinstall=False, registry=None, env=None
):
    """
    Verify that the given package is installed and is at the correct version
    (if specified).

    .. code-block:: yaml

        coffee-script:
          npm.installed:
            - user: someuser

        coffee-script@1.0.1:
          npm.installed: []

    name
        The package to install

        .. versionchanged:: 2014.7.2
            This parameter is no longer lowercased by salt so that
            case-sensitive NPM package names will work.

    pkgs
        A list of packages to install with a single npm invocation; specifying
        this argument will ignore the ``name`` argument

        .. versionadded:: 2014.7.0

    dir
        The target directory in which to install the package, or None for
        global installation

    user
        The user to run NPM with

        .. versionadded:: 0.17.0

    registry
        The NPM registry from which to install the package

        .. versionadded:: 2014.7.0

    env
        A list of environment variables to be set prior to execution. The
        format is the same as the :py:func:`cmd.run <salt.states.cmd.run>`.
        state function.

        .. versionadded:: 2014.7.0

    force_reinstall
        Install the package even if it is already installed
    """
    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    pkg_list = pkgs if pkgs else [name]

    try:
        installed_pkgs = __salt__["npm.list"](dir=dir, runas=user, env=env, depth=0)
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret["result"] = False
        ret["comment"] = "Error looking up '{}': {}".format(name, err)
        return ret
    else:
        installed_pkgs = {p: info for p, info in installed_pkgs.items()}

    pkgs_satisfied = []
    pkgs_to_install = []

    def _pkg_is_installed(pkg, installed_pkgs):
        """
        Helper function to determine if a package is installed

        This performs more complex comparison than just checking
        keys, such as examining source repos to see if the package
        was installed by a different name from the same repo

        :pkg str: The package to compare
        :installed_pkgs: A dictionary produced by npm list --json
        """
        if pkg_name in installed_pkgs and "version" in installed_pkgs[pkg_name]:
            return True
        # Check to see if we are trying to install from a URI
        elif "://" in pkg_name:  # TODO Better way?
            for pkg_details in installed_pkgs.values():
                try:
                    pkg_from = pkg_details.get("from", "").split("://")[1]
                    # Catch condition where we may have specified package as
                    # git://github.com/foo/bar but packager describes it as
                    # git://github.com/foo/bar.git in the package
                    if not pkg_from.endswith(".git") and pkg_name.startswith("git://"):
                        pkg_from += ".git"
                    if pkg_name.split("://")[1] == pkg_from:
                        return True
                except IndexError:
                    pass
        return False

    for pkg in pkg_list:
        # Valid:
        #
        # @google-cloud/bigquery@^0.9.6
        # @foobar
        # buffer-equal-constant-time@1.0.1
        # coffee-script
        matches = re.search(r"^(@?[^@\s]+)(?:@(\S+))?", pkg)
        pkg_name, pkg_ver = matches.group(1), matches.group(2) or None

        if force_reinstall is True:
            pkgs_to_install.append(pkg)
            continue
        if not _pkg_is_installed(pkg, installed_pkgs):
            pkgs_to_install.append(pkg)
            continue

        installed_name_ver = "{}@{}".format(
            pkg_name, installed_pkgs[pkg_name]["version"]
        )

        # If given an explicit version check the installed version matches.
        if pkg_ver:
            if installed_pkgs[pkg_name].get("version") != pkg_ver:
                pkgs_to_install.append(pkg)
            else:
                pkgs_satisfied.append(installed_name_ver)

            continue
        else:
            pkgs_satisfied.append(installed_name_ver)
            continue

    if __opts__["test"]:
        ret["result"] = None

        comment_msg = []
        if pkgs_to_install:
            comment_msg.append(
                "NPM package(s) '{}' are set to be installed".format(
                    ", ".join(pkgs_to_install)
                )
            )

            ret["changes"] = {"old": [], "new": pkgs_to_install}

        if pkgs_satisfied:
            comment_msg.append(
                "Package(s) '{}' satisfied by {}".format(
                    ", ".join(pkg_list), ", ".join(pkgs_satisfied)
                )
            )
            ret["result"] = True

        ret["comment"] = ". ".join(comment_msg)
        return ret

    if not pkgs_to_install:
        ret["result"] = True
        ret["comment"] = "Package(s) '{}' satisfied by {}".format(
            ", ".join(pkg_list), ", ".join(pkgs_satisfied)
        )
        return ret

    try:
        cmd_args = {
            "dir": dir,
            "runas": user,
            "registry": registry,
            "env": env,
            "pkgs": pkg_list,
        }

        call = __salt__["npm.install"](**cmd_args)
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret["result"] = False
        ret["comment"] = "Error installing '{}': {}".format(", ".join(pkg_list), err)
        return ret
    else:
        ret["result"] = True
        ret["changes"] = {"old": [], "new": pkgs_to_install}
        ret["comment"] = "Package(s) '{}' successfully installed".format(
            ", ".join(pkgs_to_install)
        )

    return ret


def removed(name, dir=None, user=None):
    """
    Verify that the given package is not installed.

    dir
        The target directory in which to install the package, or None for
        global installation

    user
        The user to run NPM with

        .. versionadded:: 0.17.0
    """
    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    try:
        installed_pkgs = __salt__["npm.list"](dir=dir, depth=0)
    except (CommandExecutionError, CommandNotFoundError) as err:
        ret["result"] = False
        ret["comment"] = "Error uninstalling '{}': {}".format(name, err)
        return ret

    if name not in installed_pkgs:
        ret["result"] = True
        ret["comment"] = "Package '{}' is not installed".format(name)
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Package '{}' is set to be removed".format(name)
        return ret

    if __salt__["npm.uninstall"](pkg=name, dir=dir, runas=user):
        ret["result"] = True
        ret["changes"][name] = "Removed"
        ret["comment"] = "Package '{}' was successfully removed".format(name)
    else:
        ret["result"] = False
        ret["comment"] = "Error removing package '{}'".format(name)

    return ret


def bootstrap(name, user=None, silent=True):
    """
    Bootstraps a node.js application.

    Will execute 'npm install --json' on the specified directory.

    user
        The user to run NPM with

        .. versionadded:: 0.17.0
    """
    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    if __opts__["test"]:
        try:
            call = __salt__["npm.install"](
                dir=name, runas=user, pkg=None, silent=silent, dry_run=True
            )
            if call:
                ret["result"] = None
                ret["changes"] = {"old": [], "new": call}
                ret["comment"] = "{} is set to be bootstrapped".format(name)
            else:
                ret["result"] = True
                ret["comment"] = "{} is already bootstrapped".format(name)
        except (CommandNotFoundError, CommandExecutionError) as err:
            ret["result"] = False
            ret["comment"] = "Error Bootstrapping '{}': {}".format(name, err)
        return ret

    try:
        call = __salt__["npm.install"](dir=name, runas=user, pkg=None, silent=silent)
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret["result"] = False
        ret["comment"] = "Error Bootstrapping '{}': {}".format(name, err)
        return ret

    if not call:
        ret["result"] = True
        ret["comment"] = "Directory is already bootstrapped"
        return ret

    # npm.install will return a string if it can't parse a JSON result
    if isinstance(call, str):
        ret["result"] = False
        ret["changes"] = call
        ret["comment"] = "Could not bootstrap directory"
    else:
        ret["result"] = True
        ret["changes"] = {name: "Bootstrapped"}
        ret["comment"] = "Directory was successfully bootstrapped"

    return ret


def cache_cleaned(name=None, user=None, force=False):
    """
    Ensure that the given package is not cached.

    If no package is specified, this ensures the entire cache is cleared.

    name
        The name of the package to remove from the cache, or None for all packages

    user
        The user to run NPM with

    force
        Force cleaning of cache.  Required for npm@5 and greater

        .. versionadded:: 2016.11.6
    """
    ret = {"name": name, "result": None, "comment": "", "changes": {}}
    specific_pkg = None

    try:
        cached_pkgs = __salt__["npm.cache_list"](path=name, runas=user)
    except (CommandExecutionError, CommandNotFoundError) as err:
        ret["result"] = False
        ret["comment"] = "Error looking up cached {}: {}".format(
            name or "packages", err
        )
        return ret

    if name:
        all_cached_pkgs = __salt__["npm.cache_list"](path=None, runas=user)
        # The first package is always the cache path
        cache_root_path = all_cached_pkgs[0]
        specific_pkg = "{}/{}/".format(cache_root_path, name)

        if specific_pkg not in cached_pkgs:
            ret["result"] = True
            ret["comment"] = "Package {} is not in the cache".format(name)
            return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Cached {} set to be removed".format(name or "packages")
        return ret

    if __salt__["npm.cache_clean"](path=name, runas=user):
        ret["result"] = True
        ret["changes"][name or "cache"] = "Removed"
        ret["comment"] = "Cached {} successfully removed".format(name or "packages")
    else:
        ret["result"] = False
        ret["comment"] = "Error cleaning cached {}".format(name or "packages")

    return ret
