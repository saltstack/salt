"""
Linux File Access Control Lists

The Linux ACL state module requires the `getfacl` and `setfacl` binaries.

Ensure a Linux ACL is present

.. code-block:: yaml

     root:
       acl.present:
         - name: /root
         - acl_type: user
         - acl_name: damian
         - perms: rwx

Ensure a Linux ACL does not exist

.. code-block:: yaml

     root:
       acl.absent:
         - name: /root
         - acl_type: user
         - acl_name: damian
         - perms: rwx

Ensure a Linux ACL list is present

.. code-block:: yaml

     root:
       acl.list_present:
         - name: /root
         - acl_type: user
         - acl_names:
           - damian
           - homer
         - perms: rwx

Ensure a Linux ACL list does not exist

.. code-block:: yaml

     root:
       acl.list_absent:
         - name: /root
         - acl_type: user
         - acl_names:
           - damian
           - homer
         - perms: rwx

.. warning::

    The effective permissions of Linux file access control lists (ACLs) are
    governed by the "effective rights mask" (the `mask` line in the output of
    the `getfacl` command) combined with the `perms` set by this module: any
    permission bits (for example, r=read) present in an ACL but not in the mask
    are ignored.  The mask is automatically recomputed when setting an ACL, so
    normally this isn't important.  However, if the file permissions are
    changed (with `chmod` or `file.managed`, for example), the mask will
    generally be set based on just the group bits of the file permissions.

    As a result, when using `file.managed` or similar to control file
    permissions as well as this module, you should set your group permissions
    to be at least as broad as any permissions in your ACL. Otherwise, the two
    state declarations will each register changes each run, and if the `file`
    declaration runs later, your ACL will be ineffective.

"""

import logging
import os

import salt.utils.path
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

__virtualname__ = "acl"


def __virtual__():
    """
    Ensure getfacl & setfacl exist
    """
    if salt.utils.path.which("getfacl") and salt.utils.path.which("setfacl"):
        return __virtualname__

    return (
        False,
        "The linux_acl state cannot be loaded: the getfacl or setfacl binary is not in"
        " the path.",
    )


