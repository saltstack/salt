===================
salt-api Quickstart
===================

Getting started with :program:`salt-api` is fast and easy. When you are done
with this document you will have basic salt-api interface using the
:py:mod:`~saltapi.netapi.rest_cherrypy` netapi module.

.. note::

    This document describes a setup that should be used for testing purposes
    only. Additional configuration is needed before moving to a production
    environment.

Installation
-----------------
* Download and install `cherrypy`__ as a dependency.
* Download salt-api::

    git clone https://github.com/saltstack/salt-api.git

* Change dirctory to the :file:`salt-api` folder and install salt-api::

    python setup.py install

* Run salt-api by issuing::

    salt-api

.. __: http://cherrypy.org/

Configuration
-----------------
* Setup :ref:`external_auth <acl-eauth>` in Salt master configuration file

* Include the ``rest_cherrypy`` in your master configuration file::

   rest_cherrypy:
     port: 8000
     debug: True
