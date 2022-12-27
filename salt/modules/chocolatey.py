"""
A dead simple module wrapping calls to the Chocolatey package manager
(http://chocolatey.org)

.. versionadded:: 2014.1.0
"""

import logging
import os
import re
import tempfile

from requests.structures import CaseInsensitiveDict

import salt.utils.data
import salt.utils.platform
from salt.exceptions import (
    CommandExecutionError,
    CommandNotFoundError,
    MinionError,
    SaltInvocationError,
)
from salt.utils.data import CaseInsensitiveDict
from salt.utils.versions import Version

log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list"}

__virtualname__ = "chocolatey"


def __virtual__():
    """
    Confirm this module is on a Windows system running Vista or later.

    While it is possible to make Chocolatey run under XP and Server 2003 with
    an awful lot of hassle (e.g. SSL is completely broken), the PowerShell shim
    for simulating UAC forces a GUI prompt, and is not compatible with
    salt-minion running as SYSTEM.
    """
    if not salt.utils.platform.is_windows():
        return (False, "Cannot load module chocolatey: Chocolatey requires Windows")

    if __grains__["osrelease"] in ("XP", "2003Server"):
        return (
            False,
            "Cannot load module chocolatey: Chocolatey requires Windows Vista or later",
        )

    return __virtualname__


def _clear_context():
    """
    Clear variables stored in __context__. Run this function when a new version
    of chocolatey is installed.
    """
    choco_items = [x for x in __context__ if x.startswith("chocolatey.")]
    for var in choco_items:
        __context__.pop(var)


def _yes():
    """
    Returns ['--yes'] if on v0.9.9.0 or later, otherwise returns an empty list
    Confirm all prompts (--yes_ is available on v0.9.9.0 or later
    """
    if "chocolatey._yes" in __context__:
        return __context__["chocolatey._yes"]
    if Version(chocolatey_version()) >= Version("0.9.9"):
        answer = ["--yes"]
    else:
        answer = []
    __context__["chocolatey._yes"] = answer
    return __context__["chocolatey._yes"]


def _no_progress():
    """
    Returns ['--no-progress'] if on v0.10.4 or later, otherwise returns an
    empty list
    """
    if "chocolatey._no_progress" in __context__:
        return __context__["chocolatey._no_progress"]
    if Version(chocolatey_version()) >= Version("0.10.4"):
        answer = ["--no-progress"]
    else:
        log.warning("--no-progress unsupported in choco < 0.10.4")
        answer = []
    __context__["chocolatey._no_progress"] = answer
    return __context__["chocolatey._no_progress"]


def _find_chocolatey():
    """
    Returns the full path to chocolatey.bat on the host.
    """
    # Check context
    if "chocolatey._path" in __context__:
        return __context__["chocolatey._path"]

    # Check the path
    choc_path = __salt__["cmd.which"]("chocolatey.exe")
    if choc_path:
        __context__["chocolatey._path"] = choc_path
        return __context__["chocolatey._path"]

    # Check in common locations
    choc_defaults = [
        os.path.join(
            os.environ.get("ProgramData"), "Chocolatey", "bin", "chocolatey.exe"
        ),
        os.path.join(
            os.environ.get("SystemDrive"), "Chocolatey", "bin", "chocolatey.bat"
        ),
    ]
    for choc_exe in choc_defaults:
        if os.path.isfile(choc_exe):
            __context__["chocolatey._path"] = choc_exe
            return __context__["chocolatey._path"]

    # Not installed, raise an error
    err = (
        "Chocolatey not installed. Use chocolatey.bootstrap to "
        "install the Chocolatey package manager."
    )
    raise CommandExecutionError(err)


def chocolatey_version():
    """
    Returns the version of Chocolatey installed on the minion.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.chocolatey_version
    """
    if "chocolatey._version" in __context__:
        return __context__["chocolatey._version"]

    cmd = [_find_chocolatey()]
    cmd.append("-v")
    out = __salt__["cmd.run"](cmd, python_shell=False)
    __context__["chocolatey._version"] = out

    return __context__["chocolatey._version"]


