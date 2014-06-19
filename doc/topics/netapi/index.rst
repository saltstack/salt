.. _netapi-introduction:

==============================
Introduction to netapi modules
==============================

netapi modules generally bind to a port and start a service. They are
purposefully open-ended. There could be multiple netapi modules that provide a
REST interface, a module that provides an XMPP interface, or Websockets, or
XMLRPC.

netapi modules are enabled by adding configuration to your master config file.
Check the docs for each module to see external requirements and configuration
settings.

Communication with Salt and Salt satellite projects is done by passing a list of
lowstate dictionaries to a client interface. A list of available client
interfaces is below. The lowstate dictionary items map to keyword arguments on
the client interface.

.. seealso:: :ref:`python-api`

Client interfaces
=================

.. autoclass:: saltapi.APIClient
    :members: local, local_async, local_batch, runner, wheel
