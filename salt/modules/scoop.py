'''
scoop execution module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Module wrapping calls to the Scoop package manager

'''

import logging
import os
import re
import tempfile

import salt.utils.data

from salt.exceptions import (
    CommandExecutionError,
    MinionError,
)

try:
    #  Import libs...
    
    HAS_LIBS = True
    MISSING_PACKAGE_REASON = None
except ImportError as ie:
    HAS_LIBS = False
    MISSING_PACKAGE_REASON = ie.message

log = logging.getLogger(__name__)

__virtualname__ = 'scoop'


def __virtual__():
    """
    Confirm this module is on a Windows system running Vista or later.

    We do not support XP and server 2003 because of awful powershell work.
    """
    if not salt.utils.platform.is_windows():
        return (False, "Cannot load module scoop: Scoop requires Windows")
    
    if __grains__["osrelease"] in ("XP", "2003Server"):
        return (
            False,
            "Cannot load module scoop: Scoop requires Windows Vista or later",
        )
    # To be deleted?
    if HAS_LIBS:
        return __virtualname__
    return (False,
            'The scoop execution module failed to load:'
            'import error - {0}.'.format(MISSING_PACKAGE_REASON))


def _clear_context():
    """
    Clear variables stored in __context__. Run this function when a new version
    of scoop is installed.
    """
    scoop_items = [x for x in __context__ if x.startswith("scoop.")]
    for var in scoop_items:
        __context__.pop(var)

def _find_scoop():
    """
    Returns the full path to scoop.bat on the host.
    """
    # Check context
    if "scoop._path" in __context__:
        return __context__["scoop._path"]
    
    # TODO: correctly detect is global or not
    __context__["scoop._global"] = True

    # Check the path
    scoop_path = __salt__["cmd.which"]("scoop")
    if scoop_path:
        __context__["scoop._path"] = scoop_path
        return __context__["scoop._path"]

    # Check in common locations
    scoop_defaults = [
        os.path.join(
            os.environ.get("USERPROFILE"), "scoop", "shims", "scoop.cmd"
        ),
        os.path.join(
            os.path.abspath(os.sep), "Scoop", "shims", "scoop.cmd"
        ),
    ]
    for scoop_exe in scoop_defaults:
        if os.path.isfile(scoop_exe):
            __context__["scoop._path"] = scoop_exe
            return __context__["scoop._path"]

    # Not installed, raise an error
    err = (
        "Scoop not installed. Use scoop.bootstrap to "
        "install the Scoop package manager."
    )
    raise CommandExecutionError(err)

def scoop_version():
    """
    Returns the version of Scoop installed on the minion.

    CLI Example:

    .. code-block:: bash

        salt '*' scoop.scoop_version
    """
    if "scoop._version" in __context__:
        return __context__["scoop._version"]

    cmd = [_find_scoop()]
    cmd.append("-v")
    out = __salt__["cmd.run"](cmd, python_shell=False)
    # Scoop version is kept in first line. Other lines are bucket versions.
    __context__["scoop._version"] = re.search(r'(\d.\d.\d)', out.splitlines()[0].search())[0]

    return __context__["scoop._version"]

