===================
Configuration guide
===================

The Salt system is amazingly simple and easy to configure, the two components
of the Salt system each have a respective configuration file. The
:command:`salt-master` is configured via the master configuration file, and the
:command:`salt-minion` is configured via the minion configuration file.

.. toctree::
    :hidden:

    examples

.. seealso:: 
    :ref:`example master configuration file <configuration-examples-master>` 
    |
    :ref:`example minion configuration file <configuration-examples-minion>` 

Configuring the Salt Master
===========================

The configuration file for the salt-master is located at
:file:`/etc/salt/master`. The available options are as follows:

.. conf_master:: interface

``interface``
-------------

Default: ``0.0.0.0`` (all interfaces)

The local interface to bind to.

.. code-block:: yaml

    interface: 192.168.0.1

.. conf_master:: publish_port

``publish_port``
----------------

Default: ``4505``

The network port to set up the publication interface

.. code-block:: yaml

    publish_port: 4505

.. conf_master:: worker_threads

``worker_threads``
------------------

Default: ``5``

The number of threads to start for receiving commands and replies from minions.
If minions are stalling on replies because you have many minions, raise the
worker_threads value.

.. code-block:: yaml

    worker_threads: 5

.. conf_master:: ret_port

``ret_port``
------------

Default: ``4506``

The port used by the return server, this is the server used by Salt to receive
execution returns and command executions.

.. code-block:: yaml

    ret_port: 4506

.. conf_master:: pki_dir

``pki_dir``
-----------

Default: :file:`/etc/salt/pki`

The directory to store the pki authentication keys.

.. code-block:: yaml

    pki_dir: /etc/salt/pki

.. conf_master:: cachedir

``cachedir``
------------

Default: :file:`/var/cache/salt`

The location used to store cache information, particularly the job information
for executed salt commands.

.. code-block:: yaml

    cachedir: /var/cache/salt

.. conf_master:: open_mode

``open_mode``
-------------

Default: ``False``

Open mode is a dangerous security feature. One problem encountered with pki
authentication systems is that keys can become "mixed up" and authentication
begins to fail. Open mode turns off authentication and tells the master to
accept all authentication. This will clean up the pki keys recieved from the
minions. Open mode should not be turned on for general use, open mode should
only be used for a short period of time to clean up pki keys. To turn on open
mode the value passed must be ``True``.

.. code-block:: yaml

    open_mode: False

Configuring the Salt Minion
===========================

The Salt Minion configuration is very simple, typically the only value that
needs to be set is the master value so the minion can find its master.

.. conf_minion:: master

``master``
----------

Default: ``mcp``

The hostname or ipv4 of the master.

.. code-block:: yaml

    master: mcp

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

``hostname``
------------

Default: hostname (as returned by the Python call: ``socket.getfqdn()``)

This value is used to statically set the default indentification name for the
minion, while this value is called hostname, salt has no hard requirement on
DNS resolution and this value does not need to be the hostname.

.. code-block:: yaml

    hostname: foo.bar.com

.. conf_minion:: cachedir

``cachedir``
------------

Default: :file:`/var/cache/salt`

The location for minion cache data.

.. code-block:: yaml

    cachedir: /var/cache/salt

.. conf_minion:: disable_modules

``disable_modules``
-------------------

Default: ``[]`` (all modules are enabled by default)

The event may occur in which the administrator desires that a minion should not
be able to execute a certain module. The sys module is built into the minion
and cannot be disabled.

.. code-block:: yaml

    disable_modules: [cmd,virt,test]

.. conf_minion:: open_mode

``open_mode``
-------------

Default: ``False``

Open mode can be used to clean out the pki key recieved from the salt master,
turn on open mode, restart the minion, then turn off open mode and restart the
minion to clean the keys.

.. code-block:: yaml

    open_mode: False
