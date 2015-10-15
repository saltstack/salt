======================
Command Line Reference
======================

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

The simple target specifications, glob, regex, and list will cover many use
cases, and for some will cover all use cases, but more powerful options exist.

Targeting with Grains
`````````````````````

The Grains interface was built into Salt to allow minions to be targeted by
system properties. So minions running on a particular operating system can
be called to execute a function, or a specific kernel.

Calling via a grain is done by passing the -G option to salt, specifying
a grain and a glob expression to match the value of the grain. The syntax for
the target is the grain key followed by a globexpression: "os:Arch*".

.. code-block:: bash

    salt -G 'os:Fedora' test.ping

Will return True from all of the minions running Fedora.

To discover what grains are available and what the values are, execute the
grains.item salt function:

.. code-block:: bash

    salt '*' grains.items

more info on using targeting with grains can be found :ref:`here
<targeting-grains>`.

Targeting with Executions
`````````````````````````

As of 0.8.8 targeting with executions is still under heavy development and this
documentation is written to reference the behavior of execution matching in the
future.

Execution matching allows for a primary function to be executed, and then based
on the return of the primary function the main function is executed.

Execution matching allows for matching minions based on any arbitrary running
data on the minions.

Compound Targeting
``````````````````

.. versionadded:: 0.9.5

Multiple target interfaces can be used in conjunction to determine the command
targets. These targets can then be combined using and or or statements. This
is well defined with an example:

.. code-block:: bash

    salt -C 'G@os:Debian and webser* or E@db.*' test.ping

In this example any minion who's id starts with ``webser`` and is running
Debian, or any minion who's id starts with db will be matched.

The type of matcher defaults to glob, but can be specified with the
corresponding letter followed by the ``@`` symbol. In the above example a grain
is used with ``G@`` as well as a regular expression with ``E@``. The
``webser*`` target does not need to be prefaced with a target type specifier
because it is a glob.

more info on using compound targeting can be found :ref:`here
<targeting-compound>`.

Node Group Targeting
````````````````````

.. versionadded:: 0.9.5

For certain cases, it can be convenient to have a predefined group of minions
on which to execute commands. This can be accomplished using what are called
:ref:`nodegroups <targeting-nodegroups>`. Nodegroups allow for predefined
compound targets to be declared in the master configuration file, as a sort of
shorthand for having to type out complicated compound expressions.

.. code-block:: yaml

    nodegroups:
      group1: 'L@foo.domain.com,bar.domain.com,baz.domain.com and bl*.domain.com'
      group2: 'G@os:Debian and foo.domain.com'
      group3: 'G@os:Debian and N@group1'


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

    salt '*' cmd.run 'echo "Hello: $FIRST_NAME"' env='{FIRST_NAME: "Joe"}'

Note: dictionaries must have curly braces around them (like the ``env``
keyword argument above).  This was changed in 0.15.1: in the above example,
the first argument used to be parsed as the dictionary
``{'echo "Hello': '$FIRST_NAME"'}``. This was generally not the expected
behavior.

If you want to test what parameters are actually passed to a module, use the
``test.arg_repr`` command:

.. code-block:: bash

    salt '*' test.arg_repr 'echo "Hello: $FIRST_NAME"' env='{FIRST_NAME: "Joe"}'

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

salt-call
=========
.. toctree::

    salt-call

salt
====
.. toctree::

    salt

salt-cloud
==========
.. toctree::

    salt-cloud

salt-cp
=======
.. toctree::

    salt-cp

salt-key
========
.. toctree::

    salt-key

salt-master
===========
.. toctree::

    salt-master

salt-minion
===========
.. toctree::

    salt-minion

salt-proxy
==========
.. toctree::

    salt-proxy

salt-run
========
.. toctree::

    salt-run

salt-ssh
========
.. toctree::

    salt-ssh

salt-syndic
===========
.. toctree::

    salt-syndic

salt-api
========
.. toctree::

    salt-api

spm
===
.. toctree::

    spm
