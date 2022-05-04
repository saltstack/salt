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
    if not os.path.exists(path):
        raise CommandExecutionError("Shortcut not found: {}".format(path))

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
        # A shortcut can have either a .lnk or a .url exension. We only want to
        # expand the target if it is a .lnk
        if path.endswith(".lnk"):
            target = salt.utils.path.expand(shortcut.TargetPath)
            if shortcut.Arguments:
                arguments = shortcut.Arguments
            if shortcut.Description:
                description = shortcut.Description
            if shortcut.Hotkey:
                hot_key = shortcut.Hotkey
            if shortcut.IconLocation:
                icon_location, icon_index = shortcut.IconLocation.split(",")
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
    target,
    arguments="",
    description="",
    hot_key="",
    icon_index=0,
    icon_location="",
    window_style="Normal",
    working_dir="",
):
    path = salt.utils.path.expand(path)

    # This will load the existing shortcut if it already exists
    # If it is a new shortcut, it won't be created until it is saved
    with salt.utils.winapi.Com():
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(path)

        # A shortcut can have either a .lnk or a .url exension. We only want to
        # expand the target if it is a .lnk
        if path.endswith(".lnk"):
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
    target,
    arguments="",
    description="",
    hot_key="",
    icon_index=0,
    icon_location="",
    window_style="Normal",
    working_dir="",
):
    if not os.path.exists(path):
        raise CommandExecutionError("Shortcut not found: {}".format(path))

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
    if not path.endswith((".lnk", ".url")):
        _, ext = os.path.splitext(path)
        raise CommandExecutionError("Invalid file extension: {}".format(ext))

    if os.path.exists(path):
        if backup:
            log.debug("Backing up: {}".format(path))
            file, ext = os.path.splitext(path)
            ext = ext.strip(".")
            backup_path = "{}-{}.{}".format(file, time.time_ns(), ext)
            os.rename(path, backup_path)
        elif force:
            log.debug("Removing: {}".format(path))
            os.remove(path)
        else:
            log.debug("Shortcut exists: {}".format(path))
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