def present(name, acl_type, acl_name="", perms="", recurse=False, force=False):
    """
    Ensure a Linux ACL is present

    name
        The acl path

    acl_type
        The type of the acl is used for it can be 'user' or 'group'

    acl_name
        The  user or group

    perms
        Set the permissions eg.: rwx

    recurse
        Set the permissions recursive in the path

    force
        Wipe out old permissions and ensure only the new permissions are set
    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    _octal = {"r": 4, "w": 2, "x": 1, "-": 0}
    _octal_lookup = {0: "-", 1: "r", 2: "w", 4: "x"}

    if not os.path.exists(name):
        ret["comment"] = f"{name} does not exist"
        ret["result"] = False
        return ret

    __current_perms = __salt__["acl.getfacl"](name, recursive=recurse)

    if acl_type.startswith(("d:", "default:")):
        _acl_type = ":".join(acl_type.split(":")[1:])
        _current_perms = __current_perms[name].get("defaults", {})
        _default = True
    else:
        _acl_type = acl_type
        _current_perms = __current_perms[name]
        _default = False

    # The getfacl execution module lists default with empty names as being
    # applied to the user/group that owns the file, e.g.,
    # default:group::rwx would be listed as default:group:root:rwx
    # In this case, if acl_name is empty, we really want to search for root
    # but still uses '' for other

    # We search through the dictionary getfacl returns for the owner of the
    # file if acl_name is empty.
    if acl_name == "":
        _search_name = __current_perms[name].get("comment").get(_acl_type, "")
    else:
        _search_name = acl_name

    if _current_perms.get(_acl_type, None) or _default:
        try:
            user = [
                i
                for i in _current_perms[_acl_type]
                if next(iter(i.keys())) == _search_name
            ].pop()
        except (AttributeError, IndexError, StopIteration, KeyError):
            user = None

        if user:
            octal_sum = sum(_octal.get(i, i) for i in perms)
            need_refresh = False
            # If recursive check all paths retrieved via acl.getfacl
            if recurse:
                for path in __current_perms:
                    acl_found = False
                    if _default:
                        # Recusive default acls only apply to directories
                        if not os.path.isdir(path):
                            continue
                        _current_perms_path = __current_perms[path].get("defaults", {})
                    else:
                        _current_perms_path = __current_perms[path]
                    for user_acl in _current_perms_path.get(_acl_type, []):
                        if (
                            _search_name in user_acl
                            and user_acl[_search_name]["octal"] == octal_sum
                        ):
                            acl_found = True
                    if not acl_found:
                        need_refresh = True
                        break

            # Check the permissions from the already located file
            elif user[_search_name]["octal"] == sum(_octal.get(i, i) for i in perms):
                need_refresh = False
            # If they don't match then refresh
            else:
                need_refresh = True

            if not need_refresh:
                ret["comment"] = "Permissions are in the desired state"
            else:
                _num = user[_search_name]["octal"]
                new_perms = "{}{}{}".format(
                    _octal_lookup[_num & 1],
                    _octal_lookup[_num & 2],
                    _octal_lookup[_num & 4],
                )
                changes = {
                    "new": {"acl_name": acl_name, "acl_type": acl_type, "perms": perms},
                    "old": {
                        "acl_name": acl_name,
                        "acl_type": acl_type,
                        "perms": new_perms,
                    },
                }

                if __opts__["test"]:
                    ret.update(
                        {
                            "comment": (
                                "Updated permissions will be applied for "
                                "{}: {} -> {}".format(acl_name, new_perms, perms)
                            ),
                            "result": None,
                            "changes": changes,
                        }
                    )
                    return ret
                try:
                    if force:
                        __salt__["acl.wipefacls"](
                            name, recursive=recurse, raise_err=True
                        )

                    __salt__["acl.modfacl"](
                        acl_type,
                        acl_name,
                        perms,
                        name,
                        recursive=recurse,
                        raise_err=True,
                    )
                    ret.update(
                        {
                            "comment": f"Updated permissions for {acl_name}",
                            "result": True,
                            "changes": changes,
                        }
                    )
                except CommandExecutionError as exc:
                    ret.update(
                        {
                            "comment": "Error updating permissions for {}: {}".format(
                                acl_name, exc.strerror
                            ),
                            "result": False,
                        }
                    )
        else:
            changes = {
                "new": {"acl_name": acl_name, "acl_type": acl_type, "perms": perms}
            }

            if __opts__["test"]:
                ret.update(
                    {
                        "comment": "New permissions will be applied for {}: {}".format(
                            acl_name, perms
                        ),
                        "result": None,
                        "changes": changes,
                    }
                )
                ret["result"] = None
                return ret

            try:
                if force:
                    __salt__["acl.wipefacls"](name, recursive=recurse, raise_err=True)

                __salt__["acl.modfacl"](
                    acl_type, acl_name, perms, name, recursive=recurse, raise_err=True
                )
                ret.update(
                    {
                        "comment": f"Applied new permissions for {acl_name}",
                        "result": True,
                        "changes": changes,
                    }
                )
            except CommandExecutionError as exc:
                ret.update(
                    {
                        "comment": "Error updating permissions for {}: {}".format(
                            acl_name, exc.strerror
                        ),
                        "result": False,
                    }
                )

    else:
        ret["comment"] = "ACL Type does not exist"
        ret["result"] = False

    return ret


def absent(name, acl_type, acl_name="", perms="", recurse=False):
    """
    Ensure a Linux ACL does not exist

    name
        The acl path

    acl_type
        The type of the acl is used for, it can be 'user' or 'group'

    acl_name
        The user or group

    perms
        Remove the permissions eg.: rwx

    recurse
        Set the permissions recursive in the path
    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    if not os.path.exists(name):
        ret["comment"] = f"{name} does not exist"
        ret["result"] = False
        return ret

    __current_perms = __salt__["acl.getfacl"](name, recursive=recurse)

    if acl_type.startswith(("d:", "default:")):
        _acl_type = ":".join(acl_type.split(":")[1:])
        _current_perms = __current_perms[name].get("defaults", {})
        _default = True
    else:
        _acl_type = acl_type
        _current_perms = __current_perms[name]
        _default = False

    # The getfacl execution module lists default with empty names as being
    # applied to the user/group that owns the file, e.g.,
    # default:group::rwx would be listed as default:group:root:rwx
    # In this case, if acl_name is empty, we really want to search for root
    # but still uses '' for other

    # We search through the dictionary getfacl returns for the owner of the
    # file if acl_name is empty.
    if acl_name == "":
        _search_name = __current_perms[name].get("comment").get(_acl_type, "")
    else:
        _search_name = acl_name

    if _current_perms.get(_acl_type, None) or _default:
        try:
            user = [
                i
                for i in _current_perms[_acl_type]
                if next(iter(i.keys())) == _search_name
            ].pop()
        except (AttributeError, IndexError, StopIteration, KeyError):
            user = None

        need_refresh = False
        for path in __current_perms:
            acl_found = False
            for user_acl in __current_perms[path].get(_acl_type, []):
                if _search_name in user_acl:
                    acl_found = True
                    break
            if acl_found:
                need_refresh = True
                break

        if user or need_refresh:
            ret["comment"] = "Removing permissions"

            if __opts__["test"]:
                ret["result"] = None
                return ret

            __salt__["acl.delfacl"](acl_type, acl_name, perms, name, recursive=recurse)
        else:
            ret["comment"] = "Permissions are in the desired state"

    else:
        ret["comment"] = "ACL Type does not exist"
        ret["result"] = False

    return ret


