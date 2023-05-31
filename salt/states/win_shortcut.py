"""
State module for creating shortcuts on Windows. Handles file shortcuts (`.lnk`)
and url shortcuts (`.url`). Allows for the configuration of icons and hot keys
on file shortcuts. Changing the icon and hot keys are unsupported for url
shortcuts.

.. versionadded:: 3005
"""
import salt.utils.data
import salt.utils.path
import salt.utils.platform
from salt.exceptions import CommandExecutionError

# Define the module's virtual name
__virtualname__ = "shortcut"


def __virtual__():
    """
    Only works on Windows systems
    """
    if not salt.utils.platform.is_windows():
        return False, "Shortcut state only available on Windows systems."
    if not __salt__.get("shortcut.create", None):
        return False, "Shortcut state requires the shortcut module."

    return __virtualname__


def present(
    name,
    arguments="",
    description="",
    hot_key="",
    icon_location="",
    icon_index=0,
    target="",
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

        name (str): The full path to the shortcut

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
        dict: A dictionary containing the changes, comments, and result of the
            state

    Example:

    .. code-block:: yaml

        KB123456:
          wusa.installed:
            - source: salt://kb123456.msu

        # Create a shortcut and set the ``Shortcut key`` (``hot_key``)
        new_shortcut:
          shortcut.present:
            - name: C:\path\to\shortcut.lnk
            - target: C:\Windows\notepad.exe
            - hot_key: Ctrl+Alt+N

        # Create a shortcut and change the icon to the 3rd one in the icon file
        new_shortcut:
          shortcut.present:
            - name: C:\path\to\shortcut.lnk
            - target: C:\Windows\notepad.exe
            - icon_location: C:\path\to\icon.ico
            - icon_index: 2

        # Create a shortcut and change the startup mode to full screen
        new_shortcut:
          shortcut.present:
            - name: C:\path\to\shortcut.lnk
            - target: C:\Windows\notepad.exe
            - window_style: Maximized

        # Create a shortcut and change the icon
        new_shortcut:
          shortcut.present:
            - name: C:\path\to\shortcut.lnk
            - target: C:\Windows\notepad.exe
            - icon_location: C:\path\to\icon.ico

        # Create a shortcut and force it to overwrite an existing shortcut
        new_shortcut:
          shortcut.present:
            - name: C:\path\to\shortcut.lnk
            - target: C:\Windows\notepad.exe
            - force: True

        # Create a shortcut and create any parent directories if they are missing
        new_shortcut:
          shortcut.present:
            - name: C:\path\to\shortcut.lnk
            - target: C:\Windows\notepad.exe
            - make_dirs: True
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": []}

    proposed = {
        "arguments": arguments,
        "description": description,
        "hot_key": hot_key,
        "icon_location": salt.utils.path.expand(icon_location),
        "icon_index": icon_index,
        "path": salt.utils.path.expand(name),
        "target": salt.utils.path.expand(target),
        "window_style": window_style,
        "working_dir": salt.utils.path.expand(working_dir),
    }

    try:
        old = __salt__["shortcut.get"](name)
        changes = salt.utils.data.compare_dicts(old, proposed)
        if not changes:
            ret["comment"] = "Shortcut already present and configured"
            return ret

    except CommandExecutionError:
        changes = {}

    if __opts__["test"]:
        if changes:
            ret["comment"] = "Shortcut will be modified: {}".format(name)
            ret["changes"] = changes
        else:
            ret["comment"] = "Shortcut will be created: {}".format(name)

        ret["result"] = None
        return ret

    try:
        __salt__["shortcut.create"](
            arguments=arguments,
            description=description,
            hot_key=hot_key,
            icon_location=icon_location,
            icon_index=icon_index,
            path=name,
            target=target,
            window_style=window_style,
            working_dir=working_dir,
            backup=backup,
            force=force,
            make_dirs=make_dirs,
            user=user,
        )
    except CommandExecutionError as exc:
        ret["comment"] = ["Failed to create the shortcut: {}".format(name)]
        ret["comment"].append(exc.message)
        ret["result"] = False
        return ret

    try:
        new = __salt__["shortcut.get"](name)
    except CommandExecutionError as exc:
        ret["comment"] = ["Failed to create the shortcut: {}".format(name)]
        ret["comment"].append(exc.message)
        ret["result"] = False
        return ret

    verify_changes = salt.utils.data.compare_dicts(new, proposed)
    if verify_changes:
        ret["comment"] = "Failed to make the following changes:"
        ret["changes"]["failed"] = verify_changes
        ret["result"] = False
        return ret

    if changes:
        ret["comment"] = "Shortcut modified: {}".format(name)
        ret["changes"] = changes
    else:
        ret["comment"] = "Shortcut created: {}".format(name)

    return ret
