"""
Management of DNF modules (modularity / AppStreams)

This state manages `DNF modularity
<https://docs.fedoraproject.org/en-US/modularity/>`_ (AppStream) module
streams on RHEL 8/9 and derivatives, using the
:mod:`dnfmodule <salt.modules.dnfmodule>` execution module.

.. code-block:: yaml

    nodejs:18:
      dnfmodule.enabled

    install_postgresql:
      dnfmodule.installed:
        - name: postgresql:15/client

.. versionadded:: 3008.0
"""


def __virtual__():
    """
    Only load if the dnfmodule execution module is available.
    """
    if "dnfmodule.enable" in __salt__:
        return "dnfmodule"
    return (False, "The dnfmodule execution module is not available")


def enabled(name, switch=False):
    """
    Ensure that the named module stream is enabled.

    name
        The module name with the stream to enable, e.g. ``nodejs:18``. If no
        stream is given, the module's default stream is enabled.

    switch
        DNF refuses to enable a stream while a *different* stream of the same
        module is already enabled. When ``False`` (the default) this state
        fails with a clear message describing the conflict. When ``True`` the
        module is first reset and the requested stream is then enabled,
        switching the enabled stream.

        .. note::
            Switching streams does not remove packages that were installed from
            the previously enabled stream; reset/switch only changes which
            stream is enabled.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    module = name.split(":", 1)[0]
    requested = name.split(":", 1)[1].split("/", 1)[0] if ":" in name else None

    if __salt__["dnfmodule.is_enabled"](name):
        ret["comment"] = f"Module stream '{name}' is already enabled"
        return ret

    # ``is_enabled`` was False above, so any enabled stream reported here must
    # be a different stream of the same module (a conflict).
    current = __salt__["dnfmodule.enabled_stream"](name)
    if current:
        if not switch:
            ret["result"] = False
            ret["comment"] = (
                f"Module '{module}' already has stream '{current}' enabled. "
                f"Reset it first or pass 'switch: True' to switch to '{name}'."
            )
            return ret
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = (
                f"Module '{module}' stream would be switched from "
                f"'{current}' to '{requested}'"
            )
            ret["changes"] = {module: {"old": current, "new": requested}}
            return ret
        __salt__["dnfmodule.enable"](name, switch=True)
        ret["changes"] = {module: {"old": current, "new": requested}}
        ret["comment"] = (
            f"Module '{module}' stream was switched from '{current}' to '{requested}'"
        )
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Module stream '{name}' would be enabled"
        ret["changes"] = {"enabled": name}
        return ret

    __salt__["dnfmodule.enable"](name)
    ret["changes"] = {"enabled": name}
    ret["comment"] = f"Module stream '{name}' was enabled"
    return ret


def disabled(name):
    """
    Ensure that the named module is disabled.

    name
        The module name to disable, e.g. ``nodejs``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if __salt__["dnfmodule.is_disabled"](name):
        ret["comment"] = f"Module '{name}' is already disabled"
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Module '{name}' would be disabled"
        ret["changes"] = {"disabled": name}
        return ret

    __salt__["dnfmodule.disable"](name)
    ret["changes"] = {"disabled": name}
    ret["comment"] = f"Module '{name}' was disabled"
    return ret


def installed(name):
    """
    Ensure that the named module profile is installed. Installing a profile
    also enables the corresponding stream if it is not already enabled.

    name
        The module to install, optionally with a stream and/or profile,
        e.g. ``nodejs:18`` or ``nodejs:18/common``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if __salt__["dnfmodule.is_installed"](name):
        ret["comment"] = f"Module '{name}' is already installed"
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Module '{name}' would be installed"
        ret["changes"] = {"installed": name}
        return ret

    __salt__["dnfmodule.install"](name)
    ret["changes"] = {"installed": name}
    ret["comment"] = f"Module '{name}' was installed"
    return ret


def removed(name):
    """
    Ensure that the named module profile is not installed. The module's stream
    remains enabled; use :py:func:`disabled` to change the stream state.

    name
        The module to remove, optionally with a stream and/or profile.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if not __salt__["dnfmodule.is_installed"](name):
        ret["comment"] = f"Module '{name}' is already not installed"
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Module '{name}' would be removed"
        ret["changes"] = {"removed": name}
        return ret

    __salt__["dnfmodule.remove"](name)
    ret["changes"] = {"removed": name}
    ret["comment"] = f"Module '{name}' was removed"
    return ret
