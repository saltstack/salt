===================
salt-api Quickstart
===================

:program:`salt-api` manages :term:`netapi modules` which are modules that
(usually) bind to a port and start a service. Each netapi module will have
specific requirements for third-party libraries and configuration (which goes
in the master config file). Read the documentation for each netapi module to
determine what is needed.

For example, the :py:mod:`~saltapi.netapi.rest_cherrypy` netapi module requires
that CherryPy be installed and that a ``rest_cherrypy`` section be added to the
master config that specifies which port to listen on.

Installation
============

PyPI
----

https://pypi.python.org/pypi/salt-api

::

    pip install salt-api

RHEL, Fedora, CentOS
--------------------

We have RPMs available in the Fedora repositories and EPEL::

    yum install salt-api

Ubuntu
------

We have PPA packages available for Ubuntu::

    sudo add-apt-repository ppa:saltstack/salt
    sudo apt-get update
    sudo apt-get install salt-api
