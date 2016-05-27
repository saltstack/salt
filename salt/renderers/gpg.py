# -*- coding: utf-8 -*-
r'''
Renderer that will decrypt GPG ciphers

Any key in the SLS file can be a GPG cipher, and this renderer will decrypt it
before passing it off to Salt. This allows you to safely store secrets in
source control, in such a way that only your Salt master can decrypt them and
distribute them only to the minions that need them.

The typical use-case would be to use ciphers in your pillar data, and keep a
secret key on your master. You can put the public key in source control so that
developers can add new secrets quickly and easily.

This renderer requires the gpg_ binary. No python libraries are required as of
the 2015.8.0 release.

.. _gpg: https://gnupg.org

Setup
-----

To set things up, first generate a keypair. On the master, run the following:

.. code-block:: bash

    # mkdir -p /etc/salt/gpgkeys
    # chmod 0700 /etc/salt/gpgkeys
    # gpg --gen-key --homedir /etc/salt/gpgkeys

Do not supply a password for the keypair, and use a name that makes sense for
your application. Be sure to back up the ``gpgkeys`` directory someplace safe!

.. note::
    Unfortunately, there are some scenarios - for example, on virtual machines
    which don’t have real hardware - where insufficient entropy causes key
    generation to be extremely slow. In these cases, there are usually means of
    increasing the system entropy. On virtualised Linux systems, this can often
    be achieved by installing the ``rng-tools`` package.


Export the Public Key
---------------------

.. code-block:: bash

    # gpg --homedir /etc/salt/gpgkeys --armor --export <KEY-NAME> > exported_pubkey.gpg


Import the Public Key
---------------------

To encrypt secrets, copy the public key to your local machine and run:

.. code-block:: bash

    $ gpg --import exported_pubkey.gpg

To generate a cipher from a secret:

.. code-block:: bash

   $ echo -n "supersecret" | gpg --armor --batch --trust-model always --encrypt -r <KEY-name>

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
'''

# Import python libs
from __future__ import absolute_import
import os
import re
import logging
from subprocess import Popen, PIPE

# Import salt libs
import salt.utils
import salt.syspaths
from salt.exceptions import SaltRenderError

# Import 3rd-party libs
import salt.ext.six as six


log = logging.getLogger(__name__)

GPG_HEADER = re.compile(r'-----BEGIN PGP MESSAGE-----')


def _get_gpg_exec():
    '''
    return the GPG executable or raise an error
    '''
    gpg_exec = salt.utils.which('gpg')
    if gpg_exec:
        return gpg_exec
    else:
        raise SaltRenderError('GPG unavailable')


def _get_key_dir():
    '''
    return the location of the GPG key directory
    '''
    if 'config.get' in __salt__:
        gpg_keydir = __salt__['config.get']('gpg_keydir')
    else:
        gpg_keydir = __opts__.get('gpg_keydir')
    return gpg_keydir or os.path.join(salt.syspaths.CONFIG_DIR, 'gpgkeys')


def _decrypt_ciphertext(cipher, translate_newlines=False):
    '''
    Given a block of ciphertext as a string, and a gpg object, try to decrypt
    the cipher and return the decrypted string. If the cipher cannot be
    decrypted, log the error, and return the ciphertext back out.
    '''
    cmd = [_get_gpg_exec(), '--homedir', _get_key_dir(), '-d']
    proc = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=False)
    decrypted_data, decrypt_error = proc.communicate(
        input=cipher.replace(r'\n', '\n') if translate_newlines else cipher
    )
    if not decrypted_data:
        log.warning(
            'Could not decrypt cipher %s, received: %s',
            cipher,
            decrypt_error
        )
        return cipher
    else:
        return str(decrypted_data)


def _decrypt_object(obj, translate_newlines=False):
    '''
    Recursively try to decrypt any object. If the object is a six.string_types
    (string or unicode), and it contains a valid GPG header, decrypt it,
    otherwise keep going until a string is found.
    '''
    if isinstance(obj, six.string_types):
        if GPG_HEADER.search(obj):
            return _decrypt_ciphertext(obj,
                                       translate_newlines=translate_newlines)
        else:
            return obj
    elif isinstance(obj, dict):
        for key, value in six.iteritems(obj):
            obj[key] = _decrypt_object(value,
                                       translate_newlines=translate_newlines)
        return obj
    elif isinstance(obj, list):
        for key, value in enumerate(obj):
            obj[key] = _decrypt_object(value,
                                       translate_newlines=translate_newlines)
        return obj
    else:
        return obj


def render(gpg_data, saltenv='base', sls='', argline='', **kwargs):
    '''
    Create a gpg object given a gpg_keydir, and then use it to try to decrypt
    the data to be rendered.
    '''
    if not _get_gpg_exec():
        raise SaltRenderError('GPG unavailable')
    log.debug('Reading GPG keys from: %s', _get_key_dir())

    translate_newlines = kwargs.get('translate_newlines', False)
    return _decrypt_object(gpg_data, translate_newlines=translate_newlines)
