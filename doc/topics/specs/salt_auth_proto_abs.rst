==============================================
Abstract on Salt Authentication and Encryption
==============================================

The Salt authentication and encryption system uses Public Key authentication
and AES encryption to facilitate both authentication and high speed encryption.

The core components of this system can be separated into a few sections,
Message Formatting, PubKey Handshake, AES key management, and encryption.

Message Formatting
==================

All messages passed within Salt are formatted with a clear header and a "load".
The header is always clear, and specifies the encryption used by the load. The
load can be encrypted with the private key of the sending system, or with the
shared, rotating, AES key.

The message itself is abstracted as a Python dict in this fashion:

.. code-block:: python

    {'enc': 'aes',
     'load': <encrypted msgpack binary data>}

When this message is received the load can be decrypted using the shared AES
key. The 'enc' dict key can also be "pub" for pubkey encryption, or "clear"
for passing messages in the clear.

PubKey Handshake
=================

RSA Public keys are generated on the Salt master and on the Salt minion. When
A salt minion establishes an initial connection to the salt master the minion
sends its public key in the clear to the salt master, along with the id of
the minion, and the command to execute on the master, in this case "_auth":

.. code-block:: python

    {'enc': 'clear',
     'load':
        {'cmd': '_auth',
         'id': <minion id>,
         'pub': <minion public key>}}

If this is the first time this minion has authenticated, then the salt master
returns a clear message informing the minion that it is pending authentication.
The minion then queries the master every ten seconds awaiting authentication.
When the public key of the minion has been approved by the master, then the
master's public key is returned, with the AES key used to encrypt messages and
information on how to connect to the salt master publish interface.

The returned AES key is encrypted with the minion's public key, and can
therefore only be decrypted by the minion that sent out the public key.

Once the minion has authenticated and is in possession of the revolving master
AES key (The AES key is regenerated when the master restarts) then it attaches
the minion subscriber to the master publisher.

All messages sent from the publisher are encrypted using the revolving AES key,
in the event that the master restarts the minions will all have an invalid
AES key because it has been regenerated on the master. The master will then
send out a publication that the minions cannot decrypt. If the minion receives
a publication that cannot be decrypted then the minion will re-authenticate,
obtain the correct AES key, and decrypt the message. This means that the
AES key on the salt master can safely revolve without interrupting the minion
connection.

Regular Communication
=====================

Once the minion has authenticated, then all messages sent between the minion
and the master are encrypted using the revolving AES key and the {'enc': 'aes'}
header.

Source Files Implimenting Components
====================================

The pubkey authentication is managed via the salt.master module:
:blob:`salt/master.py`
The regular minion authentication is managed via the salt.crypt module:
:blob:`salt/crypt.py`
The salt.crypt module contains a class "SAuth" that can be used for
standalone authentication with the Salt master, this is most likely the best
place to start when looking into how the authentication mechanism works
The encrypted "load" portion of the messages are encrypted and decrypted using
the Crypticle class in the crypt module.

Conclusion
==========

In the end Salt uses formatted messages with clear header data to specify how
the message data is encrypted. Asymetric encryption via RSA keys is only used
for authentication and to securely retrieve the master AES key. All further
communications are are encrypted with 256 bit AES.
