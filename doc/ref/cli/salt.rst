========
``salt``
========

Synopsis
========

    salt '*' [ options ] sys.doc

    salt -E '.*' [ options ] sys.doc cmd

    salt -F 'operatingsystem:Arch.*' [ options ] test.ping

    salt -Q test.ping

Description
===========

Salt allows for commands to be executed across a swath of remote systems in
parallel. This means that remote systems can be both controlled and queried
with ease.

Options
=======

.. program:: salt

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

    Execute a salt command query, this can be used to find the results os a
    previous function call: -Q test.echo')

.. option:: -c CONFIG, --config=CONFIG

    The location of the salt master configuration file, the salt master
    settings are required to know where the connections are;
    default=/etc/salt/master

See also
========

:manpage:`salt(7)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