def bootstrap(force=False, source=None):
    """
    Download and install the latest version of the Chocolatey package manager
    via the official bootstrap.

    Chocolatey requires Windows PowerShell and the .NET v4.0 runtime. Depending
    on the host's version of Windows, chocolatey.bootstrap will attempt to
    ensure these prerequisites are met by downloading and executing the
    appropriate installers from Microsoft.

    .. note::
        If PowerShell is installed, you may have to restart the host machine for
        Chocolatey to work.

    .. note::
        If you're installing offline using the source parameter, the PowerShell
        and .NET requirements must already be met on the target. This shouldn't
        be a problem on Windows versions 2012/8 and later

    Args:

        force (bool):
            Run the bootstrap process even if Chocolatey is found in the path.

        source (str):
            The location of the ``.nupkg`` file or ``.ps1`` file to run from an
            alternate location. This can be one of the following types of URLs:

            - salt://
            - http(s)://
            - ftp://
            - file:// - A local file on the system

            .. versionadded:: 3001

    Returns:
        str: The stdout of the Chocolatey installation script

    CLI Example:

    .. code-block:: bash

        # To bootstrap Chocolatey
        salt '*' chocolatey.bootstrap
        salt '*' chocolatey.bootstrap force=True

        # To bootstrap Chocolatey offline from a file on the salt master
        salt '*' chocolatey.bootstrap source=salt://files/chocolatey.nupkg

        # To bootstrap Chocolatey from a file on C:\\Temp
        salt '*' chocolatey.bootstrap source=C:\\Temp\\chocolatey.nupkg
    """
    # Check if Chocolatey is already present in the path
    try:
        choc_path = _find_chocolatey()
    except CommandExecutionError:
        choc_path = None
    if choc_path and not force:
        return "Chocolatey found at {}".format(choc_path)

    temp_dir = tempfile.gettempdir()

    # Make sure PowerShell is on the System if we're passing source
    # Vista and Windows Server 2008 do not have Powershell installed
    powershell_info = __salt__["cmd.shell_info"](shell="powershell")
    if not powershell_info["installed"]:
        # The following lookup tables are required to determine the correct
        # download required to install PowerShell. That's right, there's more
        # than one! You're welcome.
        ps_downloads = {
            (
                "Vista",
                "x86",
            ): "http://download.microsoft.com/download/A/7/5/A75BC017-63CE-47D6-8FA4-AFB5C21BAC54/Windows6.0-KB968930-x86.msu",
            (
                "Vista",
                "AMD64",
            ): "http://download.microsoft.com/download/3/C/8/3C8CF51E-1D9D-4DAA-AAEA-5C48D1CD055C/Windows6.0-KB968930-x64.msu",
            (
                "2008Server",
                "x86",
            ): "http://download.microsoft.com/download/F/9/E/F9EF6ACB-2BA8-4845-9C10-85FC4A69B207/Windows6.0-KB968930-x86.msu",
            (
                "2008Server",
                "AMD64",
            ): "http://download.microsoft.com/download/2/8/6/28686477-3242-4E96-9009-30B16BED89AF/Windows6.0-KB968930-x64.msu",
        }

        # PowerShell needs to be installed on older systems (Vista, 2008Server)
        if (__grains__["osrelease"], __grains__["cpuarch"]) in ps_downloads:

            # Install the appropriate release of PowerShell v2.0
            url = ps_downloads[(__grains__["osrelease"], __grains__["cpuarch"])]
            dest = os.path.join(temp_dir, os.path.basename(url))
            # Download the KB
            try:
                log.debug("Downloading PowerShell...")
                __salt__["cp.get_url"](path=url, dest=dest)
            except MinionError:
                err = "Failed to download PowerShell KB for {}".format(
                    __grains__["osrelease"]
                )
                if source:
                    raise CommandExecutionError(
                        "{}: PowerShell is required to bootstrap Chocolatey "
                        "with Source".format(err)
                    )
                raise CommandExecutionError(err)
            # Install the KB
            cmd = [dest, "/quiet", "/norestart"]
            log.debug("Installing PowerShell...")
            result = __salt__["cmd.run_all"](cmd, python_shell=False)
            if result["retcode"] != 0:
                err = (
                    "Failed to install PowerShell KB. For more information "
                    "run the installer manually on the host"
                )
                raise CommandExecutionError(err)
        else:
            err = "Windows PowerShell Installation not available"
            raise CommandNotFoundError(err)

    # Check that .NET v4.0+ is installed
    # Windows 7 / Windows Server 2008 R2 and below do not come with at least
    # .NET v4.0 installed
    if not __utils__["dotnet.version_at_least"](version="4"):
        # It took until .NET v4.0 for Microsoft got the hang of making
        # installers, this should work under any version of Windows
        url = "http://download.microsoft.com/download/1/B/E/1BE39E79-7E39-46A3-96FF-047F95396215/dotNetFx40_Full_setup.exe"
        dest = os.path.join(temp_dir, os.path.basename(url))
        # Download the .NET Framework 4 web installer
        try:
            log.debug("Downloading .NET v4.0...")
            __salt__["cp.get_url"](path=url, dest=dest)
        except MinionError:
            err = "Failed to download .NET v4.0 Web Installer"
            if source:
                err = (
                    "{}: .NET v4.0+ is required to bootstrap "
                    "Chocolatey with Source".format(err)
                )
            raise CommandExecutionError(err)

        # Run the .NET Framework 4 web installer
        cmd = [dest, "/q", "/norestart"]
        log.debug("Installing .NET v4.0...")
        result = __salt__["cmd.run_all"](cmd, python_shell=False)
        if result["retcode"] != 0:
            err = (
                "Failed to install .NET v4.0 failed. For more information "
                "run the installer manually on the host"
            )
            raise CommandExecutionError(err)

    # Define target / destination
    if source:
        url = source
    else:
        url = "https://chocolatey.org/install.ps1"
    dest = os.path.join(temp_dir, os.path.basename(url))

    # Download Chocolatey installer
    try:
        log.debug("Downloading Chocolatey: %s", os.path.basename(url))
        script = __salt__["cp.get_url"](path=url, dest=dest)
        log.debug("Script: %s", script)
    except MinionError:
        err = "Failed to download Chocolatey Installer"
        if source:
            err = "{0} from source"
        raise CommandExecutionError(err)

    # If this is a nupkg download we need to unzip it first
    if os.path.splitext(os.path.basename(dest))[1] == ".nupkg":
        log.debug("Unzipping Chocolatey: %s", dest)
        __salt__["archive.unzip"](
            zip_file=dest,
            dest=os.path.join(os.path.dirname(dest), "chocolatey"),
            extract_perms=False,
        )
        script = os.path.join(
            os.path.dirname(dest), "chocolatey", "tools", "chocolateyInstall.ps1"
        )

    if not os.path.exists(script):
        raise CommandExecutionError(
            "Failed to find Chocolatey installation script: {}".format(script)
        )

    # Run the Chocolatey bootstrap
    log.debug("Installing Chocolatey: %s", script)
    result = __salt__["cmd.script"](
        script, cwd=os.path.dirname(script), shell="powershell", python_shell=True
    )
    if result["retcode"] != 0:
        err = "Bootstrapping Chocolatey failed: {}".format(result["stderr"])
        raise CommandExecutionError(err)

    return result["stdout"]


