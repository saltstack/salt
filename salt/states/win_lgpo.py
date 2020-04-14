# -*- coding: utf-8 -*-
"""
Manage Windows Local Group Policy
=================================

.. versionadded:: 2016.11.0

This state allows configuring local Windows Group Policy

The state can be used to ensure the setting of a single policy or multiple
policies in one pass.

Single policies must specify the policy name, the setting, and the policy class
(Machine/User/Both)

Example single policy configuration

.. code-block:: yaml

    Ensure Account Lockout Duration:
      lgpo.set:
        - name: Account lockout duration
        - setting: 90
        - policy_class: Machine

.. code-block:: yaml

    Account lockout duration:
      lgpo.set:
        - setting: 120
        - policy_class: Machine

Multiple policy configuration

.. code-block:: yaml

    Company Local Group Policy:
        lgpo.set:
            - computer_policy:
                Deny log on locally:
                  - Guest
                Account lockout duration: 120
                Account lockout threshold: 10
                Reset account lockout counter after: 120
                Enforce password history: 24
                Maximum password age: 60
                Minimum password age: 1
                Minimum password length: 14
                Password must meet complexity requirements: Enabled
                Store passwords using reversible encryption: Disabled
                Configure Automatic Updates:
                    Configure automatic updating: 4 - Auto download and schedule the intsall
                    Scheduled install day: 7 - Every Saturday
                    Scheduled install time: 17:00
                Specify intranet Microsoft update service location:
                    Set the intranet update service for detecting updates: http://mywsus
                    Set the intranet statistics server: http://mywsus
            - user_policy:
                Do not process the legacy run list: Enabled

.. code-block:: text

    server_policy:
      lgpo.set:
        - computer_policy:
            Maximum password age: 60
            Minimum password age: 1
            Minimum password length: 14
            Account lockout duration: 120
            Account lockout threshold: 10
            Reset account lockout counter after: 120
            Manage auditing and security log:
              - "BUILTIN\\Administrators"
            Replace a process level token:
              - "NT AUTHORITY\\NETWORK SERVICE"
              - "NT AUTHORITY\\LOCAL SERVICE"
            "Accounts: Guest account status": Disabled
            "Accounts: Rename guest account": Not_4_U
            "Audit: Audit the use of Backup and Restore privilege": Enabled
            "Interactive logon: Do not display last user name": Enabled
            "Network\\DNS Client\\Dynamic update": Disabled
            "System\\Logon\\Do not display the Getting Started welcome screen at logon": Enabled
            "Windows Components\\Remote Desktop Services\\Remote Desktop Session Host\\Connections\\Select RDP transport protocols":
                "Select Transport Type": "Use both UDP and TCP"
            "Windows Components\\Windows Update\\Allow Automatic Updates immediate installation": Enabled
            "Windows Components\\Windows Update\\Allow non-administrators to receive update notifications": Disabled
            "Windows Components\\Windows Update\\Always automatically restart at the scheduled time":
                "The restart timer will give users this much time to save their work (minutes)": 15
            "Windows Components\\Windows Update\\Automatic Updates detection frequency":
                "Check for updates at the following interval (hours)": 1
            "Windows Components\\Windows Update\\Configure Automatic Updates":
                "Configure automatic updating": 4 - Auto download and schedule the install
                "Install during automatic maintenance": False
                "Scheduled install day": 7 - Every Saturday
                "Scheduled install time": "17:00"
            "Windows Components\\Windows Update\\Delay Restart for scheduled installations":
                "Wait the following period before proceeding with a scheduled restart (minutes)": 1
            "Windows Components\\Windows Update\\No auto-restart with logged on users for scheduled automatic updates installations": Disabled
            "Windows Components\\Windows Update\\Re-prompt for restart with scheduled installations":
                "Wait the following period before prompting again with a scheduled restart (minutes)": 30
            "Windows Components\\Windows Update\\Reschedule Automatic Updates scheduled installations": Disabled
            "Windows Components\\Windows Update\\Specify intranet Microsoft update service location":
                "Set the intranet update service for detecting updates": http://mywsus
                "Set the intranet statistics server": http://mywsus
        - cumulative_rights_assignments: True
"""
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import salt libs
import salt.utils.data
import salt.utils.dictdiffer
import salt.utils.json
import salt.utils.stringutils
import salt.utils.versions
import salt.utils.win_functions

