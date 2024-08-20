"""
Management of nftables
======================

This is an nftables-specific module designed to manage Linux firewalls. It is
expected that this state module, and other system-specific firewall states, may
at some point be deprecated in favor of a more generic `firewall` state.

.. code-block:: yaml

    httpd:
      nftables.append:
        - table: filter
        - chain: input
        - jump: accept
        - match: state
        - connstate: new
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    httpd:
      nftables.append:
        - table: filter
        - family: ipv6
        - chain: INPUT
        - jump: ACCEPT
        - match: state
        - connstate: NEW
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    httpd:
      nftables.insert:
        - position: 1
        - table: filter
        - chain: INPUT
        - jump: ACCEPT
        - match: state
        - connstate: NEW
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    httpd:
      nftables.insert:
        - position: 1
        - table: filter
        - family: ipv6
        - chain: INPUT
        - jump: ACCEPT
        - match: state
        - connstate: NEW
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    httpd:
      nftables.delete:
        - table: filter
        - chain: INPUT
        - jump: ACCEPT
        - match: state
        - connstate: NEW
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    httpd:
      nftables.delete:
        - position: 1
        - table: filter
        - chain: INPUT
        - jump: ACCEPT
        - match: state
        - connstate: NEW
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    httpd:
      nftables.delete:
        - table: filter
        - family: ipv6
        - chain: INPUT
        - jump: ACCEPT
        - match: state
        - connstate: NEW
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    output:
      nftables.chain_present:
        - family: ip
        - table: filter

    output:
      nftables.chain_absent:
        - family: ip
        - table: filter

"""

import logging

from salt.state import STATE_INTERNAL_KEYWORDS as _STATE_INTERNAL_KEYWORDS

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if the locale module is available in __salt__
    """
    if "nftables.version" in __salt__:
        return "nftables"
    return (False, "nftables module could not be loaded")


def chain_present(
    name, table="filter", table_type=None, hook=None, priority=None, family="ipv4"
):
    """
    .. versionadded:: 2014.7.0

    .. versionchanged:: 3002

    Verify a chain exists in a table.

    name
        A user-defined chain name.

    table
        The table to own the chain.

    family
        Networking family, either ipv4 or ipv6
    """

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    chain_check = __salt__["nftables.check_chain"](table, name, family=family)
    if chain_check["result"] is True:
        ret["result"] = True
        ret["comment"] = "nftables {} chain is already exist in {} table for {}".format(
            name, table, family
        )
        return ret

    if __opts__["test"]:
        ret["comment"] = (
            "nftables chain {} would be created in table {} for family {}".format(
                name, table, family
            )
        )
        return ret

    res = __salt__["nftables.new_chain"](
        table, name, table_type=table_type, hook=hook, priority=priority, family=family
    )

    if res["result"] is True:
        ret["changes"] = {"locale": name}
        ret["result"] = True
        ret["comment"] = "nftables {} chain in {} table create success for {}".format(
            name, table, family
        )
        return ret
    else:
        ret["result"] = False
        ret["comment"] = "Failed to create {} chain in {} table: {} for {}".format(
            name, table, res["comment"].strip(), family
        )
        return ret


def chain_absent(name, table="filter", family="ipv4"):
    """
    .. versionadded:: 2014.7.0

    Verify the chain is absent.

    family
        Networking family, either ipv4 or ipv6
    """

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    chain_check = __salt__["nftables.check_chain"](table, name, family)
    if not chain_check:
        ret["result"] = True
        ret["comment"] = (
            "nftables {} chain is already absent in {} table for {}".format(
                name, table, family
            )
        )
        return ret

    flush_chain = __salt__["nftables.flush"](table, name, family)
    if flush_chain:
        command = __salt__["nftables.delete_chain"](table, name, family)
        if command is True:
            ret["changes"] = {"locale": name}
            ret["result"] = True
            ret["comment"] = (
                "nftables {} chain in {} table delete success for {}".format(
                    name, table, family
                )
            )
        else:
            ret["result"] = False
            ret["comment"] = "Failed to delete {} chain in {} table: {} for {}".format(
                name, table, command.strip(), family
            )
    else:
        ret["result"] = False
        ret["comment"] = "Failed to flush {} chain in {} table: {} for {}".format(
            name, table, flush_chain.strip(), family
        )
    return ret


def append(name, family="ipv4", **kwargs):
    """
    .. versionadded:: 0.17.0

    Append a rule to a chain

    name
        A user-defined name to call this rule by in another part of a state or
        formula. This should not be an actual rule.

    family
        Network family, ipv4 or ipv6.

    All other arguments are passed in with the same name as the long option
    that would normally be used for nftables, with one exception: `--state` is
    specified as `connstate` instead of `state` (not to be confused with
    `ctstate`).
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    for ignore in _STATE_INTERNAL_KEYWORDS:
        if ignore in kwargs:
            del kwargs[ignore]
    res = __salt__["nftables.build_rule"](family=family, **kwargs)
    if not res["result"]:
        return res
    rule = res["rule"]

    res = __salt__["nftables.build_rule"](
        full=True, family=family, command="add", **kwargs
    )
    if not res["result"]:
        return res
    command = res["rule"]

    res = __salt__["nftables.check"](kwargs["table"], kwargs["chain"], rule, family)
    if res["result"]:
        ret["result"] = True
        ret["comment"] = "nftables rule for {} already set ({}) for {}".format(
            name, command.strip(), family
        )
        return ret
    if "test" in __opts__ and __opts__["test"]:
        ret["comment"] = "nftables rule for {} needs to be set ({}) for {}".format(
            name, command.strip(), family
        )
        return ret
    res = __salt__["nftables.append"](kwargs["table"], kwargs["chain"], rule, family)
    if res["result"]:
        ret["changes"] = {"locale": name}
        ret["result"] = True
        ret["comment"] = "Set nftables rule for {} to: {} for {}".format(
            name, command.strip(), family
        )
        if "save" in kwargs:
            if kwargs["save"]:
                __salt__["nftables.save"](filename=None, family=family)
                ret["comment"] = (
                    "Set and Saved nftables rule for {} to: {} for {}".format(
                        name, command.strip(), family
                    )
                )
        return ret
    else:
        ret["result"] = False
        ret["comment"] = (
            "Failed to set nftables rule for {}.\nAttempted rule was {} for {}.\n{}".format(
                name, command.strip(), family, res["comment"]
            )
        )
        return ret


