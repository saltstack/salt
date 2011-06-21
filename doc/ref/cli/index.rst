======================
Command line reference
======================

.. toctree::
    :maxdepth: 1

    salt
    salt-master
    salt-minion
    salt-key
    salt-cp
    salt-call

Salt can be controlled by a command line client as root on the Salt master. The
Salt command line client uses the Salt client API to communicate with the Salt
master server. The Salt client is straightforward and simple to use.

Using the Salt client commands can be easily sent to the minions.

Each of these commands accepts an explicit `--config` option to point to either
the master or minion configuration file.  If this option is not provided and
the default configuration file does not exist then Salt falls back to use the
environment variables ``SALT_MASTER_CONFIG`` and ``SALT_MINION_CONFIG``.

.. seealso::

    :doc:`../configuration/index`

Using the Salt Command
======================

The salt command needs a few components to send information to the salt
minions. The target minions need to be defined, the function to call and any
arguments the function requires.

Defining the Target Minions
---------------------------

The first argument passed to salt, defines the target minions, the target
minions are accessed via their hostname. The default target type is a bash
glob:

.. code-block:: bash

    salt '*foo.com' sys.doc


Salt can also define the target minions with regular expressions:

.. code-block:: bash

    salt -E '.*' cmd.run 'ls -l | grep foo'

Or to explicitly list hosts, salt can take a list:

.. code-block:: bash

    salt -L foo.bar.baz,quo.qux cmd.run 'ps aux | grep foo'

Calling the function
--------------------

The function to call on the specified target is placed after the target
specification.

Finding available minion functions
``````````````````````````````````

The Salt functions are self documenting, all of the function documentation can
be retried from the minions via the :func:`sys.doc` function:

.. code-block:: bash

    salt '*' sys.doc