def unbootstrap():
    """
    Uninstall chocolatey from the system by doing the following:

    .. versionadded:: 3001

    - Delete the Chocolatey Directory
    - Remove Chocolatey from the path
    - Remove Chocolatey environment variables

    Returns:
        list: A list of items that were removed, otherwise an empty list

    CLI Example:

    .. code-block:: bash

        salt * chocolatey.unbootstrap
    """
    removed = []

    # Delete the Chocolatey directory
    choco_dir = os.environ.get("ChocolateyInstall", False)
    if choco_dir:
        if os.path.exists(choco_dir):
            log.debug("Removing Chocolatey directory: %s", choco_dir)
            __salt__["file.remove"](path=choco_dir, force=True)
            removed.append("Removed Directory: {}".format(choco_dir))
    else:
        known_paths = [
            os.path.join(os.environ.get("ProgramData"), "Chocolatey"),
            os.path.join(os.environ.get("SystemDrive"), "Chocolatey"),
        ]
        for path in known_paths:
            if os.path.exists(path):
                log.debug("Removing Chocolatey directory: %s", path)
                __salt__["file.remove"](path=path, force=True)
                removed.append("Removed Directory: {}".format(path))

    # Delete all Chocolatey environment variables
    for env_var in __salt__["environ.items"]():
        if env_var.lower().startswith("chocolatey"):
            log.debug("Removing Chocolatey environment variable: %s", env_var)
            __salt__["environ.setval"](
                key=env_var, val=False, false_unsets=True, permanent="HKLM"
            )
            __salt__["environ.setval"](
                key=env_var, val=False, false_unsets=True, permanent="HKCU"
            )
            removed.append("Removed Environment Var: {}".format(env_var))

    # Remove Chocolatey from the path:
    for path in __salt__["win_path.get_path"]():
        if "chocolatey" in path.lower():
            log.debug("Removing Chocolatey path item: %s", path)
            __salt__["win_path.remove"](path=path, rehash=True)
            removed.append("Removed Path Item: {}".format(path))

    return removed


