.. _client-apis:
.. _python-api:

=================
Python client API
=================

There are several ways to access Salt programatically.

Calling Salt from shell scripts
===============================

Salt CLI tools can, of course, be called from shell scripts. Reference the help
output to see what structured :ref:`output formats <all-salt.output>` are
supported. For example:

.. code-block:: bash

    salt '*' disk.usage --out=json

Calling Salt via a REST API
===========================

Salt provides a REST API, currently as a separate sister-project. It will be
merged into Salt core.

https://github.com/saltstack/salt-api

This API utilizes Salt's Python interface documented below. It is also useful
as a reference implementation.

Calling Salt from a Python application
======================================

Salt provides several entry points for interfacing with Python applications.
These entry points are often referred to as ``*Client()`` APIs.

``opts``
--------

Some clients require access to Salt's ``opts`` dictionary. (The dictionary
representation of the :ref:`master <configuration-salt-master>` or
:ref:`minion <configuration-salt-minion>` config files.)

A common pattern for fetching the ``opts`` dictionary is to defer to
environment variables if they exist or otherwise fetch the config from the
default location.

.. code-block:: python

    import salt.config

    master_opts = salt.config.master_config(
        os.environ.get('SALT_MASTER_CONFIG', '/etc/salt/master'))

    minion_opts = salt.config.client_config(
        os.environ.get('SALT_MINION_CONFIG', '/etc/salt/minion'))

Salt's Python interface
=======================

LocalClient
-----------

.. autoclass:: salt.client.LocalClient
    :members: cmd, run_job, cmd_async, cmd_subset, cmd_iter, cmd_iter_no_block,
        get_cli_returns, get_event_iter_returns

Salt Caller
-----------

.. autoclass:: salt.client.Caller
    :members: function

RunnerClient
------------

.. autoclass:: salt.runner.RunnerClient
    :members:

WheelClient
-----------

.. autoclass:: salt.wheel.WheelClient
    :members:

CloudClient
-----------

.. autoclass:: salt.cloud.CloudClient
    :members:
