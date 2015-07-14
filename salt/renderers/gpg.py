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

.. note::
    Unfortunately, there are some scenarios - for example, on virtual machines
    which don’t have real hardware - where insufficient entropy causes key
    generation to be extremely slow. If you come across this problem, you should
    investigate means of increasing the system entropy. On virtualised Linux
    systems, this can often be achieved by installing the rng-tools package.

To retrieve the public key:

.. code-block:: bash

    # gpg --armor --homedir /etc/salt/gpgkeys --armor --export <KEY-NAME> \
          > exported_pubkey.gpg

Now, to encrypt secrets, copy the public key to your local machine and run:

.. code-block:: bash

    $ gpg --import exported_pubkey.gpg

To generate a cipher from a secret:

.. code-block:: bash

   $ echo -n "supersecret" | gpg --homedir ~/.gnupg --armor --encrypt -r <KEY-name>

There are two ways to configure salt for the usage of this renderer:

1. Set up the renderer on your master by adding something like this line to your
    config:

        .. code-block:: yaml

            renderer: jinja | yaml | gpg

    This will apply the renderers to all pillars and states while requiring
    ``python-gnupg`` to be installed on all minions since the decryption
    will happen on the minions.

2. To apply the renderer on a file-by-file basis add the following line to the top of any pillar with gpg data in it:

    .. code-block:: yaml

        #!yaml|gpg

Now with your renderers configured, you can include your ciphers in your pillar data like so:

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

# Import python libs
from __future__ import absolute_import
import os
import re
import logging

# Import salt libs
import salt.utils
import salt.syspaths
from salt.exceptions import SaltRenderError

# Import 3rd-party libs
import salt.ext.six as six
# pylint: disable=import-error
try:
    import gnupg
    HAS_GPG = True
    if salt.utils.which('gpg') is None:
        HAS_GPG = False
except ImportError:
    HAS_GPG = False
# pylint: enable=import-error

log = logging.getLogger(__name__)

GPG_HEADER = re.compile(r'-----BEGIN PGP MESSAGE-----')
DEFAULT_GPG_KEYDIR = os.path.join(salt.syspaths.CONFIG_DIR, 'gpgkeys')


def decrypt_ciphertext(cypher, gpg, safe=False):
    '''
    Given a block of ciphertext as a string, and a gpg object, try to decrypt
    the cipher and return the decrypted string. If the cipher cannot be
    decrypted, log the error, and return the ciphertext back out.

    :param safe: Raise an exception on failure instead of returning the ciphertext
    '''
    decrypted_data = gpg.decrypt(cypher)
    if not decrypted_data.ok:
        decrypt_err = "Could not decrypt cipher {0}, received {1}".format(
                cypher, decrypted_data.stderr)
        log.error(decrypt_err)
        if safe:
            raise SaltRenderError(decrypt_err)
        else:
            return cypher
    else:
        return str(decrypted_data)


def decrypt_object(obj, gpg):
    '''
    Recursively try to decrypt any object. If the object is a string, and
    it contains a valid GPG header, decrypt it, otherwise keep going until
    a string is found.
    '''
    if isinstance(obj, str):
        if GPG_HEADER.search(obj):
            return decrypt_ciphertext(obj, gpg)
        else:
            return obj
    elif isinstance(obj, dict):
        for key, val in six.iteritems(obj):
            obj[key] = decrypt_object(val, gpg)
        return obj
    elif isinstance(obj, list):
        for n, v in enumerate(obj):
            obj[n] = decrypt_object(v, gpg)
        return obj
    else:
        return obj


def render(gpg_data, saltenv='base', sls='', argline='', **kwargs):
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
    try:
        gpg = gnupg.GPG(gnupghome=homedir)
    except TypeError:
        gpg = gnupg.GPG()
    except OSError:
        raise SaltRenderError('Cannot initialize gnupg')
    return decrypt_object(gpg_data, gpg)
