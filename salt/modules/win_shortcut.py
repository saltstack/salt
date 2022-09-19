"""
Execution module for creating shortcuts on Windows. Handles file shortcuts
(`.lnk`) and url shortcuts (`.url`). Allows for the configuration of icons and
hot keys on file shortcuts. Changing the icon and hot keys are unsupported for
url shortcuts.

.. versionadded:: 3005
"""
# https://docs.microsoft.com/en-us/troubleshoot/windows-client/admin-development/create-desktop-shortcut-with-wsh
# https://docs.microsoft.com/en-us/previous-versions/windows/internet-explorer/ie-developer/windows-scripting/f5y78918(v=vs.84)
import logging
import os
import time

import salt.utils.path
import salt.utils.platform
import salt.utils.winapi
from salt.exceptions import CommandExecutionError

HAS_WIN32 = False
if salt.utils.platform.is_windows():
    import win32com.client

    HAS_WIN32 = True

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "shortcut"


WINDOW_STYLE = {
    1: "Normal",
    3: "Maximized",
    7: "Minimized",
    "Normal": 1,
    "Maximized": 3,
    "Minimized": 7,
}


def __virtual__():
    """
    Make sure we're on Windows
    """
    # Verify Windows
    if not salt.utils.platform.is_windows():
        log.debug("Shortcut module only available on Windows systems")
        return False, "Shortcut module only available on Windows systems"
    if not HAS_WIN32:
        log.debug("Shortcut module requires pywin32")
        return False, "Shortcut module requires pywin32"

    return __virtualname__


def get(path):
    r"""
    Gets the properties for a shortcut

    Args:
        path (str): The path to the shortcut. Must have a `.lnk` or `.url` file
            extension.

    Returns:
        dict: A dictionary containing all available properties for the specified
            shortcut

    CLI Example:

    .. code-block:: bash

        salt * shortcut.get path="C:\path\to\shortcut.lnk"
    """
    if not os.path.exists(path):
        raise CommandExecutionError("Shortcut not found: {}".format(path))

    if not path.endswith((".lnk", ".url")):
        _, ext = os.path.splitext(path)
        raise CommandExecutionError("Invalid file extension: {}".format(ext))

    # This will load the existing shortcut
    with salt.utils.winapi.Com():
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(path)

        arguments = ""
        description = ""
        hot_key = ""
        icon_location = ""
        icon_index = 0
        window_style = ""
        working_dir = ""

        path = salt.utils.path.expand(shortcut.FullName)
        # A shortcut can have either a .lnk or a .url extension. We only want to
        # expand the target if it is a .lnk
        if path.endswith(".lnk"):
            target = shortcut.TargetPath
            if target:
                target = salt.utils.path.expand(target)
            else:
                msg = "Not a valid shortcut: {}".format(path)
                log.debug(msg)
                raise CommandExecutionError(msg)
            if shortcut.Arguments:
                arguments = shortcut.Arguments
            if shortcut.Description:
                description = shortcut.Description
            if shortcut.Hotkey:
                hot_key = shortcut.Hotkey
            if shortcut.IconLocation:
                icon_location, icon_index = shortcut.IconLocation.split(",")
                if icon_location:
                    icon_location = salt.utils.path.expand(icon_location)
            if shortcut.WindowStyle:
                window_style = WINDOW_STYLE[shortcut.WindowStyle]
            if shortcut.WorkingDirectory:
                working_dir = salt.utils.path.expand(shortcut.WorkingDirectory)
        else:
            target = shortcut.TargetPath

        return {
            "arguments": arguments,
            "description": description,
            "hot_key": hot_key,
            "icon_index": int(icon_index),
            "icon_location": icon_location,
            "path": path,
            "target": target,
            "window_style": window_style,
            "working_dir": working_dir,
        }