def list_(
    narrow=None,
    all_versions=False,
    pre_versions=False,
    source=None,
    local_only=False,
    exact=False,
):
    """
    Instructs Chocolatey to pull a vague package list from the repository.

    Args:

        narrow (str):
            Term used to narrow down results. Searches against
            name/description/tag. Default is None.

        all_versions (bool):
            Display all available package versions in results. Default is False.

        pre_versions (bool):
            Display pre-release packages in results. Default is False.

        source (str):
            Chocolatey repository (directory, share or remote URL feed) the
            package comes from. Defaults to the official Chocolatey feed if
            None is passed. Default is None.

        local_only (bool):
            Display packages only installed locally. Default is False.

        exact (bool):
            Display only packages that match ``narrow`` exactly. Default is
            False.

            .. versionadded:: 2017.7.0

    Returns:
        dict: A dictionary of results.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.list <narrow>
        salt '*' chocolatey.list <narrow> all_versions=True
    """
    choc_path = _find_chocolatey()
    cmd = [choc_path, "list"]
    if narrow:
        cmd.append(narrow)
    if salt.utils.data.is_true(all_versions):
        cmd.append("--allversions")
    if salt.utils.data.is_true(pre_versions):
        cmd.append("--prerelease")
    if source:
        cmd.extend(["--source", source])
    if local_only:
        cmd.append("--local-only")
    if exact:
        cmd.append("--exact")

    # This is needed to parse the output correctly
    cmd.append("--limit-output")

    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    # Chocolatey introduced Enhanced Exit Codes starting with version 0.10.12
    # Exit Code 2 means there were no results, but is not a failure
    # This may start to effect other functions in the future as Chocolatey
    # moves more functions to this new paradigm
    # https://github.com/chocolatey/choco/issues/1758
    if result["retcode"] not in [0, 2]:
        err = "Running chocolatey failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)

    ret = CaseInsensitiveDict({})
    pkg_re = re.compile(r"(\S+)\|(\S+)")
    for line in result["stdout"].split("\n"):
        if line.startswith("No packages"):
            return ret
        for name, ver in pkg_re.findall(line):
            if "chocolatey" in name:
                continue
            if name not in ret:
                ret[name] = []
            ret[name].append(ver)

    return ret


def list_webpi():
    """
    Instructs Chocolatey to pull a full package list from the Microsoft Web PI
    repository.

    Returns:
        str: List of webpi packages

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.list_webpi
    """
    choc_path = _find_chocolatey()
    cmd = [choc_path, "list", "--source", "webpi"]
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] != 0:
        err = "Running chocolatey failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)

    return result["stdout"]


def list_windowsfeatures():
    """
    Instructs Chocolatey to pull a full package list from the Windows Features
    list, via the Deployment Image Servicing and Management tool.

    Returns:
        str: List of Windows Features

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.list_windowsfeatures
    """
    choc_path = _find_chocolatey()
    cmd = [choc_path, "list", "--source", "windowsfeatures"]
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] != 0:
        err = "Running chocolatey failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)

    return result["stdout"]


