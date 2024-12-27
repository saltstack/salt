r"""
Manage Windows Local Group Policy
=================================

.. versionadded:: 2016.11.0

This state module allows you to configure local Group Policy on Windows. You
can ensure the setting of a single policy or multiple policies in one pass.

Single policies must specify the policy name, the setting, and the policy class
(Machine/User/Both). Here are some examples for setting a single policy setting.

Example single policy configuration:

.. code-block:: yaml

    Ensure Account Lockout Duration:
      lgpo.set:
        - name: Account lockout duration
        - setting: 90
        - policy_class: Machine

Example using abbreviated form:

.. code-block:: yaml

    Account lockout duration:
      lgpo.set:
        - setting: 120
        - policy_class: Machine

It is also possible to set multiple policies in a single state. This is done by
setting the settings under either `computer_policy` or `user_policy`. Here are
some examples for setting multiple policy settings in a single state.

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

    Some policy settings can't be set on their own an require that other policy
    settings are set at the same time. It can be difficult to figure out what
    additional settings need to be applied. The easiest way to do this is to
    modify the setting manually using the Group Policy Editor (`gpedit.msc`) on
    the machine. Then `get` the policy settings configured on that machine. Use
    the following command:

    .. code-block:: bash

        salt-call --local lgpo.get machine

    For example, if I want to set the Windows Update settings for a Windows
    Server 2016 machine I would go into the Group Policy Editor (`gpedit.msc`)
    and configure the group policy. That policy can be found at: Computer
    Configuration -> Administrative Templates -> Windows Components -> Windows
    Update -> Configure Automatic Updates. You have the option to "Enable" the
    policy and set some configuration options. In this example, just click
    "Enable" and accept the default configuration options. Click "OK" to apply
    the setting.

    Now run the `get` command as shown above. You will find the following in
    the minion return:

    .. code-block:: bash

        Windows Components\Windows Update\Configure Automatic Updates:
            ----------
            Configure automatic updating:
                3 - Auto download and notify for install
            Install during automatic maintenance:
                False
            Install updates for other Microsoft products:
                False
            Scheduled install day:
                0 - Every day
            Scheduled install time:
                03:00

    This shows you that to enable the "Configure Automatic Updates" policy you
    also have to configure the following settings:

    - Configure automatic updating
    - Install during automatic maintenance
    - Install updates for other Microsoft products
    - Scheduled install day
    - Scheduled install time

    So, if you were writing a state for the above policy, it would look like
    this:

    .. code-block:: bash

        configure_windows_update_settings:
          lgpo.set:
            - computer_policy:
                Configure Automatic Updates:
                  Configure automatic updating: 3 - Auto download and notify for install
                  Install during automatic maintenance: False
                  Install updates for other Microsoft products: False
                  Scheduled install day: 0 - Every day
                  Scheduled install time: 03:00

    .. note::

        It is important that you put names of policies and settings exactly as
        they are displayed in the return. That includes capitalization and
        punctuation such as periods, dashes, etc. This rule applies to both
        the setting name and the setting value.

    .. warning::

        From time to time Microsoft updates the Administrative templates on the
        machine. This can cause the policy name to change or the list of
        settings that must be applied at the same time. These settings often
        change between versions of Windows as well. For example, Windows Server
        2019 allows you to also specify a specific week of the month to apply
        the update.

    Another thing note is the long policy name returned by the `get` function:

    .. code-block:: bash

        Windows Components\Windows Update\Configure Automatic Updates:

    When we wrote the state for this policy we only used the final portion of
    the policy name, `Configure Automatic Updates`. This usually works fine, but
    if you are having problems, you may try the long policy name.

    When writing the long name in a state file either wrap the name in single
    quotes to make yaml see it as raw data, or escape the back slashes.

    .. code-block:: bash

        'Windows Components\Windows Update\Configure Automatic Updates:'

        or

        Windows Components\\Windows Update\\Configure Automatic Updates:
"""

import logging

import salt.utils.data
import salt.utils.dictdiffer
import salt.utils.json
import salt.utils.stringutils
import salt.utils.versions
import salt.utils.win_functions

log = logging.getLogger(__name__)
__virtualname__ = "lgpo"
__func_alias__ = {"set_": "set"}


def __virtual__():
    """
    load this state if the win_lgpo module exists
    """
    if "lgpo.set" in __salt__:
        return __virtualname__
    return False, "lgpo module could not be loaded"


