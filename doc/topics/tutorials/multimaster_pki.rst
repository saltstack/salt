.. _tutorial-multi-master-pki:

=======================================
Multi-Master-PKI Tutorial With Failover
=======================================

This tutorial will explain, how to run a salt-environment where a single
minion can have multiple masters and fail-over between them if its current
master fails.

The individual steps are

- setup the master(s) to sign its auth-replies
- setup minion(s) to verify master-public-keys
- enable multiple masters on minion(s)
- enable master-check on  minion(s)

    Please note, that it is advised to have good knowledge of the salt-
    authentication and communication-process to understand this tutorial.
    All of the settings described here, go on top of the default
    authentication/communication process.


Motivation
==========

The default behaviour of a salt-minion is to connect to a master and accept
the masters public key. With each publication, the master sends his public-key
for the minion to check and if this public-key ever changes, the minion
complains and exits. Practically this means, that there can only be a single
master at any given time.

Would it not be much nicer, if the minion could have any number of masters
(1:n) and jump to the next master if its current master died because of a
network or hardware failure?

.. note::
    There is also a MultiMaster-Tutorial with a different approach and topology
    than this one, that might also suite your needs or might even be better suited
    `Multi-Master Tutorial <https://docs.saltproject.io/en/latest/topics/tutorials/multimaster.html>`_


It is also desirable, to add some sort of authenticity-check to the very first
public key a minion receives from a master. Currently a minions takes the
first masters public key for granted.

The Goal
========

Setup the master to sign the public key it sends to the minions and enable the
minions to verify this signature for authenticity.

Prepping the master to sign its public key
==========================================

For signing to work, both master and minion must have the signing and/or
verification settings enabled. If the master signs the public key but the
minion does not verify it, the minion will complain and exit. The same
happens, when the master does not sign but the minion tries to verify.

The easiest way to have the master sign its public key is to set

.. code-block:: yaml

    master_sign_pubkey: True

After restarting the salt-master service, the master will automatically
generate a new key-pair

.. code-block:: yaml

    master_sign.pem
    master_sign.pub

A custom name can be set for the signing key-pair by setting

.. code-block:: yaml

    master_sign_key_name: <name_without_suffix>

The master will then generate that key-pair upon restart and use it for
creating the public keys signature attached to the auth-reply.

The computation is done for every auth-request of a minion. If many minions
auth very often, it is advised to use conf_master:`master_pubkey_signature`
and conf_master:`master_use_pubkey_signature` settings described below.

If multiple masters are in use and should sign their auth-replies, the signing
key-pair master_sign.* has to be copied to each master. Otherwise a minion
will fail to verify the masters public when connecting to a different master
than it did initially. That is because the public keys signature was created
with a different signing key-pair.



Prepping the minion to verify received public keys
==================================================
The minion must have the public key (and only that one!) available to be
able to verify a signature it receives. That public key (defaults to
master_sign.pub) must be copied from the master to the minions pki-directory.


.. code-block:: bash

    /etc/salt/pki/minion/master_sign.pub

.. important::
    DO NOT COPY THE master_sign.pem FILE. IT MUST STAY ON THE MASTER AND
    ONLY THERE!

When that is done, enable the signature checking in the minions configuration

.. code-block:: yaml

    verify_master_pubkey_sign: True

and restart the minion. For the first try, the minion should be run in manual
debug mode.


.. code-block:: bash

    salt-minion -l debug

Upon connecting to the master, the following lines should appear on the output:

.. code-block:: text

    [DEBUG   ] Attempting to authenticate with the Salt Master at 172.16.0.10
    [DEBUG   ] Loaded minion key: /etc/salt/pki/minion/minion.pem
    [DEBUG   ] salt.crypt.verify_signature: Loading public key
    [DEBUG   ] salt.crypt.verify_signature: Verifying signature
    [DEBUG   ] Successfully verified signature of master public key with verification public key master_sign.pub
    [INFO    ] Received signed and verified master pubkey from master 172.16.0.10
    [DEBUG   ] Decrypting the current master AES key

If the signature verification fails, something went wrong and it will look
like this

.. code-block:: text

    [DEBUG   ] Attempting to authenticate with the Salt Master at 172.16.0.10
    [DEBUG   ] Loaded minion key: /etc/salt/pki/minion/minion.pem
    [DEBUG   ] salt.crypt.verify_signature: Loading public key
    [DEBUG   ] salt.crypt.verify_signature: Verifying signature
    [DEBUG   ] Failed to verify signature of public key
    [CRITICAL] The Salt Master server's public key did not authenticate!

In a case like this, it should be checked, that the verification pubkey
(master_sign.pub) on the minion is the same as the one on the master.

Once the verification is successful, the minion can be started in daemon mode
again.

For the paranoid among us, its also possible to verify the publication whenever
it is received from the master. That is, for every single auth-attempt which
can be quite frequent. For example just the start of the minion will force the
signature to be checked 6 times for various things like auth, mine,
:ref:`highstate <running-highstate>`, etc.

If that is desired, enable the setting


.. code-block:: yaml

    always_verify_signature: True


Multiple Masters For A Minion
=============================

Configuring multiple masters on a minion is done by specifying two settings:

- a list of masters addresses
- what type of master is defined

.. code-block:: yaml

    master:
        - 172.16.0.10
        - 172.16.0.11
        - 172.16.0.12

.. code-block:: yaml

    master_type: failover


This tells the minion that all the master above are available for it to
connect to. When started with this configuration, it will try the master
in the order they are defined. To randomize that order, set