def install(
    name,
    version=None,
    source=None,
    force=False,
    pre_versions=False,
    install_args=None,
    override_args=False,
    force_x86=False,
    package_args=None,
    allow_multiple=False,
    execution_timeout=None,
):
    """
    Instructs Chocolatey to install a package.

    Args:

        name (str):
            The name of the package to be installed. Only accepts a single
            argument. Required.

        version (str):
            Install a specific version of the package. Defaults to latest
            version. Default is None.

        source (str):
            Chocolatey repository (directory, share or remote URL feed) the
            package comes from. Defaults to the official Chocolatey feed.
            Default is None.

            Alternate Sources:

            - cygwin
            - python
            - ruby
            - webpi
            - windowsfeatures

        force (bool):
            Reinstall the current version of an existing package. Do not use
            with ``allow_multiple``. Default is False.

        pre_versions (bool):
            Include pre-release packages. Default is False.

        install_args (str):
            A list of install arguments you want to pass to the installation
            process i.e product key or feature list. Default is None.

        override_args (bool):
            Set to true if you want to override the original install arguments
            (for the native installer) in the package and use your own. When
            this is set to False install_args will be appended to the end of the
            default arguments. Default is None.

        force_x86 (bool):
            Force x86 (32bit) installation on 64 bit systems. Default is False.

        package_args (str):
            Arguments you want to pass to the package. Default is None.

        allow_multiple (bool):
            Allow multiple versions of the package to be installed. Do not use
            with ``force``. Does not work with all packages. Default is False.

            .. versionadded:: 2017.7.0

        execution_timeout (str):
            Chocolatey execution timeout value you want to pass to the
            installation process. Default is None.

            .. versionadded:: 2018.3.0

    Returns:
        str: The output of the ``chocolatey`` command

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install <package name>
        salt '*' chocolatey.install <package name> version=<package version>
        salt '*' chocolatey.install <package name> install_args=<args> override_args=True
    """
    if force and allow_multiple:
        raise SaltInvocationError(
            "Cannot use 'force' in conjunction with 'allow_multiple'"
        )

    choc_path = _find_chocolatey()
    # chocolatey helpfully only supports a single package argument
    # CORRECTION: it also supports multiple package names separated by spaces
    # but any additional arguments apply to ALL packages specified
    cmd = [choc_path, "install", name]
    if version:
        cmd.extend(["--version", version])
    if source:
        cmd.extend(["--source", source])
    if salt.utils.data.is_true(force):
        cmd.append("--force")
    if salt.utils.data.is_true(pre_versions):
        cmd.append("--prerelease")
    if install_args:
        cmd.extend(["--installarguments", install_args])
    if override_args:
        cmd.append("--overridearguments")
    if force_x86:
        cmd.append("--forcex86")
    if package_args:
        cmd.extend(["--packageparameters", package_args])
    if allow_multiple:
        cmd.append("--allow-multiple")
    if execution_timeout:
        cmd.extend(["--execution-timeout", execution_timeout])

    # Salt doesn't need to see the progress
    cmd.extend(_no_progress())
    cmd.extend(_yes())
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] not in [0, 1641, 3010]:
        err = "Running chocolatey failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)

    if name == "chocolatey":
        _clear_context()

    return result["stdout"]


def install_cygwin(name, install_args=None, override_args=False):
    """
    Instructs Chocolatey to install a package via Cygwin.

    name
        The name of the package to be installed. Only accepts a single argument.

    install_args
        A list of install arguments you want to pass to the installation process
        i.e product key or feature list

    override_args
        Set to true if you want to override the original install arguments (for
        the native installer) in the package and use your own. When this is set
        to False install_args will be appended to the end of the default
        arguments

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_cygwin <package name>
        salt '*' chocolatey.install_cygwin <package name> install_args=<args> override_args=True
    """
    return install(
        name, source="cygwin", install_args=install_args, override_args=override_args
    )


