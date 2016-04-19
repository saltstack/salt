================================
Running Commands on Salt Minions
================================

Salt can be controlled by a command line client by the root user on the Salt
master. The Salt command line client uses the Salt client API to communicate
with the Salt master server. The Salt client is straightforward and simple
to use.

Using the Salt client commands can be easily sent to the minions.

Each of these commands accepts an explicit `--config` option to point to either
the master or minion configuration file.  If this option is not provided and
the default configuration file does not exist then Salt falls back to use the
environment variables ``SALT_MASTER_CONFIG`` and ``SALT_MINION_CONFIG``.

.. seealso::

    :doc:`Configuration </ref/configuration/index>`

Using the Salt Command
======================

The Salt command needs a few components to send information to the Salt
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

More Powerful Targets
---------------------

See :ref:`Targeting <targeting>`.


Calling the Function
--------------------

The function to call on the specified target is placed after the target
specification.

.. versionadded:: 0.9.8

Functions may also accept arguments, space-delimited:

.. code-block:: bash

    salt '*' cmd.exec_code python 'import sys; print sys.version'

Optional, keyword arguments are also supported:

.. code-block:: bash

    salt '*' pip.install salt timeout=5 upgrade=True

They are always in the form of ``kwarg=argument``.

Arguments are formatted as YAML:

.. code-block:: bash

    salt '*' cmd.run 'echo "Hello: $FIRST_NAME"' saltenv='{FIRST_NAME: "Joe"}'

Note: dictionaries must have curly braces around them (like the ``saltenv``
keyword argument above).  This was changed in 0.15.1: in the above example,
the first argument used to be parsed as the dictionary
``{'echo "Hello': '$FIRST_NAME"'}``. This was generally not the expected
behavior.

If you want to test what parameters are actually passed to a module, use the
``test.arg_repr`` command:

.. code-block:: bash

    salt '*' test.arg_repr 'echo "Hello: $FIRST_NAME"' saltenv='{FIRST_NAME: "Joe"}'

Finding available minion functions
``````````````````````````````````

The Salt functions are self documenting, all of the function documentation can
be retried from the minions via the :func:`sys.doc` function:

.. code-block:: bash

    salt '*' sys.doc

Compound Command Execution
--------------------------

If a series of commands needs to be sent to a single target specification then
the commands can be sent in a single publish. This can make gathering
groups of information faster, and lowers the stress on the network for repeated
commands.

Compound command execution works by sending a list of functions and arguments
instead of sending a single function and argument. The functions are executed
on the minion in the order they are defined on the command line, and then the
data from all of the commands are returned in a dictionary. This means that
the set of commands are called in a predictable way, and the returned data can
be easily interpreted.

Executing compound commands if done by passing a comma delimited list of
functions, followed by a comma delimited list of arguments:

.. code-block:: bash

    salt '*' cmd.run,test.ping,test.echo 'cat /proc/cpuinfo',,foo

The trick to look out for here, is that if a function is being passed no
arguments, then there needs to be a placeholder for the absent arguments. This
is why in the above example, there are two commas right next to each other.
``test.ping`` takes no arguments, so we need to add another comma, otherwise
Salt would attempt to pass "foo" to ``test.ping``.

If you need to pass arguments that include commas, then make sure you add
spaces around the commas that separate arguments. For example:

.. code-block:: bash

    salt '*' cmd.run,test.ping,test.echo 'echo "1,2,3"' , , foo

You may change the arguments separator using the ``--args-separator`` option:

.. code-block:: bash

    salt --args-separator=:: '*' some.fun,test.echo params with , comma :: foo

CLI Completion
==============

Shell completion scripts for the Salt CLI are available in the ``pkg`` Salt
`source directory`_.

.. _source directory: https://github.com/saltstack/salt/tree/develop/pkg