def insert(name, family="ipv4", **kwargs):
    """
    .. versionadded:: 2014.7.0

    Insert a rule into a chain

    name
        A user-defined name to call this rule by in another part of a state or
        formula. This should not be an actual rule.

    family
        Networking family, either ipv4 or ipv6

    All other arguments are passed in with the same name as the long option
    that would normally be used for nftables, with one exception: `--state` is
    specified as `connstate` instead of `state` (not to be confused with
    `ctstate`).
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    for ignore in _STATE_INTERNAL_KEYWORDS:
        if ignore in kwargs:
            del kwargs[ignore]
    res = __salt__["nftables.build_rule"](family=family, **kwargs)
    if not res["result"]:
        return res
    rule = res["rule"]

    res = __salt__["nftables.build_rule"](
        full=True, family=family, command="insert", **kwargs
    )
    if not res["result"]:
        return res
    command = res["rule"]

    res = __salt__["nftables.check"](kwargs["table"], kwargs["chain"], rule, family)
    if res["result"]:
        ret["result"] = True
        ret["comment"] = "nftables rule for {} already set for {} ({})".format(
            name, family, command.strip()
        )
        return ret
    if "test" in __opts__ and __opts__["test"]:
        ret["comment"] = "nftables rule for {} needs to be set for {} ({})".format(
            name, family, command.strip()
        )
        return ret
    res = __salt__["nftables.insert"](
        kwargs["table"], kwargs["chain"], kwargs["position"], rule, family
    )
    if res["result"]:
        ret["changes"] = {"locale": name}
        ret["result"] = True
        ret["comment"] = "Set nftables rule for {} to: {} for {}".format(
            name, command.strip(), family
        )
        if "save" in kwargs:
            if kwargs["save"]:
                __salt__["nftables.save"](filename=None, family=family)
                ret["comment"] = (
                    "Set and Saved nftables rule for {} to: {} for {}".format(
                        name, command.strip(), family
                    )
                )
        return ret
    else:
        ret["result"] = False
        ret["comment"] = (
            "Failed to set nftables rule for {}.\nAttempted rule was {}".format(
                name, command.strip()
            )
        )
        return ret


def delete(name, family="ipv4", **kwargs):
    """
    .. versionadded:: 2014.7.0

    Delete a rule to a chain

    name
        A user-defined name to call this rule by in another part of a state or
        formula. This should not be an actual rule.

    family
        Networking family, either ipv4 or ipv6

    All other arguments are passed in with the same name as the long option
    that would normally be used for nftables, with one exception: `--state` is
    specified as `connstate` instead of `state` (not to be confused with
    `ctstate`).
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    for ignore in _STATE_INTERNAL_KEYWORDS:
        if ignore in kwargs:
            del kwargs[ignore]
    res = __salt__["nftables.build_rule"](family=family, **kwargs)
    if not res["result"]:
        return res
    rule = res["rule"]

    res = __salt__["nftables.build_rule"](
        full=True, family=family, command="D", **kwargs
    )
    if not res["result"]:
        return res
    command = res["rule"]

    res = __salt__["nftables.check"](kwargs["table"], kwargs["chain"], rule, family)

    if not res["result"]:
        ret["result"] = True
        ret["comment"] = "nftables rule for {} already absent for {} ({})".format(
            name, family, command.strip()
        )
        return ret
    if "test" in __opts__ and __opts__["test"]:
        ret["comment"] = "nftables rule for {} needs to be deleted for {} ({})".format(
            name, family, command.strip()
        )
        return ret

    if "position" in kwargs:
        res = __salt__["nftables.delete"](
            kwargs["table"], kwargs["chain"], family=family, position=kwargs["position"]
        )
    else:
        res = __salt__["nftables.delete"](
            kwargs["table"], kwargs["chain"], family=family, rule=rule
        )

    if res["result"]:
        ret["changes"] = {"locale": name}
        ret["result"] = True
        ret["comment"] = f"Delete nftables rule for {name} {command.strip()}"
        if "save" in kwargs:
            if kwargs["save"]:
                __salt__["nftables.save"](filename=None, family=family)
                ret["comment"] = (
                    "Deleted and Saved nftables rule for {} for {}{}".format(
                        name, command.strip(), family
                    )
                )
        return ret
    else:
        ret["result"] = False
        ret["comment"] = (
            "Failed to delete nftables rule for {}.\nAttempted rule was {}".format(
                name, command.strip()
            )
        )
        return ret


