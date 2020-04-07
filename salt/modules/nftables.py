# -*- coding: utf-8 -*-
"""
Support for nftables
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import json
import logging
import re

import salt.utils.data
import salt.utils.files
import salt.utils.path
from salt.exceptions import CommandExecutionError

# Import salt libs
from salt.ext import six
from salt.state import STATE_INTERNAL_KEYWORDS as _STATE_INTERNAL_KEYWORDS

# Set up logging
log = logging.getLogger(__name__)

_NFTABLES_FAMILIES = {
    "ipv4": "ip",
    "ip4": "ip",
    "ip": "ip",
    "ipv6": "ip6",
    "ip6": "ip6",
    "inet": "inet",
    "arp": "arp",
    "bridge": "bridge",
    "netdev": "netdev",
}


def __virtual__():
    """
    Only load the module if nftables is installed
    """
    if salt.utils.path.which("nft"):
        return "nftables"
    return (
        False,
        "The nftables execution module failed to load: nftables is not installed.",
    )


def _nftables_cmd():
    """
    Return correct command
    """
    return "nft"


def _conf(family="ip"):
    """
    Use the same file for rules for now.
    """
    if __grains__["os_family"] == "RedHat":
        return "/etc/nftables"
    elif __grains__["os_family"] == "Arch":
        return "/etc/nftables"
    elif __grains__["os_family"] == "Debian":
        return "/etc/nftables"
    elif __grains__["os"] == "Gentoo":
        return "/etc/nftables"
    else:
        return False


def version():
    """
    Return version from nftables --version

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.version

    """
    cmd = "{0} --version".format(_nftables_cmd())
    out = __salt__["cmd.run"](cmd).split()
    return out[1]


def build_rule(
    table=None,
    chain=None,
    command=None,
    position="",
    full=None,
    family="ipv4",
    **kwargs
):
    """
    Build a well-formatted nftables rule based on kwargs.
    A `table` and `chain` are not required, unless `full` is True.

    If `full` is `True`, then `table`, `chain` and `command` are required.
    `command` may be specified as either insert, append, or delete.
    This will return the nftables command, exactly as it would
    be used from the command line.

    If a position is required (as with `insert` or `delete`), it may be specified as
    `position`. This will only be useful if `full` is True.

    If `connstate` is passed in, it will automatically be changed to `state`.

    CLI Examples:

    .. code-block:: bash

        salt '*' nftables.build_rule match=state \\
            connstate=RELATED,ESTABLISHED jump=ACCEPT
        salt '*' nftables.build_rule filter input command=insert position=3 \\
            full=True match=state state=related,established jump=accept

        IPv6:
        salt '*' nftables.build_rule match=state \\
            connstate=related,established jump=accept \\
            family=ipv6
        salt '*' nftables.build_rule filter input command=insert position=3 \\
            full=True match=state state=related,established jump=accept \\
            family=ipv6

    """
    ret = {"comment": "", "rule": "", "result": False}

    if "target" in kwargs:
        kwargs["jump"] = kwargs["target"]
        del kwargs["target"]

    for ignore in list(_STATE_INTERNAL_KEYWORDS) + ["chain", "save", "table"]:
        if ignore in kwargs:
            del kwargs[ignore]

    rule = ""
    proto = ""

    nft_family = _NFTABLES_FAMILIES[family]

    if "if" in kwargs:
        rule += "meta iifname {0} ".format(kwargs["if"])
        del kwargs["if"]

    if "of" in kwargs:
        rule += "meta oifname {0} ".format(kwargs["of"])
        del kwargs["of"]

    if "proto" in kwargs:
        proto = kwargs["proto"]

    if "state" in kwargs:
        del kwargs["state"]

    if "connstate" in kwargs:
        rule += "ct state {{ {0}}} ".format(kwargs["connstate"])
        del kwargs["connstate"]

    if "dport" in kwargs:
        kwargs["dport"] = six.text_type(kwargs["dport"])
        if ":" in kwargs["dport"]:
            kwargs["dport"] = kwargs["dport"].replace(":", "-")
        rule += "dport {{ {0} }} ".format(kwargs["dport"])
        del kwargs["dport"]

    if "sport" in kwargs:
        kwargs["sport"] = six.text_type(kwargs["sport"])
        if ":" in kwargs["sport"]:
            kwargs["sport"] = kwargs["sport"].replace(":", "-")
        rule += "sport {{ {0} }} ".format(kwargs["sport"])
        del kwargs["sport"]

    if "dports" in kwargs:
        # nftables reverse sorts the ports from
        # high to low, create rule like this
        # so that the check will work
        _dports = kwargs["dports"].split(",")
        _dports = [int(x) for x in _dports]
        _dports.sort(reverse=True)
        kwargs["dports"] = ", ".join(six.text_type(x) for x in _dports)

        rule += "dport {{ {0} }} ".format(kwargs["dports"])
        del kwargs["dports"]

    if "sports" in kwargs:
        # nftables reverse sorts the ports from
        # high to low, create rule like this
        # so that the check will work
        _sports = kwargs["sports"].split(",")
        _sports = [int(x) for x in _sports]
        _sports.sort(reverse=True)
        kwargs["sports"] = ", ".join(six.text_type(x) for x in _sports)

        rule += "sport {{ {0} }} ".format(kwargs["sports"])
        del kwargs["sports"]

    # Jumps should appear last, except for any arguments that are passed to
    # jumps, which of course need to follow.
    after_jump = []

    if "jump" in kwargs:
        after_jump.append("{0} ".format(kwargs["jump"]))
        del kwargs["jump"]

    if "j" in kwargs:
        after_jump.append("{0} ".format(kwargs["j"]))
        del kwargs["j"]

    if "to-port" in kwargs:
        after_jump.append("--to-port {0} ".format(kwargs["to-port"]))
        del kwargs["to-port"]

    if "to-ports" in kwargs:
        after_jump.append("--to-ports {0} ".format(kwargs["to-ports"]))
        del kwargs["to-ports"]

    if "to-destination" in kwargs:
        after_jump.append("--to-destination {0} ".format(kwargs["to-destination"]))
        del kwargs["to-destination"]

    if "reject-with" in kwargs:
        after_jump.append("--reject-with {0} ".format(kwargs["reject-with"]))
        del kwargs["reject-with"]

    for item in after_jump:
        rule += item

    # Strip trailing spaces off rule
    rule = rule.strip()

    # Insert the protocol prior to dport or sport
    rule = rule.replace("dport", "{0} dport".format(proto))
    rule = rule.replace("sport", "{0} sport".format(proto))

    ret["rule"] = rule

    if full in ["True", "true"]:

        if not table:
            ret["comment"] = "Table needs to be specified"
            return ret

        if not chain:
            ret["comment"] = "Chain needs to be specified"
            return ret

        if not command:
            ret["comment"] = "Command needs to be specified"
            return ret

        if command in ["Insert", "insert", "INSERT"]:
            if position:
                ret["rule"] = "{0} insert rule {1} {2} {3} " "position {4} {5}".format(
                    _nftables_cmd(), nft_family, table, chain, position, rule
                )
            else:
                ret["rule"] = "{0} insert rule " "{1} {2} {3} {4}".format(
                    _nftables_cmd(), nft_family, table, chain, rule
                )
        else:
            ret["rule"] = "{0} {1} rule {2} {3} {4} {5}".format(
                _nftables_cmd(), command, nft_family, table, chain, rule
            )

    if ret["rule"]:
        ret["comment"] = "Successfully built rule"
    ret["result"] = True
    return ret


def get_saved_rules(conf_file=None):
    """
    Return a data structure of the rules in the conf file

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.get_saved_rules

    """
    if _conf() and not conf_file:
        conf_file = _conf()

    with salt.utils.files.fopen(conf_file) as fp_:
        lines = salt.utils.data.decode(fp_.readlines())
    rules = []
    for line in lines:
        tmpline = line.strip()
        if not tmpline:
            continue
        if tmpline.startswith("#"):
            continue
        rules.append(line)
    return rules


def list_tables(family="ipv4"):
    """
    Return a data structure of the current, in-memory tables

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.list_tables

        salt '*' nftables.list_tables family=ipv6

    """
    nft_family = _NFTABLES_FAMILIES[family]
    tables = []
    cmd = "{0} --json --numeric --numeric --numeric " "list tables {1}".format(
        _nftables_cmd(), nft_family
    )
    out = __salt__["cmd.run"](cmd, python_shell=False)
    if not out:
        return tables
    data = json.loads(out)

    for item in data.get("nftables", []):
        if "metainfo" not in item:
            tables.append(item["table"])
    log.debug(tables)
    return tables


def get_rules(family="ipv4"):
    """
    Return a data structure of the current, in-memory rules

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.get_rules

        salt '*' nftables.get_rules family=ipv6

    """
    tables = list_tables(family)
    nft_family = _NFTABLES_FAMILIES[family]

    rules = []
    for table in tables:
        table_name = table["name"]
        cmd = "{0} --numeric --numeric --numeric " "list table {1} {2}".format(
            _nftables_cmd(), nft_family, table_name
        )
        out = __salt__["cmd.run"](cmd, python_shell=False)
        rules.append(out)
    return rules


def save(filename=None, family="ipv4"):
    """
    Save the current in-memory rules to disk

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.save /etc/nftables
    """
    if _conf() and not filename:
        filename = _conf()

    nft_families = ["ip", "ip6", "arp", "bridge"]
    rules = "#! nft -f\n"
    for family in nft_families:
        out = get_rules(family)
        if out:
            rules += "\n"
        rules = rules + "\n".join(out)
    rules = rules + "\n"

    try:
        with salt.utils.files.fopen(filename, "wb") as _fh:
            # Write out any changes
            _fh.write(salt.utils.data.encode(rules))
    except (IOError, OSError) as exc:
        raise CommandExecutionError(
            "Problem writing to configuration file: {0}".format(exc)
        )
    return rules


def get_rule_handle(table="filter", chain=None, rule=None, family="ipv4"):
    """
    Get the handle for a particular rule

    This function accepts a rule in a standard nftables command format,
        starting with the chain. Trying to force users to adapt to a new
        method of creating rules would be irritating at best, and we
        already have a parser that can handle it.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.get_rule_handle filter input \\
            rule='tcp dport 22 log accept'

        IPv6:
        salt '*' nftables.get_rule_handle filter input \\
            rule='tcp dport 22 log accept' \\
            family=ipv6
    """
    ret = {"comment": "", "result": False}

    if not chain:
        ret["comment"] = "Chain needs to be specified"
        return ret

    if not rule:
        ret["comment"] = "Rule needs to be specified"
        return ret

    res = check_table(table, family=family)
    if not res["result"]:
        return res

    res = check_chain(table, chain, family=family)
    if not res["result"]:
        return res

    res = check(table, chain, rule, family=family)
    if not res["result"]:
        return res

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = "{0} --numeric --numeric --numeric --handle list chain {1} {2} {3}".format(
        _nftables_cmd(), nft_family, table, chain
    )
    out = __salt__["cmd.run"](cmd, python_shell=False)
    rules = re.split("\n+", out)

    pat = re.compile(r"{0} # handle (?P<handle>\d+)".format(rule))
    for r in rules:
        match = pat.search(r)
        if match:
            return {"result": True, "handle": match.group("handle")}
    return {"result": False, "comment": "Could not find rule {0}".format(rule)}


def check(table="filter", chain=None, rule=None, family="ipv4"):
    """
    Check for the existence of a rule in the table and chain

    This function accepts a rule in a standard nftables command format,
        starting with the chain. Trying to force users to adapt to a new
        method of creating rules would be irritating at best, and we
        already have a parser that can handle it.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.check filter input \\
            rule='tcp dport 22 log accept'

        IPv6:
        salt '*' nftables.check filter input \\
            rule='tcp dport 22 log accept' \\
            family=ipv6
    """
    ret = {"comment": "", "result": False}

    if not chain:
        ret["comment"] = "Chain needs to be specified"
        return ret

    if not rule:
        ret["comment"] = "Rule needs to be specified"
        return ret

    res = check_table(table, family=family)
    if not res["result"]:
        return res

    res = check_chain(table, chain, family=family)
    if not res["result"]:
        return res

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = "{0} --handle --numeric --numeric --numeric list chain {1} {2} {3}".format(
        _nftables_cmd(), nft_family, table, chain
    )
    search_rule = "{0} #".format(rule)
    out = __salt__["cmd.run"](cmd, python_shell=False).find(search_rule)

    if out == -1:
        ret[
            "comment"
        ] = "Rule {0} in chain {1} in table {2} in family {3} does not exist".format(
            rule, chain, table, family
        )
    else:
        ret[
            "comment"
        ] = "Rule {0} in chain {1} in table {2} in family {3} exists".format(
            rule, chain, table, family
        )
        ret["result"] = True
    return ret


def check_chain(table="filter", chain=None, family="ipv4"):
    """
    .. versionadded:: 2014.7.0

    Check for the existence of a chain in the table

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.check_chain filter input

        IPv6:
        salt '*' nftables.check_chain filter input family=ipv6
    """

    ret = {"comment": "", "result": False}

    if not chain:
        ret["comment"] = "Chain needs to be specified"
        return ret

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = "{0} list table {1} {2}".format(_nftables_cmd(), nft_family, table)
    out = __salt__["cmd.run"](cmd, python_shell=False).find(
        "chain {0} {{".format(chain)
    )

    if out == -1:
        ret["comment"] = "Chain {0} in table {1} in family {2} does not exist".format(
            chain, table, family
        )
    else:
        ret["comment"] = "Chain {0} in table {1} in family {2} exists".format(
            chain, table, family
        )
        ret["result"] = True
    return ret


def check_table(table=None, family="ipv4"):
    """
    Check for the existence of a table

    CLI Example::

        salt '*' nftables.check_table nat
    """
    ret = {"comment": "", "result": False}

    if not table:
        ret["comment"] = "Table needs to be specified"
        return ret

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = "{0} list tables {1}".format(_nftables_cmd(), nft_family)
    out = __salt__["cmd.run"](cmd, python_shell=False).find(
        "table {0} {1}".format(nft_family, table)
    )

    if out == -1:
        ret["comment"] = "Table {0} in family {1} does not exist".format(table, family)
    else:
        ret["comment"] = "Table {0} in family {1} exists".format(table, family)
        ret["result"] = True
    return ret


def new_table(table, family="ipv4"):
    """
    .. versionadded:: 2014.7.0

    Create new custom table.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.new_table filter

        IPv6:
        salt '*' nftables.new_table filter family=ipv6
    """
    ret = {"comment": "", "result": False}

    if not table:
        ret["comment"] = "Table needs to be specified"
        return ret

    res = check_table(table, family=family)
    if res["result"]:
        return res

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = "{0} add table {1} {2}".format(_nftables_cmd(), nft_family, table)
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        ret["comment"] = "Table {0} in family {1} created".format(table, family)
        ret["result"] = True
    else:
        ret["comment"] = "Table {0} in family {1} could not be created".format(
            table, family
        )
    return ret


def delete_table(table, family="ipv4"):
    """
    .. versionadded:: 2014.7.0

    Create new custom table.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.delete_table filter

        IPv6:
        salt '*' nftables.delete_table filter family=ipv6
    """
    ret = {"comment": "", "result": False}

    if not table:
        ret["comment"] = "Table needs to be specified"
        return ret

    res = check_table(table, family=family)
    if not res["result"]:
        return res

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = "{0} delete table {1} {2}".format(_nftables_cmd(), nft_family, table)
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        ret["comment"] = "Table {0} in family {1} deleted".format(table, family)
        ret["result"] = True
    else:
        ret["comment"] = "Table {0} in family {1} could not be deleted".format(
            table, family
        )
    return ret


def new_chain(
    table="filter", chain=None, table_type=None, hook=None, priority=None, family="ipv4"
):
    """
    .. versionadded:: 2014.7.0

    Create new chain to the specified table.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.new_chain filter input

        salt '*' nftables.new_chain filter input \\
                table_type=filter hook=input priority=0

        salt '*' nftables.new_chain filter foo

        IPv6:
        salt '*' nftables.new_chain filter input family=ipv6

        salt '*' nftables.new_chain filter input \\
                table_type=filter hook=input priority=0 family=ipv6

        salt '*' nftables.new_chain filter foo family=ipv6
    """
    ret = {"comment": "", "result": False}

    if not chain:
        ret["comment"] = "Chain needs to be specified"
        return ret

    res = check_table(table, family=family)
    if not res["result"]:
        return res

    res = check_chain(table, chain, family=family)
    if res["result"]:
        ret["comment"] = "Chain {0} in table {1} in family {2} already exists".format(
            chain, table, family
        )
        return ret

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = "{0} add chain {1} {2} {3}".format(_nftables_cmd(), nft_family, table, chain)
    if table_type or hook or priority:
        if table_type and hook and six.text_type(priority):
            cmd = r"{0} \{{ type {1} hook {2} priority {3}\; \}}".format(
                cmd, table_type, hook, priority
            )
        else:
            # Specify one, require all
            ret["comment"] = "Table_type, hook, and priority required."
            return ret

    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        ret["comment"] = "Chain {0} in table {1} in family {2} created".format(
            chain, table, family
        )
        ret["result"] = True
    else:
        ret[
            "comment"
        ] = "Chain {0} in table {1} in family {2} could not be created".format(
            chain, table, family
        )
    return ret


def delete_chain(table="filter", chain=None, family="ipv4"):
    """
    .. versionadded:: 2014.7.0

    Delete the chain from the specified table.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.delete_chain filter input

        salt '*' nftables.delete_chain filter foo

        IPv6:
        salt '*' nftables.delete_chain filter input family=ipv6

        salt '*' nftables.delete_chain filter foo family=ipv6
    """
    ret = {"comment": "", "result": False}

    if not chain:
        ret["comment"] = "Chain needs to be specified"
        return ret

    res = check_table(table, family=family)
    if not res["result"]:
        return res

    res = check_chain(table, chain, family=family)
    if not res["result"]:
        return res

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = "{0} delete chain {1} {2} {3}".format(
        _nftables_cmd(), nft_family, table, chain
    )
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        ret["comment"] = "Chain {0} in table {1} in family {2} deleted".format(
            chain, table, family
        )
        ret["result"] = True
    else:
        ret[
            "comment"
        ] = "Chain {0} in table {1} in family {2} could not be deleted".format(
            chain, table, family
        )
    return ret


def append(table="filter", chain=None, rule=None, family="ipv4"):
    """
    Append a rule to the specified table & chain.

    This function accepts a rule in a standard nftables command format,
        starting with the chain. Trying to force users to adapt to a new
        method of creating rules would be irritating at best, and we
        already have a parser that can handle it.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.append filter input \\
            rule='tcp dport 22 log accept'

        IPv6:
        salt '*' nftables.append filter input \\
            rule='tcp dport 22 log accept' \\
            family=ipv6
    """
    ret = {
        "comment": "Failed to append rule {0} to chain {1} in table {2}.".format(
            rule, chain, table
        ),
        "result": False,
    }

    if not chain:
        ret["comment"] = "Chain needs to be specified"
        return ret

    if not rule:
        ret["comment"] = "Rule needs to be specified"
        return ret

    res = check_table(table, family=family)
    if not res["result"]:
        return res

    res = check_chain(table, chain, family=family)
    if not res["result"]:
        return res

    res = check(table, chain, rule, family=family)
    if res["result"]:
        ret[
            "comment"
        ] = "Rule {0} chain {1} in table {2} in family {3} already exists".format(
            rule, chain, table, family
        )
        return ret

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = "{0} add rule {1} {2} {3} {4}".format(
        _nftables_cmd(), nft_family, table, chain, rule
    )
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if len(out) == 0:
        ret["result"] = True
        ret[
            "comment"
        ] = 'Added rule "{0}" chain {1} in table {2} in family {3}.'.format(
            rule, chain, table, family
        )
    else:
        ret[
            "comment"
        ] = 'Failed to add rule "{0}" chain {1} in table {2} in family {3}.'.format(
            rule, chain, table, family
        )
    return ret


def insert(table="filter", chain=None, position=None, rule=None, family="ipv4"):
    """
    Insert a rule into the specified table & chain, at the specified position.

    If position is not specified, rule will be inserted in first position.

    This function accepts a rule in a standard nftables command format,
        starting with the chain. Trying to force users to adapt to a new
        method of creating rules would be irritating at best, and we
        already have a parser that can handle it.

    CLI Examples:

    .. code-block:: bash

        salt '*' nftables.insert filter input \\
            rule='tcp dport 22 log accept'

        salt '*' nftables.insert filter input position=3 \\
            rule='tcp dport 22 log accept'

        IPv6:
        salt '*' nftables.insert filter input \\
            rule='tcp dport 22 log accept' \\
            family=ipv6

        salt '*' nftables.insert filter input position=3 \\
            rule='tcp dport 22 log accept' \\
            family=ipv6
    """
    ret = {
        "comment": "Failed to insert rule {0} to table {1}.".format(rule, table),
        "result": False,
    }

    if not chain:
        ret["comment"] = "Chain needs to be specified"
        return ret

    if not rule:
        ret["comment"] = "Rule needs to be specified"
        return ret

    res = check_table(table, family=family)
    if not res["result"]:
        return res

    res = check_chain(table, chain, family=family)
    if not res["result"]:
        return res

    res = check(table, chain, rule, family=family)
    if res["result"]:
        ret[
            "comment"
        ] = "Rule {0} chain {1} in table {2} in family {3} already exists".format(
            rule, chain, table, family
        )
        return ret

    nft_family = _NFTABLES_FAMILIES[family]
    if position:
        cmd = "{0} insert rule {1} {2} {3} position {4} {5}".format(
            _nftables_cmd(), nft_family, table, chain, position, rule
        )
    else:
        cmd = "{0} insert rule {1} {2} {3} {4}".format(
            _nftables_cmd(), nft_family, table, chain, rule
        )
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if len(out) == 0:
        ret["result"] = True
        ret[
            "comment"
        ] = 'Added rule "{0}" chain {1} in table {2} in family {3}.'.format(
            rule, chain, table, family
        )
    else:
        ret[
            "comment"
        ] = 'Failed to add rule "{0}" chain {1} in table {2} in family {3}.'.format(
            rule, chain, table, family
        )
    return ret


def delete(table, chain=None, position=None, rule=None, family="ipv4"):
    """
    Delete a rule from the specified table & chain, specifying either the rule
        in its entirety, or the rule's position in the chain.

    This function accepts a rule in a standard nftables command format,
        starting with the chain. Trying to force users to adapt to a new
        method of creating rules would be irritating at best, and we
        already have a parser that can handle it.

    CLI Examples:

    .. code-block:: bash

        salt '*' nftables.delete filter input position=3

        salt '*' nftables.delete filter input \\
            rule='tcp dport 22 log accept'

        IPv6:
        salt '*' nftables.delete filter input position=3 family=ipv6

        salt '*' nftables.delete filter input \\
            rule='tcp dport 22 log accept' \\
            family=ipv6
    """
    ret = {
        "comment": "Failed to delete rule {0} in table {1}.".format(rule, table),
        "result": False,
    }

    if position and rule:
        ret["comment"] = "Only specify a position or a rule, not both"
        return ret

    res = check_table(table, family=family)
    if not res["result"]:
        return res

    res = check_chain(table, chain, family=family)
    if not res["result"]:
        return res

    res = check(table, chain, rule, family=family)
    if not res["result"]:
        ret[
            "comment"
        ] = "Rule {0} chain {1} in table {2} in family {3} does not exist".format(
            rule, chain, table, family
        )
        return ret

    # nftables rules can only be deleted using the handle
    # if we don't have it, find it.
    if not position:
        position = get_rule_handle(table, chain, rule, family)

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = "{0} delete rule {1} {2} {3} handle {4}".format(
        _nftables_cmd(), nft_family, table, chain, position
    )
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if len(out) == 0:
        ret["result"] = True
        ret[
            "comment"
        ] = 'Deleted rule "{0}" in chain {1} in table {2} in family {3}.'.format(
            rule, chain, table, family
        )
    else:
        ret[
            "comment"
        ] = 'Failed to delete rule "{0}" in chain {1}  table {2} in family {3}'.format(
            rule, chain, table, family
        )
    return ret


def flush(table="filter", chain="", family="ipv4"):
    """
    Flush the chain in the specified table, flush all chains in the specified
    table if chain is not specified.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.flush filter

        salt '*' nftables.flush filter input

        IPv6:
        salt '*' nftables.flush filter input family=ipv6
    """
    ret = {
        "comment": "Failed to flush rules from chain {0} in table {1}.".format(
            chain, table
        ),
        "result": False,
    }

    res = check_table(table, family=family)
    if not res["result"]:
        return res

    nft_family = _NFTABLES_FAMILIES[family]

    if chain:
        res = check_chain(table, chain, family=family)
        if not res["result"]:
            return res
        cmd = "{0} flush chain {1} {2} {3}".format(
            _nftables_cmd(), nft_family, table, chain
        )
        comment = "from chain {0} in table {1} in family {2}.".format(
            chain, table, family
        )
    else:
        cmd = "{0} flush table {1} {2}".format(_nftables_cmd(), nft_family, table)
        comment = "from table {0} in family {1}.".format(table, family)
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if len(out) == 0:
        ret["result"] = True
        ret["comment"] = "Flushed rules {0}".format(comment)
    else:
        ret["comment"] = "Failed to flush rules {0}".format(comment)
    return ret
