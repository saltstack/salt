======================
Writing netapi modules
======================

:py:mod:`~salt.netapi` modules, put simply, bind a port and start a service.
They are purposefully open-ended and can be used to present a variety of
external interfaces to Salt, and even present multiple interfaces at once.

.. seealso:: :ref:`The full list of netapi modules <all-netapi-modules>`

Configuration
=============

All :py:mod:`~salt.netapi` configuration is done in the :ref:`Salt master
config <configuration-salt-master>` and takes a form similar to the following:

.. code-block:: yaml

    rest_cherrypy:
      port: 8000
      debug: True
      ssl_crt: /etc/pki/tls/certs/localhost.crt
      ssl_key: /etc/pki/tls/certs/localhost.key

The ``__virtual__`` function
============================

Like all module types in Salt, :py:mod:`~salt.netapi` modules go through
Salt's loader interface to determine if they should be loaded into memory and
then executed.

The ``__virtual__`` function in the module makes this determination and should
return ``False`` or a string that will serve as the name of the module. If the
module raises an ``ImportError`` or any other errors, it will not be loaded.

The ``start`` function
======================

The ``start()`` function will be called for each :py:mod:`~salt.netapi`
module that is loaded. This function should contain the server loop that
actually starts the service. This is started in a multiprocess.

Inline documentation
====================

As with the rest of Salt, it is a best-practice to include liberal inline
documentation in the form of a module docstring and docstrings on any classes,
methods, and functions in your :py:mod:`~salt.netapi` module.

Loader “magic” methods
======================

The loader makes the ``__opts__`` data structure available to any function in
a :py:mod:`~salt.netapi` module.