def _compare_policies(new_policy, current_policy):
    """
    Helper function that returns ``True`` if the policies are the same,
    otherwise ``False``
    """
    # Compared dicts, lists, and strings
    if isinstance(new_policy, (str, int)):
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
    if isinstance(data, str):
        data = data.replace("\x00", "")
        return salt.utils.stringutils.to_unicode(data)
    elif isinstance(data, dict):
        return {_convert_to_unicode(k): _convert_to_unicode(v) for k, v in data.items()}
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
    refresh_cache=False,
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

        refresh_cache (bool):
            Clear the cached policy definitions before applying the state. This
            is useful when the underlying policy files (ADMX/ADML) have been
            added/modified in the same state. This will allow those new policies
            to be picked up. This adds time to the state run when applied to
            multiple states within the same run. Therefore, it is best to only
            apply this to the first policy that is applied. For individual runs
            this will have no effect. Default is ``False``

            .. versionadded:: 3006.8
            .. versionadded:: 3007.1
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
        msg = "The policy_class parameter must be one of the following: {}"
        ret["result"] = False
        ret["comment"] = msg
        return ret
    if not setting:
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

    if refresh_cache:
        # Remove cached policies so new policies can be picked up
        __salt__["lgpo.clear_policy_cache"]()

    current_policy = {}
    deprecation_comments = []
    for p_class, p_data in pol_data.items():
        if p_data["requested_policy"]:
            for p_name, _ in p_data["requested_policy"].items():
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
                                # format. If found, add to deprecation comments
                                # and bail
                                if new_e_name in valid_names:
                                    msg = (
                                        '"{}" is no longer valid.\n'
                                        'Please use "{}" instead.'
                                        "".format(e_name, new_e_name)
                                    )
                                    deprecation_comments.append(msg)
                                else:
                                    msg = f"Invalid element name: {e_name}"
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
        if deprecation_comments:
            deprecation_comments.insert(
                0, "The LGPO module changed the way it gets policy element names."
            )
        deprecation_comments.append(ret["comment"])
        ret["comment"] = "\n".join(deprecation_comments).strip()
        return ret

    log.debug("pol_data == %s", pol_data)
    log.debug("current policy == %s", current_policy)

    # compare policies
    policy_changes = []
    for p_class, p_data in pol_data.items():
        requested_policy = p_data.get("requested_policy")
        if requested_policy:
            for p_name, p_setting in requested_policy.items():
                if p_name in current_policy[class_map[p_class]]:
                    # compare the requested and current policies
                    log.debug(
                        "need to compare %s from current/requested policy", p_name
                    )

                    # resolve user names in the requested policy and the current
                    # policy so that we are comparing apples to apples
                    if p_data["policy_lookup"][p_name]["rights_assignment"]:
                        resolved_names = []
                        for name in p_data["requested_policy"][p_name]:
                            resolved_names.append(
                                salt.utils.win_functions.get_sam_name(name)
                            )
                        p_data["requested_policy"][p_name] = resolved_names
                        resolved_names = []
                        for name in current_policy[class_map[p_class]][p_name]:
                            resolved_names.append(
                                salt.utils.win_functions.get_sam_name(name)
                            )
                        current_policy[class_map[p_class]][p_name] = resolved_names

                    changes = False
                    requested_policy_json = salt.utils.json.dumps(
                        p_data["requested_policy"][p_name], sort_keys=True
                    )
                    current_policy_json = salt.utils.json.dumps(
                        current_policy[class_map[p_class]][p_name], sort_keys=True
                    )

                    requested_policy_check = salt.utils.json.loads(
                        requested_policy_json
                    )
                    current_policy_check = salt.utils.json.loads(current_policy_json)

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
                        msg = f'"{p_name}" is already set'
                        log.debug(msg)
                else:
                    policy_changes.append(p_name)
                    log.debug("policy %s is not set, we will configure it", p_name)
    if __opts__["test"]:
        if policy_changes:
            msg = "The following policies are set to change:\n{}".format(
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
                for p_class, p_data in pol_data.items():
                    if p_data["requested_policy"]:
                        for p_name, p_setting in p_data["requested_policy"].items():
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
                    msg = "The following policies changed:\n{}".format(
                        "\n".join(policy_changes)
                    )
                else:
                    msg = "Failed to set the following policies:\n{}".format(
                        "\n".join(policy_changes)
                    )
                    ret["result"] = False
            else:
                msg = (
                    "Errors occurred while attempting to configure policies: {}".format(
                        _ret
                    )
                )
                ret["result"] = False
            deprecation_comments.append(msg)
            ret["comment"] = "\n".join(deprecation_comments).strip()
        else:
            msg = "All specified policies are properly configured"
            deprecation_comments.append(msg)
            ret["comment"] = "\n".join(deprecation_comments).strip()

    return ret
