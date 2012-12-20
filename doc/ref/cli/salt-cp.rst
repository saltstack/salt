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

Salt copy copies a local file out to all of the Salt minions matched by the
given target.

Options
=======

.. program:: salt-cp

.. option:: -h, --help

    Print a usage message briefly summarizing these command-line options

.. option:: -t TIMEOUT, --timeout=TIMEOUT

    The timeout in seconds to wait for replies from the Salt minions.

.. option:: -E, --pcre

    The target expression will be interpreted as a PCRE regular expression
    rather than a shell glob.

.. option:: -L, --list

    The target expression will be interpreted as a comma delimited list,
    example: server1.foo.bar,server2.foo.bar,example7.quo.qux

.. option:: -G, --grain

    The target expression matches values returned by the Salt grains system on
    the minions. The target expression is in the format of '<grain value>:<glob
    expression>'; example: 'os:Arch*'

.. option:: --grain-pcre

    The target expression matches values returned by the Salt grains system on
    the minions. The target expression is in the format of '<grain value>:<pcre
    regular expression>'; example: 'os:Arch.*'

.. option:: -R, --range

    Instead of using shell globs to evaluate the target use a range expression
    to identify targets. Range expressions look like %cluster.

    Using the Range option requires that a range server is set up and the
    location of the range server is referenced in the master configuration
    file.

.. option:: -C, --compound

    Utilize many target definitions to make the call very granular. This option
    takes a group of targets separated by and or or. The default matcher is a
    glob as usual, if something other than a glob is used preface it with the
    letter denoting the type, example: 'webserv* and G@os:Debian or E@db*'
    make sure that the compound target is encapsulated in quotes.

.. option:: -c CONFIG, --config=CONFIG

    The location of the Salt master configuration file, the Salt master
    settings are required to know where the connections are;
    default=/etc/salt/master

See also
========

:manpage:`salt(1)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
