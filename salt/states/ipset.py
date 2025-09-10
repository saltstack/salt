"""
Management of ipsets
======================

This is an ipset-specific module designed to manage IPSets for use
in IPTables Firewalls.

.. code-block:: yaml

    setname:
      ipset.set_present:
        - set_type: bitmap:ip
        - range: 192.168.0.0/16
        - comment: True

    setname:
      ipset.set_absent:
        - set_type: bitmap:ip
        - range: 192.168.0.0/16
        - comment: True

    setname_entries:
      ipset.present:
        - set_name: setname
        - entry: 192.168.0.3
        - comment: Hello
        - require:
            - ipset: baz

    setname_entries:
      ipset.present:
        - set_name: setname
        - entry:
            - 192.168.0.3
            - 192.168.1.3
        - comment: Hello
        - require:
            - ipset: baz

    setname_entries:
      ipset.absent:
        - set_name: setname
        - entry:
            - 192.168.0.3
            - 192.168.1.3
        - comment: Hello
        - require:
            - ipset: baz

    setname:
      ipset.flush:

"""

import logging

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if the ipset module is available in __salt__
    """
    if "ipset.version" in __salt__:
        return True
    return (False, "ipset module could not be loaded")


def set_present(name, set_type, family="ipv4", **kwargs):
    """
    .. versionadded:: 2014.7.0

    Verify the set exists.

    name
        A user-defined set name.

    set_type
        The type for the set.

    family
        Networking family, either ipv4 or ipv6
    """

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    set_check = __salt__["ipset.check_set"](name)
    if set_check is True:
        ret["result"] = True
        ret["comment"] = f"ipset set {name} already exists for {family}"
        return ret

    if __opts__["test"]:
        ret["comment"] = f"ipset set {name} would be added for {family}"
        return ret
    command = __salt__["ipset.new_set"](name, set_type, family, **kwargs)
    if command is True:
        ret["changes"] = {"locale": name}
        ret["result"] = True
        ret["comment"] = f"ipset set {name} created successfully for {family}"
        return ret
    else:
        ret["result"] = False
        ret["comment"] = "Failed to create set {0} for {2}: {1}".format(
            name, command.strip(), family
        )
        return ret


def set_absent(name, family="ipv4", **kwargs):
    """
    .. versionadded:: 2014.7.0

    Verify the set is absent.

    family
        Networking family, either ipv4 or ipv6
    """

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    set_check = __salt__["ipset.check_set"](name, family)
    if not set_check:
        ret["result"] = True
        ret["comment"] = f"ipset set {name} for {family} is already absent"
        return ret
    if __opts__["test"]:
        ret["comment"] = f"ipset set {name} for {family} would be removed"
        return ret
    flush_set = __salt__["ipset.flush"](name, family)
    if flush_set:
        command = __salt__["ipset.delete_set"](name, family)
        if command is True:
            ret["changes"] = {"locale": name}
            ret["result"] = True
            ret["comment"] = "ipset set {} deleted successfully for family {}".format(
                name, family
            )
        else:
            ret["result"] = False
            ret["comment"] = "Failed to delete set {0} for {2}: {1}".format(
                name, command.strip(), family
            )
    else:
        ret["result"] = False
        ret["comment"] = "Failed to flush set {0} for {2}: {1}".format(
            name, flush_set.strip(), family
        )
    return ret


def present(name, entry=None, family="ipv4", **kwargs):
    """
    .. versionadded:: 2014.7.0

    Append a entry to a set

    name
        A user-defined name to call this entry by in another part of a state or
        formula. This should not be an actual entry.

    entry
        A single entry to add to a set or a list of entries to add to a set

    family
        Network family, ipv4 or ipv6.

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if not entry:
        ret["result"] = False
        ret["comment"] = "ipset entry must be specified"
        return ret

    entries = []
    if isinstance(entry, list):
        entries = entry
    else:
        entries.append(entry)

    for entry in entries:
        entry_opts = ""
        if " " in entry:
            entry, entry_opts = entry.split(" ", 1)
        if "timeout" in kwargs and "timeout" not in entry_opts:
            entry_opts = "timeout {} {}".format(kwargs["timeout"], entry_opts)
        if "comment" in kwargs and "comment" not in entry_opts:
            entry_opts = "{} comment {}".format(entry_opts, kwargs["comment"])
        _entry = " ".join([entry, entry_opts.lstrip()]).strip()

        if __salt__["ipset.check"](kwargs["set_name"], _entry, family) is True:
            ret["comment"] += "entry for {} already in set {} for {}\n".format(
                entry, kwargs["set_name"], family
            )
        else:
            if __opts__["test"]:
                ret["result"] = None
                ret[
                    "comment"
                ] += "entry {} would be added to set {} for family {}\n".format(
                    entry, kwargs["set_name"], family
                )
            else:
                command = __salt__["ipset.add"](
                    kwargs["set_name"], _entry, family, **kwargs
                )
                if "Error" not in command:
                    ret["changes"] = {"locale": name}
                    ret["comment"] += "entry {} added to set {} for family {}\n".format(
                        _entry, kwargs["set_name"], family
                    )
                else:
                    ret["result"] = False
                    ret["comment"] = (
                        "Failed to add to entry {1} to set {0} for family {2}.\n{3}".format(
                            kwargs["set_name"], _entry, family, command
                        )
                    )
    return ret


