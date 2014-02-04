The Table Cryptographic Normalization System
============================================

.. note::

    This library is currently experimental, no security claims are yet present
    and is still undergoing extensive evaluation and heavy development

The idea is very simple, a single interface that simplifies cryptographic
routines to make complex libraries easy and safe to use.

Unified API
-----------

Table delivers a unified API, where the same commands can access different
cryptographic routines. This allows for backend routines to be easily swapped
in and out as time moves forward and the race for cryptographic security
continues.

Cryptographic Backends
----------------------

Backends are simplified, instead of large numbers of groups backends are
simplified into `public` for public key encryption, and `secret` for symmetric
encryption.

No Cryptographic Code
---------------------

This library has no cryptographic code, it only uses established and accepted
backend libraries to deliver simplified cryptographic routines.

Currently Available Public Key Backends
---------------------------------------

Curve 25519 via pynacl and libsodium
RSA via pycrypto and openssl

Currently Available Symmetric Backends
--------------------------------------

Salsa20 via pynacl and libsodium
AES via pycrypto and openssl
