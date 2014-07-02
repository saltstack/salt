=================================
Multiple Master Failover Tutorial
=================================

When using salts default setup, a minion can only work with one single master.
While this works very nicely with a few hundred minions, it does not provide
redundancy of any kind on the masters end.

For smaller networks with several hundred minions, there is the possibility of
running a Multi-Master setup, in which a minion connects to a list of masters
and keeps all connections open. Any master a minion is connected to, can
can publish commands.

In larger networks with several thousand or more minions, its not always possible
or desirable, to have all minions connected to two or more masters all the time.
What would be more appealing is to have a bunch of masters, and spread the minions
over all of them evenly. Or if the hardware differs between the masters, have more
minions on stronger hardware and less on weaker.

This tutorial explains alle the settings to make this possible. It will describe:

- setting up a mutli-master environment without having to copy AES-master-keys back and forth after restarting the salt-master daemon on one of the masters
- how to enable minions to work with multiple masters without compromising security
- in detail how to enable signing and verifying of trusted masters public keys
- it will show how to limit the number of minions on a master
- how to have a minion detect that its lost its master and should connect to the next

    Please note, that it is advised to have good knowledge of the salt-authentication and
    communication-process to understand this tutorial. All of the settings described here,
    go on top of the default authentication/communication process.



Motivation
----------

The default behaviour of a salt-minion is to connect to a master and accept the masters
public key after being accepted by the master. The minions saves this masters public
in its pki-directory. In future communication, the master sends its public key on
various occasions and the minions checks it every time with the one, it has saved
locally. If this public key ever changes (for example when the master is changed
without copying the master keys), the minion complains and exits. That means, a minion
only accepts one single master at a time. Wouldnt it be much nicer, if the minion
could just jump to the next master if its current master died because of a network or
hardware failure?


Another thought why some sort of master verification would be nice is, that its
in theory possible, to use ARP-spoofing or DNS-Hijacking to have the minion connect
to a rogue salt-master and accept that rogue masters public key. In theory because ARP-
spoofing requires access to the direct network the minion is connected to and DNS-Hijacking
requires very good timing to catch a minion on its very first connection attempt to
a master. To make this theoretical attack impossible, it would be great if the authenticity
of even the very first public key a minion receives could be verified.



The Goal
--------

Setup the master to sign the public key it sends to the minions and enable the
minions to verify this signature for authenticity.



How the signing and verification works
--------------------------------------

The salt-master auto-generates a new default master-key-pair in its pki-directory
upon first start.

.. code-block:: yaml

    /etc/salt/pki/master/master.pem
    /etc/salt/pki/master/master.pub

To improve security and make signing and verifiying possible, a new key-pair is
created.

The default name is:

.. code-block:: yaml

    master_sign.pem
    master_sign.pub

The combination of the master.* and master_sign.* key-pairs give the possibility
of generating signatures. The signature of a given message is unique and can be verified,
if the matching public-key is available.

The signature of the master public key in master.pub is computed with

.. code-block:: yaml

    master_sign.pem + master.pub + M2Crypto.EVP.sign_update()

This results in binary signature which is then converted to base64 and attached to the
auth-reply send to the minion.

As said before, the matching public key has to be available for verification. In
this case that means the

.. code-block:: yaml

    master_sign.pub


must be available in the minions pki-directory (copied from master). Once the
master_sign.pub is created, it can be easily included in the setup-procedure of
a new minion. For example when starting a new EC2-Instance or creating a new
vagrant-VM. Verification of the signature is done with

.. code-block:: yaml

    master_sign.pub + master.pub and M2Cryptos EVP.verify_update().

When running multiple masters, the signing key-pair has to be present on all of
them. But unlike required during the Multimaster-Setup and the AES-key, the signing
pair only has to be copied once, not after every master-restart.



Prepping the master to sign its public key
------------------------------------------

For signing to work, both master and minion must have the signing/verification
settings enabled. If the master signs the public key but the minion does not verify
it, the minion will complain and exit. The same happens, when the master does not
sign but the minion tries to verify. Therfore the master has to configured first.


The easiest way to have the master sign its public key is to set

.. code-block:: yaml

    master_sign_pubkey: True

After restarting the service, the master will automatically generate a new key-pair

.. code-block:: yaml

    master_sign.pem
    master_sign.pub

A custom name can be set for the signing key-pair by setting

.. code-block:: yaml

    master_key_sign_name: <name>

The master will then generate that key-pair upon restart and use it for creating the
public keys signature attached to the auth-reply.

The computation is done for every auth-request of a minion. If many minions auth very often,
it is advised to use conf_master:`master_pubkey_signature` and conf_master:`master_use_pubkey_signature` settings
described below.

If multiple masters are in use and should sign the auth-replies, the signing key-pair
master_sign.* has to be copied to each master. Otherwise a minion will fail to verify
the masters public when connecting to a different master than it did initially. Thats
because the public keys signature was created with a different signing key-pair.



Prepping the minion to verify received public keys
--------------------------------------------------

Please note, that the master has to be configured first. See above.

The minion must have the public key (and only that one!) available to be able to verify
a signatures it receives. That public key (defaults to master_sign.pub) must be copied
from the master to the minions pki-directory.


.. code-block:: bash

    /etc/salt/pki/minion/master_sign.pub

When that is done, enable the signature checking in the minions configuration

.. code-block:: yaml

    verify_master_pub_sig: True

and restart the minion. For the first try, the minion should be run in manual debug mode.