def flush(name, family="ipv4", ignore_absence=False, **kwargs):
    """
    .. versionadded:: 2014.7.0

    .. versionchanged:: 3002

    Flush current nftables state

    family
        Networking family, either ipv4 or ipv6

    ignore_absence
        If set to True, attempts to flush a non-existent table will not
        result in a failed state.

        .. versionadded:: 3002

    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    if __opts__["test"]:
        ret["comment"] = "nftables flush not performed in test mode."
        return ret

    for ignore in _STATE_INTERNAL_KEYWORDS:
        if ignore in kwargs:
            del kwargs[ignore]

    if "table" not in kwargs:
        kwargs["table"] = "filter"

    check_table = __salt__["nftables.check_table"](kwargs["table"], family=family)
    if not ignore_absence and not check_table["result"]:
        ret["result"] = False
        ret["comment"] = (
            "Failed to flush table {} in family {}, table does not exist.".format(
                kwargs["table"], family
            )
        )
        return ret

    if "chain" not in kwargs:
        kwargs["chain"] = ""
    else:
        check_chain = __salt__["nftables.check_chain"](
            kwargs["table"], kwargs["chain"], family=family
        )
        if not ignore_absence and not check_chain["result"]:
            ret["result"] = False
            ret["comment"] = (
                "Failed to flush chain {} in table {} in family {}, chain does not"
                " exist.".format(kwargs["chain"], kwargs["table"], family)
            )
            return ret

    res = __salt__["nftables.flush"](kwargs["table"], kwargs["chain"], family)
    if res["result"] or (
        ignore_absence and (not check_table["result"] or not check_chain["result"])
    ):
        ret["changes"] = {"locale": name}
        ret["result"] = True
        ret["comment"] = "Flush nftables rules in {} table {} chain {} family".format(
            kwargs["table"], kwargs["chain"], family
        )
        return ret
    else:
        ret["result"] = False
        ret["comment"] = "Failed to flush nftables rules"
        return ret


def set_policy(name, table="filter", family="ipv4", **kwargs):
    """
    .. versionadded:: 3002

    Sets the default policy for nftables chains

    table
        The table that owns the chain that should be modified

    family
        Networking family, either ipv4 or ipv6

    policy
        The requested table policy (accept or drop)

    save
        Boolean to save the in-memory nftables settings to a file.

    save_filename
        The filename to save the nftables settings (default: /etc/nftables
        or /etc/nftables/salt-all-in-one.nft if the former is a directory)

    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    for ignore in _STATE_INTERNAL_KEYWORDS:
        if ignore in kwargs:
            del kwargs[ignore]

    policy = __salt__["nftables.get_policy"](table, kwargs["chain"], family)

    if (policy or "").lower() == kwargs["policy"].lower():
        ret["result"] = True
        ret["comment"] = (
            "nftables default policy for chain {} on table {} for {} already set to {}".format(
                kwargs["chain"], table, family, kwargs["policy"]
            )
        )
        return ret

    if __opts__["test"]:
        ret["comment"] = (
            "nftables default policy for chain {} on table {} for {} needs to be set"
            " to {}".format(kwargs["chain"], table, family, kwargs["policy"])
        )
        return ret

    if __salt__["nftables.set_policy"](
        table, kwargs["chain"], kwargs["policy"].lower(), family
    ):
        ret["changes"] = {"locale": name}
        ret["result"] = True
        ret["comment"] = "Set default policy for {} to {} family {}".format(
            kwargs["chain"], kwargs["policy"], family
        )

        if "save" in kwargs:
            if kwargs["save"]:
                __salt__["nftables.save"](
                    filename=kwargs.get("save_filename"), family=family
                )
                ret["comment"] = (
                    "Set and saved default policy for {} to {} family {}".format(
                        kwargs["chain"], kwargs["policy"], family
                    )
                )
    else:
        ret["result"] = False
        ret["comment"] = "Failed to set nftables default policy"

    return ret


