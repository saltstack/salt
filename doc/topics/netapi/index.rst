.. _netapi-introduction:

==================
``netapi`` modules
==================

netapi modules provide API access to Salt functionality over the network.

The included :ref:`netapi modules <all-netapi-modules>` support REST (over
HTTP and WSGI) and WebSockets.

Modules expose functions from the :py:class:`NetapiClient <salt.netapi.NetapiClient>`
and give access to the same functionality as the Salt commandline tools
(:command:`salt`, :command:`salt-run`, etc).


Client interfaces
=================

Salt's client interfaces provide the ability to execute functions from
execution, runnner, and wheel modules.

The client interfaces available via netapi modules are defined in the
:py:class:`NetapiClient <salt.netapi.NetapiClient>`, which is a
limited version of the :ref:`Python API <python-api>`.

The client interfaces accept a dictionary with values for the function
and its arguments.

Available interfaces:

* local - run execution modules on minions
* local_subset - run execution modules on a subset of minions
* runner - run runner modules on master
* ssh - run salt-ssh commands
* wheel - run wheel modules

The local, runner, and wheel clients also have async variants to run
modules asynchronously.


Configuration
=============

The :conf_master:`netapi_enable_clients` list in the master config sets which
client interfaces are available. It is recommended to only enable the client
interfaces required to complete the tasks needed to reduce the amount of Salt
functionality exposed via the netapi. See the
:ref:`netapi_enable clients <netapi-enable-clients>` documentation.

.. toctree::

    netapi-enable-clients

Individual netapi modules can be enabled by adding the module configuration
section to the master config. The required configuration and dependencies are
documented for each :ref:`module <all-netapi-modules>`.

The :command:`salt-api` daemon manages netapi modules instances and must be
started to enable the configured netapi modules. It is possible to run
multiple netapi modules and multiple instances of each module.

.. admonition:: :conf_master:`netapi_enable_clients`

    Prior to Salt's 3006.0 release all client interfaces were enabled and it
    was not possible to disable clients individually.


Developing modules
==================

Developing custom netapi modules for new transports or protocols is documented in
the :ref:`Writing netapi modules <netapi-writing>` and :ref:`NetapiClient <netapi-client>`
documentation.

.. toctree::

     writing
     netapiclient
