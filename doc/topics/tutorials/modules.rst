.. _tutorial-remote-execution-modules:

=========================
Remote execution tutorial
=========================

.. include:: /_incl/requisite_incl.rst

Order your minions around
=========================

Now that you have a :term:`master <Master>` and at least one :term:`minion <Minion>`
communicating with each other you can perform commands on the minion via the
:command:`salt` command. Salt calls are comprised of three main components:

.. code-block:: bash

    salt '<target>' <function> [arguments]

.. seealso:: :ref:`salt manpage <ref-cli-salt>`

target
------

The target component allows you to filter which minions should run the
following function. The default filter is a glob on the minion id. For example:

.. code-block:: bash

    salt '*' test.version
    salt '*.example.org' test.version

Targets can be based on minion system information using the Grains system:

.. code-block:: bash

    salt -G 'os:Ubuntu' test.version

.. seealso:: :ref:`Grains system <targeting-grains>`

Targets can be filtered by regular expression:

.. code-block:: bash

    salt -E 'virtmach[0-9]' test.version

Targets can be explicitly specified in a list:

.. code-block:: bash

    salt -L 'foo,bar,baz,quo' test.version

Or Multiple target types can be combined in one command:

.. code-block:: bash

    salt -C 'G@os:Ubuntu and webser* or E@database.*' test.version


function
--------

A function is some functionality provided by a module. Salt ships with a large
collection of available functions. List all available functions on your
minions:

.. code-block:: bash

    salt '*' sys.doc

Here are some examples:

Show all currently available minions:

.. code-block:: bash

    salt '*' test.version

Run an arbitrary shell command:

.. code-block:: bash

    salt '*' cmd.run 'uname -a'

.. seealso:: :ref:`the full list of modules <all-salt.modules>`

arguments
---------

Space-delimited arguments to the function:

.. code-block:: bash

    salt '*' cmd.exec_code python 'import sys; print sys.version'

Optional, keyword arguments are also supported:

.. code-block:: bash

    salt '*' pip.install salt timeout=5 upgrade=True

They are always in the form of ``kwarg=argument``.