def list_present(name, acl_type, acl_names=None, perms="", recurse=False, force=False):
    """
    Ensure a Linux ACL list is present

    Takes a list of acl names and add them to the given path

    name
        The acl path

    acl_type
        The type of the acl is used for it can be 'user' or 'group'

    acl_names
        The list of users or groups

    perms
        Set the permissions eg.: rwx

    recurse
        Set the permissions recursive in the path

    force
        Wipe out old permissions and ensure only the new permissions are set
    """
    if acl_names is None:
        acl_names = []
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    _octal = {"r": 4, "w": 2, "x": 1, "-": 0}
    _octal_perms = sum(_octal.get(i, i) for i in perms)
    if not os.path.exists(name):
        ret["comment"] = f"{name} does not exist"
        ret["result"] = False
        return ret

    __current_perms = __salt__["acl.getfacl"](name)

    if acl_type.startswith(("d:", "default:")):
        _acl_type = ":".join(acl_type.split(":")[1:])
        _current_perms = __current_perms[name].get("defaults", {})
        _default = True
    else:
        _acl_type = acl_type
        _current_perms = __current_perms[name]
        _default = False
        _origin_group = _current_perms.get("comment", {}).get("group", None)
        _origin_owner = _current_perms.get("comment", {}).get("owner", None)

        _current_acl_types = []
        diff_perms = False
        for key in _current_perms[acl_type]:
            for current_acl_name in key.keys():
                _current_acl_types.append(current_acl_name.encode("utf-8"))
                diff_perms = _octal_perms == key[current_acl_name]["octal"]
        if acl_type == "user":
            try:
                _current_acl_types.remove(_origin_owner)
            except ValueError:
                pass
        else:
            try:
                _current_acl_types.remove(_origin_group)
            except ValueError:
                pass
        diff_acls = set(_current_acl_types) ^ set(acl_names)
        if not diff_acls and diff_perms and not force:
            ret = {
                "name": name,
                "result": True,
                "changes": {},
                "comment": "Permissions and {}s are in the desired state".format(
                    acl_type
                ),
            }
            return ret
    # The getfacl execution module lists default with empty names as being
    # applied to the user/group that owns the file, e.g.,
    # default:group::rwx would be listed as default:group:root:rwx
    # In this case, if acl_names is empty, we really want to search for root
    # but still uses '' for other

    # We search through the dictionary getfacl returns for the owner of the
    # file if acl_names is empty.
    if acl_names == "":
        _search_names = __current_perms[name].get("comment").get(_acl_type, "")
    else:
        _search_names = acl_names

    if _current_perms.get(_acl_type, None) or _default:
        try:
            users = {}
            for i in _current_perms[_acl_type]:
                if i and next(iter(i.keys())) in _search_names:
                    users.update(i)
        except (AttributeError, KeyError):
            users = None

        if users:
            changes = {}
            for count, search_name in enumerate(_search_names):
                if search_name in users:
                    if users[search_name]["octal"] == sum(
                        _octal.get(i, i) for i in perms
                    ):
                        ret["comment"] = "Permissions are in the desired state"
                    else:
                        changes.update(
                            {
                                "new": {
                                    "acl_name": ", ".join(acl_names),
                                    "acl_type": acl_type,
                                    "perms": _octal_perms,
                                },
                                "old": {
                                    "acl_name": ", ".join(acl_names),
                                    "acl_type": acl_type,
                                    "perms": str(users[search_name]["octal"]),
                                },
                            }
                        )
                        if __opts__["test"]:
                            ret.update(
                                {
                                    "comment": (
                                        "Updated permissions will be applied for "
                                        "{}: {} -> {}".format(
                                            acl_names,
                                            str(users[search_name]["octal"]),
                                            perms,
                                        )
                                    ),
                                    "result": None,
                                    "changes": changes,
                                }
                            )
                            return ret
                        try:
                            if force:
                                __salt__["acl.wipefacls"](
                                    name, recursive=recurse, raise_err=True
                                )

                            for acl_name in acl_names:
                                __salt__["acl.modfacl"](
                                    acl_type,
                                    acl_name,
                                    perms,
                                    name,
                                    recursive=recurse,
                                    raise_err=True,
                                )
                            ret.update(
                                {
                                    "comment": "Updated permissions for {}".format(
                                        acl_names
                                    ),
                                    "result": True,
                                    "changes": changes,
                                }
                            )
                        except CommandExecutionError as exc:
                            ret.update(
                                {
                                    "comment": (
                                        "Error updating permissions for {}: {}".format(
                                            acl_names, exc.strerror
                                        )
                                    ),
                                    "result": False,
                                }
                            )
                else:
                    changes = {
                        "new": {
                            "acl_name": ", ".join(acl_names),
                            "acl_type": acl_type,
                            "perms": perms,
                        }
                    }

                    if __opts__["test"]:
                        ret.update(
                            {
                                "comment": (
                                    "New permissions will be applied for {}: {}".format(
                                        acl_names, perms
                                    )
                                ),
                                "result": None,
                                "changes": changes,
                            }
                        )
                        ret["result"] = None
                        return ret

                    try:
                        if force:
                            __salt__["acl.wipefacls"](
                                name, recursive=recurse, raise_err=True
                            )

                        for acl_name in acl_names:
                            __salt__["acl.modfacl"](
                                acl_type,
                                acl_name,
                                perms,
                                name,
                                recursive=recurse,
                                raise_err=True,
                            )
                        ret.update(
                            {
                                "comment": "Applied new permissions for {}".format(
                                    ", ".join(acl_names)
                                ),
                                "result": True,
                                "changes": changes,
                            }
                        )
                    except CommandExecutionError as exc:
                        ret.update(
                            {
                                "comment": (
                                    "Error updating permissions for {}: {}".format(
                                        acl_names, exc.strerror
                                    )
                                ),
                                "result": False,
                            }
                        )

        else:
            changes = {
                "new": {
                    "acl_name": ", ".join(acl_names),
                    "acl_type": acl_type,
                    "perms": perms,
                }
            }

            if __opts__["test"]:
                ret.update(
                    {
                        "comment": "New permissions will be applied for {}: {}".format(
                            acl_names, perms
                        ),
                        "result": None,
                        "changes": changes,
                    }
                )
                ret["result"] = None
                return ret

            try:
                if force:
                    __salt__["acl.wipefacls"](name, recursive=recurse, raise_err=True)

                for acl_name in acl_names:
                    __salt__["acl.modfacl"](
                        acl_type,
                        acl_name,
                        perms,
                        name,
                        recursive=recurse,
                        raise_err=True,
                    )
                ret.update(
                    {
                        "comment": "Applied new permissions for {}".format(
                            ", ".join(acl_names)
                        ),
                        "result": True,
                        "changes": changes,
                    }
                )
            except CommandExecutionError as exc:
                ret.update(
                    {
                        "comment": "Error updating permissions for {}: {}".format(
                            acl_names, exc.strerror
                        ),
                        "result": False,
                    }
                )

    else:
        ret["comment"] = "ACL Type does not exist"
        ret["result"] = False

    return ret


