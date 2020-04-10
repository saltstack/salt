# -*- coding: utf-8 -*-
"""
Package management operations specific to APT- and DEB-based systems
====================================================================
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

# Import salt libs
import salt.utils.data

log = logging.getLogger(__name__)


# Define the module's virtual name
__virtualname__ = "apt"


def __virtual__():
    """
    Only work on apt-based platforms with pkg.get_selections
    """
    return __virtualname__ if __salt__.get("pkg.get_selections", False) else False


def held(name):
    """
    Set package in 'hold' state, meaning it will not be upgraded.

    name
        The name of the package, e.g., 'tmux'
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    state = __salt__["pkg.get_selections"](pattern=name,)
    if not state:
        ret.update(comment="Package {0} does not have a state".format(name))
    elif not salt.utils.data.is_true(state.get("hold", False)):
        if not __opts__["test"]:
            result = __salt__["pkg.set_selections"](selection={"hold": [name]})
            ret.update(
                changes=result[name],
                result=True,
                comment="Package {0} is now being held".format(name),
            )
        else:
            ret.update(
                result=None, comment="Package {0} is set to be held".format(name)
            )
    else:
        ret.update(result=True, comment="Package {0} is already held".format(name))

    return ret
