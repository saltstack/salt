"""
Manage etcd Keys
================

.. versionadded:: 2015.8.0

:depends:  - etcd3gw

This state module supports setting and removing keys from etcd.

Configuration
-------------

To work with an etcd server you must configure an etcd profile. The etcd config
can be set in either the Salt Minion configuration file or in pillar:

.. code-block:: yaml

    my_etd_config:
      etcd.host: 127.0.0.1
      etcd.port: 4001

It is technically possible to configure etcd without using a profile, but this
is not considered to be a best practice, especially when multiple etcd servers
or clusters are available.

.. code-block:: yaml

    etcd.host: 127.0.0.1
    etcd.port: 4001

.. versionchanged:: 3009.0

    The etcd v2 API was removed. Only the v3 API is supported; the
    ``etcd.require_v2`` option is no longer accepted and setting it to
    ``True`` raises a ``CommandExecutionError``.

    The client library changed from ``etcd3-py`` to ``etcd3gw``; install it
    with ``salt-pip install etcd3gw``. ``set``, ``rm`` and ``directory`` honor
    ``test=True``, ``set`` no longer rewrites a key that already has the
    right value, and errors talking to etcd fail the state.

When using API v3, there are some specific options available to be configured
within your etcd profile.  They are defaulted to the following...

.. code-block:: yaml

    etcd.encode_keys: False
    etcd.encode_values: True
    etcd.raw_keys: False
    etcd.raw_values: False
    etcd.unicode_errors: "surrogateescape"

``etcd.encode_keys`` indicates whether you want to pre-encode keys using msgpack before
adding them to etcd.

.. note::

    If you set ``etcd.encode_keys`` to ``True``, all recursive functionality will no longer work.
    This includes ``tree`` and ``ls`` and all other methods if you set ``recurse``/``recursive`` to ``True``.
    This is due to the fact that when encoding with msgpack, keys like ``/salt`` and ``/salt/stack`` will have
    differing byte prefixes, and etcd v3 searches recursively using prefixes.

``etcd.encode_values`` indicates whether you want to pre-encode values using msgpack before
adding them to etcd.  This defaults to ``True`` to avoid data loss on non-string values wherever possible.

``etcd.raw_keys`` determines whether you want the raw key or a string returned.

``etcd.raw_values`` determines whether you want the raw value or a string returned.

``etcd.unicode_errors`` determines what you policy to follow when there are encoding/decoding errors.

.. note::

    The etcd configuration can also be set in the Salt Master config file,
    but in order to use any etcd configurations defined in the Salt Master
    config, the :conf_master:`pillar_opts` must be set to ``True``.

    Be aware that setting ``pillar_opts`` to ``True`` has security implications
    as this makes all master configuration settings available in all minion's
    pillars.

Etcd profile configuration can be overridden using following arguments: ``host``,
``port``, ``username``, ``password``, ``ca``, ``client_key`` and ``client_cert``.
The v3 specific arguments can also be used for overriding if you are using v3.

.. code-block:: yaml

    my-value:
      etcd.set:
        - name: /path/to/key
        - value: value
        - host: 127.0.0.1
        - port: 2379
        - username: user
        - password: pass

Available Functions
-------------------

- ``set``

  This will set a value to a key in etcd. Changes will be returned if the key
  has been created or the value of the key has been updated. This
  means you can watch these states for changes.

  .. code-block:: yaml

      /foo/bar/baz:
        etcd.set:
          - value: foo
          - profile: my_etcd_config

- ``wait_set``

  Performs the same functionality as ``set`` but only if a watch requisite is ``True``.

  .. code-block:: yaml

      /some/file.txt:
        file.managed:
          - source: salt://file.txt

      /foo/bar/baz:
        etcd.wait_set:
          - value: foo
          - profile: my_etcd_config
          - watch:
            - file: /some/file.txt

- ``rm``

  This will delete a key from etcd. If the key exists then changes will be
  returned and thus you can watch for changes on the state, if the key does
  not exist then no changes will occur.

  .. code-block:: yaml

      /foo/bar/baz:
        etcd.rm:
          - profile: my_etcd_config

- ``wait_rm``

  Performs the same functionality as ``rm`` but only if a watch requisite is ``True``.

  .. code-block:: yaml

      /some/file.txt:
        file.managed:
          - source: salt://file.txt

      /foo/bar/baz:
        etcd.wait_rm:
          - profile: my_etcd_config
          - watch:
            - file: /some/file.txt
"""

import salt.utils.args
from salt.exceptions import CommandExecutionError

# Define the module's virtual name
__virtualname__ = "etcd"

# Function aliases
__func_alias__ = {
    "set_": "set",
}

try:
    import salt.utils.etcd_util  # pylint: disable=W0611

    HAS_LIBS = salt.utils.etcd_util.HAS_ETCD_V3
except ImportError:
    HAS_LIBS = False


def __virtual__():
    """
    Only return if etcd3gw is installed
    """
    if HAS_LIBS:
        return __virtualname__
    return (False, "The etcd3gw library is not installed")


