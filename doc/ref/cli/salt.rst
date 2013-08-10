========
``salt``
========

Synopsis
========

    salt '*' [ options ] sys.doc

    salt -E '.*' [ options ] sys.doc cmd

    salt -G 'os:Arch.*' [ options ] test.ping

    salt -C 'G@os:Arch.* and webserv* or G@kernel:FreeBSD' [ options ] test.ping

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

    The timeout in seconds to wait for replies from the Salt minions. The
    timeout number specifies how long the command line client will wait to
    query the minions and check on running jobs.

.. option:: -s, --static

    By default as of version 0.9.8 the salt command returns data to the
    console as it is received from minions, but previous releases would return
    data only after all data was received. To only return the data with a hard
    timeout and after all minions have returned then use the static option.

.. option:: --async

    Instead of waiting for the job to run on minions only print the jod id of
    the started execution and complete.

.. option:: -b BATCH, --batch-size=BATCH

    Instead of executing on all targeted minions at once, execute on a
    progressive set of minions. This option takes an argument in the form of
    an explicit number of minions to execute at once, or a percentage of
    minions to execute on.

.. option:: -a EAUTH, --auth=EAUTH

    Pass in an external authentication medium to validate against. The
    credentials will be prompted for. Can be used with the -T option.

.. option:: -T, --make-token

    Used in conjunction with the -a option. This creates a token that allows
    for the authenticated user to send commands without needing to
    re-authenticate.

.. option:: --version

    Print the version of Salt that is running.

.. option:: --versions-report

    Show program's dependencies version number and exit

.. include:: _includes/target-selection.rst
.. include:: _includes/extended-target-selection.rst


.. option:: --return

    Chose an alternative returner to call on the minion, if an alternative
    returner is used then the return will not come back to the command line
    but will be sent to the specified return system.

.. option:: -c CONFIG_DIR, --config-dir=CONFIG_dir

    The location of the Salt configuration directory, this directory contains
    the configuration files for Salt master and minions. The default location
    on most systems is /etc/salt.

.. option:: -v VERBOSE, --verbose

    Turn on verbosity for the salt call, this will cause the salt command to
    print out extra data like the job id.

.. option:: -d, --doc, --documentation

    Return the documentation for the module functions available on the minions

.. include:: _includes/output-options.rst

See also
========

:manpage:`salt(7)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