def install_gem(name, version=None, install_args=None, override_args=False):
    """
    Instructs Chocolatey to install a package via Ruby's Gems.

    name
        The name of the package to be installed. Only accepts a single argument.

    version
        Install a specific version of the package. Defaults to latest version
        available.

    install_args
        A list of install arguments you want to pass to the installation process
        i.e product key or feature list

    override_args
        Set to true if you want to override the original install arguments (for
        the native installer) in the package and use your own. When this is set
        to False install_args will be appended to the end of the default
        arguments

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_gem <package name>
        salt '*' chocolatey.install_gem <package name> version=<package version>
        salt '*' chocolatey.install_gem <package name> install_args=<args> override_args=True
    """
    return install(
        name,
        version=version,
        source="ruby",
        install_args=install_args,
        override_args=override_args,
    )


def install_missing(name, version=None, source=None):
    """
    Instructs Chocolatey to install a package if it doesn't already exist.

    .. versionchanged:: 2014.7.0
        If the minion has Chocolatey >= 0.9.8.24 installed, this function calls
        :mod:`chocolatey.install <salt.modules.chocolatey.install>` instead, as
        ``installmissing`` is deprecated as of that version and will be removed
        in Chocolatey 1.0.

    name
        The name of the package to be installed. Only accepts a single argument.

    version
        Install a specific version of the package. Defaults to latest version
        available.

    source
        Chocolatey repository (directory, share or remote URL feed) the package
        comes from. Defaults to the official Chocolatey feed.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_missing <package name>
        salt '*' chocolatey.install_missing <package name> version=<package version>
    """
    if Version(chocolatey_version()) >= Version("0.9.8.24"):
        log.warning("installmissing is deprecated, using install")
        return install(name, version=version)

    # chocolatey helpfully only supports a single package argument
    cmd = [_find_chocolatey(), "installmissing", name]
    if version:
        cmd.extend(["--version", version])
    if source:
        cmd.extend(["--source", source])
    # Shouldn't need this as this code should never run on v0.9.9 and newer
    cmd.extend(_yes())
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] != 0:
        err = "Running chocolatey failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)

    return result["stdout"]


def install_python(name, version=None, install_args=None, override_args=False):
    """
    Instructs Chocolatey to install a package via Python's easy_install.

    name
        The name of the package to be installed. Only accepts a single argument.

    version
        Install a specific version of the package. Defaults to latest version
        available.

    install_args
        A list of install arguments you want to pass to the installation process
        i.e product key or feature list

    override_args
        Set to true if you want to override the original install arguments (for
        the native installer) in the package and use your own. When this is set
        to False install_args will be appended to the end of the default
        arguments

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_python <package name>
        salt '*' chocolatey.install_python <package name> version=<package version>
        salt '*' chocolatey.install_python <package name> install_args=<args> override_args=True
    """
    return install(
        name,
        version=version,
        source="python",
        install_args=install_args,
        override_args=override_args,
    )


def install_windowsfeatures(name):
    """
    Instructs Chocolatey to install a Windows Feature via the Deployment Image
    Servicing and Management tool.

    name
        The name of the feature to be installed. Only accepts a single argument.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_windowsfeatures <package name>
    """
    return install(name, source="windowsfeatures")


def install_webpi(name, install_args=None, override_args=False):
    """
    Instructs Chocolatey to install a package via the Microsoft Web PI service.

    name
        The name of the package to be installed. Only accepts a single argument.

    install_args
        A list of install arguments you want to pass to the installation process
        i.e product key or feature list

    override_args
        Set to true if you want to override the original install arguments (for
        the native installer) in the package and use your own. When this is set
        to False install_args will be appended to the end of the default
        arguments

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_webpi <package name>
        salt '*' chocolatey.install_webpi <package name> install_args=<args> override_args=True
    """
    return install(
        name, source="webpi", install_args=install_args, override_args=override_args
    )


def uninstall(name, version=None, uninstall_args=None, override_args=False):
    """
    Instructs Chocolatey to uninstall a package.

    name
        The name of the package to be uninstalled. Only accepts a single
        argument.

    version
        Uninstalls a specific version of the package. Defaults to latest version
        installed.

    uninstall_args
        A list of uninstall arguments you want to pass to the uninstallation
        process i.e product key or feature list

    override_args
        Set to true if you want to override the original uninstall arguments
        (for the native uninstaller) in the package and use your own. When this
        is set to False uninstall_args will be appended to the end of the
        default arguments

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.uninstall <package name>
        salt '*' chocolatey.uninstall <package name> version=<package version>
        salt '*' chocolatey.uninstall <package name> version=<package version> uninstall_args=<args> override_args=True
    """
    # chocolatey helpfully only supports a single package argument
    cmd = [_find_chocolatey(), "uninstall", name]
    if version:
        cmd.extend(["--version", version])
    if uninstall_args:
        cmd.extend(["--uninstallarguments", uninstall_args])
    if override_args:
        cmd.extend(["--overridearguments"])
    cmd.extend(_yes())
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] not in [0, 1605, 1614, 1641]:
        err = "Running chocolatey failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)

    return result["stdout"]


