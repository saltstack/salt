.. _client-apis:
.. _python-api:

=================
Python client API
=================

Salt provides several entry points for interfacing with Python applications.
These entry points are often referred to as ``*Client()`` APIs. Each client
accesses different parts of Salt, either from the master or from a minion. Each
client is detailed below.

.. note::
    For Tiamat-bundled Salt distribution, you need to use the bundled Python runtime
    as the system Python won't be able to access Salt internals.

    To execute scripts via bundled Python runtime, either run the script with
    ``/path/to/salt python script.py`` or use ``#!/path/to/salt python`` `shebang <https://en.wikipedia.org/wiki/Shebang_(Unix)>`_


.. seealso:: There are many ways to access Salt programmatically.

    Salt can be used from CLI scripts as well as via a REST interface.

    See Salt's :ref:`outputter system <all-salt.output>` to retrieve structured
    data from Salt as JSON, or as shell-friendly text, or many other formats.

    See the :py:func:`state.event <salt.runners.state.event>` runner to utilize
    Salt's event bus from shell scripts.

    Salt's `netapi module`_ provides access to Salt externally via a REST interface.
    Review the `netapi module`_ documentation for more information.

.. _`netapi module`: https://docs.saltproject.io/en/latest/topics/netapi/index.html

Salt's ``opts`` dictionary
==========================

Some clients require access to Salt's ``opts`` dictionary. (The dictionary
representation of the :ref:`master <configuration-salt-master>` or
:ref:`minion <configuration-salt-minion>` config files.)

A common pattern for fetching the ``opts`` dictionary is to defer to
environment variables if they exist or otherwise fetch the config from the
default location.

.. autofunction:: salt.config.client_config

.. autofunction:: salt.config.minion_config

Salt's Loader Interface
=======================

Modules in the Salt ecosystem are loaded into memory using a custom loader
system. This allows modules to have conditional requirements (OS, OS version,
installed libraries, etc) and allows Salt to inject special variables
(``__salt__``, ``__opts__``, etc).

Most modules can be manually loaded. This is often useful in third-party Python
apps or when writing tests. However some modules require and expect a full,
running Salt system underneath. Notably modules that facilitate
master-to-minion communication such as the :py:mod:`~salt.modules.mine`,
:py:mod:`~salt.modules.publish`, and :py:mod:`~salt.modules.peer` execution
modules. The error ``KeyError: 'master_uri'`` is a likely indicator for this
situation. In those instances use the :py:class:`~salt.client.Caller` class
to execute those modules instead.

Each module type has a corresponding loader function.

.. autofunction:: salt.loader.minion_mods

.. autofunction:: salt.loader.raw_mod

.. autofunction:: salt.loader.states

.. autofunction:: salt.loader.grains

.. autofunction:: salt.loader.grain_funcs

Salt's Client Interfaces
========================

.. _client-interfaces:
.. _local-client:

LocalClient
-----------

.. autoclass:: salt.client.LocalClient
    :members: cmd, run_job, cmd_async, cmd_subset, cmd_batch, cmd_iter,
        cmd_iter_no_block, get_cli_returns, get_event_iter_returns

Salt Caller
-----------

.. autoclass:: salt.client.Caller
    :members: cmd

Salt Proxy Caller
-----------------

.. autoclass:: salt.client.ProxyCaller
    :members: cmd

RunnerClient
------------

.. autoclass:: salt.runner.RunnerClient
    :members: cmd, asynchronous, cmd_sync, cmd_async

WheelClient
-----------

.. autoclass:: salt.wheel.WheelClient
    :members: cmd, asynchronous, cmd_sync, cmd_async

CloudClient
-----------

.. autoclass:: salt.cloud.CloudClient
    :members:

SSHClient
---------

.. autoclass:: salt.client.ssh.client.SSHClient
    :members: cmd, cmd_iter
