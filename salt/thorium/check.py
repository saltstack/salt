"""
Create gate states that succeed or fail based on Thorium register contents or
incoming events.

These states are usually placed between a register-building state and an action
state. The action then uses a requisite to run only when the check succeeds.
"""

import logging

import salt.utils.stringutils

log = logging.getLogger(__file__)


def gt(name, value):
    """
    Only succeed if the value in the given register location is greater than
    the given value

    USAGE:

    .. code-block:: yaml

        foo:
          check.gt:
            - value: 42

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping
            - require:
              - check: foo
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    if name not in __reg__:
        ret["result"] = False
        ret["comment"] = f"Value {name} not in register"
        return ret
    if __reg__[name]["val"] > value:
        ret["result"] = True
    return ret


def gte(name, value):
    """
    Only succeed if the value in the given register location is greater or equal
    than the given value

    USAGE:

    .. code-block:: yaml

        foo:
          check.gte:
            - value: 42

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping
            - require:
              - check: foo
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    if name not in __reg__:
        ret["result"] = False
        ret["comment"] = f"Value {name} not in register"
        return ret
    if __reg__[name]["val"] >= value:
        ret["result"] = True
    return ret


def lt(name, value):
    """
    Only succeed if the value in the given register location is less than
    the given value

    USAGE:

    .. code-block:: yaml

        foo:
          check.lt:
            - value: 42

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping
            - require:
              - check: foo
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    if name not in __reg__:
        ret["result"] = False
        ret["comment"] = f"Value {name} not in register"
        return ret
    if __reg__[name]["val"] < value:
        ret["result"] = True
    return ret


def lte(name, value):
    """
    Only succeed if the value in the given register location is less than
    or equal the given value

    USAGE:

    .. code-block:: yaml

        foo:
          check.lte:
            - value: 42

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping
            - require:
              - check: foo
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    if name not in __reg__:
        ret["result"] = False
        ret["comment"] = f"Value {name} not in register"
        return ret
    if __reg__[name]["val"] <= value:
        ret["result"] = True
    return ret


def eq(name, value):
    """
    Only succeed if the value in the given register location is equal to
    the given value

    USAGE:

    .. code-block:: yaml

        foo:
          check.eq:
            - value: 42

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping
            - require:
              - check: foo
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    if name not in __reg__:
        ret["result"] = False
        ret["comment"] = f"Value {name} not in register"
        return ret
    if __reg__[name]["val"] == value:
        ret["result"] = True
    return ret


def ne(name, value):
    """
    Only succeed if the value in the given register location is not equal to
    the given value

    USAGE:

    .. code-block:: yaml

        foo:
          check.ne:
            - value: 42

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping
            - require:
              - check: foo
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    if name not in __reg__:
        ret["result"] = False
        ret["comment"] = f"Value {name} not in register"
        return ret
    if __reg__[name]["val"] != value:
        ret["result"] = True
    return ret


def contains(
    name,
    value,
    count_lt=None,
    count_lte=None,
    count_eq=None,
    count_gte=None,
    count_gt=None,
    count_ne=None,
):
    """
    Only succeed if the value in the given register location contains
    the given value.

    This is most useful with ``reg.set`` for simple membership checks. When the
    ``count_*`` options are used, the check compares how many times a value
    appears in the register.

    USAGE:

    .. code-block:: yaml

        foo:
          reg.set:
            - add: bar
            - match: my/custom/event
          check.contains:
            - value: itni

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping
            - require:
              - check: foo
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    if name not in __reg__:
        ret["result"] = False
        ret["comment"] = f"Value {name} not in register"
        return ret
    try:
        count_compare = (
            count_lt or count_lte or count_eq or count_gte or count_gt or count_ne
        )
        if count_compare:
            occurrences = __reg__[name]["val"].count(value)
            log.debug("%s appears %s times", value, occurrences)
            ret["result"] = True
            if count_lt:
                ret["result"] &= occurrences < count_lt
            if count_lte:
                ret["result"] &= occurrences <= count_lte
            if count_eq:
                ret["result"] &= occurrences == count_eq
            if count_gte:
                ret["result"] &= occurrences >= count_gte
            if count_gt:
                ret["result"] &= occurrences > count_gt
            if count_ne:
                ret["result"] &= occurrences != count_ne
        else:
            if value in __reg__[name]["val"]:
                ret["result"] = True
    except TypeError:
        pass
    return ret


def event(name):
    """
    Check the current Thorium event batch for a matching event tag and return
    ``True`` if the match happens.

    Use this when you want a direct event-to-action trigger without storing the
    event in a register first.

    USAGE:

    .. code-block:: yaml

        salt/foo/*/bar:
          check.event

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping
            - require:
              - check: salt/foo/*/bar
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": False}

    for event in __events__:
        if salt.utils.stringutils.expr_match(event["tag"], name):
            ret["result"] = True

    return ret


def len_gt(name, value):
    """
    Only succeed if length of the given register location is greater than
    the given value.

    USAGE:

    .. code-block:: yaml

        foo:
          check.len_gt:
            - value: 42

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping
            - require:
              - check: foo
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    if name not in __reg__:
        ret["result"] = False
        ret["comment"] = f"Value {name} not in register"
        return ret
    if len(__reg__[name]["val"]) > value:
        ret["result"] = True
    return ret


def len_gte(name, value):
    """
    Only succeed if the length of the given register location is greater or equal
    than the given value

    USAGE:

    .. code-block:: yaml

        foo:
          check.len_gte:
            - value: 42

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping
            - require:
              - check: foo
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    if name not in __reg__:
        ret["result"] = False
        ret["comment"] = f"Value {name} not in register"
        return ret
    if len(__reg__[name]["val"]) >= value:
        ret["result"] = True
    return ret


def len_lt(name, value):
    """
    Only succeed if the length of the given register location is less than
    the given value.

    USAGE:

    .. code-block:: yaml

        foo:
          check.len_lt:
            - value: 42

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping
            - require:
              - check: foo
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    if name not in __reg__:
        ret["result"] = False
        ret["comment"] = f"Value {name} not in register"
        return ret
    if len(__reg__[name]["val"]) < value:
        ret["result"] = True
    return ret


def len_lte(name, value):
    """
    Only succeed if the length of the given register location is less than
    or equal the given value

    USAGE:

    .. code-block:: yaml

        foo:
          check.len_lte:
            - value: 42

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping
            - require:
              - check: foo
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    if name not in __reg__:
        ret["result"] = False
        ret["comment"] = f"Value {name} not in register"
        return ret
    if len(__reg__[name]["val"]) <= value:
        ret["result"] = True
    return ret


def len_eq(name, value):
    """
    Only succeed if the length of the given register location is equal to
    the given value.

    USAGE:

    .. code-block:: yaml

        foo:
          check.len_eq:
            - value: 42

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping
            - require:
              - check: foo
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    if name not in __reg__:
        ret["result"] = False
        ret["comment"] = f"Value {name} not in register"
        return ret
    if __reg__[name]["val"] == value:
        ret["result"] = True
    return ret


def len_ne(name, value):
    """
    Only succeed if the length of the given register location is not equal to
    the given value.

    USAGE:

    .. code-block:: yaml

        foo:
          check.len_ne:
            - value: 42

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping
            - require:
              - check: foo
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    if name not in __reg__:
        ret["result"] = False
        ret["comment"] = f"Value {name} not in register"
        return ret
    if len(__reg__[name]["val"]) != value:
        ret["result"] = True
    return ret
