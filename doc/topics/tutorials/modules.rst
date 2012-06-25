=========================
Remote execution tutorial
=========================

.. include:: requisite_incl.rst

Order your minions around
=========================

Now that you have a :term:`master` and at least one :term:`minion`
communicating with each other you can perform commands on the minion via the
:command:`salt` command. Salt calls are comprised of three main components::

    salt '<target>' <function> [arguments]

.. seealso:: :doc:`salt manpage </ref/cli/salt>`

target
------

The target component allows you to filter which minions should run the
following function. The default filter is a glob on the minion id. For example::

    salt '*' test.ping
    salt '*.example.org' test.ping

Targets can be based on minion system information using the Grains system::

    salt -G 'os:Ubuntu' test.ping

.. seealso:: :doc:`Grains system </topics/targeting/grains>`

Targets can be filtered by regular expression::

    salt -E 'virtmach[0-9]' test.ping

Finally, targets can be explicitly specified in a list::

    salt -L foo,bar,baz,quo test.ping

function
--------

A function is some functionality provided by a module. Salt ships with a large
collection of available functions. List all available functions on your
minions::

    salt '*' sys.doc

Here are some examples:

Show all currently available minions::

    salt '*' test.ping

Run an arbitrary shell command::

    salt '*' cmd.run 'uname -a'

.. seealso:: :doc:`the full list of modules </ref/modules/index>`

arguments
---------

Space-delimited arguments to the function::

    salt '*' cmd.exec_code python 'import sys; print sys.version'