def bootstrap(source=None, user=None, password=None):
    """
    Download and install the latest version of the Scoop package manager
    using install script by Scoop authors.

    Scoop requires Windows PowerShell.
    
    .. note::
        When using custom location script, do not forget to modify
        url of downloading scoop zip.

    Args:

        source (str):
            The location of the ``.ps1`` file to run from an
            alternate location. This can be one of the following types of URLs:

            - salt://
            - http(s)://
            - ftp://
            - file:// - A local file on the system
            
        user (str):
            Install for defined user. Requries password, marked in 'password' argument.
            
        password (str):
            Password for user, marked in 'user' argument.

    Returns:
        str: The stdout of the Scoop installation script

    CLI Example:

    .. code-block:: bash

        # To bootstrap Scoop
        salt '*' scoop.bootstrap

        # To bootstrap Scoop offline from a file on the salt master
        salt '*' scoop.bootstrap source=salt://files/scoop.ps1

        # To bootstrap Scoop from a file on C:\\Temp
        salt '*' scoop.bootstrap source=C:\\Temp\\scoop.ps1
    """
    if user:
        if not password:
            return CommandExecutionError("User defined, but password is not")
    else:
        # We print this warning because scoop is typically installed for user
        # and global installed is not supported yet. See https://github.com/ScoopInstaller/Scoop/issues/3875
        log.warning("Installing scoop globally is not recommended")
    
    # Check if Scoop is already present in the path
    try:
        scoop_path = _find_scoop()
    except CommandExecutionError:
        scoop_path = None
    if scoop_path:
        return "Scoop found at {}".format(scoop_path)
    temp_dir = tempfile.gettempdir()

    # Make sure PowerShell is on the System
    powershell_info = __salt__["cmd.shell_info"](shell="powershell")
    if not powershell_info["installed"]:
        return CommandExecutionError("Powershell is not installed")

    # Define target / destination
    if source:
        url = source
    else:
        url = "https://raw.githubusercontent.com/scoopinstaller/install/master/install.ps1"
    dest = os.path.join(temp_dir, os.path.basename(url))

    # Download Scoop installer
    try:
        log.debug("Downloading Scoop: %s", os.path.basename(url))
        script = __salt__["cp.get_url"](path=url, dest=dest)
        log.debug("Script: %s", script)
    except MinionError:
        err = "Failed to download Scoop Installer"
        if source:
            err = "{0} from source"
        raise CommandExecutionError(err)

    # Run the Scoop bootstrap
    result=None
    log.debug("Installing Scoop locally: %s", script)
    # Script will anyway complain about admin rights, so we add this param
    scoop_args="-RunAsAdmin"
    if not user:
        # By default we use 'RunAsAdmin' option to install scoop globally
        # Also, we 'ScoopDir' option to install it to root directory, not internal user directory
        global_dir=os.path.join(os.path.abspath(os.sep), "Scoop")
        scoop_args=scoop_args+" ".join(["", "-ScoopDir", global_dir])

    result = __salt__["cmd.script"](
            script, cwd=os.path.dirname(script), shell="powershell", python_shell=True,
            runas=user, password=password, args=scoop_args
        )
    
    if not user and result["retcode"] == 0:
        log.debug("Adding Scoop to global PATH")
        __salt__["win_path.add"](path=os.path.join(global_dir, "shims"), rehash=True)
            
    if result["retcode"] != 0:
        err = "Bootstrapping Scoop failed:\n stderr: {},\n stdout: {}".format(result["stderr"], result["stdout"])
        raise CommandExecutionError(err)           

    return result["stdout"]

def unbootstrap():
    """
    Uninstall scoop from the system by doing the following:

    - Run 'scoop uninstall scoop'
    - Remove 'scoop' directory
    - Remove scoop from the path
    
    Args:
    
        user (str):
            Install for defined user. Requries password, marked in 'password' argument.
            
        password (str):
            Password for user, marked in 'user' argument.
            
    .. note::
        Uninstalling user-mode installed scoop is not supported
    Returns:
        list: A list of items that were removed, otherwise an empty list

    CLI Example:

    .. code-block:: bash

        salt * scoop.unbootstrap
    """
    #if user:
    #    if not password:
    #        return CommandExecutionError("User defined, but password is not")
    
    removed = []
    
    # First of all we try to use scoop internal remove
    try:
        scoop_path = _find_scoop()
    except CommandExecutionError:
        scoop_path = None
    # We try to use internal remove if scoop is detected
    if scoop_path:
        cmd = [scoop_path]
        cmd.append("uninstall")
        cmd.append("scoop")
        # Scoop asks "Are you sure? (yN):"
        # Also scoop always returns 1 error-code.
        out = __salt__["cmd.run"](cmd, python_shell=False, stdin='y', success_retcodes=[1])
        log.debug("Result of running internal scoop remove: {}".format(out))

    # Delete the Scoop directory
    known_paths = [
        os.path.join(os.environ.get("ProgramData"), "scoop"),
        os.path.join(os.environ.get("USERPROFILE"), "scoop"),
        os.path.join(os.environ.get("USERPROFILE"), ".config", "scoop", "config.conf"),
        os.path.join(os.path.abspath(os.sep), "Scoop")
    ]
    for path in known_paths:
        if os.path.exists(path):
            log.debug("Removing Scoop directory: %s", path)
            __salt__["file.remove"](path=path, force=True)
            removed.append("Removed Directory: {}".format(path))

    # Remove Scoop from the path:
    for path in __salt__["win_path.get_path"]():
        if "scoop" in path.lower():
            log.debug("Removing Scoop path item: %s", path)
            __salt__["win_path.remove"](path=path, rehash=True)
            removed.append("Removed Path Item: {}".format(path))

    return removed

