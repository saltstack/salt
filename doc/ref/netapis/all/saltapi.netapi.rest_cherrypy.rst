=============
rest_cherrypy
=============

.. automodule:: saltapi.netapi.rest_cherrypy

.. py:currentmodule:: saltapi.netapi.rest_cherrypy

.. ............................................................................

.. _rest-cherrypy-config:

Setup and configuration
=======================

The :py:mod:`rest_cherrypy` module requires a few bits of configuration in the
master config of the form:

.. code-block:: yaml

    rest_cherrypy:
      port: 8000
      ssl_crt: /etc/pki/tls/certs/localhost.crt
      ssl_key: /etc/pki/tls/certs/localhost.key

SSL certificate
---------------

The REST interface requires a secure HTTPS connection. You must provide an SSL
certificate to use. If you don't already have a certificate, or don't wish to
buy one, you can generate a self-signed certificate using the
:py:func:`~salt.modules.tls.create_self_signed_cert` function in Salt (note the
setup requirements for this module):

.. code-block:: bash

    % salt-call tls.create_self_signed_cert

.. ............................................................................

