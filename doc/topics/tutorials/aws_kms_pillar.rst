.. _aws-kms-pillar:

=============================================================
Encrypting pillar with the ``aws_kms`` renderer (walkthrough)
=============================================================

The :py:mod:`aws_kms <salt.renderers.aws_kms>` renderer decrypts
Fernet-encrypted ciphertext inside pillar SLS files. The Fernet key
itself is unwrapped at render time with an AWS KMS Customer Master
Key (CMK).

The :py:mod:`aws_kms <salt.renderers.aws_kms>` module docstring lists
the configuration options. This page is the missing piece: an
end-to-end recipe from "I have nothing" to "my pillar SLS contains a
ciphertext that Salt decrypts."

Issue history: :issue:`56247`.

.. contents::
   :local:
   :depth: 1


What this renderer encrypts and decrypts
========================================

* **Encrypts:** individual pillar values, in any SLS file. The
  cleartext is the value (string); the ciphertext is a
  ``urlsafe_b64`` Fernet token written into the SLS.
* **Decrypts:** on the master, at pillar render time. The minion
  never sees ciphertext; the master ships rendered cleartext over
  the encrypted master-minion channel.
* **Does not encrypt:** the ``data_key`` in the master config. The
  ``data_key`` is itself a KMS-wrapped blob (binary), but the value
  on disk in ``/etc/salt/master`` is the wrapped form — anyone with
  read access to the master config plus the master's IAM role can
  unwrap it. See :ref:`security-threat-model` for the broader
  master-host trust boundary.


Prerequisites
=============

On the master:

* Python ``cryptography`` (Fernet) — bundled with the Salt onedir.
* Python ``boto3`` — install into the master's environment.
* AWS credentials that resolve via boto's standard chain (env vars,
  ``~/.aws/credentials`` profile, IAM role on the EC2 instance, EC2
  IMDSv2, etc).
* IAM permissions on the master's principal:

  * ``kms:GenerateDataKey`` on the chosen CMK (one-time, to mint the
    data key)
  * ``kms:Decrypt`` on the chosen CMK (every render of the pillar)

Encryption (of new ciphertext) is local Fernet; the master only
calls KMS to *decrypt* the data key. ``kms:Encrypt`` is not needed
on the master after initial provisioning.


Step 1: create a KMS Customer Master Key
========================================

If you do not already have a CMK, create one. Choose a symmetric key
(used for envelope encryption) and grant the master's IAM principal
``Decrypt`` and ``GenerateDataKey`` access in the key policy.

.. code-block:: bash

    aws kms create-key \
        --description 'Salt pillar encryption' \
        --key-usage ENCRYPT_DECRYPT \
        --customer-master-key-spec SYMMETRIC_DEFAULT

Note the ``KeyId`` (a UUID) from the response. Optionally give it an
alias for human-readable use:

.. code-block:: bash

    aws kms create-alias \
        --alias-name alias/salt-pillar \
        --target-key-id <KeyId-from-above>


Step 2: generate the data key
=============================

Mint a 256-bit data key, wrapped with the CMK. The ciphertext blob
of the wrapped key is what goes into the master config.

.. code-block:: bash

    aws kms generate-data-key \
        --key-id alias/salt-pillar \
        --key-spec AES_256 \
        --query CiphertextBlob \
        --output text

The output is a single line of base64. This is the **wrapped data
key**; the master will unwrap it with ``kms:Decrypt`` at startup and
on every pillar refresh.

The plaintext data key is never written to disk. It exists only in
the master process memory once unwrapped.


Step 3: install the wrapped data key on the master
==================================================

Edit ``/etc/salt/master`` and add:

.. code-block:: yaml

    aws_kms:
      # Optional: name of the boto3 profile to use. Defaults to the
      # standard boto3 chain.
      profile_name: salt
      # Wrapped data key from step 2 — pasted as YAML !!binary.
      data_key: !!binary |
        AQIDAHi4jM... (full base64 line from step 2) ...A==

The ``!!binary`` tag tells YAML to base64-decode the value at parse
time so the renderer sees the raw bytes ``boto3`` expects in
``CiphertextBlob``.

Restart ``salt-master`` and watch the log: on a misconfigured key
you will see ``aws_kms:data_key is not a valid KMS data key`` or
``aws_kms:data_key is not set``.


Step 4: encrypt a value for a pillar SLS
========================================