def install(
    name,
    globally=None,
    no_cache=False,
    no_update_scoop=False,
    skip=False,
    arch=None
):
    """
    Instructs Scoop to install a package.

    Args:

        name (str):
            The name of the package to be installed. Only accepts a single
            argument. Required.

        globally (bool):
            Install the app globally. Default is None.

        no_cache (bool):
            Do not use the download cache. Default is False.

        no_update_scoop (bool):
            Install a specific version of the package. Defaults to latest
            version. Default is False.

        skip (bool):
            Skip hash validation (use with caution!). Default is False.

        arch (str):
            Define arch <32bit|64bit|arm64> of packages. Default is None.

    Returns:
        str: The output of the ``scoop`` command

    CLI Example:

    .. code-block:: bash

        salt '*' scoop.install <package name>
        salt '*' scoop.install <package name> globally=True
    """

    scoop_path = _find_scoop()
    
    if "," in name:
        pkg_to_install = name.split(",")
    else:
        pkg_to_install = [name]
    
    cmd = [scoop_path, "install"] + pkg_to_install
    if globally is not False and __context__["scoop._global"]:
        cmd.append("--global")
    if no_cache:
        cmd.append("--no-cache")
    if no_update_scoop:
        cmd.append("--no-update-scoop")
    if skip:
        cmd.append("--skip")
    if arch:
        cmd.extend(["--arch", arch])
        
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] != 0:
        err = "Running scoop failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)

    if name == "scoop":
        _clear_context()

    return result["stdout"]

def update(
    name=None,
    force=False,
    globally=None,
    independent=False,
    no_cache=False,
    skip=False,
    quiet=False,
    all_packages=False
):
    """
    Instructs Scoop to install a package.

    Args:

        name (str):
            The name of the package to be installed. Only accepts a single
            argument.

        force (bool):
            Force update even when there isn't a newer version.
            Default is False.

        globally (bool):
            Update a globally installed app. Default is None.

        independent (bool):
            Do not install dependencies automatically
            Default is False.

        no_cache (bool):
            Do not use the download cache. Default is False.

        skip (bool):
            Skip hash validation (use with caution!). Default is False.

        quiet (bool):
            Hide extraneous messages. Default is False.

        all_packages (bool):
            Update all apps. Then is set to True name is ignored.
            Default is False.

    Returns:
        str: The output of the ``scoop`` command

    CLI Example:

    .. code-block:: bash

        salt '*' scoop.update <package name>
        salt '*' scoop.update <package name> globally=True
    """

    scoop_path = _find_scoop()
    
    cmd = [scoop_path, "update"]
    
    if all_packages:
        name = '*'
    
    if "," in name:
        pkg_to_uninstall = name.split(",")
    else:
        pkg_to_uninstall = [name]
        
    cmd = cmd + pkg_to_uninstall
    
    if force:
        cmd.append("--force")
    if globally is not False and __context__["scoop._global"]:
        cmd.append("--global")
    if independent:
        cmd.append("--independent")
    if no_cache:
        cmd.append("--no-cache")
    if skip:
        cmd.append("--skip")
    if quiet:
        cmd.append("--quiet")
        
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] != 0:
        err = "Running scoop failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)

    if name == "scoop":
        _clear_context()

    return result["stdout"]

