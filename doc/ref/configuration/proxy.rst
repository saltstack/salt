.. _configuration-salt-proxy:

=================================
Configuring the Salt Proxy Minion
=================================

The Salt system is amazingly simple and easy to configure. The two components
of the Salt system each have a respective configuration file. The
:command:`salt-master` is configured via the master configuration file, and the
:command:`salt-proxy` is configured via the proxy configuration file.

.. seealso::
    :ref:`example proxy minion configuration file <configuration-examples-proxy>`

The Salt Minion configuration is very simple. Typically, the only value that
needs to be set is the master value so the proxy knows where to locate its master.

By default, the salt-proxy configuration will be in :file:`/etc/salt/proxy`.
A notable exception is FreeBSD, where the configuration will be in
:file:`/usr/local/etc/salt/proxy`.



Proxy-specific Configuration Options
====================================

.. conf_proxy:: add_proxymodule_to_opts

``add_proxymodule_to_opts``
--------------------------

.. versionadded:: 2015.8.2

.. versionchanged:: 2016.3.0

Default: ``False``

Add the proxymodule LazyLoader object to opts.

.. code-block:: yaml

    add_proxymodule_to_opts: True


.. conf_proxy:: proxy_merge_grains_in_module

``proxy_merge_grains_in_module``
--------------------------------

.. versionadded:: 2016.3.0

.. versionchanged:: Nitrogen

Default: ``True``

If a proxymodule has a function called ``grains``, then call it during
regular grains loading and merge the results with the proxy's grains
dictionary.  Otherwise it is assumed that the module calls the grains
function in a custom way and returns the data elsewhere.

.. code-block:: yaml

    proxy_merge_grains_in_module: False


.. conf_proxy:: proxy_keep_alive

``proxy_keep_alive``
--------------------

.. versionadded:: Nitrogen

Default: ``True``

Whether the connection with the remote device should be restarted
when dead. The proxy module must implement the ``alive`` function,
otherwise the connection is considered alive.

.. code-block:: yaml

    proxy_keep_alive: False


.. conf_proxy:: proxy_keep_alive_interval

``proxy_keep_alive_interval``
-----------------------------

.. versionadded:: Nitrogen

Default: ``1``

The frequency of keepalive checks, in minutes. It requires the
:conf_minion:`proxy_keep_alive` option to be enabled
(and the proxy module to implement the ``alive`` function).

.. code-block:: yaml

    proxy_keep_alive_interval: 5


.. conf_proxy:: proxy_always_alive

``proxy_always_alive``
----------------------

.. versionadded:: Nitrogen

Default: ``True``

Wheter the proxy should maintain the connection with the remote
device. Similarly to :conf_minion:`proxy_keep_alive`, this option
is very specific to the design of the proxy module.
When :conf_minion:`proxy_always_alive` is set to ``False``,
the connection with the remote device is not maintained and
has to be closed after every command.

.. code-block:: yaml

    proxy_always_alive: False
