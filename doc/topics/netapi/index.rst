.. _netapi-introduction:

==================
``netapi`` modules
==================

Introduction to netapi modules
==============================

netapi modules provide API-centric access to Salt. Usually externally-facing
services such as REST or WebSockets, XMPP, XMLRPC, etc.

In general netapi modules bind to a port and start a service. They are
purposefully open-ended. A single module can be configured to run as well as
multiple modules simultaneously.

netapi modules are enabled by adding configuration to your Salt Master config
file and then starting the :command:`salt-api` daemon. Check the docs for each
module to see external requirements and configuration settings.

Communication with Salt and Salt satellite projects is done using Salt's own
:ref:`Python API <python-api>`. A list of available client interfaces is below.

.. admonition:: salt-api

    Prior to Salt's 2014.7.0 release, netapi modules lived in the separate sister
    projected ``salt-api``. That project has been merged into the main Salt
    project.

.. seealso:: :ref:`The full list of netapi modules <all-netapi-modules>`

Client interfaces
=================

Salt's client interfaces expose executing functions by crafting a dictionary of
values that are mapped to function arguments. This allows calling functions
simply by creating a data structure. (And this is exactly how much of Salt's
own internals work!)

The :conf_master:`netapi_enable_clients` list in the master config sets which
clients are available. It is recommended to only enable the clients required
to complete the tasks needed to reduce the amount of Salt functionality exposed
via the netapi. Enabling the local clients will provide the same functionality as 
the :command:`salt` command.

.. admonition:: :conf_master:`netapi_enable_clients`

    Prior to Salt's 3006.0 release all clients were enabled and it was not possible
    to disable clients individually.


.. autoclass:: salt.netapi.NetapiClient
    :members: local, local_async, local_subset, ssh, runner, runner_async,
        wheel, wheel_async

.. toctree::

    writing