def absent(name, entry=None, entries=None, family="ipv4", **kwargs):
    """
    .. versionadded:: 2014.7.0

    Remove a entry or entries from a chain

    name
        A user-defined name to call this entry by in another part of a state or
        formula. This should not be an actual entry.

    family
        Network family, ipv4 or ipv6.

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if not entry:
        ret["result"] = False
        ret["comment"] = "ipset entry must be specified"
        return ret

    entries = []
    if isinstance(entry, list):
        entries = entry
    else:
        entries.append(entry)

    for entry in entries:
        entry_opts = ""
        if " " in entry:
            entry, entry_opts = entry.split(" ", 1)
        if "timeout" in kwargs and "timeout" not in entry_opts:
            entry_opts = "timeout {} {}".format(kwargs["timeout"], entry_opts)
        if "comment" in kwargs and "comment" not in entry_opts:
            entry_opts = "{} comment {}".format(entry_opts, kwargs["comment"])
        _entry = " ".join([entry, entry_opts]).strip()

        log.debug("_entry %s", _entry)
        if not __salt__["ipset.check"](kwargs["set_name"], _entry, family) is True:
            ret["result"] = True
            ret[
                "comment"
            ] += "ipset entry for {} not present in set {} for {}\n".format(
                _entry, kwargs["set_name"], family
            )
        else:
            if __opts__["test"]:
                ret["result"] = None
                ret[
                    "comment"
                ] += "ipset entry {} would be removed from set {} for {}\n".format(
                    entry, kwargs["set_name"], family
                )
            else:
                command = __salt__["ipset.delete"](
                    kwargs["set_name"], entry, family, **kwargs
                )
                if "Error" not in command:
                    ret["changes"] = {"locale": name}
                    ret["result"] = True
                    ret[
                        "comment"
                    ] += "ipset entry {} removed from set {} for {}\n".format(
                        _entry, kwargs["set_name"], family
                    )
                else:
                    ret["result"] = False
                    ret["comment"] = (
                        "Failed to delete ipset entry from set {} for {}. "
                        "Attempted entry was {}.\n"
                        "{}\n".format(kwargs["set_name"], family, _entry, command)
                    )
    return ret


def flush(name, family="ipv4", **kwargs):
    """
    .. versionadded:: 2014.7.0

    Flush current ipset set

    family
        Networking family, either ipv4 or ipv6

    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    set_check = __salt__["ipset.check_set"](name)
    if set_check is False:
        ret["result"] = False
        ret["comment"] = f"ipset set {name} does not exist for {family}"
        return ret

    if __opts__["test"]:
        ret["comment"] = "ipset entries in set {} for {} would be flushed".format(
            name, family
        )
        return ret
    if __salt__["ipset.flush"](name, family):
        ret["changes"] = {"locale": name}
        ret["result"] = True
        ret["comment"] = f"Flushed ipset entries from set {name} for {family}"
        return ret
    else:
        ret["result"] = False
        ret["comment"] = "Failed to flush ipset entries from set {} for {}".format(
            name, family
        )
        return ret
