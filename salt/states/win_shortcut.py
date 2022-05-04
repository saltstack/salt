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
):
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
