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

.. option:: -q, --quiet

   Suppress output

.. option:: -y, --yes

   Answer 'Yes' to all questions presented, defaults to False

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


See also
========

:manpage:`salt(7)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
