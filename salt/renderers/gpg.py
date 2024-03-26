r"""
Renderer that will decrypt GPG ciphers

Any value in the SLS file can be a GPG cipher, and this renderer will decrypt it
before passing it off to Salt. This allows you to safely store secrets in
source control, in such a way that only your Salt master can decrypt them and
distribute them only to the minions that need them.

The typical use-case would be to use ciphers in your pillar data, and keep a
secret key on your master. You can put the public key in source control so that
developers can add new secrets quickly and easily.

This renderer requires the gpg_ binary. No python libraries are required as of
the 2015.8.0 release.

.. _gpg-homedir:

GPG Homedir
-----------

The default `GPG Homedir <gpg-homedir>` is ``~/.gnupg`` and needs to be set using
``gpg --homedir``. Be very careful to not forget this option. It is also important
to run ``gpg`` commands as the user that owns the keys directory. If the salt-master
runs as user ``salt``, then use ``su - salt`` before running any gpg commands.

In some cases, it's preferable to have gpg keys stored on removable media or
other non-standard locations. This can be done using the ``gpg_keydir`` option
on the salt master. This will also require using a different path to ``--homedir``.

The ``--homedir`` argument can be configured for the current user using
``echo 'homedir /etc/salt/gpgkeys' >> ~/.gnupg``, but this should be used with
caution to avoid potential confusion.

.. code-block:: bash

    gpg_keydir: <path/to/homedir>

.. _gpg: https://gnupg.org

GPG Keys
--------

GPG key pairs include both a public and private key. The private key is akin to
a password and should be kept secure by the owner. A public key is used to
encrypt data being sent to the owner of the private key.

This means that the public key will be freely distributed so that others can
encrypt pillar data without access to the secret key.

New Key Pair
************

To create a new GPG key pair for encrypting data, log in to the master as root
and run the following:

.. code-block:: bash

    # mkdir -p /etc/salt/gpgkeys
    # chmod 0700 /etc/salt/gpgkeys
    # gpg --homedir /etc/salt/gpgkeys --gen-key

Do not supply a password for the keypair and use a name that makes sense for
your application.

.. note::
    In some situations, gpg may be starved of entropy and will take an incredibly
    long time to finish. Two common tools to generate (less secure) pseudo-random
    data are ``rng-tools`` and ``haveged``.

The new keys can be seen and verified using ``--list-secret-keys``:

.. code-block:: bash

    # gpg --homedir /etc/salt/gpgkeys --list-secret-keys
    /etc/salt/gpgkeys/pubring.kbx
    -----------------------------
    sec   rsa4096 2002-05-12 [SC] [expires: 2012-05-10]
          2DC47B416EE8C3484450B450A4D44406274AF44E
    uid           [ultimate] salt-master (gpg key for salt) <salt@cm.domain.tld>
    ssb   rsa4096 2002-05-12 [E] [expires: 2012-05-10]

In the example above, our KEY-ID is ``2DC47B416EE8C3484450B450A4D44406274AF44E``.

Export Public Key
*****************

To export a public key suitable for public distribution:

.. code-block:: bash

    # gpg --homedir /etc/salt/gpgkeys --armor --export <KEY-ID> > exported_pubkey.asc

.. _gpg-importpubkey:

Import Public Key
*****************

Users wishing to import the public key into their local keychain may run:

.. code-block:: bash

    $ gpg --import exported_pubkey.asc

Export (Save) Private Key
*************************

This key protects all gpg-encrypted pillar data and should be backed up to a
safe and secure location. This command will generate a backup of secret keys
in the ``/etc/salt/gpgkeys`` directory to the ``gpgkeys.secret`` file:

.. code-block:: bash

    # gpg --homedir /etc/salt/gpgkeys --export-secret-keys --export-options export-backup -o gpgkeys.secret

Salt does not support password-protected private keys, which means this file
is essentially a clear-text password (just add ``--armor``). Fortunately, it
is trivial to pass this export back to gpg to be encrypted with symmetric key:

.. code-block:: bash

    # gpg --homedir /etc/salt/gpgkeys --export-secret-keys --export-options export-backup | gpg --symmetric -o gpgkeys.gpg

.. note::
    In some cases, particularly when using su/sudo, gpg gets confused and needs
    to be told which TTY to use; this can be done with: ``export GPG_TTY=$(tty)``.

Import (Restore) Private Key
****************************

To import/restore a private key, create a directory with the correct permissions
and import using gpg.

.. code-block:: bash

    # mkdir -p /etc/salt/gpgkeys
    # chmod 0700 /etc/salt/gpgkeys
    # gpg --homedir /etc/salt/gpgkeys --import gpgkeys.secret

If the export was encrypted using a symmetric key, then decrypt first with:

.. code-block:: bash

    # gpg --decrypt gpgkeys.gpg | gpg --homedir /etc/salt/gpgkeys --import


Adjust trust level of imported keys
***********************************

In some cases, importing existing keys may not be enough and the trust level of
the key needs to be adjusted. This can be done by editing the key. The ``KEY-ID``
and the actual trust level of the key can be seen by listing the already imported
keys.


If the trust-level is not ``ultimate`` it needs to be changed by running

.. code-block:: bash

    gpg --homedir /etc/salt/gpgkeys --edit-key <KEY-ID>

This will open an interactive shell for the management of the GPG encryption key.
Type ``trust`` to be able to set the trust level for the key and then select ``5
(I trust ultimately)``. Then quit the shell by typing ``save``.

Encrypting Data
---------------

In order to encrypt data to a recipient (salt), the public key must be imported
into the local keyring. Importing the public key is described above in the
`Import Public Key <gpg-importpubkey:>` section.

To generate a cipher from a secret:

.. code-block:: bash

   $ echo -n 'supersecret' | gpg --trust-model always -ear <KEY-ID>

To apply the renderer on a file-by-file basis add the following line to the
top of any pillar with gpg data in it:

.. code-block:: yaml

    #!yaml|gpg

Now with your renderer configured, you can include your ciphers in your pillar
data like so:

.. code-block:: yaml

    #!yaml|gpg

    a-secret: |
      -----BEGIN PGP MESSAGE-----
      Version: GnuPG v1

      hQEMAweRHKaPCfNeAQf9GLTN16hCfXAbPwU6BbBK0unOc7i9/etGuVc5CyU9Q6um
      QuetdvQVLFO/HkrC4lgeNQdM6D9E8PKonMlgJPyUvC8ggxhj0/IPFEKmrsnv2k6+
      cnEfmVexS7o/U1VOVjoyUeliMCJlAz/30RXaME49Cpi6No2+vKD8a4q4nZN1UZcG
      RhkhC0S22zNxOXQ38TBkmtJcqxnqT6YWKTUsjVubW3bVC+u2HGqJHu79wmwuN8tz
      m4wBkfCAd8Eyo2jEnWQcM4TcXiF01XPL4z4g1/9AAxh+Q4d8RIRP4fbw7ct4nCJv
      Gr9v2DTF7HNigIMl4ivMIn9fp+EZurJNiQskLgNbktJGAeEKYkqX5iCuB1b693hJ
      FKlwHiJt5yA8X2dDtfk8/Ph1Jx2TwGS+lGjlZaNqp3R1xuAZzXzZMLyZDe5+i3RJ
      skqmFTbOiA===Eqsm
      -----END PGP MESSAGE-----

.. _encrypted-cli-pillar-data:

Encrypted CLI Pillar Data
-------------------------

.. versionadded:: 2016.3.0

Functions like :py:func:`state.highstate <salt.modules.state.highstate>` and
:py:func:`state.sls <salt.modules.state.sls>` allow for pillar data to be
passed on the CLI.

.. code-block:: bash

    salt myminion state.highstate pillar="{'mypillar': 'foo'}"

Starting with the 2016.3.0 release of Salt, it is now possible for this pillar
data to be GPG-encrypted, and to use the GPG renderer to decrypt it.

Replacing Newlines
******************

To pass encrypted pillar data on the CLI, the ciphertext must have its newlines
replaced with a literal backslash-n (``\n``), as newlines are not supported
within Salt CLI arguments. There are a number of ways to do this:

With awk or Perl:

.. code-block:: bash

    # awk
    ciphertext=`echo -n "supersecret" | gpg --armor --batch --trust-model always --encrypt -r user@domain.com | awk '{printf "%s\\n",$0} END {print ""}'`
    # Perl
    ciphertext=`echo -n "supersecret" | gpg --armor --batch --trust-model always --encrypt -r user@domain.com | perl -pe 's/\n/\\n/g'`

With Python:

.. code-block:: python

    import subprocess

    secret, stderr = subprocess.Popen(
        ['gpg', '--armor', '--batch', '--trust-model', 'always', '--encrypt',
         '-r', 'user@domain.com'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE).communicate(input='supersecret')

    if secret:
        print(secret.replace('\n', r'\n'))
    else:
        raise ValueError('No ciphertext found: {0}'.format(stderr))

.. code-block:: bash

    ciphertext=`python /path/to/script.py`


The ciphertext can be included in the CLI pillar data like so:

.. code-block:: bash

    salt myminion state.sls secretstuff pillar_enc=gpg pillar="{secret_pillar: '$ciphertext'}"

The ``pillar_enc=gpg`` argument tells Salt that there is GPG-encrypted pillar
data, so that the CLI pillar data is passed through the GPG renderer, which
will iterate recursively though the CLI pillar dictionary to decrypt any
encrypted values.


Encrypting the Entire CLI Pillar Dictionary
*******************************************

If several values need to be encrypted, it may be more convenient to encrypt
the entire CLI pillar dictionary. Again, this can be done in several ways:

With awk or Perl:

.. code-block:: bash

    # awk
    ciphertext=`echo -n "{'secret_a': 'CorrectHorseBatteryStaple', 'secret_b': 'GPG is fun!'}" | gpg --armor --batch --trust-model always --encrypt -r user@domain.com | awk '{printf "%s\\n",$0} END {print ""}'`
    # Perl
    ciphertext=`echo -n "{'secret_a': 'CorrectHorseBatteryStaple', 'secret_b': 'GPG is fun!'}" | gpg --armor --batch --trust-model always --encrypt -r user@domain.com | perl -pe 's/\n/\\n/g'`

With Python:

.. code-block:: python

    import subprocess

    pillar_data = {'secret_a': 'CorrectHorseBatteryStaple',
                   'secret_b': 'GPG is fun!'}

    secret, stderr = subprocess.Popen(
        ['gpg', '--armor', '--batch', '--trust-model', 'always', '--encrypt',
         '-r', 'user@domain.com'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE).communicate(input=repr(pillar_data))

    if secret:
        print(secret.replace('\n', r'\n'))
    else:
        raise ValueError('No ciphertext found: {0}'.format(stderr))

.. code-block:: bash

    ciphertext=`python /path/to/script.py`

With the entire pillar dictionary now encrypted, it can be included in the CLI
pillar data like so:

.. code-block:: bash

    salt myminion state.sls secretstuff pillar_enc=gpg pillar="$ciphertext"

Configuration
*************

The default behaviour of this renderer is to log a warning if a block could not
be decrypted; in other words, it just returns the ciphertext rather than the
encrypted secret.

This behaviour can be changed via the `gpg_decrypt_must_succeed` configuration
option.  If set to `True`, any gpg block that cannot be decrypted raises a
`SaltRenderError` exception, which registers an error in ``_errors`` during
rendering.

In the Chlorine release, the default behavior will be reversed and an error
message will be added to ``_errors`` by default.
"""

