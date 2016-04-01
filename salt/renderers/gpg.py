# -*- coding: utf-8 -*-
'''
Renderer that will decrypt GPG ciphers

Any key in the SLS file can be a GPG cipher, and this renderer will decrypt it
before passing it off to Salt. This allows you to safely store secrets in
source control, in such a way that only your Salt master can decrypt them and
distribute them only to the minions that need them.

The typical use-case would be to use ciphers in your pillar data, and keep a
secret key on your master. You can put the public key in source control so that
developers can add new secrets quickly and easily.

This renderer requires the gpg binary.

**No python libraries are required as of the 2015.8.3 release.**

To set things up, you will first need to generate a keypair. On your master,
run:

.. code-block:: shell

    # mkdir -p /etc/salt/gpgkeys
    # chmod 0700 /etc/salt/gpgkeys
    # gpg --gen-key --homedir /etc/salt/gpgkeys

Do not supply a password for your keypair, and use a name that makes sense
for your application. Be sure to back up your gpg directory someplace safe!

.. note::
    Unfortunately, there are some scenarios - for example, on virtual machines
    which don’t have real hardware - where insufficient entropy causes key
    generation to be extremely slow. If you come across this problem, you should
    investigate means of increasing the system entropy. On virtualised Linux
    systems, this can often be achieved by installing the rng-tools package.

To retrieve the public key:

.. code-block:: shell

    # gpg --homedir /etc/salt/gpgkeys --armor --export <KEY-NAME> \
        > exported_pubkey.gpg

Now, to encrypt secrets, copy the public key to your local machine and run:

.. code-block:: shell

    $ gpg --import exported_pubkey.gpg

To generate a cipher from a secret:

.. code-block:: shell

   $ echo -n "supersecret" | gpg --armor --encrypt -r <KEY-name>

To apply the renderer on a file-by-file basis add the following line to the
top of any pillar with gpg data in it:

    .. code-block:: yaml

        #!yaml|gpg

Now with your renderer configured, you can include your ciphers in your pillar data like so:

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
      skqmFTbOiA==
      =Eqsm
      -----END PGP MESSAGE-----
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

if salt.utils.which('gpg'):
    HAS_GPG = True
else:
    HAS_GPG = False
    raise SaltRenderError('GPG unavailable')

LOG = logging.getLogger(__name__)

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
    if __salt__['config.get']('gpg_keydir'):
        return __salt__['config.get']('gpg_keydir')
    else:
        return os.path.join(salt.syspaths.CONFIG_DIR, 'gpgkeys')


def _decrypt_ciphertext(cipher):
    '''
    Given a block of ciphertext as a string, and a gpg object, try to decrypt
    the cipher and return the decrypted string. If the cipher cannot be
    decrypted, log the error, and return the ciphertext back out.
    '''
    cmd = [_get_gpg_exec(), '--homedir', _get_key_dir(), '-d']
    proc = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=False)
    decrypted_data, decrypt_error = proc.communicate(input=cipher)
    if not decrypted_data:
        LOG.error('Could not decrypt cipher %s, received: %s', cipher, decrypt_error)
        return cipher
    else:
        return str(decrypted_data)


def _decrypt_object(obj):
    '''
    Recursively try to decrypt any object. If the object is a string, and
    it contains a valid GPG header, decrypt it, otherwise keep going until
    a string is found.
    '''
    if isinstance(obj, str):
        if GPG_HEADER.search(obj):
            return _decrypt_ciphertext(obj)
        else:
            return obj
    elif isinstance(obj, dict):
        for key, val in six.iteritems(obj):
            obj[key] = _decrypt_object(val)
        return obj
    elif isinstance(obj, list):
        for key, value in enumerate(obj):
            obj[key] = _decrypt_object(value)
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
    LOG.debug('Reading GPG keys from: %s', _get_key_dir())

    return _decrypt_object(gpg_data)
