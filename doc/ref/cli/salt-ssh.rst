============
``salt-ssh``
============

Synopsis
========

    salt-ssh '*' [ options ] sys.doc

    salt-ssh -E '.*' [ options ] sys.doc cmd

Description
===========

Salt ssh allows for salt routines to be executed using only ssh for transport

Options
=======

.. program:: salt

.. option:: -h, --help

    Print a usage message briefly summarizing these command-line options

.. option:: -t TIMEOUT, --timeout=TIMEOUT

    The timeout in seconds to wait for replies from the Salt minions. The
    timeout number specifies how long the command line client will wait to
    query the minions and check on running jobs.

.. option:: --version

    Print the version of Salt that is running.

.. option:: --versions-report

    Show program's dependencies version number and exit

.. option:: -E, --pcre

    The target expression will be interpreted as a pcre regular expression
    rather than a shell glob.

.. option:: --return

    Chose an alternative returner to call on the minion, if an alternative
    returner is used then the return will not come back to the command line
    but will be sent to the specified return system.

.. option:: -c CONFIG_DIR, --config-dir=CONFIG_dir

    The location of the Salt configuration directory, this directory contains
    the configuration files for Salt master and minions. The default location
    on most systems is /etc/salt.

.. option:: --out

    Pass in an alternative outputter to display the return of data. This
    outputter can be any of the available outputters:
    grains, highstate, json, key, overstatestage, pprint, raw, txt, yaml
    Some outputters are formatted only for data returned from specific
    functions, for instance the grains outputter will not work for non grains
    data.
    If an outputter is used that does not support the data passed into it, then
    Salt will fall back on the pprint outputter and display the return data
    using the python pprint library.

.. option:: --out-indent OUTPUT_INDENT, --output-indent OUTPUT_INDENT

    Print the output indented by the provided value in spaces. Negative values
    disables indentation. Only applicable in outputters that support indentation.

.. option:: --no-color

    Disable all colored output

See also
========

:manpage:`salt(7)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
