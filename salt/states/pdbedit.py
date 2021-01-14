# -*- coding: utf-8 -*-
"""
Manage accounts in Samba's passdb using pdbedit

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       pdbedit
:platform:      posix

.. versionadded:: 2017.7.0

.. code-block:: yaml

    wash:
      pdbedit.absent

    kaylee:
      pdbedit.managed:
        - password: A70C708517B5DD0EDB67714FE25336EB
        - password_hashed: True
        - drive: 'X:'
        - homedir: '\\\\serenity\\mechanic\\profile'
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging

# Import Salt libs
import salt.utils.data

log = logging.getLogger(__name__)

# Define the state's virtual name
__virtualname__ = "pdbedit"


def __virtual__():
    """
    Provides pdbedit when available
    """
    if "pdbedit.create" in __salt__:
        return True
    else:
        return (
            False,
            "{0} state module can only be loaded when the pdbedit module is available".format(
                __virtualname__
            ),
        )


def absent(name):
    """
    Ensure user account is absent

    name : string
        username
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    # remove if needed
    if name in __salt__["pdbedit.list"](False):
        res = __salt__["pdbedit.delete"](name)
        if res[name] in ["deleted"]:  # check if we need to update changes
            ret["changes"].update(res)
        elif res[name] not in ["absent"]:  # oops something went wrong
            ret["result"] = False
    else:
        ret["comment"] = "account {login} is absent".format(login=name)

    return ret


def managed(name, **kwargs):
    """
    Manage user account

    login : string
        login name
    password : string
        password
    password_hashed : boolean
        set if password is a nt hash instead of plain text
    domain : string
        users domain
    profile : string
        profile path
    script : string
        logon script
    drive : string
        home drive
    homedir : string
        home directory
    fullname : string
        full name
    account_desc : string
        account description
    machine_sid : string
        specify the machines new primary group SID or rid
    user_sid : string
        specify the users new primary group SID or rid
    account_control : string
        specify user account control properties

        .. note::
            Only the following can be set:
            - N: No password required
            - D: Account disabled
            - H: Home directory required
            - L: Automatic Locking
            - X: Password does not expire
    reset_login_hours : boolean
        reset the users allowed logon hours
    reset_bad_password_count : boolean
        reset the stored bad login counter
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    # save state
    saved = __salt__["pdbedit.list"](hashes=True)
    saved = saved[name] if name in saved else {}

    # call pdbedit.modify
    kwargs["login"] = name
    res = __salt__["pdbedit.modify"](**kwargs)

    # calculate changes
    if res[name] in ["created"]:
        ret["changes"] = res
    elif res[name] in ["updated"]:
        ret["changes"][name] = salt.utils.data.compare_dicts(
            saved, __salt__["pdbedit.list"](hashes=True)[name],
        )
    elif res[name] not in ["unchanged"]:
        ret["result"] = False
        ret["comment"] = res[name]

    return ret


def present(name, **kwargs):
    """
    Alias for pdbedit.managed
    """
    return managed(name, **kwargs)


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
