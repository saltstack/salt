===========================
Configuring the Salt Minion
===========================

The Salt system is amazingly simple and easy to configure, the two components
of the Salt system each have a respective configuration file. The
:command:`salt-master` is configured via the master configuration file, and the
:command:`salt-minion` is configured via the minion configuration file.

.. seealso::
    :ref:`example minion configuration file <configuration-examples-minion>`

The Salt Minion configuration is very simple, typically the only value that
needs to be set is the master value so the minion can find its master.

Minion Primary Configuration
----------------------------

.. conf_minion:: master

``master``
----------

Default: ``salt``

The hostname or ipv4 of the master.

.. code-block:: yaml

    master: salt

.. conf_minion:: master_port

``master_port``
---------------

Default: ``4506``

The port of the master ret server, this needs to coincide with the ret_port
option on the salt master.

.. code-block:: yaml

    master_port: 4506

.. conf_minion:: pki_dir

``pki_dir``
-----------

Default: :file:`/etc/salt/pki`

The directory used to store the minion's public and private keys.

.. code-block:: yaml

    pki_dir: /etc/salt/pki

.. conf_minion:: hostname

``id``
------------

Default: hostname (as returned by the Python call: ``socket.getfqdn()``)

Explicitly declare the id for this minion to use, if left commented the id
will be the hostname as returned by the python call: socket.getfqdn()
Since salt uses detached ids it is possible to run multiple minions on the
same machine but with different ids, this can be useful for salt compute
clusters.

.. code-block:: yaml

    id: foo.bar.com

.. conf_minion:: cachedir

``cachedir``
------------

Default: :file:`/var/cache/salt`

The location for minion cache data.

.. code-block:: yaml

    cachedir: /var/cache/salt

Minion Module Management
------------------------

.. conf_minion:: disable_modules

``disable_modules``
-------------------

Default: ``[]`` (all modules are enabled by default)

The event may occur in which the administrator desires that a minion should not
be able to execute a certain module. The sys module is built into the minion
and cannot be disabled.

.. code-block:: yaml

    disable_modules: [cmd, virt, test]

.. conf_minion:: open_mode

``open_mode``
-------------

Default: ``False``

Open mode can be used to clean out the pki key received from the salt master,
turn on open mode, restart the minion, then turn off open mode and restart the
minion to clean the keys.

.. code-block:: yaml

    open_mode: False