# Import 3rd party libs
from salt.ext import six

log = logging.getLogger(__name__)
__virtualname__ = "lgpo"
__func_alias__ = {"set_": "set"}


def __virtual__():
    """
    load this state if the win_lgpo module exists
    """
    return __virtualname__ if "lgpo.set" in __salt__ else False


def _compare_policies(new_policy, current_policy):
    """
    Helper function that returns ``True`` if the policies are the same,
    otherwise ``False``
    """
    # Compared dicts, lists, and strings
    if isinstance(new_policy, (six.string_types, six.integer_types)):
        return new_policy == current_policy
    elif isinstance(new_policy, list):
        if isinstance(current_policy, list):
            return salt.utils.data.compare_lists(new_policy, current_policy) == {}
        else:
            return False
    elif isinstance(new_policy, dict):
        if isinstance(current_policy, dict):
            return salt.utils.data.compare_dicts(new_policy, current_policy) == {}
        else:
            return False


def _convert_to_unicode(data):
    """
    Helper function that makes sure all items in the dictionary are unicode for
    comparing the existing state with the desired state. This function is only
    needed for Python 2 and can be removed once we've migrated to Python 3.

    The data returned by the current settings sometimes has a mix of unicode and
    string values (these don't matter in Py3). This causes the comparison to
    say it's not in the correct state even though it is. They basically compares
    apples to apples, etc.

    Also, in Python 2, the utf-16 encoded strings remain utf-16 encoded (each
    character separated by `/x00`) In Python 3 it returns a utf-8 string. This
    will just remove all the null bytes (`/x00`), again comparing apples to
    apples.
    """
    if isinstance(data, six.string_types):
        data = data.replace("\x00", "")
        return salt.utils.stringutils.to_unicode(data)
    elif isinstance(data, dict):
        return dict(
            (_convert_to_unicode(k), _convert_to_unicode(v)) for k, v in data.items()
        )
    elif isinstance(data, list):
        return list(_convert_to_unicode(v) for v in data)
    else:
        return data


