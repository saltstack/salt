========
``salt``
========

Synopsis
========

    salt '*' [ options ] sys.doc

    salt -E '.*' [ options ] sys.doc cmd

    salt -G 'os:Arch.*' [ options ] test.ping

    salt -C 'G@os:Arch.* and webserv* or G@kernel:FreeBSD' [ options ] test.ping

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

    The timeout in seconds to wait for replies from the Salt minions.

.. option:: -s STATIC, --static=STATIC

    By default as of version 0.9.8 the salt command returns data to the
    console as it is received from minions, but previous releases would return
    data only after all data was received. To only return the data with a hard
    timeout and after all minions have returned then use the static option.

.. option:: -b BATCH, --batch-size=BATCH

    Instead of executing on all targeted minions at once, execute on a
    progressive set of minions. This option takes an argument in the form of
    an explicit number of minions to execute at once, or a percentage of
    minions to execute on.

.. option:: --version

    Print the version of Salt that is running.

.. option:: -E, --pcre

    The target expression will be interpreted as a pcre regular expression
    rather than a shell glob.

.. option:: -L, --list

    The target expression will be interpreted as a comma delimited list,
    example: server1.foo.bar,server2.foo.bar,example7.quo.qux

.. option:: -G, --grain

    The target expression matches values returned by the Salt grains system on
    the minions. The target expression is in the format of '<grain value>:<glob
    expression>'; example: 'os:Arch*'

    This was changed in version 0.9.8 to accept glob expressions instead of
    regular expression. To use regular expression matching with grains use
    the --grain-pcre option.

.. option:: --grain-pcre

    The target expression matches values returned by the Salt grains system on
    the minions. The target expression is in the format of '<grain value>:<
    regular expression>'; example: 'os:Arch.*'

.. option:: -C, --compound

    Utilize many target definitions to make the call very granular. This option
    takes a group of targets separated by and or or. The default matcher is a
    glob as usual, if something other than a glob is used preface it with the
    letter denoting the type, example: 'webserv* and G@os:Debian or E@db*'
    make sure that the compound target is encapsulated in quotes.

.. option:: -X, --exsel

    Instead of using shell globs use the return code of a function.

.. option:: -N, --nodegroup

    Use a predefined compound target defined in the Salt master configuration
    file

.. option:: -R, --range

    Instead of using shell globs to evaluate the target use a range expression
    to identify targets. Range expressions look like %cluster.

    Using the Range option requires that a range server is set up and the
    location of the range server is referenced in the master configuration
    file.

.. option:: --return

    Chose an alternative returner to call on the minion, if an alternative
    returner is used then the return will not come back tot he command line
    but will be sent to the specified return system.

.. option:: -Q, --query

    The -Q option is being deprecated and will be removed in version 0.9.9,
    Use the Salt jobs interface instead, for documentation on the Salt jobs
    interface execute the command "salt-run -d jobs"

    Execute a salt command query, this can be used to find the results of a
    previous function call: -Q test.echo')

.. option:: -c CONFIG, --config=CONFIG

    The location of the Salt master configuration file, the Salt master
    settings are required to know where the connections are;
    default=/etc/salt/master

.. option::  --raw-out

    Print the output from the salt command in raw Python
    form, this is suitable for re-reading the output into
    an executing Python script with eval.

.. option::   --text-out

    Print the output from the salt command in the same
    form the shell would.

.. option::   --yaml-out

    Print the output from the salt command in YAML.

.. option::   --json-out

    Print the output from the salt command in JSON.

.. option:: --no-color

    Disable all colored output

See also
========

:manpage:`salt(7)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
