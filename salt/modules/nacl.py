# -*- coding: utf-8 -*-
'''
This module helps include encrypted passwords in pillars, grains and salt state files.

:depends: libnacl, https://github.com/saltstack/libnacl

This is often useful if you wish to store your pillars in source control or
share your pillar data with others that you trust. I don't advise making your pillars public
regardless if they are encrypted or not.

When generating keys and encrypting passwords use --local when using salt-call for extra
security. Also consider using just the salt runner nacl when encrypting pillar passwords.

:configuration: The following configuration defaults can be
    define (pillar or config files) Avoid storing private keys in pillars!:

    .. code-block:: python

        # cat /etc/salt/master.d/nacl.conf
        nacl.config:
            key: 'cKEzd4knLTIqXwnUiD1ulgXsbeCE7/4NoeeYcCFpd9k='
            keyfile: /root/.nacl
            key_pub: 'cTIqXwnUiD1ulg4kXsbeCE7/NoeKEzd4nLeYcCFpd9k='
            keyfile_pub: /root/.nacl.pub

    Usage can override the config defaults:

    .. code-block:: bash

        salt-call nacl.enc keyfile=/root/.nacl key_pub=/root/.nacl.pub


The nacl lib uses 32byte keys, these keys are base64 encoded to make your life more simple.
To generate your `key`, `keyfile` and `keyfile_pub` can use:

.. code-block:: bash

    salt-call --local nacl.keygen keyfile=/root/.nacl keyfile_pub=/root/.nacl.pub

Now with your private key, you can encrypt data:

.. code-block:: bash

    salt-call --local nacl.enc mypass keyfile=/root/.nacl
    DRB7Q6/X5gGSRCTpZyxS6hXO5LnlJIIJ4ivbmUlbWj0llUA+uaVyvou3vJ4=

To decrypt the data:

.. code-block:: bash

    salt-call --local nacl.dec data='DRB7Q6/X5gGSRCllUA+uaVyvou3vJ4=' keyfile=/root/.nacl
    mypass


When the keys are defined in the master config you can use it from the nacl runner
without including the keyfile parameters:

.. code-block:: bash

    salt-run nacl.enc 'myotherpass'
    salt-run nacl.enc_pub 'myotherpass'

SealedBox enables pub keys one way encryption.

.. code-block:: bash

    # for example on a master server
    salt-run nacl.keygen keyfile=/root/.nacl
    salt-run nacl.keygen_pub keyfile=/root/.nacl keyfile_pub=/root/.nacl.pub
    salt-run nacl.enc_pub neverhaveiever keyfile_pub=/root/.nacl.pub
    k7uLB8+XAXYK5yi8AJJk/wcmw16xqvPAq61sf5l8LlKVagELpY2NXxoJLAuBBk4=

    cat /root/.nacl.pub
    cTIqXwnUil1ulg4kXsbeCE7/NoeKEzd4nLeYcCFpd9k=

.. code-block:: yam
    # a salt developers minion could have pillar data that includes the nacl key_pub
    nacl.config:
        key_pub: 'cTIqXwnUiD1ulg4kXsbeCE7/NoeKEzd4nLeYcCFpd9k='

The developer can then use a less secure system than the master to encrypt passwords.

.. code-block:: bash

    salt-call --local nacl.enc_pub apassword


Pillar files with protected look like:

.. code-block:: jinja

    pillarexample:
        user: root
        password1: {{salt.nacl.dec('DRB7Q6/X5gGSRCTpZyxS6hlbWj0llUA+uaVyvou3vJ4=')|json}}
        password2: {{salt.nacl.dec_pub('CTpZyxS6hXO54ivbmUlbGSRlJIIJWj0llou3vJ4=')|json}}


Larger files like certificates can be encrypted with:

.. code-block:: bash

    cert=$(cat /tmp/cert.crt); salt-run nacl.enc_pub data="$cert"
    # or
    salt-run nacl.enc_pub_file /tmp/cert.crt

In Pillars be sure to include `|json` so line breaks are encoded:

.. code-block:: jinja

    cert: "{{salt.nacl.dec_pub('S2uogToXkgENz9...085KYt')|json}}"

In States also be sure to include `|json`:

.. code-block:: jinja

    {{sls}} private key:
        file.managed:
            - name: /etc/ssl/private/cert.key
            - mode: 700
            - contents: "{{salt.pillar.get('cert')|json}}"
'''

