========
salt-api
========

:program:`salt-api` is a modular interface on top of `Salt`_ that can provide a
variety of entry points into a running Salt system. It can start and manage
multiple interfaces allowing a REST API to coexist with XMLRPC or even a
Websocket API.

.. _`Salt`: http://saltstack.org/

Getting started
===============

1.  Install :program:`salt-api` on the same machine as your Salt master.
2.  Edit your Salt master config file for all required options for each
    ``netapi`` module you wish to run.
3.  Install any required additional libraries or software for each ``netapi``
    module you wish to run.
4.  Run :command:`salt-api` which will then start all configured ``netapi``
    modules.

.. note::

    Each ``netapi`` module will have differing configuration requirements and
    differing required software libraries.

    Exactly like the various module types in Salt (:term:`execution modules`,
    :term:`renderer modules`, :term:`returner modules`, etc.), :term:`netapi
    modules` in :program:`salt-api` will *not* be loaded into memory or started
    if all requirements are not met.

Development quickstart
======================

.. toctree::
    :maxdepth: 1

    topics/quickstart

``netapi`` modules
==================

The core functionality for :program:`salt-api` lies in pluggable ``netapi``
modules that adhere to the simple interface of binding to a port and starting a
service. :program:`salt-api` can manage one or many services concurrently.

Full list of ``netapi`` modules
-------------------------------

.. toctree::
    :maxdepth: 3

    ref/netapis/all/index

``netapi`` developer reference
------------------------------

.. toctree::
    :maxdepth: 1

    topics/netapis/index
    topics/netapis/writing

Releases
========

.. toctree::
    :maxdepth: 2

    topics/releases/index

Reference
=========

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
* :ref:`glossary`