def set_(
    name,
    setting=None,
    policy_class=None,
    computer_policy=None,
    user_policy=None,
    cumulative_rights_assignments=True,
    adml_language="en-US",
):
    """
    Ensure the specified policy is set.

    .. warning::
        The ``setting`` argument cannot be used in conjunction with the
        ``computer_policy`` or ``user_policy`` arguments

    Args:
        name (str): The name of a single policy to configure

        setting (str, dict, list):
            The configuration setting for the single named policy. If this
            argument is used the ``computer_policy`` / ``user_policy`` arguments
            will be ignored

        policy_class (str):
            The policy class of the single named policy to configure. This can
            ``machine``, ``user``, or ``both``

        computer_policy (dict):
            A dictionary of containing the policy name and key/value pairs of a
            set of computer policies to configure. If this argument is used, the
            ``name`` / ``policy_class`` arguments will be ignored

        user_policy (dict):
            A dictionary of containing the policy name and key/value pairs of a
            set of user policies to configure. If this argument is used, the
            ``name`` / ``policy_class`` arguments will be ignored

        cumulative_rights_assignments (bool):
            If user rights assignments are being configured, determines if any
            user right assignment policies specified will be cumulative or
            explicit

        adml_language (str):
            The adml language to use for AMDX policy data/display conversions.
            Default is ``en-US``
    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}
    policy_classes = ["machine", "computer", "user", "both"]
    class_map = {
        "computer": "Computer Configuration",
        "machine": "Computer Configuration",
        "user": "User Configuration",
    }
    if not setting and not computer_policy and not user_policy:
        msg = (
            "At least one of the parameters setting, computer_policy, or "
            "user_policy must be specified."
        )
        ret["result"] = False
        ret["comment"] = msg
        return ret
    if setting and not policy_class:
        msg = (
            "A single policy setting was specified but the policy_class "
            "was not specified."
        )
        ret["result"] = False
        ret["comment"] = msg
        return ret
    if setting and (computer_policy or user_policy):
        msg = (
            "The setting and computer_policy/user_policy parameters are "
            "mutually exclusive.  Please specify either a policy name and "
            "setting or a computer_policy and/or user_policy dict"
        )
        ret["result"] = False
        ret["comment"] = msg
        return ret
    if policy_class and policy_class.lower() not in policy_classes:
        msg = "The policy_class parameter must be one of the following: {0}"
        ret["result"] = False
        ret["comment"] = msg
        return ret
    if not setting:
        if computer_policy and user_policy:
            policy_class = "both"
        elif computer_policy:
            policy_class = "machine"
        elif user_policy:
            policy_class = "user"
        if computer_policy and not isinstance(computer_policy, dict):
            msg = "The computer_policy must be specified as a dict."
            ret["result"] = False
            ret["comment"] = msg
            return ret
        if user_policy and not isinstance(user_policy, dict):
            msg = "The user_policy must be specified as a dict."
            ret["result"] = False
            ret["comment"] = msg
            return ret
    else:
        user_policy = {}
        computer_policy = {}
        if policy_class.lower() == "both":
            user_policy[name] = setting
            computer_policy[name] = setting
        elif policy_class.lower() == "user":
            user_policy[name] = setting
        elif policy_class.lower() in ["machine", "computer"]:
            computer_policy[name] = setting
    pol_data = {
        "user": {"requested_policy": user_policy, "policy_lookup": {}},
        "machine": {"requested_policy": computer_policy, "policy_lookup": {}},
    }

    current_policy = {}
    deprecation_comments = []
    for p_class, p_data in six.iteritems(pol_data):
        if p_data["requested_policy"]:
            for p_name, _ in six.iteritems(p_data["requested_policy"]):
                lookup = __salt__["lgpo.get_policy_info"](
                    policy_name=p_name,
                    policy_class=p_class,
                    adml_language=adml_language,
                )
                if lookup["policy_found"]:
                    pol_data[p_class]["policy_lookup"][p_name] = lookup
                    # Since we found the policy, let's get the current setting
                    # as well
                    current_policy.setdefault(class_map[p_class], {})
                    current_policy[class_map[p_class]][p_name] = __salt__[
                        "lgpo.get_policy"
                    ](
                        policy_name=p_name,
                        policy_class=p_class,
                        adml_language=adml_language,
                        return_value_only=True,
                    )
                    # Validate element names
                    if isinstance(p_data["requested_policy"][p_name], dict):
                        valid_names = []
                        for element in lookup["policy_elements"]:
                            valid_names.extend(element["element_aliases"])
                        for e_name in p_data["requested_policy"][p_name]:
                            if e_name not in valid_names:
                                new_e_name = e_name.split(":")[-1].strip()
                                # If we find an invalid name, test the new
                                # format. If found, replace the old with the
                                # new
                                if new_e_name in valid_names:
                                    msg = (
                                        "The LGPO module changed the way "
                                        "it gets policy element names.\n"
                                        '"{0}" is no longer valid.\n'
                                        'Please use "{1}" instead.'
                                        "".format(e_name, new_e_name)
                                    )
                                    salt.utils.versions.warn_until("Phosphorus", msg)
                                    pol_data[p_class]["requested_policy"][p_name][
                                        new_e_name
                                    ] = pol_data[p_class]["requested_policy"][
                                        p_name
                                    ].pop(
                                        e_name
                                    )
                                    deprecation_comments.append(msg)
                                else:
                                    msg = "Invalid element name: {0}".format(e_name)
                                    ret["comment"] = "\n".join(
                                        [ret["comment"], msg]
                                    ).strip()
                                    ret["result"] = False
                else:
                    ret["comment"] = "\n".join(
                        [ret["comment"], lookup["message"]]
                    ).strip()
                    ret["result"] = False
    if not ret["result"]:
        deprecation_comments.append(ret["comment"])
        ret["comment"] = "\n".join(deprecation_comments).strip()
        return ret

    log.debug("pol_data == %s", pol_data)
    log.debug("current policy == %s", current_policy)

    # compare policies
    policy_changes = []
    for p_class, p_data in six.iteritems(pol_data):
        requested_policy = p_data.get("requested_policy")
        if requested_policy:
            for p_name, p_setting in six.iteritems(requested_policy):
                if p_name in current_policy[class_map[p_class]]:
                    # compare
                    log.debug(
                        "need to compare %s from current/requested " "policy", p_name
                    )
                    changes = False
                    requested_policy_json = salt.utils.json.dumps(
                        p_data["requested_policy"][p_name], sort_keys=True
                    ).lower()
                    current_policy_json = salt.utils.json.dumps(
                        current_policy[class_map[p_class]][p_name], sort_keys=True
                    ).lower()

                    requested_policy_check = salt.utils.json.loads(
                        requested_policy_json
                    )
                    current_policy_check = salt.utils.json.loads(current_policy_json)

                    if six.PY2:
                        current_policy_check = _convert_to_unicode(current_policy_check)

                    # Are the requested and current policies identical
                    policies_are_equal = _compare_policies(
                        requested_policy_check, current_policy_check
                    )

                    if not policies_are_equal:
                        if (
                            p_data["policy_lookup"][p_name]["rights_assignment"]
                            and cumulative_rights_assignments
                        ):
                            for user in p_data["requested_policy"][p_name]:
                                if (
                                    user
                                    not in current_policy[class_map[p_class]][p_name]
                                ):
                                    user = salt.utils.win_functions.get_sam_name(user)
                                    if (
                                        user
                                        not in current_policy[class_map[p_class]][
                                            p_name
                                        ]
                                    ):
                                        changes = True
                        else:
                            changes = True
                        if changes:
                            log.debug("%s current policy != requested policy", p_name)
                            log.debug(
                                "We compared %s to %s",
                                requested_policy_json,
                                current_policy_json,
                            )
                            policy_changes.append(p_name)
                    else:
                        msg = '"{0}" is already set'.format(p_name)
                        log.debug(msg)
                else:
                    policy_changes.append(p_name)
                    log.debug("policy %s is not set, we will configure it", p_name)
    if __opts__["test"]:
        if policy_changes:
            msg = "The following policies are set to change:\n{0}" "".format(
                "\n".join(policy_changes)
            )
            ret["result"] = None
        else:
            msg = "All specified policies are properly configured"
        deprecation_comments.append(msg)
        ret["comment"] = "\n".join(deprecation_comments).strip()
    else:
        if policy_changes:
            _ret = __salt__["lgpo.set"](
                computer_policy=pol_data["machine"]["requested_policy"],
                user_policy=pol_data["user"]["requested_policy"],
                cumulative_rights_assignments=cumulative_rights_assignments,
                adml_language=adml_language,
            )
            if _ret:
                ret["result"] = _ret
                new_policy = {}
                for p_class, p_data in six.iteritems(pol_data):
                    if p_data["requested_policy"]:
                        for p_name, p_setting in six.iteritems(
                            p_data["requested_policy"]
                        ):
                            new_policy.setdefault(class_map[p_class], {})
                            new_policy[class_map[p_class]][p_name] = __salt__[
                                "lgpo.get_policy"
                            ](
                                policy_name=p_name,
                                policy_class=p_class,
                                adml_language=adml_language,
                                return_value_only=True,
                            )
                ret["changes"] = salt.utils.dictdiffer.deep_diff(
                    old=current_policy, new=new_policy
                )
                if ret["changes"]:
                    msg = "The following policies changed:\n{0}" "".format(
                        "\n".join(policy_changes)
                    )
                else:
                    msg = (
                        "The following policies are in the correct "
                        "state:\n{0}".format("\n".join(policy_changes))
                    )
            else:
                msg = (
                    "Errors occurred while attempting to configure "
                    "policies: {0}".format(_ret)
                )
                ret["result"] = False
            deprecation_comments.append(msg)
            ret["comment"] = "\n".join(deprecation_comments).strip()
        else:
            msg = "All specified policies are properly configured"
            deprecation_comments.append(msg)
            ret["comment"] = "\n".join(deprecation_comments).strip()

    return ret
