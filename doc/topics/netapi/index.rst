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

.. autoclass:: salt.netapi.NetapiClient
    :members: local, local_async, local_batch, local_subset, runner, wheel

.. toctree::

    ../tutorials/http
    writing