import logging
import os
import re
from subprocess import PIPE, Popen

import salt.syspaths
import salt.utils.cache
import salt.utils.path
import salt.utils.stringio
import salt.utils.stringutils
import salt.utils.versions
from salt.exceptions import SaltRenderError

log = logging.getLogger(__name__)

GPG_CIPHERTEXT = re.compile(
    salt.utils.stringutils.to_bytes(
        r"-----BEGIN PGP MESSAGE-----.*?-----END PGP MESSAGE-----"
    ),
    re.DOTALL,
)
GPG_CACHE = None


def _get_gpg_exec():
    """
    return the GPG executable or raise an error
    """
    gpg_exec = salt.utils.path.which("gpg")
    if gpg_exec:
        return gpg_exec
    else:
        raise SaltRenderError("GPG unavailable")


def _get_key_dir():
    """
    return the location of the GPG key directory
    """
    gpg_keydir = None
    if "config.get" in __salt__:
        gpg_keydir = __salt__["config.get"]("gpg_keydir")

    if not gpg_keydir:
        gpg_keydir = __opts__.get(
            "gpg_keydir",
            os.path.join(
                __opts__.get("config_dir", os.path.dirname(__opts__["conf_file"])),
                "gpgkeys",
            ),
        )

    return gpg_keydir


