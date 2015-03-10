# -*- coding: utf-8 -*-
'''
Renderer that will decrypt GPG ciphers

Any key in the SLS file can be a GPG cipher, and this renderer will decrypt
it before passing it off to Salt. This allows you to safely store secrets in
source control, in such a way that only your Salt master can decrypt them and
distribute them only to the minions that need them.

The typical use-case would be to use ciphers in your pillar data, and keep a
secret key on your master. You can put the public key in source control so that
developers can add new secrets quickly and easily.

This renderer requires the python-gnupg package. Be careful to install the
``python-gnupg`` package, not the ``gnupg`` package, or you will get errors.

To set things up, you will first need to generate a keypair. On your master,
run:

.. code-block:: bash

    # gpg --gen-key --homedir /etc/salt/gpgkeys

Do not supply a password for your keypair, and use a name that makes sense
for your application. Be sure to back up your gpg directory someplace safe!

To retrieve the public key:

.. code-block:: bash

    # gpg --armor --homedir /etc/salt/gpgkeys --armor --export <KEY-NAME> \
          > exported_pubkey.gpg

Now, to encrypt secrets, copy the public key to your local machine and run:

.. code-block:: bash

    $ gpg --import exported_pubkey.gpg

To generate a cipher from a secret:

.. code-block:: bash

   $ echo -n"supersecret" | gpg --homedir --armor --encrypt -r <KEY-name>

Set up the renderer on your master by adding something like this line to your
config:

.. code-block:: yaml

    renderer: jinja | yaml | gpg

Now you can include your ciphers in your pillar data like so:

.. code-block:: yaml

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

import os
import re
import salt.utils
import salt.syspaths
try:
    import gnupg
    HAS_GPG = True
    if salt.utils.which('gpg') is None:
        HAS_GPG = False
except ImportError:
    HAS_GPG = False
import logging

from salt.exceptions import SaltRenderError

log = logging.getLogger(__name__)
GPG_HEADER = re.compile(r'-----BEGIN PGP MESSAGE-----')
DEFAULT_GPG_KEYDIR = os.path.join(salt.syspaths.CONFIG_DIR, 'gpgkeys')


def decrypt_ciphertext(c, gpg):
    '''
    Given a block of ciphertext as a string, and a gpg object, try to decrypt
    the cipher and return the decrypted string. If the cipher cannot be
    decrypted, log the error, and return the ciphertext back out.
    '''
    decrypted_data = gpg.decrypt(c)
    if not decrypted_data.ok:
        log.info("Could not decrypt cipher {0}, received {1}".format(
            c, decrypted_data.stderr))
        return c
    else:
        return str(decrypted_data)


def decrypt_object(o, gpg):
    '''
    Recursively try to decrypt any object. If the object is a string, and
    it contains a valid GPG header, decrypt it, otherwise keep going until
    a string is found.
    '''
    if isinstance(o, str):
        if GPG_HEADER.search(o):
            return decrypt_ciphertext(o, gpg)
        else:
            return o
    elif isinstance(o, dict):
        for k, v in o.items():
            o[k] = decrypt_object(v, gpg)
        return o
    elif isinstance(o, list):
        for number, value in enumerate(o):
            o[number] = decrypt_object(value, gpg)
        return o
    else:
        return o


def render(data, saltenv='base', sls='', argline='', **kwargs):
    '''
    Create a gpg object given a gpg_keydir, and then use it to try to decrypt
    the data to be rendered.
    '''
    if not HAS_GPG:
        raise SaltRenderError('GPG unavailable')
    if 'config.get' in __salt__:
        homedir = __salt__['config.get']('gpg_keydir', DEFAULT_GPG_KEYDIR)
    else:
        homedir = __opts__.get('gpg_keydir', DEFAULT_GPG_KEYDIR)
    log.debug('Reading GPG keys from: {0}'.format(homedir))
    gpg = gnupg.GPG(gnupghome=homedir)
    return decrypt_object(data, gpg)
