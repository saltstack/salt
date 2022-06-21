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

With the Salt 3004 release, the ability to configure proxy minions using the delta proxy
was introduced.  The delta proxy provides the ability for a single control proxy
minion to manage multiple proxy minions.

.. seealso::
    :ref:`Installing and Using Deltaproxy <delta-proxy-information>`


Proxy-specific Configuration Options
====================================

.. conf_proxy:: add_proxymodule_to_opts

``add_proxymodule_to_opts``
---------------------------

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

.. versionchanged:: 2017.7.0

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

.. versionadded:: 2017.7.0

Default: ``True``

Whether the connection with the remote device should be restarted
when dead. The proxy module must implement the ``alive`` function,
otherwise the connection is considered alive.

.. code-block:: yaml

    proxy_keep_alive: False


.. conf_proxy:: proxy_keep_alive_interval

``proxy_keep_alive_interval``
-----------------------------

.. versionadded:: 2017.7.0

Default: ``1``

The frequency of keepalive checks, in minutes. It requires the
:conf_proxy:`proxy_keep_alive` option to be enabled
(and the proxy module to implement the ``alive`` function).

.. code-block:: yaml

    proxy_keep_alive_interval: 5


.. conf_proxy:: proxy_always_alive

``proxy_always_alive``
----------------------

.. versionadded:: 2017.7.0

Default: ``True``

Whether the proxy should maintain the connection with the remote
device. Similarly to :conf_proxy:`proxy_keep_alive`, this option
is very specific to the design of the proxy module.
When :conf_proxy:`proxy_always_alive` is set to ``False``,
the connection with the remote device is not maintained and
has to be closed after every command.

.. code-block:: yaml

    proxy_always_alive: False

``proxy_merge_pillar_in_opts``
------------------------------

.. versionadded:: 2017.7.3

Default: ``False``.

Whether the pillar data to be merged into the proxy configuration options.
As multiple proxies can run on the same server, we may need different
configuration options for each, while there's one single configuration file.
The solution is merging the pillar data of each proxy minion into the opts.

.. code-block:: yaml

    proxy_merge_pillar_in_opts: True

``proxy_deep_merge_pillar_in_opts``
-----------------------------------

.. versionadded:: 2017.7.3

Default: ``False``.

Deep merge of pillar data into configuration opts.
This option is evaluated only when :conf_proxy:`proxy_merge_pillar_in_opts` is
enabled.

``proxy_merge_pillar_in_opts_strategy``
---------------------------------------

.. versionadded:: 2017.7.3

Default: ``smart``.

The strategy used when merging pillar configuration into opts.
This option is evaluated only when :conf_proxy:`proxy_merge_pillar_in_opts` is
enabled.

``proxy_mines_pillar``
----------------------

.. versionadded:: 2017.7.3

Default: ``True``.

Allow enabling mine details using pillar data. This evaluates the mine
configuration under the pillar, for the following regular minion options that
are also equally available on the proxy minion: :conf_minion:`mine_interval`,
and :conf_minion:`mine_functions`.
