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

    Delete the named minion key for command execution.

.. option:: -D DELETE_ALL, --delete-all=DELETE_ALL

    Deleta all keys

.. option:: -c CONFIG, --config=CONFIG

    The master configuration file needs to be read to determine where the Salt
    keys are stored via the pki_dir configuration value;
    default=/etc/salt/master
