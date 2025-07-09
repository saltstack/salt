"""
Common functions for working with powershell

.. note:: The PSModulePath environment variable should be set to the default
    location for PowerShell modules. This applies to all OS'es that support
    powershell. If not set, then Salt will attempt to use some default paths.
    If Salt can't find your modules, ensure that the PSModulePath is set and
    pointing to all locations of your Powershell modules.
"""

import logging
import os

import salt.utils.path

log = logging.getLogger(__name__)


def module_exists(name):
    """
    Check if a module exists on the system.

    Use this utility instead of attempting to import the module with powershell.
    Using powershell to try to import the module is expensive.

    Args:

        name (str):
            The name of the module to check

    Returns:
        bool: True if present, otherwise returns False

    Example:

    .. code-block:: python

        import salt.utils.powershell
        exists = salt.utils.powershell.module_exists('ServerManager')
    """
    return name in get_modules()


def get_modules():
    """
    Get a list of the PowerShell modules which are potentially available to be
    imported. The intent is to mimic the functionality of ``Get-Module
    -ListAvailable | Select-Object -Expand Name``, without the delay of loading
    PowerShell to do so.

    Returns:
        list: A list of modules available to Powershell

    Example:

    .. code-block:: python

        import salt.utils.powershell
        modules = salt.utils.powershell.get_modules()
    """
    ret = list()
    valid_extensions = (".psd1", ".psm1", ".cdxml", ".xaml", ".dll")
    # need to create an info function to get PS information including version
    # __salt__ is not available from salt.utils... need to create a salt.util
    # for the registry to avoid loading powershell to get the version
    # not sure how to get the powershell version in linux outside of powershell
    # if running powershell to get version need to use subprocess.Popen
    # That information will be loaded here
    # ps_version = info()['version_raw']
    root_paths = []

    home_dir = os.environ.get("HOME", os.environ.get("HOMEPATH"))
    system_dir = "{}\\System32".format(os.environ.get("WINDIR", "C:\\Windows"))
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    default_paths = [
        f"{home_dir}/.local/share/powershell/Modules",
        # Once version is available, these can be enabled
        # '/opt/microsoft/powershell/{0}/Modules'.format(ps_version),
        # '/usr/local/microsoft/powershell/{0}/Modules'.format(ps_version),
        "/usr/local/share/powershell/Modules",
        f"{system_dir}\\WindowsPowerShell\\v1.0\\Modules\\",
        f"{program_files}\\WindowsPowerShell\\Modules",
    ]
    default_paths = ";".join(default_paths)

    ps_module_path = os.environ.get("PSModulePath", default_paths)

    # Check if defaults exist, add them if they do
    ps_module_path = ps_module_path.split(";")
    for item in ps_module_path:
        if os.path.exists(item):
            root_paths.append(item)

    # Did we find any, if not log the error and return
    if not root_paths:
        log.error("Default paths not found")
        return ret

    for root_path in root_paths:

        # only recurse directories
        if not os.path.isdir(root_path):
            continue

        # get a list of all files in the root_path
        for root_dir, sub_dirs, file_names in salt.utils.path.os_walk(root_path):
            for file_name in file_names:
                base_name, file_extension = os.path.splitext(file_name)

                # If a module file or module manifest is present, check if
                # the base name matches the directory name.

                if file_extension.lower() in valid_extensions:
                    dir_name = os.path.basename(os.path.normpath(root_dir))

                    # Stop recursion once we find a match, and use
                    # the capitalization from the directory name.
                    if dir_name not in ret and base_name.lower() == dir_name.lower():
                        del sub_dirs[:]
                        ret.append(dir_name)

    return ret