def upgrade(
    name,
    version=None,
    source=None,
    force=False,
    pre_versions=False,
    install_args=None,
    override_args=False,
    force_x86=False,
    package_args=None,
):
    """
    .. versionadded:: 2016.3.4

    Instructs Chocolatey to upgrade packages on the system. (update is being
    deprecated). This command will install the package if not installed.

    Args:

        name (str):
            The name of the package to update, or "all" to update everything
            installed on the system.

        version (str):
            Install a specific version of the package. Defaults to latest
            version.

        source (str):
            Chocolatey repository (directory, share or remote URL feed) the
            package comes from. Defaults to the official Chocolatey feed.

        force (bool):
            Reinstall the **same** version already installed

        pre_versions (bool):
            Include pre-release packages in comparison. Defaults to False.

        install_args (str):
            A list of install arguments you want to pass to the installation
            process i.e product key or feature list

        override_args (str):
            Set to true if you want to override the original install arguments
            (for the native installer) in the package and use your own. When
            this is set to False install_args will be appended to the end of the
            default arguments

        force_x86
            Force x86 (32bit) installation on 64 bit systems. Defaults to false.

        package_args
            A list of arguments you want to pass to the package

    Returns:
        str: Results of the ``chocolatey`` command

    CLI Example:

    .. code-block:: bash

        salt "*" chocolatey.upgrade all
        salt "*" chocolatey.upgrade <package name> pre_versions=True
    """
    # chocolatey helpfully only supports a single package argument
    cmd = [_find_chocolatey(), "upgrade", name]
    if version:
        cmd.extend(["--version", version])
    if source:
        cmd.extend(["--source", source])
    if salt.utils.data.is_true(force):
        cmd.append("--force")
    if salt.utils.data.is_true(pre_versions):
        cmd.append("--prerelease")
    if install_args:
        cmd.extend(["--installarguments", install_args])
    if override_args:
        cmd.append("--overridearguments")
    if force_x86:
        cmd.append("--forcex86")
    if package_args:
        cmd.extend(["--packageparameters", package_args])

    # Salt doesn't need to see the progress
    cmd.extend(_no_progress())
    cmd.extend(_yes())

    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] not in [0, 1641, 3010]:
        err = "Running chocolatey failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)

    return result["stdout"]


def update(name, source=None, pre_versions=False):
    """
    Instructs Chocolatey to update packages on the system.

    name
        The name of the package to update, or "all" to update everything
        installed on the system.

    source
        Chocolatey repository (directory, share or remote URL feed) the package
        comes from. Defaults to the official Chocolatey feed.

    pre_versions
        Include pre-release packages in comparison. Defaults to False.

    CLI Example:

    .. code-block:: bash

        salt "*" chocolatey.update all
        salt "*" chocolatey.update <package name> pre_versions=True
    """
    # chocolatey helpfully only supports a single package argument
    if Version(chocolatey_version()) >= Version("0.9.8.24"):
        log.warning("update is deprecated, using upgrade")
        return upgrade(name, source=source, pre_versions=pre_versions)

    cmd = [_find_chocolatey(), "update", name]
    if source:
        cmd.extend(["--source", source])
    if salt.utils.data.is_true(pre_versions):
        cmd.append("--prerelease")

    # Salt doesn't need to see the progress
    cmd.extend(_no_progress())
    cmd.extend(_yes())
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] not in [0, 1641, 3010]:
        err = "Running chocolatey failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)

    return result["stdout"]