The renderer ships only a decrypter. To produce ciphertext you need
the plaintext data key from the same KMS CMK. The simplest way is
to ask KMS to decrypt the wrapped data key for you, then use that
plaintext key to encrypt your secret:

.. code-block:: bash

    # 1) Pull the plaintext data key (raw 32 bytes).
    aws kms decrypt \
        --ciphertext-blob fileb://<(echo "<WRAPPED-DATA-KEY-FROM-STEP-2>" | base64 -d) \
        --output text \
        --query Plaintext > /tmp/data_key.b64

    # 2) Encrypt the secret with that data key.
    python3 - <<'PY'
    import base64
    from cryptography.fernet import Fernet
    with open('/tmp/data_key.b64') as fh:
        # `aws kms decrypt` already prints urlsafe_b64-encoded plaintext.
        # The aws_kms renderer expects the same urlsafe_b64 form as the
        # Fernet key. If your aws CLI version emits raw bytes, re-encode
        # with base64.urlsafe_b64encode().
        key = fh.read().strip().encode()
    token = Fernet(key).encrypt(b'hunter2')
    print(token.decode())
    PY

    # 3) Securely delete the plaintext key.
    shred -u /tmp/data_key.b64

The string printed by the Python block is a Fernet token. Paste it
into a pillar SLS:

.. code-block:: yaml

    #!yaml|aws_kms

    db_password: gAAAAABhA1...<token>...==

The shebang line on the first line tells Salt to run the SLS
through ``yaml``, then through ``aws_kms``, in that order. Without
the shebang the renderer is not invoked and the ciphertext is
shipped to the minion verbatim.


Step 5: verify the round trip
=============================

On the master, refresh pillar and inspect:

.. code-block:: bash

    salt 'minion-id' saltutil.refresh_pillar
    salt 'minion-id' pillar.item db_password

The minion should print the cleartext value. If you see the
ciphertext, the renderer was not invoked — re-check that the SLS
first line is ``#!yaml|aws_kms`` and that the pillar top file points
at this SLS.

Common failure modes:

* ``aws_kms:data_key is not set`` — the master config is not
  reloading the ``aws_kms`` block. Confirm the file path
  (``/etc/salt/master`` or a fragment under
  ``/etc/salt/master.d/``) and restart the master.
* ``aws_kms:data_key is not a valid KMS data key`` — the wrapped
  blob in the master config is corrupted or was generated against a
  different CMK. Re-do step 2 against the CMK whose ``kms:Decrypt``
  the master can call.
* ``boto3 could not find the "salt" profile configured in Salt`` —
  the ``profile_name`` setting points at a boto profile that does
  not exist on the master host. Either create the profile under
  ``~/.aws/credentials`` for the user running ``salt-master`` or
  drop ``profile_name`` to use the default chain (IAM role, env
  vars, ...).
* ``Boto3 was unable to determine the AWS endpoint region`` — the
  resolved profile/role has no default region. Set ``region`` in
  the profile or set ``AWS_DEFAULT_REGION`` in the master's
  environment.


Rotation
========

The wrapped data key is bound to one KMS CMK *and* one Fernet key.
To rotate:

1. Generate a new wrapped data key with ``aws kms generate-data-key``
   (step 2) — either against a new CMK or the same one.
2. Decrypt every existing ciphertext in your pillar with the *old*
   plaintext data key.
3. Re-encrypt with the *new* plaintext data key (step 4).
4. Swap the ``data_key`` value in the master config (step 3) and
   restart the master.

KMS automatic key rotation rotates the *CMK*, not your wrapped data
key — the wrapped data key still decrypts because KMS preserves the
old key version. Until you regenerate the wrapped data key the
Fernet token is the same, and an attacker who exfiltrated the
plaintext Fernet key from master memory still decrypts every
ciphertext.


What is tested
==============

The decryption codepath in ``salt/renderers/aws_kms.py`` is pinned
by ``tests/pytests/unit/renderers/test_aws_kms.py`` (mocked KMS
client). The walkthrough above is not exercised in CI end-to-end
because that would require live KMS access; the steps were last
verified manually against the version of ``aws_kms.py`` shipped in
this branch.


Cross-reference
===============

* :py:mod:`salt.renderers.aws_kms` — module docstring with config
  options.
* :py:mod:`salt.renderers.gpg` — the alternative, GPG-based pillar
  encryption renderer.
* :ref:`security-threat-model` — what encrypted pillar *does not*
  protect.
