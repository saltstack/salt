"""
Support for nftables
"""

import json
import logging
import re

import salt.utils.data
import salt.utils.files
import salt.utils.path
from salt.exceptions import CommandExecutionError
from salt.state import STATE_INTERNAL_KEYWORDS as _STATE_INTERNAL_KEYWORDS

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
    cmd = f"{_nftables_cmd()} --version"
    out = __salt__["cmd.run"](cmd).split()
    return out[1]


def build_rule(
    table=None,
    chain=None,
    command=None,
    position="",
    full=None,
    family="ipv4",
    **kwargs,
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
        rule += "meta iifname {} ".format(kwargs["if"])
        del kwargs["if"]

    if "of" in kwargs:
        rule += "meta oifname {} ".format(kwargs["of"])
        del kwargs["of"]

    if "proto" in kwargs:
        proto = kwargs["proto"]

    if "state" in kwargs:
        del kwargs["state"]

    if "connstate" in kwargs:
        rule += "ct state {{ {0} }} ".format(kwargs["connstate"])
        del kwargs["connstate"]

    if "icmp-type" in kwargs:
        rule += "icmp type {{ {0} }} ".format(kwargs["icmp-type"])
        del kwargs["icmp-type"]

    if "pkttype" in kwargs:
        rule += "meta pkttype {{ {0} }} ".format(kwargs["pkttype"])
        del kwargs["pkttype"]

    if "counter" in kwargs:
        rule += "counter "
        del kwargs["counter"]

    if "saddr" in kwargs or "source" in kwargs:
        rule += "ip saddr {} ".format(kwargs.get("saddr") or kwargs.get("source"))
        if "saddr" in kwargs:
            del kwargs["saddr"]
        if "source" in kwargs:
            del kwargs["source"]

    if "daddr" in kwargs or "destination" in kwargs:
        rule += "ip daddr {} ".format(kwargs.get("daddr") or kwargs.get("destination"))
        if "daddr" in kwargs:
            del kwargs["daddr"]
        if "destination" in kwargs:
            del kwargs["destination"]

    if "dport" in kwargs:
        kwargs["dport"] = str(kwargs["dport"])
        if ":" in kwargs["dport"]:
            kwargs["dport"] = kwargs["dport"].replace(":", "-")
        rule += "dport {{ {0} }} ".format(kwargs["dport"])
        del kwargs["dport"]

    if "sport" in kwargs:
        kwargs["sport"] = str(kwargs["sport"])
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
        kwargs["dports"] = ", ".join(str(x) for x in _dports)

        rule += "dport {{ {0} }} ".format(kwargs["dports"])
        del kwargs["dports"]

    if "sports" in kwargs:
        # nftables reverse sorts the ports from
        # high to low, create rule like this
        # so that the check will work
        _sports = kwargs["sports"].split(",")
        _sports = [int(x) for x in _sports]
        _sports.sort(reverse=True)
        kwargs["sports"] = ", ".join(str(x) for x in _sports)

        rule += "sport {{ {0} }} ".format(kwargs["sports"])
        del kwargs["sports"]

    # Jumps should appear last, except for any arguments that are passed to
    # jumps, which of course need to follow.
    after_jump = []

    if "jump" in kwargs:
        after_jump.append("{} ".format(kwargs["jump"]))
        del kwargs["jump"]

    if "j" in kwargs:
        after_jump.append("{} ".format(kwargs["j"]))
        del kwargs["j"]

    if "redirect-to" in kwargs or "to-port" in kwargs:
        after_jump.append(
            "redirect to {} ".format(kwargs.get("redirect-to") or kwargs.get("to-port"))
        )
        if "redirect-to" in kwargs:
            del kwargs["redirect-to"]
        if "to-port" in kwargs:
            del kwargs["to-port"]

    if "to-ports" in kwargs:
        after_jump.append("--to-ports {} ".format(kwargs["to-ports"]))
        del kwargs["to-ports"]

    if "to-source" in kwargs:
        after_jump.append("{} ".format(kwargs["to-source"]))
        del kwargs["to-source"]

    if "to-destination" in kwargs:
        after_jump.append("{} ".format(kwargs["to-destination"]))
        del kwargs["to-destination"]

    if "reject-with" in kwargs:
        after_jump.append("reject with {} ".format(kwargs["reject-with"]))
        del kwargs["reject-with"]

    for item in after_jump:
        rule += item

    # Strip trailing spaces off rule
    rule = rule.strip()

    # Insert the protocol prior to dport or sport
    rule = rule.replace("dport", f"{proto} dport")
    rule = rule.replace("sport", f"{proto} sport")

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
                ret["rule"] = "{} insert rule {} {} {} position {} {}".format(
                    _nftables_cmd(), nft_family, table, chain, position, rule
                )
            else:
                ret["rule"] = "{} insert rule {} {} {} {}".format(
                    _nftables_cmd(), nft_family, table, chain, rule
                )
        else:
            ret["rule"] = "{} {} rule {} {} {} {}".format(
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
    cmd = "{} --json --numeric --numeric --numeric list tables {}".format(
        _nftables_cmd(), nft_family
    )
    out = __salt__["cmd.run"](cmd, python_shell=False)
    if not out:
        return tables

    try:
        data = json.loads(out)
    except ValueError:
        return tables

    if not data or not data.get("nftables"):
        return tables

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
        cmd = "{} --numeric --numeric --numeric list table {} {}".format(
            _nftables_cmd(), nft_family, table_name
        )
        out = __salt__["cmd.run"](cmd, python_shell=False)
        rules.append(out)
    return rules


def get_rules_json(family="ipv4"):
    """
    .. versionadded:: 3002

    Return a list of dictionaries comprising the current, in-memory rules

    family
        Networking family, either ipv4 or ipv6

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.get_rules_json

        salt '*' nftables.get_rules_json family=ipv6

    """
    nft_family = _NFTABLES_FAMILIES[family]
    rules = []
    cmd = "{} --numeric --numeric --numeric --json list ruleset {}".format(
        _nftables_cmd(), nft_family
    )
    out = __salt__["cmd.run"](cmd, python_shell=False)
    if not out:
        return rules

    try:
        rules = (json.loads(out))["nftables"]
    except (KeyError, ValueError):
        return rules

    return rules


def save(filename=None, family="ipv4"):
    """
    .. versionchanged:: 3002

    Save the current in-memory rules to disk. On systems where /etc/nftables is
    a directory, a file named salt-all-in-one.nft will be dropped inside by default.
    The main nftables configuration will need to include this file.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.save /etc/nftables
    """
    if _conf() and not filename:
        filename = _conf()

    # Invert the dictionary twice to get unique values only.
    nft_families = {v: k for k, v in _NFTABLES_FAMILIES.items()}
    nft_families = {v: k for k, v in nft_families.items()}

    rules = "#! nft -f\n"

    for family in nft_families:
        out = get_rules(family)
        if out:
            rules += "\n"
        rules = rules + "\n".join(out)
    rules = rules + "\n"

    if __salt__["file.directory_exists"](filename):
        filename = f"{filename}/salt-all-in-one.nft"

    try:
        with salt.utils.files.fopen(filename, "wb") as _fh:
            # Write out any changes
            _fh.write(salt.utils.data.encode(rules))
    except OSError as exc:
        raise CommandExecutionError(f"Problem writing to configuration file: {exc}")
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
    cmd = "{} --numeric --numeric --numeric --handle list chain {} {} {}".format(
        _nftables_cmd(), nft_family, table, chain
    )
    out = __salt__["cmd.run"](cmd, python_shell=False)
    rules = re.split("\n+", out)

    pat = re.compile(rf"{rule} # handle (?P<handle>\d+)")
    for r in rules:
        match = pat.search(r)
        if match:
            return {"result": True, "handle": match.group("handle")}
    return {"result": False, "comment": f"Could not find rule {rule}"}


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
    cmd = "{} --handle --numeric --numeric --numeric list chain {} {} {}".format(
        _nftables_cmd(), nft_family, table, chain
    )
    search_rule = f"{rule} #"
    out = __salt__["cmd.run"](cmd, python_shell=False).find(search_rule)

    if out == -1:
        ret["comment"] = (
            "Rule {} in chain {} in table {} in family {} does not exist".format(
                rule, chain, table, family
            )
        )
    else:
        ret["comment"] = "Rule {} in chain {} in table {} in family {} exists".format(
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
    cmd = f"{_nftables_cmd()} list table {nft_family} {table}"
    out = __salt__["cmd.run"](cmd, python_shell=False).find(f"chain {chain} {{")

    if out == -1:
        ret["comment"] = "Chain {} in table {} in family {} does not exist".format(
            chain, table, family
        )
    else:
        ret["comment"] = "Chain {} in table {} in family {} exists".format(
            chain, table, family
        )
        ret["result"] = True
    return ret


def check_table(table=None, family="ipv4"):
    """
    Check for the existence of a table

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.check_table nat
    """
    ret = {"comment": "", "result": False}

    if not table:
        ret["comment"] = "Table needs to be specified"
        return ret

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = f"{_nftables_cmd()} list tables {nft_family}"
    out = __salt__["cmd.run"](cmd, python_shell=False).find(
        f"table {nft_family} {table}"
    )

    if out == -1:
        ret["comment"] = f"Table {table} in family {family} does not exist"
    else:
        ret["comment"] = f"Table {table} in family {family} exists"
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
    cmd = f"{_nftables_cmd()} add table {nft_family} {table}"
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        ret["comment"] = f"Table {table} in family {family} created"
        ret["result"] = True
    else:
        ret["comment"] = "Table {} in family {} could not be created".format(
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
    cmd = f"{_nftables_cmd()} delete table {nft_family} {table}"
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        ret["comment"] = f"Table {table} in family {family} deleted"
        ret["result"] = True
    else:
        ret["comment"] = "Table {} in family {} could not be deleted".format(
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
        ret["comment"] = "Chain {} in table {} in family {} already exists".format(
            chain, table, family
        )
        return ret

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = f"{_nftables_cmd()} -- add chain {nft_family} {table} {chain}"
    if table_type or hook or priority:
        if table_type and hook and str(priority):
            cmd = r"{0} \{{ type {1} hook {2} priority {3}\; \}}".format(
                cmd, table_type, hook, priority
            )
        else:
            # Specify one, require all
            ret["comment"] = "Table_type, hook, and priority required."
            return ret

    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        ret["comment"] = "Chain {} in table {} in family {} created".format(
            chain, table, family
        )
        ret["result"] = True
    else:
        ret["comment"] = (
            "Chain {} in table {} in family {} could not be created".format(
                chain, table, family
            )
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
    cmd = f"{_nftables_cmd()} delete chain {nft_family} {table} {chain}"
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        ret["comment"] = "Chain {} in table {} in family {} deleted".format(
            chain, table, family
        )
        ret["result"] = True
    else:
        ret["comment"] = (
            "Chain {} in table {} in family {} could not be deleted".format(
                chain, table, family
            )
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
        "comment": "Failed to append rule {} to chain {} in table {}.".format(
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
        ret["comment"] = (
            "Rule {} chain {} in table {} in family {} already exists".format(
                rule, chain, table, family
            )
        )
        return ret

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = "{} add rule {} {} {} {}".format(
        _nftables_cmd(), nft_family, table, chain, rule
    )
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        ret["result"] = True
        ret["comment"] = 'Added rule "{}" chain {} in table {} in family {}.'.format(
            rule, chain, table, family
        )
    else:
        ret["comment"] = (
            'Failed to add rule "{}" chain {} in table {} in family {}.'.format(
                rule, chain, table, family
            )
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
        "comment": f"Failed to insert rule {rule} to table {table}.",
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
        ret["comment"] = (
            "Rule {} chain {} in table {} in family {} already exists".format(
                rule, chain, table, family
            )
        )
        return ret

    nft_family = _NFTABLES_FAMILIES[family]
    if position:
        cmd = "{} insert rule {} {} {} position {} {}".format(
            _nftables_cmd(), nft_family, table, chain, position, rule
        )
    else:
        cmd = "{} insert rule {} {} {} {}".format(
            _nftables_cmd(), nft_family, table, chain, rule
        )
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        ret["result"] = True
        ret["comment"] = 'Added rule "{}" chain {} in table {} in family {}.'.format(
            rule, chain, table, family
        )
    else:
        ret["comment"] = (
            'Failed to add rule "{}" chain {} in table {} in family {}.'.format(
                rule, chain, table, family
            )
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
        "comment": f"Failed to delete rule {rule} in table {table}.",
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
        ret["comment"] = (
            "Rule {} chain {} in table {} in family {} does not exist".format(
                rule, chain, table, family
            )
        )
        return ret

    # nftables rules can only be deleted using the handle
    # if we don't have it, find it.
    if not position:
        position = get_rule_handle(table, chain, rule, family)

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = "{} delete rule {} {} {} handle {}".format(
        _nftables_cmd(), nft_family, table, chain, position
    )
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        ret["result"] = True
        ret["comment"] = (
            'Deleted rule "{}" in chain {} in table {} in family {}.'.format(
                rule, chain, table, family
            )
        )
    else:
        ret["comment"] = (
            'Failed to delete rule "{}" in chain {}  table {} in family {}'.format(
                rule, chain, table, family
            )
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
        "comment": "Failed to flush rules from chain {} in table {}.".format(
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
        cmd = "{} flush chain {} {} {}".format(
            _nftables_cmd(), nft_family, table, chain
        )
        comment = f"from chain {chain} in table {table} in family {family}."
    else:
        cmd = f"{_nftables_cmd()} flush table {nft_family} {table}"
        comment = f"from table {table} in family {family}."
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        ret["result"] = True
        ret["comment"] = f"Flushed rules {comment}"
    else:
        ret["comment"] = f"Failed to flush rules {comment}"
    return ret


def get_policy(table="filter", chain=None, family="ipv4"):
    """
    .. versionadded:: 3002

    Return the current policy for the specified table/chain

    table
        Name of the table containing the chain to check

    chain
        Name of the chain to get the policy for

    family
        Networking family, either ipv4 or ipv6

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.get_policy filter input

        IPv6:
        salt '*' nftables.get_policy filter input family=ipv6
    """
    if not chain:
        return "Error: Chain needs to be specified"

    nft_family = _NFTABLES_FAMILIES[family]

    rules = get_rules_json(family=nft_family)

    try:
        for rule in rules["nftables"]:
            if (
                rule.get("chain", {}).get("name") == chain
                and rule.get("chain", {}).get("type") == table
            ):
                return rule["chain"]["policy"]
    except (KeyError, TypeError, ValueError):
        return None


def set_policy(table="filter", chain=None, policy=None, family="ipv4"):
    """
    .. versionadded:: 3002

    Set the current policy for the specified table/chain. This only works on
    chains with an existing base chain.

    table
        Name of the table containing the chain to modify

    chain
        Name of the chain to set the policy for

    policy
        accept or drop

    family
        Networking family, either ipv4 or ipv6

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.set_policy filter input accept

        IPv6:
        salt '*' nftables.set_policy filter input accept family=ipv6
    """
    if not chain:
        return "Error: Chain needs to be specified"
    if not policy:
        return "Error: Policy needs to be specified"

    nft_family = _NFTABLES_FAMILIES[family]

    chain_info = {}
    rules = get_rules_json(family=nft_family)

    if not rules:
        return False

    for rule in rules:
        try:
            if rule["chain"]["table"] == table and rule["chain"]["name"] == chain:
                chain_info = rule["chain"]
                break
        except KeyError:
            continue

    if not chain_info:
        return False

    cmd = f"{_nftables_cmd()} add chain {nft_family} {table} {chain}"

    # We can't infer the base chain parameters. Bail out if they're not present.
    if "type" not in chain_info or "hook" not in chain_info or "prio" not in chain_info:
        return False

    params = "type {} hook {} priority {};".format(
        chain_info["type"], chain_info["hook"], chain_info["prio"]
    )

    cmd = f'{cmd} "{{ {params} policy {policy}; }}"'

    out = __salt__["cmd.run_all"](cmd, python_shell=False)

    return not out["retcode"]
