.. _client-apis:
.. _python-api:

=================
Python client API
=================

Salt is written to be completely API centric, Salt minions and master can be
built directly into third party applications as a communication layer. The Salt
client API is very straightforward.

A number of client command methods are available depending on the exact
behavior desired.

LocalClient
===========

.. autoclass:: salt.client.LocalClient
    :members: cmd, cmd_cli, cmd_iter, cmd_iter_no_block, cmd_async

Salt Caller
===========

.. autoclass:: salt.client.Caller
    :members: function

RunnerClient
============

.. autoclass:: salt.runner.RunnerClient
    :members: cmd, low

WheelClient
===========

.. autoclass:: salt.wheel.Wheel
    :members: call_func, master_call