def list_absent(name, acl_type, acl_names=None, recurse=False):
    """
    Ensure a Linux ACL list does not exist

    Takes a list of acl names and remove them from the given path

    name
        The acl path

    acl_type
        The type of the acl is used for, it can be 'user' or 'group'

    acl_names
        The list of users or groups

    perms
        Remove the permissions eg.: rwx

    recurse
        Set the permissions recursive in the path

    """
    if acl_names is None:
        acl_names = []

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    if not os.path.exists(name):
        ret["comment"] = f"{name} does not exist"
        ret["result"] = False
        return ret

    __current_perms = __salt__["acl.getfacl"](name)

    if acl_type.startswith(("d:", "default:")):
        _acl_type = ":".join(acl_type.split(":")[1:])
        _current_perms = __current_perms[name].get("defaults", {})
        _default = True
    else:
        _acl_type = acl_type
        _current_perms = __current_perms[name]
        _default = False
    # The getfacl execution module lists default with empty names as being
    # applied to the user/group that owns the file, e.g.,
    # default:group::rwx would be listed as default:group:root:rwx
    # In this case, if acl_names is empty, we really want to search for root
    # but still uses '' for other

    # We search through the dictionary getfacl returns for the owner of the
    # file if acl_names is empty.
    if not acl_names:
        _search_names = set(__current_perms[name].get("comment").get(_acl_type, ""))
    else:
        _search_names = set(acl_names)

    if _current_perms.get(_acl_type, None) or _default:
        try:
            users = {}
            for i in _current_perms[_acl_type]:
                if i and next(iter(i.keys())) in _search_names:
                    users.update(i)
        except (AttributeError, KeyError):
            users = None

        if users:
            ret["comment"] = "Removing permissions"

            if __opts__["test"]:
                ret["result"] = None
                return ret
            for acl_name in acl_names:
                __salt__["acl.delfacl"](acl_type, acl_name, name, recursive=recurse)
        else:
            ret["comment"] = "Permissions are in the desired state"

    else:
        ret["comment"] = "ACL Type does not exist"
        ret["result"] = False

    return ret