.. code-block:: bash

    $ salt-minion -l debug

Upon connecting to the master, the following lines should appear on the output:

.. code-block:: bash

    [DEBUG   ] Attempting to authenticate with the Salt Master at 172.16.0.10
    [DEBUG   ] Loaded minion key: /etc/salt/pki/minion/minion.pem
    [DEBUG   ] salt.crypt.verify_signature: Loading public key
    [DEBUG   ] salt.crypt.verify_signature: Verifying signature
    [DEBUG   ] Successfully verified signature of master public key with verification public key master_sign.pub
    [INFO    ] Received signed and verified master pubkey from master 172.16.0.10
    [DEBUG   ] Decrypting the current master AES key

If the signature verification fails, something went wrong and it will look like this

.. code-block:: bash

    [DEBUG   ] Attempting to authenticate with the Salt Master at 172.16.0.10
    [DEBUG   ] Loaded minion key: /etc/salt/pki/minion/minion.pem
    [DEBUG   ] salt.crypt.verify_signature: Loading public key
    [DEBUG   ] salt.crypt.verify_signature: Verifying signature
    [DEBUG   ] Failed to verify signature of public key
    [CRITICAL] The Salt Master server's public key did not authenticate!

In a case like this, it should be checked, that the verification pubkey (master_sign.pub) on
the minion is the same as the on the master.

Once the verification is successfull, the minion can be started in daemon mode again.

From now on, whenever the public key of the master changes, the minion will be able to
tell, if its a legit public key it has received from any master.

For the paranoid among us, its also possible to verify the public whenever it is received
from the master. That is, for every single auth-attempt which are quite frequent. For example
just the start of the minion will force the signature to be checked 6 times for various things
like auth, mine, highstate, etc.

If thats desired, enable the setting


.. code-block:: yaml

    always_verify_signature: True



Multiple Masters For A Minion
-----------------------------

Configuring multiple masters on a minion is done by specifying two settings. A list of
masters and what type of master is defined:

.. code-block:: yaml

    master:
        - 172.16.0.10
        - 172.16.0.11
        - 172.16.0.12

.. code-block:: yaml

    master_type: failover


This tells the minion that all the master above are available for it to connect to.
When started with this configuration, it will try the master in the order they are
defined. To randomize that order, set

.. code-block:: yaml

    master_shuffle: True

The master-list will then be shuffled before the first connection attempt.

The first master that accepts the minion, is used by the minion. If the master does not yet
know the minion and only tells the minion to wait until the key is accepted, that counts as
accepted and the minion stays on that master.


For the minion to be able to detect if its still connected to its current master, set

.. code-block:: yaml
    master_alive_interval: <value>

The value is in seconds. If the loss of the connection is detected, the minion will temporarily
remove the failed (current) master from the list and try one of the other masters defined (again
shuffled if thats enabled).

The master_alive_interval setting can also be used in single-master mode. The minion will then log
to its logfile that the connection was lost and when it is re-established. Quite useful because
ZeroMQ does not provide that information to the minion by default.



Testing the setup
-----------------

At least two running masters are needed to test the failover setup.

Both masters should be running and the minion should be running on the command
line in debug mode

.. code-block:: bash

    $ salt-minion -l debug

The minion will connect to the first master from its master list

.. code-block:: bash

    [DEBUG   ] Attempting to authenticate with the Salt Master at 172.16.0.10
    [DEBUG   ] Loaded minion key: /etc/salt/pki/minion/minion.pem
    [DEBUG   ] salt.crypt.verify_signature: Loading public key
    [DEBUG   ] salt.crypt.verify_signature: Verifying signature
    [DEBUG   ] Successfully verified signature of master public key with verification public key master_sign.pub
    [INFO    ] Received signed and verified master pubkey from master 172.16.0.10
    [DEBUG   ] Decrypting the current master AES key


A test.ping on the master the minion is currently connected to should be run to
test connectivity.

If successful, that master should be turned off. A firewall-rule denying the
minions packets can also be used.

Depending on the configured master_alive_interval, the minion will notice the
loss of the connection and log it to its logfile.


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
------------------

With the setup described above, the master computes a signature for every
auth-request of a minion. With many minions and many auth-requests, that can
chew up quite a bite of CPU-Power.

To avoid that, the master can, as an alternative to signing its public key
on the fly, use a pre-created signature of its public-key. The signature is
saved as a base64 encoded string which the master reads once when starting
and attaches only that string to auth-replies.

That signature can be created with

    THIS IS NOT YET IMPLEMENTED. BUT I THINK ITS THE RIGHT PLACE TO PUT IT.
.. code-block:: bash

    $ salt-key --master-pair=master --signing-pair=master_sign --out=master_pubkey_signature

It is a simple text-file with the binary-signature converted to base64. The minion
converts it to binary again before doing the verification.

Enabling this also gives paranoid users the possibility, to have the signing
key-pair on a different system than the actual salt-master and create the public
keys signature there. Probably on a system with more restrictive firewall rules,
without internet access, less users, etc.

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

Another tuning possibitlity is the max_minions setting on the master. If multiple
masters with different (read stronger and weaker) hardware are running, it is
possible to limit the number of minions a master accepts with

.. code-block:: yaml

    max_minions: 100

That will limit the master to accept only 100 minions.

If a minion is rejected by a master because it is full, it is told that the
master is full. It will log that to its logfile and (if configured), will try
the next master from its list of masters.
