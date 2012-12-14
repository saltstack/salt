============
``salt-key``
============

Synopsis
========

salt-key [ options ]

Description
===========

Salt-key executes simple management of Salt server public keys used for
authentication.

Options
=======

.. program:: salt-key

.. option:: -h, --help

    Print a usage message briefly summarizing these command-line options.

.. option:: -l, --list

    List the unaccepted minion public keys.

.. option:: -L, --list-all

    List all public keys on this Salt master: accepted, pending,
    and rejected.

.. option:: -a ACCEPT, --accept=ACCEPT

    Accept the named minion public key for command execution.

.. option:: -A, --accept-all

    Accepts all pending public keys.

.. option:: -r REJECT, --reject=REJECT

    Reject the named minion public key.

.. option:: -R, --reject-all

    Rejects all pending public keys.

.. option:: -d DELETE, --delete=DELETE

    Delete the named minion key or minion keys matching a glob for command
    execution.

.. option:: -D, --delete-all

    Delete all keys

.. option:: -c CONFIG_DIR, --config-dir=CONFIG_dir

    The location of the Salt configuration directory, this directory contains
    the configuration files for Salt master and minions. The default location
    on most systems is /etc/salt.

.. option:: -p PRINT, --print=PRINT

   Print the specified public key

.. option:: -P, --print-all

   Print all public keys

.. option:: -q, --quiet

   Supress output

.. option:: -y, --yes

   Answer 'Yes' to all questions presented, defaults to False

.. option:: --key-logfile=KEY_LOGFILE

   Send all output to a file. Default is /var/log/salt/key

.. option:: --gen-keys=GEN_KEYS

   Set a name to generate a keypair for use with salt

.. option:: --gen-keys-dir=GEN_KEYS_DIR

   Set the directory to save the generated keypair.  Only works
   with 'gen_keys_dir' option; default is the current directory.

.. option:: --keysize=KEYSIZE

   Set the keysize for the generated key, only works with
   the '--gen-keys' option, the key size must be 2048 or
   higher, otherwise it will be rounded up to 2048. The
   default is 2048.

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
