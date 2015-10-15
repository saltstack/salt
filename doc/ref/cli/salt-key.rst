============
``salt-key``
============

Synopsis
========

.. code-block:: bash

    salt-key [ options ]

Description
===========

Salt-key executes simple management of Salt server public keys used for
authentication.

On initial connection, a Salt minion sends its public key to the Salt
master. This key must be accepted using the ``salt-key`` command on the
Salt master.

Salt minion keys can be in one of the following states:

- **unaccepted**: key is waiting to be accepted.
- **accepted**: key was accepted and the minion can communicate with the Salt
  master.
- **rejected**: key was rejected using the ``salt-key`` command. In
  this state the minion does not receive any communication from the Salt
  master.
- **denied**: key was rejected automatically by the Salt master.
  This occurs when a minion has a duplicate ID, or when a minion was rebuilt or
  had new keys generated and the previous key was not deleted from the Salt
  master. In this state the minion does not receive any communication from the
  Salt master.

To change the state of a minion key, use ``-d`` to delete the key and then
accept or reject the key.

Options
=======

.. program:: salt-key

.. include:: _includes/common-options.rst

.. option:: -u USER, --user=USER

    Specify user to run salt-key

.. option:: --hard-crash

    Raise any original exception rather than exiting gracefully. Default is
    False.

.. option:: -q, --quiet

   Suppress output

.. option:: -y, --yes

   Answer 'Yes' to all questions presented, defaults to False

.. option:: --rotate-aes-key=ROTATE_AES_KEY

    Setting this to False prevents the master from refreshing the key session
    when keys are deleted or rejected, this lowers the security of the key
    deletion/rejection operation. Default is True.

.. include:: _includes/logging-options.rst
    :end-before: start-console-output
.. include:: _includes/logging-options.rst
    :start-after: stop-console-output
.. |logfile| replace:: /var/log/salt/minion
.. |loglevel| replace:: ``warning``

.. include:: _includes/output-options.rst

Actions
-------

.. option:: -l ARG, --list=ARG

    List the public keys. The args ``pre``, ``un``, and ``unaccepted`` will
    list unaccepted/unsigned keys. ``acc`` or ``accepted`` will list
    accepted/signed keys. ``rej`` or ``rejected`` will list rejected keys.
    Finally, ``all`` will list all keys.

.. option:: -L, --list-all

    List all public keys. (Deprecated: use ``--list all``)

.. option:: -a ACCEPT, --accept=ACCEPT

    Accept the specified public key (use --include-all to match rejected keys
    in addition to pending keys). Globs are supported.

.. option:: -A, --accept-all

    Accepts all pending keys.

.. option:: -r REJECT, --reject=REJECT

    Reject the specified public key (use --include-all to match accepted keys
    in addition to pending keys). Globs are supported.

.. option:: -R, --reject-all

    Rejects all pending keys.

.. option:: --include-all

    Include non-pending keys when accepting/rejecting.

.. option:: -p PRINT, --print=PRINT

    Print the specified public key.

.. option:: -P, --print-all

    Print all public keys

.. option:: -d DELETE, --delete=DELETE

    Delete the specified key. Globs are supported.

.. option:: -D, --delete-all

    Delete all keys.

.. option:: -f FINGER, --finger=FINGER

    Print the specified key's fingerprint.

.. option:: -F, --finger-all

    Print all keys' fingerprints.


Key Generation Options
-----------------------

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

.. option:: --gen-signature

    Create a signature file of the masters public-key named
    master_pubkey_signature. The signature can be send to a minion in the
    masters auth-reply and enables the minion to verify the masters public-key
    cryptographically. This requires a new signing-key- pair which can be
    auto-created with the --auto-create parameter.

.. option:: --priv=PRIV

    The private-key file to create a signature with

.. option:: --signature-path=SIGNATURE_PATH

    The path where the signature file should be written

.. option:: --pub=PUB

    The public-key file to create a signature for

.. option:: --auto-create

    Auto-create a signing key-pair if it does not yet exist

See also
========

:manpage:`salt(7)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
