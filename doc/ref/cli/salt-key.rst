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

.. include:: _includes/common-options.rst

.. option:: -l ARG, --list=ARG

    List the public keys. The args "pre", "un", and "unaccepted" will list
    unaccepted/unsigned keys. "acc" or "accepted" will list accepted/signed
    keys. "rej" or "rejected" will list rejected keys. Finally, "all" will list
    all keys.

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

.. option:: -p PRINT, --print=PRINT

   Print the specified public key

.. option:: -P, --print-all

   Print all public keys

.. option:: -q, --quiet

   Supress output

.. option:: -y, --yes

   Answer 'Yes' to all questions presented, defaults to False

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

.. include:: _includes/logging-options.rst
    :end-before: start-console-output
.. include:: _includes/logging-options.rst
    :start-after: stop-console-output
.. |logfile| replace:: /var/log/salt/minion
.. |loglevel| replace:: ``warning``

.. include:: _includes/output-options.rst


See also
========

:manpage:`salt(7)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
