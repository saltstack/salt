"""
Package management operations specific to APT- and DEB-based systems
====================================================================
"""

import logging

import salt.utils.data

log = logging.getLogger(__name__)


# Define the module's virtual name
__virtualname__ = "apt"


def __virtual__():
    """
    Only work on apt-based platforms with pkg.get_selections
    """
    if "pkg.get_selections" in __salt__:
        return True
    return (False, "apt module could not be loaded")


def held(name):
    """
    Set package in 'hold' state, meaning it will not be upgraded.

    name
        The name of the package, e.g., 'tmux'
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    state = __salt__["pkg.get_selections"](
        pattern=name,
    )
    if not state:
        ret.update(comment=f"Package {name} does not have a state")
    elif not salt.utils.data.is_true(state.get("hold", False)):
        if not __opts__["test"]:
            result = __salt__["pkg.set_selections"](selection={"hold": [name]})
            ret.update(
                changes=result[name],
                result=True,
                comment=f"Package {name} is now being held",
            )
        else:
            ret.update(result=None, comment=f"Package {name} is set to be held")
    else:
        ret.update(result=True, comment=f"Package {name} is already held")

    return ret