def _set_info(
    path,
    target="",
    arguments="",
    description="",
    hot_key="",
    icon_index=0,
    icon_location="",
    window_style="Normal",
    working_dir="",
):
    r"""
    The main worker function for creating and modifying shortcuts. the `create`
    and `modify` functions are wrappers around this function.

    Args:

        path (str): The full path to the shortcut

        target (str): The full path to the target

        arguments (str, optional): Any arguments to be passed to the target

        description (str, optional): The description for the shortcut. This is
            shown in the ``Comment`` field of the dialog box. Default is an
            empty string

        hot_key (str, optional): A combination of hot Keys to trigger this
            shortcut. This is something like ``Ctrl+Alt+D``. This is shown in
            the ``Shortcut key`` field in the dialog box. Default is an empty
            string. Available options are:

            - Ctrl
            - Alt
            - Shift
            - Ext

        icon_index (int, optional): The index for the icon to use in files that
            contain multiple icons. Default is 0

        icon_location (str, optional): The full path to a file containing icons.
            This is shown in the ``Change Icon`` dialog box by clicking the
            ``Change Icon`` button. If no file is specified and a binary is
            passed as the target, Windows will attempt to get the icon from the
            binary file. Default is an empty string

        window_style (str, optional): The window style the program should start
            in. This is shown in the ``Run`` field of the dialog box. Default is
            ``Normal``. Valid options are:

            - Normal
            - Minimized
            - Maximized

        working_dir (str, optional): The full path to the working directory for
            the program to run in. This is shown in the ``Start in`` field of
            the dialog box.

    Returns:
        bool: True if successful
    """
    path = salt.utils.path.expand(path)

    # This will load the existing shortcut if it already exists
    # If it is a new shortcut, it won't be created until it is saved
    with salt.utils.winapi.Com():
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(path)

        # A shortcut can have either a .lnk or a .url extension. We only want to
        # expand the target if it is a .lnk
        if path.endswith(".lnk"):
            if target:
                target = salt.utils.path.expand(target)

            # These settings only apply to lnk shortcuts
            if arguments:
                shortcut.Arguments = arguments
            if description:
                shortcut.Description = description
            if hot_key:
                shortcut.Hotkey = hot_key
            if icon_location:
                shortcut.IconLocation = ",".join([icon_location, str(icon_index)])
            if window_style:
                shortcut.WindowStyle = WINDOW_STYLE[window_style]
            if working_dir:
                shortcut.WorkingDirectory = working_dir

        shortcut.TargetPath = target

        shortcut.Save()
    return True


def modify(
    path,
    target="",
    arguments="",
    description="",
    hot_key="",
    icon_index=0,
    icon_location="",
    window_style="Normal",
    working_dir="",
):
    r"""
    Modify an existing shortcut. This can be a file shortcut (``.lnk``) or a
    url shortcut (``.url``).

    Args:

        path (str): The full path to the shortcut. Must have a `.lnk` or `.url`
            file extension.

        target (str, optional): The full path to the target

        arguments (str, optional): Any arguments to be passed to the target

        description (str, optional): The description for the shortcut. This is
            shown in the ``Comment`` field of the dialog box. Default is an
            empty string

        hot_key (str, optional): A combination of hot Keys to trigger this
            shortcut. This is something like ``Ctrl+Alt+D``. This is shown in
            the ``Shortcut key`` field in the dialog box. Default is an empty
            string. Available options are:

            - Ctrl
            - Alt
            - Shift
            - Ext

        icon_index (int, optional): The index for the icon to use in files that
            contain multiple icons. Default is 0

        icon_location (str, optional): The full path to a file containing icons.
            This is shown in the ``Change Icon`` dialog box by clicking the
            ``Change Icon`` button. If no file is specified and a binary is
            passed as the target, Windows will attempt to get the icon from the
            binary file. Default is an empty string

        window_style (str, optional): The window style the program should start
            in. This is shown in the ``Run`` field of the dialog box. Default is
            ``Normal``. Valid options are:

            - Normal
            - Minimized
            - Maximized

        working_dir (str, optional): The full path to the working directory for
            the program to run in. This is shown in the ``Start in`` field of
            the dialog box.

    Returns:
        bool: True if successful

    CLI Example:

    .. code-block:: bash

        # Modify an existing shortcut. Set it to target notepad.exe
        salt * shortcut.modify "C:\path\to\shortcut.lnk" "C:\Windows\notepad.exe"
    """
    if not os.path.exists(path):
        raise CommandExecutionError("Shortcut not found: {}".format(path))

    if not path.endswith((".lnk", ".url")):
        _, ext = os.path.splitext(path)
        raise CommandExecutionError("Invalid file extension: {}".format(ext))

    return _set_info(
        path=path,
        arguments=arguments,
        description=description,
        hot_key=hot_key,
        icon_index=icon_index,
        icon_location=icon_location,
        target=target,
        window_style=window_style,
        working_dir=working_dir,
    )


