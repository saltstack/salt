"""
States for managing Hashicorp Vault.
Currently handles policies.
Configuration instructions are documented in the :ref:`execution module docs <vault-setup>`.

:maintainer:    SaltStack
:maturity:      new
:platform:      all

.. versionadded:: 2017.7.0

"""

import difflib
import logging

from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

__deprecated__ = (
    3009,
    "vault",
    "https://github.com/salt-extensions/saltext-vault",
)


def policy_present(name, rules):
    """
    Ensure a Vault policy with the given name and rules is present.

    name
        The name of the policy

    rules
        Rules formatted as in-line HCL


    .. code-block:: yaml

        demo-policy:
          vault.policy_present:
            - name: foo/bar
            - rules: |
                path "secret/top-secret/*" {
                  policy = "deny"
                }
                path "secret/not-very-secret/*" {
                  policy = "write"
                }

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        existing_rules = __salt__["vault.policy_fetch"](name)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to read policy: {err}"
        return ret

    if existing_rules == rules:
        ret["comment"] = "Policy exists, and has the correct content"
        return ret

    diff = "".join(
        difflib.unified_diff(
            (existing_rules or "").splitlines(True), rules.splitlines(True)
        )
    )

    ret["changes"] = {name: diff}

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Policy would be " + (
            "created" if existing_rules is None else "updated"
        )
        return ret

    try:
        __salt__["vault.policy_write"](name, rules)
        ret["comment"] = "Policy has been " + (
            "created" if existing_rules is None else "updated"
        )
        return ret
    except CommandExecutionError as err:
        return {
            "name": name,
            "changes": {},
            "result": False,
            "comment": f"Failed to write policy: {err}",
        }


def policy_absent(name):
    """
    Ensure a Vault policy with the given name and rules is absent.

    name
        The name of the policy
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        existing_rules = __salt__["vault.policy_fetch"](name)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to read policy: {err}"
        return ret

    if existing_rules is None:
        ret["comment"] = "Policy is already absent"
        return ret

    ret["changes"] = {"deleted": name}

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Policy would be deleted"
        return ret

    try:
        if not __salt__["vault.policy_delete"](name):
            raise CommandExecutionError(
                "Policy was initially reported as existent, but seemed to be "
                "absent while deleting."
            )
        ret["comment"] = "Policy has been deleted"
        return ret
    except CommandExecutionError as err:
        return {
            "name": name,
            "changes": {},
            "result": False,
            "comment": f"Failed to delete policy: {err}",
        }