.. code-block:: yaml

    random_master: True

The master-list will then be shuffled before the first connection attempt.

The first master that accepts the minion, is used by the minion. If the
master does not yet know the minion, that counts as accepted and the minion
stays on that master.


For the minion to be able to detect if its still connected to its current
master enable the check for it

.. code-block:: yaml

    master_alive_interval: <seconds>

If the loss of the connection is detected, the minion will temporarily
remove the failed master from the list and try one of the other masters
defined (again shuffled if that is enabled).


Testing the setup
=================

At least two running masters are needed to test the failover setup.

Both masters should be running and the minion should be running on the command
line in debug mode

.. code-block:: bash

    salt-minion -l debug

The minion will connect to the first master from its master list

.. code-block:: bash

    [DEBUG   ] Attempting to authenticate with the Salt Master at 172.16.0.10
    [DEBUG   ] Loaded minion key: /etc/salt/pki/minion/minion.pem
    [DEBUG   ] salt.crypt.verify_signature: Loading public key
    [DEBUG   ] salt.crypt.verify_signature: Verifying signature
    [DEBUG   ] Successfully verified signature of master public key with verification public key master_sign.pub
    [INFO    ] Received signed and verified master pubkey from master 172.16.0.10
    [DEBUG   ] Decrypting the current master AES key


A test.version on the master the minion is currently connected to should be run to
test connectivity.

If successful, that master should be turned off. A firewall-rule denying the
minions packets will also do the trick.

Depending on the configured conf_minion:`master_alive_interval`, the minion
will notice the loss of the connection and log it to its logfile.


.. code-block:: bash

    [INFO    ] Connection to master 172.16.0.10 lost
    [INFO    ] Trying to tune in to next master from master-list


The minion will then remove the current master from the list and try connecting
to the next master

.. code-block:: bash

    [INFO    ] Removing possibly failed master 172.16.0.10 from list of masters
    [WARNING ] Master ip address changed from 172.16.0.10 to 172.16.0.11
    [DEBUG   ] Attempting to authenticate with the Salt Master at 172.16.0.11


If everything is configured correctly, the new masters public key will be
verified successfully


.. code-block:: bash

    [DEBUG   ] Loaded minion key: /etc/salt/pki/minion/minion.pem
    [DEBUG   ] salt.crypt.verify_signature: Loading public key
    [DEBUG   ] salt.crypt.verify_signature: Verifying signature
    [DEBUG   ] Successfully verified signature of master public key with verification public key master_sign.pub

the authentication with the new master is successful

.. code-block:: bash

    [INFO    ] Received signed and verified master pubkey from master 172.16.0.11
    [DEBUG   ] Decrypting the current master AES key
    [DEBUG   ] Loaded minion key: /etc/salt/pki/minion/minion.pem
    [INFO    ] Authentication with master successful!


and the minion can be pinged again from its new master.



Performance Tuning
==================

With the setup described above, the master computes a signature for every
auth-request of a minion. With many minions and many auth-requests, that
can chew up quite a bit of CPU-Power.

To avoid that, the master can use a pre-created signature of its public-key.
The signature is saved as a base64 encoded string which the master reads
once when starting and attaches only that string to auth-replies.

Enabling this also gives paranoid users the possibility, to have the signing
key-pair on a different system than the actual salt-master and create the public
keys signature there. Probably on a system with more restrictive firewall rules,
without internet access, less users, etc.

That signature can be created with

.. code-block:: bash

    salt-key --gen-signature

This will create a default signature file in the master pki-directory

.. code-block:: bash

    /etc/salt/pki/master/master_pubkey_signature

It is a simple text-file with the binary-signature converted to base64.

If no signing-pair is present yet, this will auto-create the signing pair and
the signature file in one call

.. code-block:: bash

    salt-key --gen-signature --auto-create


Telling the master to use the pre-created signature is done with

.. code-block:: yaml

    master_use_pubkey_signature: True


That requires the file 'master_pubkey_signature' to be present in the masters
pki-directory with the correct signature.

If the signature file is named differently, its name can be set with

.. code-block:: yaml

    master_pubkey_signature: <filename>

With many masters and many public-keys (default and signing), it is advised to
use the salt-masters hostname for the signature-files name. Signatures can be
easily confused because they do not provide any information about the key the
signature was created from.

Verifying that everything works is done the same way as above.

How the signing and verification works
======================================

The default key-pair of the salt-master is

.. code-block:: yaml

    /etc/salt/pki/master/master.pem
    /etc/salt/pki/master/master.pub

To be able to create a signature of a message (in this case a public-key),
another key-pair has to be added to the setup. Its default name is:

.. code-block:: yaml

    master_sign.pem
    master_sign.pub

The combination of the master.* and master_sign.* key-pairs give the
possibility of generating signatures. The signature of a given message
is unique and can be verified, if the public-key of the signing-key-pair
is available to the recipient (the minion).

The signature of the masters public-key in master.pub is computed with

.. code-block:: yaml

    master_sign.pem
    master.pub
    M2Crypto.EVP.sign_update()

This results in a binary signature which is converted to base64 and attached
to the auth-reply send to the minion.

With the signing-pairs public-key available to the minion, the attached
signature can be verified with

.. code-block:: yaml

    master_sign.pub
    master.pub
    M2Cryptos EVP.verify_update().


When running multiple masters, either the signing key-pair has to be present
on all of them, or the master_pubkey_signature has to be pre-computed for
each master individually (because they all have different public-keys).

    DO NOT PUT THE SAME master.pub ON ALL MASTERS FOR EASE OF USE.