from __future__ import absolute_import
import base64
import os
import salt.utils
import salt.syspaths


REQ_ERROR = None
try:
    import libnacl.secret
    import libnacl.sealed
except (ImportError, OSError) as e:
    REQ_ERROR = 'libnacl import error, perhaps missing python libnacl package'

__virtualname__ = 'nacl'


def __virtual__():
    return (REQ_ERROR is None, REQ_ERROR)


def _get_config(**kwargs):
    '''
    Return configuration
    '''
    config = {
        'key': None,
        'keyfile': None,
        'key_pub': None,
        'keyfile_pub': None,
    }
    config_key = '{0}.config'.format(__virtualname__)
    try:
        config.update(__salt__['config.get'](config_key, {}))
    except (NameError, KeyError) as e:
        # likly using salt-run so fallback to __opts__
        config.update(__opts__.get(config_key, {}))
    # pylint: disable=C0201
    for k in set(config.keys()) & set(kwargs.keys()):
        config[k] = kwargs[k]
    return config


def _get_key(rstrip_newline=True, **kwargs):
    '''
    Return key
    '''
    config = _get_config(**kwargs)
    key = config['key']
    keyfile = config['keyfile']
    if not key and keyfile:
        with salt.utils.fopen(keyfile, 'rb') as keyf:
            key = keyf.read()
    if key is None:
        raise Exception('no key or keyfile found')
    key = str(key)
    if rstrip_newline:
        key = key.rstrip('\n')
    return key


def _get_key_pub(rstrip_newline=True, **kwargs):
    '''
    Return key pub
    '''
    config = _get_config(**kwargs)
    key_pub = config['key_pub']
    keyfile_pub = config['keyfile_pub']
    if not key_pub and keyfile_pub:
        with salt.utils.fopen(keyfile_pub, 'rb') as keyf:
            key_pub = keyf.read()
    if key_pub is None:
        raise Exception('no key_pub or keyfile_pub found')
    key_pub = str(key_pub)
    if rstrip_newline:
        key_pub = key_pub.rstrip('\n')
    return key_pub


def keygen(keyfile=None, keyfile_pub=None):
    '''
    Use libnacl to generate a private key.

    If both keyfile and keyfile_pub are defined.
    This function will generate a keypair.

    CLI Examples:

    .. code-block:: bash

        salt-call nacl.keygen
        salt-call nacl.keygen keyfile=/root/.nacl
        salt-call nacl.keygen keyfile=/root/.nacl keyfile_pub=/root/.nacl.pub
        salt-call --local --out=newline_values_only nacl.keygen > /root/.nacl
    '''
    b = libnacl.secret.SecretBox()
    key = b.sk
    key = base64.b64encode(key)
    if keyfile:
        if os.path.isfile(keyfile):
            raise Exception('file already found: {0}'.format(keyfile))
        with salt.utils.fopen(keyfile, 'w') as keyf:
            keyf.write(key)
        if keyfile_pub:
            ret = keygen_pub(keyfile_pub=keyfile_pub, keyfile=keyfile)
            return 'saved: {0} and {1}'.format(keyfile, ret)
        return 'saved: {0}'.format(keyfile)
    return key


def keygen_pub(keyfile_pub=None, **kwargs):
    '''
    Generate a public key from a private key created using `nacl.keygen`.
    The public key can be used with `nacl.enc_pub` to encrypt but not decrypt.

    CLI Examples:

    .. code-block:: bash

        salt-call nacl.keygen_pub
        salt-call nacl.keygen_pub key="YmFkcGFzcwo="
        salt-call nacl.keygen_pub keyfile=/root/.nacl  keyfile_pub=/root/.nacl.pub
        salt-call --local --out=newline_values_only nacl.keygen_pub > /root/.nacl.pub
    '''
    key = _get_key(**kwargs)
    sk = base64.b64decode(key)
    b = libnacl.public.SecretKey(sk)
    key = b.pk
    key = base64.b64encode(key)
    if keyfile_pub:
        if os.path.isfile(keyfile_pub):
            raise Exception('file already found: {0}'.format(keyfile_pub))
        with salt.utils.fopen(keyfile_pub, 'w') as keyf:
            keyf.write(key)
            return 'saved: {0}'.format(keyfile_pub)
    return key