def _get_cache():
    global GPG_CACHE
    if not GPG_CACHE:
        cachedir = __opts__.get("cachedir")
        GPG_CACHE = salt.utils.cache.CacheFactory.factory(
            __opts__.get("gpg_cache_backend"),
            __opts__.get("gpg_cache_ttl"),
            minion_cache_path=os.path.join(cachedir, "gpg_cache"),
        )
    return GPG_CACHE


def _decrypt_ciphertext(cipher):
    """
    Given a block of ciphertext as a string, and a gpg object, try to decrypt
    the cipher and return the decrypted string. If the cipher cannot be
    decrypted, log the error, and return the ciphertext back out.
    """
    try:
        cipher = salt.utils.stringutils.to_unicode(cipher).replace(r"\n", "\n")
    except UnicodeDecodeError:
        # ciphertext is binary
        pass
    cipher = salt.utils.stringutils.to_bytes(cipher)
    if __opts__.get("gpg_cache"):
        cache = _get_cache()
        if cipher in cache:
            return cache[cipher]
    cmd = [
        _get_gpg_exec(),
        "--homedir",
        _get_key_dir(),
        "--status-fd",
        "2",
        "--no-tty",
        "-d",
    ]
    proc = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=False)
    decrypted_data, decrypt_error = proc.communicate(input=cipher)
    if not decrypted_data:
        log.warning("Could not decrypt cipher %r, received: %r", cipher, decrypt_error)
        if __opts__["gpg_decrypt_must_succeed"]:
            raise SaltRenderError(
                "Could not decrypt cipher {!r}, received: {!r}".format(
                    cipher,
                    decrypt_error,
                )
            )
        else:
            salt.utils.versions.warn_until(
                "Chlorine",
                "After the Chlorine release of Salt, gpg_decrypt_must_succeed will default to True.",
            )
        return cipher
    else:
        if __opts__.get("gpg_cache"):
            cache[cipher] = decrypted_data
        return decrypted_data