def uninstall(
    name,
    globally=None,
    purge=False
):
    """
    Instructs Scoop to uninstall a package.

    Args:

        name (str):
            The name of the package to be installed. Only accepts a single
            argument. Required.

        globally (bool):
            Install the app globally. Default is None.

        purge (bool):
            Remove all persistent data. Default is False.

    Returns:
        str: The output of the ``scoop`` command

    CLI Example:

    .. code-block:: bash

        salt '*' scoop.uninstall <package name>
        salt '*' scoop.uninstall <package name> globally=True
    """

    scoop_path = _find_scoop()
    
    if "," in name:
        pkg_to_uninstall = name.split(",")
    else:
        pkg_to_uninstall = [name]
        
    cmd = [scoop_path, "uninstall"] + pkg_to_uninstall
    if globally is not False and __context__["scoop._global"]:
        cmd.append("--global")
    if purge:
        cmd.append("--purge")
        
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] != 0:
        err = "Running scoop failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)

    if name == "scoop":
        _clear_context()

    return result["stdout"]

def list(query=None):
    """
    Instructs Scoop to list installed packages.

    Args:

        query (str):
            Query for listing

    Returns:
        str: The output of the ``scoop`` command

    CLI Example:

    .. code-block:: bash

        salt '*' scoop.list
        salt '*' scoop.list query=sudo
    """
    
    scoop_path = _find_scoop()
    
    cmd = [scoop_path, "list", query]
    
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] != 0:
        err = "Running scoop failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)
    
    return result["stdout"]

def export(config=False):
    """
    Instructs Scoop to export list of packages in JSON-wide.

    Args:

        config (bool):
            Also export Scoop config

    Returns:
        str: The output of the ``scoop`` command

    CLI Example:

    .. code-block:: bash

        salt '*' scoop.export
        salt '*' scoop.export config=True
    """
    
    scoop_path = _find_scoop()
    
    cmd = [scoop_path, "export"]
    
    if config:
        cmd.append("--config")
    
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] != 0:
        err = "Running scoop failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)
    
    return result["stdout"]

def bucket_add(name, url=None):
    """
    Add bucket using name and url or add known bucket.

    Args:

        name (str):
            Name of bucket. Required.

        url (str):
            URL of bucket.

    Returns:
        str: The output of the ``scoop`` command

    CLI Example:

    .. code-block:: bash

        salt '*' scoop.bucket_add extras
        salt '*' scoop.bucket_add name=extras url=https://github.com/ScoopInstaller/Extras.git
    """
    
    scoop_path = _find_scoop()
    
    cmd = [scoop_path, "bucket", "add", name]
    
    if url:
        cmd.append(url)
    
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] != 0:
        err = "Running scoop failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)
    
    return result["stdout"]

def bucket_rm(name):
    """
    Remove bucket using name.

    Args:

        name (str):
            Name of bucket. Required.

    Returns:
        str: The output of the ``scoop`` command

    CLI Example:

    .. code-block:: bash

        salt '*' scoop.bucket_del extras
    """
    
    scoop_path = _find_scoop()
    
    cmd = [scoop_path, "bucket", "rm", name]
    
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] != 0:
        err = "Running scoop failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)
    
    return result["stdout"]

def bucket_list():
    """
    List used buckets.

    Returns:
        str: The output of the ``scoop`` command

    CLI Example:

    .. code-block:: bash

        salt '*' scoop.bucket_list
    """
    
    scoop_path = _find_scoop()
    
    cmd = [scoop_path, "bucket", "list"]
    
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] != 0:
        err = "Running scoop failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)
    
    return result["stdout"]
