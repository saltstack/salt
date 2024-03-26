"""
Support for poudriere
"""

import logging
import os

import salt.utils.files
import salt.utils.path
import salt.utils.stringutils

log = logging.getLogger(__name__)


def __virtual__():
    """
    Module load on freebsd only and if poudriere installed
    """
    if __grains__["os"] == "FreeBSD" and salt.utils.path.which("poudriere"):
        return "poudriere"
    else:
        return (
            False,
            "The poudriere execution module failed to load: only available on FreeBSD"
            " with the poudriere binary in the path.",
        )


def _config_file():
    """
    Return the config file location to use
    """
    return __salt__["config.option"]("poudriere.config")


def _config_dir():
    """
    Return the configuration directory to use
    """
    return __salt__["config.option"]("poudriere.config_dir")


def _check_config_exists(config_file=None):
    """
    Verify the config file is present
    """
    if config_file is None:
        config_file = _config_file()
    if not os.path.isfile(config_file):
        return False
    return True


def is_jail(name):
    """
    Return True if jail exists False if not

    CLI Example:

    .. code-block:: bash

        salt '*' poudriere.is_jail <jail name>
    """
    jails = list_jails()
    for jail in jails:
        if jail.split()[0] == name:
            return True
    return False


def make_pkgng_aware(jname):
    """
    Make jail ``jname`` pkgng aware

    CLI Example:

    .. code-block:: bash

        salt '*' poudriere.make_pkgng_aware <jail name>
    """
    ret = {"changes": {}}
    cdir = _config_dir()
    # ensure cdir is there
    if not os.path.isdir(cdir):
        os.makedirs(cdir)
        if os.path.isdir(cdir):
            ret["changes"] = f"Created poudriere make file dir {cdir}"
        else:
            return f"Could not create or find required directory {cdir}"

    # Added args to file
    __salt__["file.write"](f"{os.path.join(cdir, jname)}-make.conf", "WITH_PKGNG=yes")

    if os.path.isfile(os.path.join(cdir, jname) + "-make.conf"):
        ret["changes"] = "Created {}".format(os.path.join(cdir, f"{jname}-make.conf"))
        return ret
    else:
        return "Looks like file {} could not be created".format(
            os.path.join(cdir, jname + "-make.conf")
        )


def parse_config(config_file=None):
    """
    Returns a dict of poudriere main configuration definitions

    CLI Example:

    .. code-block:: bash

        salt '*' poudriere.parse_config
    """
    if config_file is None:
        config_file = _config_file()
    ret = {}
    if _check_config_exists(config_file):
        with salt.utils.files.fopen(config_file) as ifile:
            for line in ifile:
                key, val = salt.utils.stringutils.to_unicode(line).split("=")
                ret[key] = val
        return ret

    return f"Could not find {config_file} on file system"


def version():
    """
    Return poudriere version

    CLI Example:

    .. code-block:: bash

        salt '*' poudriere.version
    """
    cmd = "poudriere version"
    return __salt__["cmd.run"](cmd)


def list_jails():
    """
    Return a list of current jails managed by poudriere

    CLI Example:

    .. code-block:: bash

        salt '*' poudriere.list_jails
    """
    _check_config_exists()
    cmd = "poudriere jails -l"
    res = __salt__["cmd.run"](cmd)
    return res.splitlines()


def list_ports():
    """
    Return a list of current port trees managed by poudriere

    CLI Example:

    .. code-block:: bash

        salt '*' poudriere.list_ports
    """
    _check_config_exists()
    cmd = "poudriere ports -l"
    res = __salt__["cmd.run"](cmd).splitlines()
    return res


