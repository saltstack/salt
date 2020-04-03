# -*- coding: utf-8 -*-

"""
Manage etcd Keys
================

.. versionadded:: 2015.8.0

:depends:  - python-etcd

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

.. note::

    The etcd configuration can also be set in the Salt Master config file,
    but in order to use any etcd configurations defined in the Salt Master
    config, the :conf_master:`pillar_opts` must be set to ``True``.

    Be aware that setting ``pillar_opts`` to ``True`` has security implications
    as this makes all master configuration settings available in all minion's
    pillars.

Etcd profile configuration can be overridden using following arguments: ``host``,
``port``, ``username``, ``password``, ``ca``, ``client_key`` and ``client_cert``.

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

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Define the module's virtual name
__virtualname__ = "etcd"

# Function aliases
__func_alias__ = {
    "set_": "set",
}

# Import third party libs
try:
    import salt.utils.etcd_util  # pylint: disable=W0611

    HAS_ETCD = True
except ImportError:
    HAS_ETCD = False


def __virtual__():
    """
    Only return if python-etcd is installed
    """

    return __virtualname__ if HAS_ETCD else False


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

    created = False

    rtn = {
        "name": name,
        "comment": "Key contains correct value",
        "result": True,
        "changes": {},
    }

    current = __salt__["etcd.get"](name, profile=profile, **kwargs)
    if not current:
        created = True

    result = __salt__["etcd.set"](name, value, profile=profile, **kwargs)

    if result and result != current:
        if created:
            rtn["comment"] = "New key created"
        else:
            rtn["comment"] = "Key value updated"
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

    created = False

    rtn = {"name": name, "comment": "Directory exists", "result": True, "changes": {}}

    current = __salt__["etcd.get"](name, profile=profile, recurse=True, **kwargs)
    if not current:
        created = True

    result = __salt__["etcd.set"](name, None, directory=True, profile=profile, **kwargs)

    if result and result != current:
        if created:
            rtn["comment"] = "New directory created"
            rtn["changes"] = {name: "Created"}

    return rtn


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

    if not __salt__["etcd.get"](name, profile=profile, **kwargs):
        rtn["comment"] = "Key does not exist"
        return rtn

    if __salt__["etcd.rm"](name, recurse=recurse, profile=profile, **kwargs):
        rtn["comment"] = "Key removed"
        rtn["changes"] = {name: "Deleted"}
    else:
        rtn["comment"] = "Unable to remove key"

    return rtn


def wait_rm(name, recurse=False, profile=None, **kwargs):
    """
    Deletes a key from etcd only if the watch statement calls it.
    This function is also aliased as ``wait_rm``.

    name
        The etcd key name to remove, for example ``/foo/bar/baz``.
    recurse
        Optional, defaults to ``False``. If ``True`` performs a recursive
        delete, see: https://python-etcd.readthedocs.io/en/latest/#delete-a-key.
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

    # Watch to set etcd key
    if kwargs.get("sfun") in ["wait_set_key", "wait_set"]:
        return set_(name, kwargs.get("value"), kwargs.get("profile"))

    # Watch to rm etcd key
    if kwargs.get("sfun") in ["wait_rm_key", "wait_rm"]:
        return rm(name, kwargs.get("profile"))

    return {
        "name": name,
        "changes": {},
        "comment": "etcd.{0[sfun]} does not work with the watch requisite, "
        "please use etcd.wait_set or etcd.wait_rm".format(kwargs),
        "result": False,
    }