def version(name, check_remote=False, source=None, pre_versions=False):
    """
    Instructs Chocolatey to check an installed package version, and optionally
    compare it to one available from a remote feed.

    Args:

        name (str):
            The name of the package to check. Required.

        check_remote (bool):
            Get the version number of the latest package from the remote feed.
            Default is False.

        source (str):
            Chocolatey repository (directory, share or remote URL feed) the
            package comes from. Defaults to the official Chocolatey feed.
            Default is None.

        pre_versions (bool):
            Include pre-release packages in comparison. Default is False.

    Returns:
        dict: A dictionary of currently installed software and versions

    CLI Example:

    .. code-block:: bash

        salt "*" chocolatey.version <package name>
        salt "*" chocolatey.version <package name> check_remote=True
    """
    installed = list_(narrow=name, local_only=True)

    packages = {}
    lower_name = name.lower()
    for pkg in installed:
        if lower_name in pkg.lower():
            packages[pkg] = installed[pkg]

    if check_remote:
        available = list_(narrow=name, pre_versions=pre_versions, source=source)

        for pkg in packages:
            # Grab the current version from the package that was installed
            packages[pkg] = {"installed": installed[pkg]}

            # If there's a remote package available, then also include that
            # in the dictionary that we return.
            if pkg in available:
                packages[pkg]["available"] = available[pkg]

    return packages


def add_source(name, source_location, username=None, password=None, priority=None):
    """
    Instructs Chocolatey to add a source.

    name
        The name of the source to be added as a chocolatey repository.

    source
        Location of the source you want to work with.

    username
        Provide username for chocolatey sources that need authentication
        credentials.

    password
        Provide password for chocolatey sources that need authentication
        credentials.

    priority
        The priority order of this source as compared to other sources,
        lower is better. Defaults to 0 (no priority). All priorities
        above 0 will be evaluated first, then zero-based values will be
        evaluated in config file order.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.add_source <source name> <source_location>
        salt '*' chocolatey.add_source <source name> <source_location> priority=100
        salt '*' chocolatey.add_source <source name> <source_location> user=<user> password=<password>

    """
    cmd = [
        _find_chocolatey(),
        "sources",
        "add",
        "--name",
        name,
        "--source",
        source_location,
    ]
    if username:
        cmd.extend(["--user", username])
    if password:
        cmd.extend(["--password", password])
    if priority:
        cmd.extend(["--priority", priority])
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] != 0:
        err = "Running chocolatey failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)

    return result["stdout"]


def _change_source_state(name, state):
    """
    Instructs Chocolatey to change the state of a source.

    name
        Name of the repository to affect.

    state
        State in which you want the chocolatey repository.

    """
    cmd = [_find_chocolatey(), "source", state, "--name", name]
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if result["retcode"] != 0:
        err = "Running chocolatey failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)

    return result["stdout"]


def enable_source(name):
    """
    Instructs Chocolatey to enable a source.

    name
        Name of the source repository to enable.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.enable_source <name>

    """
    return _change_source_state(name, "enable")


def disable_source(name):
    """
    Instructs Chocolatey to disable a source.

    name
        Name of the source repository to disable.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.disable_source <name>
    """
    return _change_source_state(name, "disable")


def list_sources():
    """
    Returns the list of installed sources.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.list_sources
    """
    choc_path = _find_chocolatey()
    cmd = [choc_path, "source"]

    # This is needed to parse the output correctly
    cmd.append("--limit-output")

    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    # Chocolatey introduced Enhanced Exit Codes starting with version 0.10.12
    # Exit Code 2 means there were no results, but is not a failure
    # This may start to effect other functions in the future as Chocolatey
    # moves more functions to this new paradigm
    # https://github.com/chocolatey/choco/issues/1758
    if result["retcode"] not in [0, 2]:
        err = "Running chocolatey failed: {}".format(result["stdout"])
        raise CommandExecutionError(err)

    ret = CaseInsensitiveDict({})
    pkg_re = re.compile(r"(.*)\|(.*)\|(.*)\|(.*)\|.*\|.*\|.*\|.*\|.*")
    for line in result["stdout"].split("\n"):
        for name, url, disabled, user in pkg_re.findall(line):
            if name not in ret:
                ret[name] = {"URL: ": url, "Disabled": disabled, "User: ": user}

    return ret
