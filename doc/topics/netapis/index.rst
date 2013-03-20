.. _netapi-introduction:

==============================
Introduction to netapi modules
==============================

netapi modules simply bind to a port and start a service. They are enabled by
specifying the name of a netapi module and the port to bind in the master
config file.

Communication with Salt and Salt satelite projects is done by passing a list of
low-data dictionaries to a client interface. Low-data is a dictionary that
specifies the client, the function inside that client to execute, and any
additional arguments or parameters.

Client interfaces
=================

.. autoclass:: saltapi.APIClient
    :members: local, local_async, runner, wheel
