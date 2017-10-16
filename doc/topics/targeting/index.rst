.. _targeting:

=================
Targeting Minions
=================

Targeting minions is specifying which minions should run a command or execute a
state by matching against hostnames, or system information, or defined groups,
or even combinations thereof.

For example the command ``salt web1 apache.signal restart`` to restart the
Apache httpd server specifies the machine ``web1`` as the target and the
command will only be run on that one minion.

Similarly when using States, the following :term:`top file` specifies that only
the ``web1`` minion should execute the contents of ``webserver.sls``:

.. code-block:: yaml

    base:
      'web1':
        - webserver

The simple target specifications, glob, regex, and list will cover many use
cases, and for some will cover all use cases, but more powerful options exist.

Targeting with Grains
=====================

The Grains interface was built into Salt to allow minions to be targeted by
system properties. So minions running on a particular operating system can
be called to execute a function, or a specific kernel.

Calling via a grain is done by passing the -G option to salt, specifying
a grain and a glob expression to match the value of the grain. The syntax for
the target is the grain key followed by a glob expression: "os:Arch*".

.. code-block:: bash

    salt -G 'os:Fedora' test.ping

Will return True from all of the minions running Fedora.

To discover what grains are available and what the values are, execute the
grains.item salt function:

.. code-block:: bash

    salt '*' grains.items

More info on using targeting with grains can be found :ref:`here
<targeting-grains>`.

Compound Targeting
==================

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

More info on using compound targeting can be found :ref:`here
<targeting-compound>`.

Node Group Targeting
====================

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


Advanced Targeting Methods
==========================

There are many ways to target individual minions or groups of minions in Salt:

.. toctree::
    :maxdepth: 2

    globbing
    grains
    pillar
    ipcidr
    compound
    nodegroups
    batch
    range