def enc_pub(data, **kwargs):
    '''
    Encrypt data using a public key generated from `nacl.keygen_pub`.
    The encryptd data can be decrypted using `nacl.dec_pub` with the private key.

    CLI Examples:

    .. code-block:: bash

        salt-call nacl.enc_pub datatoenc
        salt-call --local nacl.enc_pub datatoenc keyfile_pub=/root/.nacl.pub
        salt-call --local nacl.enc_pub datatoenc key_pub='vrwQF7cNiNAVQVAiS3bvcbJUnF0cN6fU9YTZD9mBfzQ='
    '''
    key = _get_key_pub(**kwargs)
    pk = base64.b64decode(key)
    b = libnacl.sealed.SealedBox(pk)
    return base64.b64encode(b.encrypt(data))


def enc_pub_file(name, **kwargs):
    '''
    This is a helper function for `enc_pub` to encrypt a file.

    CLI Examples:

    .. code-block:: bash

        salt-call --local nacl.enc_pub_file name="/tmp/id_rsa" \
            keyfile_pub=/root/.nacl.pub \
            > /tmp/id_rsa.enc
    '''
    data = None
    with salt.utils.fopen(name, 'rb') as f:
        data = f.read()
    return enc_pub(data, **kwargs)


def dec_pub(data, **kwargs):
    '''
    Decrypt data that was encrypted using `nacl.enc_pub` using a

    CLI Examples:

    .. code-block:: bash

        salt-call nacl.dec_pub pEXHQM6cuaF7A=
        salt-call --local nacl.dec_pub data='pEXHQM6cuaF7A=' keyfile=/root/.nacl
        salt-call --local nacl.dec_pub data='pEXHQM6cuaF7A=' key='YmFkcGFzcwo='
    '''
    key = _get_key(**kwargs)
    sk = base64.b64decode(key)
    keypair = libnacl.public.SecretKey(sk)
    b = libnacl.sealed.SealedBox(keypair)
    return b.decrypt(base64.b64decode(data))


def dec_pub_file(name, **kwargs):
    '''
    This is a helper function for `dec_pub` to decrypt a file.

    CLI Examples:

    .. code-block:: bash

        salt-call nacl.dec_pub_file name="/tmp/id_rsa.enc" \
            keyfile=/root/.nacl \
            > /tmp/id_rsa
    '''
    data = None
    with salt.utils.fopen(name, 'rb') as f:
        data = f.read()
    return dec_pub(data, **kwargs)


def enc(data, **kwargs):
    '''
    Encrypt data using a key generated from `nacl.keygen`.
    The same key can be used to decrypt the data!

    CLI Examples:

    .. code-block:: bash

        salt-call nacl.enc datatoenc
        salt-call --local nacl.enc datatoenc keyfile=/root/.nacl
        salt-call --local nacl.enc datatoenc key='YmFkcGFzcwo='
    '''
    key = _get_key(**kwargs)
    sk = base64.b64decode(key)
    b = libnacl.secret.SecretBox(sk)
    return base64.b64encode(b.encrypt(data))


def dec(data, **kwargs):
    '''
    Decrypt data that was encrypted using `nacl.enc` using the key
    that was generated from `nacl.keygen`.

    CLI Examples:

    .. code-block:: bash

        salt-call nacl.dec pEXHQM6cuaF7A=
        salt-call --local nacl.dec data='pEXHQM6cuaF7A=' keyfile=/root/.nacl
        salt-call --local nacl.dec data='pEXHQM6cuaF7A=' key='YmFkcGFzcwo='
    '''
    if data == None:
      return None
    key = _get_key(**kwargs)
    sk = base64.b64decode(key)
    b = libnacl.secret.SecretBox(key=sk)
    return b.decrypt(base64.b64decode(data))