def table_present(name, family="ipv4", **kwargs):
    """
    .. versionadded:: 3002

    Ensure an nftables table is present

    name
        A user-defined table name.

    family
        Networking family, either ipv4 or ipv6
    """

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    table_check = __salt__["nftables.check_table"](name, family=family)

    if table_check["result"] is True:
        ret["result"] = True
        ret["comment"] = "nftables table {} already exists in family {}".format(
            name, family
        )
        return ret

    if __opts__["test"]:
        ret["comment"] = "nftables table {} would be created in family {}".format(
            name, family
        )
        return ret

    res = __salt__["nftables.new_table"](name, family=family)

    if res["result"] is True:
        ret["changes"] = {"locale": name}
        ret["result"] = True
        ret["comment"] = "nftables table {} successfully created in family {}".format(
            name, family
        )
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to create table {name} for family {family}"

    return ret


def table_absent(name, family="ipv4", **kwargs):
    """
    .. versionadded:: 3002

    Ensure an nftables table is absent

    name
        Name of the table to ensure is absent

    family
        Networking family, either ipv4 or ipv6
    """

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    table_check = __salt__["nftables.check_table"](name, family)

    if table_check["result"] is False:
        ret["result"] = True
        ret["comment"] = "nftables table {} is already absent from family {}".format(
            name, family
        )
        return ret

    if __opts__["test"]:
        ret["comment"] = "nftables table {} would be deleted from family {}".format(
            name, family
        )
        return ret

    res = __salt__["nftables.delete_table"](name, family=family)

    if res["result"] is True:
        ret["changes"] = {"locale": name}
        ret["result"] = True
        ret["comment"] = "nftables table {} successfully deleted from family {}".format(
            name, family
        )
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to delete table {name} from family {family}"

    return ret
