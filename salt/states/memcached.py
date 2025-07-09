"""
States for Management of Memcached Keys
=======================================

.. versionadded:: 2014.1.0
"""

from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.modules.memcached import (
    DEFAULT_HOST,
    DEFAULT_MIN_COMPRESS_LEN,
    DEFAULT_PORT,
    DEFAULT_TIME,
)

__virtualname__ = "memcached"


def __virtual__():
    """
    Only load if memcache module is available
    """
    if f"{__virtualname__}.status" in __salt__:
        return __virtualname__
    return (False, "memcached module could not be loaded")


def managed(
    name,
    value=None,
    host=DEFAULT_HOST,
    port=DEFAULT_PORT,
    time=DEFAULT_TIME,
    min_compress_len=DEFAULT_MIN_COMPRESS_LEN,
):
    """
    Manage a memcached key.

    name
        The key to manage

    value
        The value to set for that key

    host
        The memcached server IP address

    port
        The memcached server port


    .. code-block:: yaml

        foo:
          memcached.managed:
            - value: bar
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    try:
        cur = __salt__["memcached.get"](name, host, port)
    except CommandExecutionError as exc:
        ret["comment"] = str(exc)
        return ret

    if cur == value:
        ret["result"] = True
        ret["comment"] = f"Key '{name}' does not need to be updated"
        return ret

    if __opts__["test"]:
        ret["result"] = None
        if cur is None:
            ret["comment"] = f"Key '{name}' would be added"
        else:
            ret["comment"] = f"Value of key '{name}' would be changed"
        return ret

    try:
        ret["result"] = __salt__["memcached.set"](
            name, value, host, port, time, min_compress_len
        )
    except (CommandExecutionError, SaltInvocationError) as exc:
        ret["comment"] = str(exc)
    else:
        if ret["result"]:
            ret["comment"] = f"Successfully set key '{name}'"
            if cur is not None:
                ret["changes"] = {"old": cur, "new": value}
            else:
                ret["changes"] = {"key added": name, "value": value}
        else:
            ret["comment"] = f"Failed to set key '{name}'"
    return ret


def absent(name, value=None, host=DEFAULT_HOST, port=DEFAULT_PORT, time=DEFAULT_TIME):
    """
    Ensure that a memcached key is not present.

    name
        The key

    value : None
        If specified, only ensure that the key is absent if it matches the
        specified value.

    host
        The memcached server IP address

    port
        The memcached server port


    .. code-block:: yaml

        foo:
          memcached.absent

        bar:
          memcached.absent:
            - host: 10.0.0.1
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    try:
        cur = __salt__["memcached.get"](name, host, port)
    except CommandExecutionError as exc:
        ret["comment"] = str(exc)
        return ret

    if value is not None:
        if cur is not None and cur != value:
            ret["result"] = True
            ret["comment"] = "Value of key '{}' ('{}') is not '{}'".format(
                name, cur, value
            )
            return ret
    if cur is None:
        ret["result"] = True
        ret["comment"] = f"Key '{name}' does not exist"
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Key '{name}' would be deleted"
        return ret

    try:
        ret["result"] = __salt__["memcached.delete"](name, host, port, time)
    except (CommandExecutionError, SaltInvocationError) as exc:
        ret["comment"] = str(exc)
    else:
        if ret["result"]:
            ret["comment"] = f"Successfully deleted key '{name}'"
            ret["changes"] = {"key deleted": name, "value": cur}
        else:
            ret["comment"] = f"Failed to delete key '{name}'"
    return ret