def create(
    path,
    target,
    arguments="",
    description="",
    hot_key="",
    icon_index=0,
    icon_location="",
    window_style="Normal",
    working_dir="",
    backup=False,
    force=False,
    make_dirs=False,
    user=None,
):
    r"""
    Create a new shortcut. This can be a file shortcut (``.lnk``) or a url
    shortcut (``.url``).

    Args:

        path (str): The full path to the shortcut. Must have a `.lnk` or `.url`
            file extension.

        target (str): The full path to the target

        arguments (str, optional): Any arguments to be passed to the target

        description (str, optional): The description for the shortcut. This is
            shown in the ``Comment`` field of the dialog box. Default is an
            empty string

        hot_key (str, optional): A combination of hot Keys to trigger this
            shortcut. This is something like ``Ctrl+Alt+D``. This is shown in
            the ``Shortcut key`` field in the dialog box. Default is an empty
            string. Available options are:

            - Ctrl
            - Alt
            - Shift
            - Ext

        icon_index (int, optional): The index for the icon to use in files that
            contain multiple icons. Default is 0

        icon_location (str, optional): The full path to a file containing icons.
            This is shown in the ``Change Icon`` dialog box by clicking the
            ``Change Icon`` button. If no file is specified and a binary is
            passed as the target, Windows will attempt to get the icon from the
            binary file. Default is an empty string

        window_style (str, optional): The window style the program should start
            in. This is shown in the ``Run`` field of the dialog box. Default is
            ``Normal``. Valid options are:

            - Normal
            - Minimized
            - Maximized

        working_dir (str, optional): The full path to the working directory for
            the program to run in. This is shown in the ``Start in`` field of
            the dialog box.

        backup (bool, optional): If there is already a shortcut with the same
            name, set this value to ``True`` to backup the existing shortcut and
            continue creating the new shortcut. Default is ``False``

        force (bool, optional): If there is already a shortcut with the same
            name and you aren't backing up the shortcut, set this value to
            ``True`` to remove the existing shortcut and create a new with these
            settings. Default is ``False``

        make_dirs (bool, optional): If the parent directory structure does not
            exist for the new shortcut, create it. Default is ``False``

        user (str, optional): The user to be the owner of any directories
            created by setting ``make_dirs`` to ``True``. If no value is passed
            Salt will use the user account that it is running under. Default is
            an empty string.

    Returns:
        bool: True if successful

    Raises:
        CommandExecutionError: If the path is not a ``.lnk`` or ``.url`` file
            extension.
        CommandExecutionError: If there is an existing shortcut with the same
            name and ``backup`` and ``force`` are both ``False``
        CommandExecutionError: If the parent directory is not created and
            ``make_dirs`` is ``False``
        CommandExecutionError: If there was an error creating the parent
            directories

    CLI Example:

    .. code-block:: bash

        # Create a shortcut and set the ``Shortcut key`` (``hot_key``)
        salt * shortcut.create "C:\path\to\shortcut.lnk" "C:\Windows\notepad.exe" hot_key="Ctrl+Alt+N"

        # Create a shortcut and change the icon to the 3rd one in the icon file
        salt * shortcut.create "C:\path\to\shortcut.lnk" "C:\Windows\notepad.exe" icon_location="C:\path\to\icon.ico" icon_index=2

        # Create a shortcut and change the startup mode to full screen
        salt * shortcut.create "C:\path\to\shortcut.lnk" "C:\Windows\notepad.exe" window_style="Maximized"

        # Create a shortcut and change the icon
        salt * shortcut.create "C:\path\to\shortcut.lnk" "C:\Windows\notepad.exe" icon_location="C:\path\to\icon.ico"

        # Create a shortcut and force it to overwrite an existing shortcut
        salt * shortcut.create "C:\path\to\shortcut.lnk" "C:\Windows\notepad.exe" force=True

        # Create a shortcut and create any parent directories if they are missing
        salt * shortcut.create "C:\path\to\shortcut.lnk" "C:\Windows\notepad.exe" make_dirs=True
    """
    if not path.endswith((".lnk", ".url")):
        _, ext = os.path.splitext(path)
        raise CommandExecutionError("Invalid file extension: {}".format(ext))

    if os.path.exists(path):
        if backup:
            log.debug("Backing up: %s", path)
            file, ext = os.path.splitext(path)
            ext = ext.strip(".")
            backup_path = "{}-{}.{}".format(file, time.time_ns(), ext)
            os.rename(path, backup_path)
        elif force:
            log.debug("Removing: %s", path)
            os.remove(path)
        else:
            log.debug("Shortcut exists: %s", path)
            raise CommandExecutionError("Found existing shortcut")

    if not os.path.isdir(os.path.dirname(path)):
        if make_dirs:

            # Get user from opts if not defined
            if not user:
                user = __opts__["user"]

            # Make sure the user exists in Windows
            # Salt default is 'SYSTEM' for Windows
            if not __salt__["user.info"](user):
                # User not found, use the account salt is running under
                # If username not found, use System
                user = __salt__["user.current"]()
                if not user:
                    user = "SYSTEM"

            try:
                __salt__["file.makedirs"](path=path, owner=user)
            except CommandExecutionError as exc:
                raise CommandExecutionError(
                    "Error creating parent directory: {}".format(exc.message)
                )
        else:
            raise CommandExecutionError(
                "Parent directory not present: {}".format(os.path.dirname(path))
            )

    return _set_info(
        path=path,
        arguments=arguments,
        description=description,
        hot_key=hot_key,
        icon_index=icon_index,
        icon_location=icon_location,
        target=target,
        window_style=window_style,
        working_dir=working_dir,
    )
