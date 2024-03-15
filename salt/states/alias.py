"""
Configuration of email aliases

The mail aliases file can be managed to contain definitions for specific email
aliases:

.. code-block:: yaml

    username:
      alias.present:
        - target: user@example.com

.. code-block:: yaml

    thomas:
      alias.present:
        - target: thomas@example.com

The default alias file is set to ``/etc/aliases``, as defined in Salt's
:mod:`config execution module <salt.modules.config>`. To change the alias
file from the default location, set the following in your minion config:

.. code-block:: yaml

    aliases.file: /my/alias/file

"""


def present(name, target):
    """
    Ensures that the named alias is present with the given target or list of
    targets. If the alias exists but the target differs from the previous
    entry, the target(s) will be overwritten. If the alias does not exist, the
    alias will be created.

    name
        The local user/address to assign an alias to

    target
        The forwarding address
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    if __salt__["aliases.has_target"](name, target):
        ret["result"] = True
        ret["comment"] = f"Alias {name} already present"
        return ret
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Alias {name} -> {target} is set to be added"
        return ret
    if __salt__["aliases.set_target"](name, target):
        ret["changes"] = {"alias": name}
        ret["result"] = True
        ret["comment"] = f"Set email alias {name} -> {target}"
        return ret
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to set alias {name} -> {target}"
        return ret


def absent(name):
    """
    Ensure that the named alias is absent

    name
        The alias to remove
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    if not __salt__["aliases.get_target"](name):
        ret["result"] = True
        ret["comment"] = f"Alias {name} already absent"
        return ret
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Alias {name} is set to be removed"
        return ret
    if __salt__["aliases.rm_alias"](name):
        ret["changes"] = {"alias": name}
        ret["result"] = True
        ret["comment"] = f"Removed alias {name}"
        return ret
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to remove alias {name}"
        return ret