def create_jail(name, arch, version="9.0-RELEASE"):
    """
    Creates a new poudriere jail if one does not exist

    *NOTE* creating a new jail will take some time the master is not hanging

    CLI Example:

    .. code-block:: bash

        salt '*' poudriere.create_jail 90amd64 amd64
    """
    # Config file must be on system to create a poudriere jail
    _check_config_exists()

    # Check if the jail is there
    if is_jail(name):
        return f"{name} already exists"

    cmd = f"poudriere jails -c -j {name} -v {version} -a {arch}"
    __salt__["cmd.run"](cmd)

    # Make jail pkgng aware
    make_pkgng_aware(name)

    # Make sure the jail was created
    if is_jail(name):
        return f"Created jail {name}"

    return f"Issue creating jail {name}"


def update_jail(name):
    """
    Run freebsd-update on `name` poudriere jail

    CLI Example:

    .. code-block:: bash

        salt '*' poudriere.update_jail freebsd:10:x86:64
    """
    if is_jail(name):
        cmd = f"poudriere jail -u -j {name}"
        ret = __salt__["cmd.run"](cmd)
        return ret
    else:
        return f"Could not find jail {name}"


def delete_jail(name):
    """
    Deletes poudriere jail with `name`

    CLI Example:

    .. code-block:: bash

        salt '*' poudriere.delete_jail 90amd64
    """
    if is_jail(name):
        cmd = f"poudriere jail -d -j {name}"
        __salt__["cmd.run"](cmd)

        # Make sure jail is gone
        if is_jail(name):
            return f"Looks like there was an issue deleting jail {name}"
    else:
        # Could not find jail.
        return f"Looks like jail {name} has not been created"

    # clean up pkgng make info in config dir
    make_file = os.path.join(_config_dir(), f"{name}-make.conf")
    if os.path.isfile(make_file):
        try:
            os.remove(make_file)
        except OSError:
            return 'Deleted jail "{}" but was unable to remove jail make file'.format(
                name
            )
        __salt__["file.remove"](make_file)

    return f"Deleted jail {name}"


def info_jail(name):
    """
    Show information on `name` poudriere jail

    CLI Example:

    .. code-block:: bash

        salt '*' poudriere.info_jail head-amd64
    """
    if is_jail(name):
        cmd = f"poudriere jail -i -j {name}"
        ret = __salt__["cmd.run"](cmd).splitlines()
        return ret
    else:
        return f"Could not find jail {name}"


def create_ports_tree():
    """
    Not working need to run portfetch non interactive
    """
    _check_config_exists()
    cmd = "poudriere ports -c"
    ret = __salt__["cmd.run"](cmd)
    return ret


def update_ports_tree(ports_tree):
    """
    Updates the ports tree, either the default or the `ports_tree` specified

    CLI Example:

    .. code-block:: bash

        salt '*' poudriere.update_ports_tree staging
    """
    _check_config_exists()
    if ports_tree:
        cmd = f"poudriere ports -u -p {ports_tree}"
    else:
        cmd = "poudriere ports -u"
    ret = __salt__["cmd.run"](cmd)
    return ret


def bulk_build(jail, pkg_file, keep=False):
    """
    Run bulk build on poudriere server.

    Return number of pkg builds, failures, and errors, on error dump to CLI

    CLI Example:

    .. code-block:: bash

        salt -N buildbox_group poudriere.bulk_build 90amd64 /root/pkg_list

    """
    # make sure `pkg file` and jail is on file system
    if not os.path.isfile(pkg_file):
        return f"Could not find file {pkg_file} on filesystem"
    if not is_jail(jail):
        return f"Could not find jail {jail}"

    # Generate command
    if keep:
        cmd = f"poudriere bulk -k -f {pkg_file} -j {jail}"
    else:
        cmd = f"poudriere bulk -f {pkg_file} -j {jail}"

    # Bulk build this can take some time, depending on pkg_file ... hours
    res = __salt__["cmd.run"](cmd)
    lines = res.splitlines()
    for line in lines:
        if "packages built" in line:
            return line
    return "There may have been an issue building packages dumping output: {}".format(
        res
    )
