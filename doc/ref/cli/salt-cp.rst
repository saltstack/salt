===========
``salt-cp``
===========

Copy a file to a set of systems

Synopsis
========

::

    salt-cp '*' [ options ] SOURCE DEST

    salt-cp -E '.*' [ options ] SOURCE DEST

    salt-cp -G 'os:Arch.*' [ options ] SOURCE DEST

Description
===========

Salt copy copies a local file out to all of the salt minions matched by the
given target.

Options
=======

.. program:: salt-cp

.. option:: -h, --help

    Print a usage message briefly summarizing these command-line options

.. option:: -t TIMEOUT, --timeout=TIMEOUT

    The timeout in seconds to wait for replies from the salt minions.

.. option:: -E, --pcre

    The target expression will be interpreted as a pcre regular expression
    rather than a shell glob.

.. option:: -L, --list

    The target expression will be interpreted as a comma delimited list,
    example: server1.foo.bar,server2.foo.bar,example7.quo.qux

.. option:: -G, --grain

    The target expression matches values returned by the salt grains system on
    the minions. The target expression is in the format of '<grain value>:<pcre
    regular expression>'; example: 'os:Arch.*'

.. option:: -Q, --query

    Execute a salt command query, this can be used to find the results of a
    previous function call: -Q test.echo')

.. option:: -c CONFIG, --config=CONFIG

    The location of the salt master configuration file, the salt master
    settings are required to know where the connections are;
    default=/etc/salt/master
