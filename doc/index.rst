========
salt-api
========

:command:`salt-api` is a modular interface on top of `Salt`_ that can provide a
variety of entry points into a running Salt system. It can start and manage
multiple interfaces allowing a REST API to coexist with XMLRPC or even a
Websocket API.

.. _`Salt`: http://saltstack.org/

netapi Modules
==============

The core functionality for :command:`salt-api` lies in pluggable netapi modules
that adhere to the simple interface of binding to a port and starting a
service.

Full list of netapi modules
---------------------------

.. toctree::
    :maxdepth: 2

    ref/netapis/all/index

Releases
========

.. toctree::
    :maxdepth: 1

    topics/releases/index

Reference
=========

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
* :ref:`glossary`
