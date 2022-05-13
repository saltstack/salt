"""
State to work with sysrc

"""


# define the module's virtual name
__virtualname__ = "sysrc"


def __virtual__():
    """
    Only load if sysrc executable exists
    """
    if __salt__["cmd.has_exec"]("sysrc"):
        return True
    return (False, "Command not found: sysrc")


def managed(name, value, **kwargs):
    """
    Ensure a sysrc variable is set to a specific value.

    name
        The variable name to set
    value
        Value to set the variable to
    file
        (optional) The rc file to add the variable to.
    jail
        (option) the name or JID of the jail to set the value in.

    Example:

    .. code-block:: yaml

        syslogd:
          sysrc.managed:
            - name: syslogd_flags
            - value: -ss
    """

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    # Check the current state
    current_state = __salt__["sysrc.get"](name=name, **kwargs)
    if current_state is not None:
        for rcname, rcdict in current_state.items():
            if rcdict[name] == value:
                ret["result"] = True
                ret["comment"] = "{} is already set to the desired value.".format(name)
                return ret

    if __opts__["test"] is True:
        ret["comment"] = 'The value of "{}" will be changed!'.format(name)
        ret["changes"] = {
            "old": current_state,
            "new": name + " = " + value + " will be set.",
        }

        # When test=true return none
        ret["result"] = None

        return ret

    new_state = __salt__["sysrc.set"](name=name, value=value, **kwargs)

    ret["comment"] = 'The value of "{}" was changed!'.format(name)

    ret["changes"] = {"old": current_state, "new": new_state}

    ret["result"] = True

    return ret


def absent(name, **kwargs):
    """
    Ensure a sysrc variable is absent.

    name
        The variable name to set
    file
        (optional) The rc file to add the variable to.
    jail
        (option) the name or JID of the jail to set the value in.
    """

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    # Check the current state
    current_state = __salt__["sysrc.get"](name=name, **kwargs)
    if current_state is None:
        ret["result"] = True
        ret["comment"] = '"{}" is already absent.'.format(name)
        return ret

    if __opts__["test"] is True:
        ret["comment"] = '"{}" will be removed!'.format(name)
        ret["changes"] = {
            "old": current_state,
            "new": '"{}" will be removed.'.format(name),
        }

        # When test=true return none
        ret["result"] = None

        return ret

    new_state = __salt__["sysrc.remove"](name=name, **kwargs)

    ret["comment"] = '"{}" was removed!'.format(name)

    ret["changes"] = {"old": current_state, "new": new_state}

    ret["result"] = True

    return ret
