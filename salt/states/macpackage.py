"""
Installing of mac pkg files
===========================

Install any kind of pkg, dmg or app file on macOS:

.. code-block:: yaml

    /mnt/test.pkg:
      macpackage.installed:
        - store: True

    /mnt/test.dmg:
      macpackage.installed:
        - dmg: True

    /mnt/xcode.dmg:
      macpackage.installed:
        - dmg: True
        - app: True
        - target: /Applications/Xcode.app
        - version_check: xcodebuild -version=Xcode 7.1\\n.*7B91b

"""

import logging
import os
import re
import shutil

import salt.utils.platform
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

__virtualname__ = "macpackage"


def __virtual__():
    """
    Only work on Mac OS
    """
    if salt.utils.platform.is_darwin():
        return __virtualname__
    return (False, "Only supported on Mac OS")


def installed(
    name,
    target="LocalSystem",
    dmg=False,
    store=False,
    app=False,
    mpkg=False,
    force=False,
    allow_untrusted=False,
    version_check=None,
):
    """
    Install a Mac OS Package from a pkg or dmg file, if given a dmg file it
    will first be mounted in a temporary location

    name
        The pkg or dmg file to install

    target
        The location in which to install the package. This can be a path or LocalSystem

    dmg
        Is the given file a dmg file?

    store
        Should the pkg be installed as if it was from the Mac OS Store?

    app
        Is the file a .app? If so then we'll just copy that to /Applications/ or the given
        target

    mpkg
        Is the file a .mpkg? If so then we'll check all of the .pkg files found are installed

    force
        Force the package to be installed even if its already been found installed

    allow_untrusted
        Allow the installation of untrusted packages

    version_check
        The command and version that we want to check against, the version number can use regex.

        .. code-block:: yaml

            version_check: python --version_check=2.7.[0-9]

    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    found = []
    installing = []

    real_pkg = name

    # Check version info
    if version_check is not None:
        split = version_check.split("=")
        if len(split) == 2:
            version_cmd = split[0]
            expected_version = split[1]
            try:
                version_out = __salt__["cmd.run"](
                    version_cmd, output_loglevel="quiet", ignore_retcode=True
                )
                version_out = version_out.strip()
            except CommandExecutionError:
                version_out = ""

            if re.match(expected_version, version_out) is not None:
                ret["comment"] += f"Version already matches {expected_version}"
                return ret
            else:
                ret["comment"] += "Version {} doesn't match {}. ".format(
                    version_out, expected_version
                )

    if app and target == "LocalSystem":
        target = "/Applications/"

    # Mount the dmg first
    mount_point = None
    if dmg:
        out, mount_point = __salt__["macpackage.mount"](name)
        if "attach failed" in out:
            ret["result"] = False
            ret["comment"] += f"Unable to mount {name}"
            return ret

        if app:
            real_pkg = mount_point + "/*.app"
        elif mpkg:
            real_pkg = mount_point + "/*.mpkg"
        else:
            real_pkg = mount_point + "/*.pkg"

    try:
        # Check if we have already installed this
        if app:
            if dmg:
                # Run with python shell due to the wildcard
                cmd = "ls -d *.app"
                out = __salt__["cmd.run"](cmd, cwd=mount_point, python_shell=True)

                if ".app" not in out:
                    ret["result"] = False
                    ret["comment"] += f"Unable to find .app in {mount_point}"
                    return ret
                else:
                    pkg_ids = out.split("\n")
            else:
                pkg_ids = [os.path.basename(name)]
                mount_point = os.path.dirname(name)

            if version_check is None:
                for p in pkg_ids:
                    if target[-4:] == ".app":
                        install_dir = target
                    else:
                        install_dir = os.path.join(target, p)
                    if os.path.exists(install_dir) and force is False:
                        found.append(p)
                    else:
                        installing.append(p)
            else:
                installing = pkg_ids
        else:
            installed_pkgs = __salt__["macpackage.installed_pkgs"]()

            if mpkg:
                pkg_ids = __salt__["macpackage.get_mpkg_ids"](real_pkg)
            else:
                pkg_ids = __salt__["macpackage.get_pkg_id"](real_pkg)

            if len(pkg_ids) > 0:
                for p in pkg_ids:
                    if p in installed_pkgs and force is False:
                        found.append(p)
                    else:
                        installing.append(p)
                if len(pkg_ids) == len(found):
                    return ret

        if app:

            def failed_pkg(f_pkg):
                ret["result"] = False
                ret["comment"] += f"{name} failed to install: {out}"

                if "failed" in ret["changes"]:
                    ret["changes"]["failed"].append(f_pkg)
                else:
                    ret["changes"]["failed"] = [f_pkg]

            for app in installing:
                try:
                    log.info("Copying %s to %s", app, target)

                    out = __salt__["macpackage.install_app"](
                        os.path.join(mount_point, app), target
                    )

                    if len(out) != 0:
                        failed_pkg(app)
                    else:
                        ret["comment"] += f"{app} installed"
                        if "installed" in ret["changes"]:
                            ret["changes"]["installed"].append(app)
                        else:
                            ret["changes"]["installed"] = [app]

                except OSError:
                    failed_pkg(app)
        else:
            out = __salt__["macpackage.install"](
                real_pkg, target, store, allow_untrusted
            )

            if out["retcode"] != 0:
                ret["result"] = False
                ret["comment"] += f". {name} failed to install: {out}"
            else:
                ret["comment"] += f"{name} installed"
                ret["changes"]["installed"] = installing

    finally:
        if dmg:
            # Unmount to be kind
            out = __salt__["macpackage.unmount"](mount_point)
            # If unmount succeeded cleanup mount point
            if out["retcode"] == 0:
                shutil.rmtree(mount_point)

    return ret