def _decrypt_ciphertexts(cipher, translate_newlines=False, encoding=None):
    to_bytes = salt.utils.stringutils.to_bytes
    cipher = to_bytes(cipher)
    if translate_newlines:
        cipher = cipher.replace(to_bytes(r"\n"), to_bytes("\n"))

    def replace(match):
        result = to_bytes(_decrypt_ciphertext(match.group()))
        return result

    ret, num = GPG_CIPHERTEXT.subn(replace, to_bytes(cipher))
    if num > 0:
        # Remove trailing newlines. Without if crypted value initially specified as a YAML multiline
        # it will conain unexpected trailing newline.
        ret = ret.rstrip(b"\n")
    else:
        ret = cipher

    try:
        ret = salt.utils.stringutils.to_unicode(ret, encoding=encoding)
    except UnicodeDecodeError:
        # decrypted data contains some sort of binary data - not our problem
        pass
    return ret


def _decrypt_object(obj, translate_newlines=False, encoding=None):
    """
    Recursively try to decrypt any object. If the object is a string
    or bytes and it contains a valid GPG header, decrypt it,
    otherwise keep going until a string is found.
    """
    if salt.utils.stringio.is_readable(obj):
        return _decrypt_object(obj.getvalue(), translate_newlines)
    if isinstance(obj, (str, bytes)):
        return _decrypt_ciphertexts(
            obj, translate_newlines=translate_newlines, encoding=encoding
        )
    elif isinstance(obj, dict):
        for key, value in obj.items():
            obj[key] = _decrypt_object(value, translate_newlines=translate_newlines)
        return obj
    elif isinstance(obj, list):
        for key, value in enumerate(obj):
            obj[key] = _decrypt_object(value, translate_newlines=translate_newlines)
        return obj
    else:
        return obj


def render(gpg_data, saltenv="base", sls="", argline="", **kwargs):
    """
    Create a gpg object given a gpg_keydir, and then use it to try to decrypt
    the data to be rendered.
    """
    if not _get_gpg_exec():
        raise SaltRenderError("GPG unavailable")
    log.debug("Reading GPG keys from: %s", _get_key_dir())

    translate_newlines = kwargs.get("translate_newlines", False)
    return _decrypt_object(
        gpg_data,
        translate_newlines=translate_newlines,
        encoding=kwargs.get("encoding", None),
    )
