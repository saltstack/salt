# -*- coding: utf-8 -*-
"""
Manage IPMI devices over LAN
============================

The following configuration defaults can be defined in the
minion, master config or pillar:

.. code-block:: yaml

    ipmi.config:
        api_host: 127.0.0.1
        api_user: admin
        api_pass: apassword
        api_port: 623
        api_kg: None

Every call can override the config defaults:

.. code-block:: yaml

    ensure myipmi system is set to network boot:
        ipmi.boot_device:
            - name: network
            - api_host: myipmi.hostname.com
            - api_user: root
            - api_pass: apassword
            - api_kg: None

    ensure myipmi system is powered on:
        ipmi.power:
            - name: boot
            - api_host: myipmi.hostname.com
            - api_user: root
            - api_pass: apassword
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
from salt.ext import six


def __virtual__():
    IMPORT_ERR = None
    try:
        from pyghmi.ipmi import command  # pylint: disable=unused-import
    except Exception as exc:  # pylint: disable=broad-except
        IMPORT_ERR = six.text_type(exc)
    return (IMPORT_ERR is None, IMPORT_ERR)


def boot_device(name="default", **kwargs):
    """
    Request power state change

    name = ``default``
        * network -- Request network boot
        * hd -- Boot from hard drive
        * safe -- Boot from hard drive, requesting 'safe mode'
        * optical -- boot from CD/DVD/BD drive
        * setup -- Boot into setup utility
        * default -- remove any IPMI directed boot device request

    kwargs
        - api_host=localhost
        - api_user=admin
        - api_pass=
        - api_port=623
        - api_kg=None
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    org = __salt__["ipmi.get_bootdev"](**kwargs)
    if "bootdev" in org:
        org = org["bootdev"]

    if org == name:
        ret["result"] = True
        ret["comment"] = "system already in this state"
        return ret

    if __opts__["test"]:
        ret["comment"] = "would change boot device"
        ret["result"] = None
        ret["changes"] = {"old": org, "new": name}
        return ret

    outdddd = __salt__["ipmi.set_bootdev"](bootdev=name, **kwargs)
    ret["comment"] = "changed boot device"
    ret["result"] = True
    ret["changes"] = {"old": org, "new": name}
    return ret


def power(name="power_on", wait=300, **kwargs):
    """
    Request power state change

    name
        Ensure power state one of:
            * power_on -- system turn on
            * power_off -- system turn off (without waiting for OS)
            * shutdown -- request OS proper shutdown
            * reset -- reset (without waiting for OS)
            * boot -- If system is off, then 'on', else 'reset'

    wait
        wait X seconds for the job to complete before forcing.
        (defaults to 300 seconds)

    kwargs
        - api_host=localhost
        - api_user=admin
        - api_pass=
        - api_port=623
        - api_kg=None
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    org = __salt__["ipmi.get_power"](**kwargs)

    state_map = {
        "off": "off",
        "on": "on",
        "power_off": "off",
        "power_on": "on",
        "shutdown": "off",
        "reset": "na",
        "boot": "na",
    }

    if org == state_map[name]:
        ret["result"] = True
        ret["comment"] = "system already in this state"
        return ret

    if __opts__["test"]:
        ret["comment"] = "would power: {0} system".format(name)
        ret["result"] = None
        ret["changes"] = {"old": org, "new": name}
        return ret

    outdddd = __salt__["ipmi.set_power"](name, wait=wait, **kwargs)
    ret["comment"] = "changed system power"
    ret["result"] = True
    ret["changes"] = {"old": org, "new": name}
    return ret


def user_present(
    name,
    uid,
    password,
    channel=14,
    callback=False,
    link_auth=True,
    ipmi_msg=True,
    privilege_level="administrator",
    **kwargs
):
    """
    Ensure IPMI user and user privileges.

    name
        name of user (limit 16 bytes)

    uid
        user id number (1 to 7)

    password
        user password (limit 16 bytes)

    channel
        ipmi channel defaults to 14 for auto

    callback
        User Restricted to Callback

        False = User Privilege Limit is determined by the User Privilege Limit
            parameter privilege_level, for both callback and non-callback connections.

        True  = User Privilege Limit is determined by the privilege_level
            parameter for callback connections, but is restricted to Callback
            level for non-callback connections. Thus, a user can only initiate
            a Callback when they 'call in' to the BMC, but once the callback
            connection has been made, the user could potentially establish a
            session as an Operator.

    link_auth
        User Link authentication
        True/False
        user name and password information will be used for link
        authentication, e.g. PPP CHAP) for the given channel. Link
        authentication itself is a global setting for the channel and is
        enabled/disabled via the serial/modem configuration parameters.

    ipmi_msg
        User IPMI Messaging
        True/False
        user name and password information will be used for IPMI
        Messaging. In this case, 'IPMI Messaging' refers to the ability to
        execute generic IPMI commands that are not associated with a
        particular payload type. For example, if IPMI Messaging is disabled for
        a user, but that user is enabled for activating the SOL
        payload type, then IPMI commands associated with SOL and session
        management, such as Get SOL Configuration Parameters and Close Session
        are available, but generic IPMI commands such as Get SEL Time are
        unavailable.)
        ipmi_msg

    privilege_level
        * callback
        * user
        * operator
        * administrator
        * proprietary
        * no_access

    kwargs
        - api_host=localhost
        - api_user=admin
        - api_pass=
        - api_port=623
        - api_kg=None
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    org_user = __salt__["ipmi.get_user"](uid=uid, channel=channel, **kwargs)

    change = False
    if org_user["access"]["callback"] != callback:
        change = True
    if org_user["access"]["link_auth"] != link_auth:
        change = True
    if org_user["access"]["ipmi_msg"] != ipmi_msg:
        change = True
    if org_user["access"]["privilege_level"] != privilege_level:
        change = True
    if (
        __salt__["ipmi.set_user_password"](
            uid, mode="test_password", password=password, **kwargs
        )
        is False
    ):
        change = True

    if change is False:
        ret["result"] = True
        ret["comment"] = "user already present"
        return ret

    if __opts__["test"]:
        ret["comment"] = "would (re)create user"
        ret["result"] = None
        ret["changes"] = {"old": org_user, "new": name}
        return ret

    __salt__["ipmi.ensure_user"](
        uid,
        name,
        password,
        channel,
        callback,
        link_auth,
        ipmi_msg,
        privilege_level,
        **kwargs
    )
    current_user = __salt__["ipmi.get_user"](uid=uid, channel=channel, **kwargs)
    ret["comment"] = "(re)created user"
    ret["result"] = True
    ret["changes"] = {"old": org_user, "new": current_user}
    return ret


def user_absent(name, channel=14, **kwargs):
    """
    Remove user
    Delete all user (uid) records having the matching name.

    name
        string name of user to delete

    channel
        channel to remove user access from defaults to 14 for auto.

    kwargs
        - api_host=localhost
        - api_user=admin
        - api_pass=
        - api_port=623
        - api_kg=None
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    user_id_list = __salt__["ipmi.get_name_uids"](name, channel, **kwargs)

    if len(user_id_list) == 0:
        ret["result"] = True
        ret["comment"] = "user already absent"
        return ret

    if __opts__["test"]:
        ret["comment"] = "would delete user(s)"
        ret["result"] = None
        ret["changes"] = {"delete": user_id_list}
        return ret

    for uid in user_id_list:
        __salt__["ipmi.delete_user"](uid, channel, **kwargs)

    ret["comment"] = "user(s) removed"
    ret["changes"] = {"old": user_id_list, "new": "None"}
    return ret