def set_(name, value, profile=None, **kwargs):
    """
    Set a key in etcd

    name
        The etcd key name, for example: ``/foo/bar/baz``.
    value
        The value the key should contain.

    profile
        Optional, defaults to ``None``. Sets the etcd profile to use which has
        been defined in the Salt Master config.

        .. code-block:: yaml

            my_etd_config:
              etcd.host: 127.0.0.1
              etcd.port: 4001

    """
    rtn = {
        "name": name,
        "comment": "Key contains correct value",
        "result": True,
        "changes": {},
    }
    try:
        current = __salt__["etcd.get"](name, profile=profile, **kwargs)
        if current == value:
            return rtn
        if __opts__.get("test"):
            rtn["result"] = None
            rtn["comment"] = (
                "Key would be created" if current is None else "Key would be updated"
            )
            rtn["changes"] = {name: value}
            return rtn
        __salt__["etcd.set"](name, value, profile=profile, **kwargs)
    except CommandExecutionError as exc:
        rtn["result"] = False
        rtn["comment"] = str(exc)
        return rtn
    rtn["comment"] = "New key created" if current is None else "Key value updated"
    rtn["changes"] = {name: value}
    return rtn


def wait_set(name, value, profile=None, **kwargs):
    """
    Set a key in etcd only if the watch statement calls it. This function is
    also aliased as ``wait_set``.

    name
        The etcd key name, for example: ``/foo/bar/baz``.
    value
        The value the key should contain.
    profile
        The etcd profile to use that has been configured on the Salt Master,
        this is optional and defaults to ``None``.

        .. code-block:: yaml

            my_etd_config:
              etcd.host: 127.0.0.1
              etcd.port: 4001

    """

    return {"name": name, "changes": {}, "result": True, "comment": ""}


def directory(name, profile=None, **kwargs):
    """
    Create a directory in etcd.

    .. versionchanged:: 3009.0

        etcd v3 has no directories, so this state always fails. Set the keys
        under the prefix with ``etcd.set`` instead.

    name
        The etcd directory name, for example: ``/foo/bar/baz``.
    profile
        Optional, defaults to ``None``. Sets the etcd profile to use which has
        been defined in the Salt Master config.

        .. code-block:: yaml

            my_etd_config:
              etcd.host: 127.0.0.1
              etcd.port: 4001
    """
    return {
        "name": name,
        "changes": {},
        "result": False,
        "comment": (
            "etcd v3 has no directories. Set the keys under the prefix with "
            "etcd.set instead."
        ),
    }


def rm(name, recurse=False, profile=None, **kwargs):
    """
    Deletes a key from etcd

    name
        The etcd key name to remove, for example ``/foo/bar/baz``.

    recurse
        Optional, defaults to ``False``. If ``True`` performs a recursive delete.

    profile
        Optional, defaults to ``None``. Sets the etcd profile to use which has
        been defined in the Salt Master config.

        .. code-block:: yaml

            my_etd_config:
              etcd.host: 127.0.0.1
              etcd.port: 4001
    """
    rtn = {"name": name, "result": True, "changes": {}}
    try:
        current = __salt__["etcd.get"](name, recurse=recurse, profile=profile, **kwargs)
        if not current:
            rtn["comment"] = "Key does not exist"
            return rtn
        if __opts__.get("test"):
            rtn["result"] = None
            rtn["comment"] = "Key would be removed"
            rtn["changes"] = {name: "Deleted"}
            return rtn
        removed = __salt__["etcd.rm"](name, recurse=recurse, profile=profile, **kwargs)
    except CommandExecutionError as exc:
        rtn["result"] = False
        rtn["comment"] = str(exc)
        return rtn
    if removed:
        rtn["comment"] = "Key removed"
        rtn["changes"] = {name: "Deleted"}
    else:
        rtn["comment"] = "Key does not exist"
    return rtn


def wait_rm(name, recurse=False, profile=None, **kwargs):
    """
    Deletes a key from etcd only if the watch statement calls it.
    This function is also aliased as ``wait_rm``.

    name
        The etcd key name to remove, for example ``/foo/bar/baz``.
    recurse
        Optional, defaults to ``False``. If ``True`` performs a recursive
        delete of keys under the given prefix.
    profile
        Optional, defaults to ``None``. Sets the etcd profile to use which has
        been defined in the Salt Master config.

        .. code-block:: yaml

            my_etd_config:
              etcd.host: 127.0.0.1
              etcd.port: 4001
    """

    return {"name": name, "changes": {}, "result": True, "comment": ""}


def mod_watch(name, **kwargs):
    """
    The etcd watcher, called to invoke the watch command.
    When called, execute a etcd function based on a watch call requisite.

    .. note::
        This state exists to support special handling of the ``watch``
        :ref:`requisite <requisites>`. It should not be called directly.

        Parameters for this function should be set by the state being triggered.
    """

    sfun = kwargs.get("sfun")
    # Keep the connection overrides (host, port, ...) given to the wait state.
    conn_kwargs = {
        k: v
        for k, v in salt.utils.args.clean_kwargs(**kwargs).items()
        if k not in ("sfun", "value", "recurse", "profile")
    }

    # Watch to set etcd key
    if sfun in ["wait_set_key", "wait_set"]:
        return set_(
            name, kwargs.get("value"), profile=kwargs.get("profile"), **conn_kwargs
        )

    # Watch to rm etcd key
    if sfun in ["wait_rm_key", "wait_rm"]:
        return rm(
            name,
            recurse=kwargs.get("recurse", False),
            profile=kwargs.get("profile"),
            **conn_kwargs,
        )

    return {
        "name": name,
        "changes": {},
        "comment": (
            "etcd.{0[sfun]} does not work with the watch requisite, "
            "please use etcd.wait_set or etcd.wait_rm".format(kwargs)
        ),
        "result": False,
    }
