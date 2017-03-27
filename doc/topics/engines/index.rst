.. _engines:

============
Salt Engines
============

.. versionadded:: 2015.8.0

Salt Engines are long-running, external system processes that leverage Salt.

- Engines have access to Salt configuration, execution modules, and runners (``__opts__``, ``__salt__``, and ``__runners__``).
- Engines are executed in a separate process that is monitored by Salt. If a Salt engine stops, it is restarted automatically.
- Engines can run on the Salt master and on Salt minions.

Salt engines enhance and replace the :ref:`external processes <ext-processes>` functionality.

Configuration
=============

Salt engines are configured under an ``engines`` top-level section in your Salt master or Salt minion configuration. Provide a list of engines and parameters under this section.

.. code-block:: yaml

   engines:
     - logstash:
         host: log.my_network.com
         port: 5959
         proto: tcp

Salt engines must be in the Salt path, or you can add the ``engines_dirs`` option in your Salt master configuration with a list of directories under which Salt attempts to find Salt engines.

Writing an Engine
=================

An example Salt engine, :blob:`salt/engines/test.py`, is available in the Salt source. To develop an engine, the only requirement is that your module implement the ``start()`` function.
