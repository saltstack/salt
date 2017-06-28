# -*- coding: utf-8 -*-
'''
This runner helps create encrypted passwords that can be included in pillars.

:depends: libnacl, https://github.com/saltstack/libnacl

This is often useful if you wish to store your pillars in source control or
share your pillar data with others that you trust. I don't advise making your pillars public
regardless if they are encrypted or not.

The following configurations can be defined in the master config
so your users can create encrypted passwords using the runner nacl:

.. code-block:: bash

    cat /etc/salt/master.d/nacl.conf
    nacl.config:
        key: 'cKEzd4kXsbeCE7/nLTIqXwnUiD1ulg4NoeeYcCFpd9k='
        keyfile: /root/.nacl

Now with the config in the master you can use the runner nacl like:

.. code-block:: bash

    salt-run nacl.enc 'data'
'''

from __future__ import absolute_import
import base64
import os
import salt.utils
import salt.syspaths


REQ_ERROR = None
try:
    import libnacl.secret
except ImportError as e:
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
    }
    config_key = '{0}.config'.format(__virtualname__)
    config.update(__opts__.get(config_key, {}))
    for k in set(config) & set(kwargs):
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
        if not os.path.isfile(keyfile):
            raise Exception('file not found: {0}'.format(keyfile))
        with salt.utils.fopen(keyfile, 'rb') as keyf:
            key = keyf.read()
    if key is None:
        raise Exception('no key found')
    key = str(key)
    if rstrip_newline:
        key = key.rstrip('\n')
    return key


def keygen(keyfile=None):
    '''
    Use libnacl to generate a private key

    CLI Examples:

    .. code-block:: bash

        salt-run nacl.keygen
        salt-run nacl.keygen keyfile=/root/.nacl
        salt-run --out=newline_values_only nacl.keygen > /root/.nacl
    '''
    b = libnacl.secret.SecretBox()
    key = b.sk
    key = base64.b64encode(key)
    if keyfile:
        if os.path.isfile(keyfile):
            raise Exception('file already found: {0}'.format(keyfile))
        with salt.utils.fopen(keyfile, 'w') as keyf:
            keyf.write(key)
            return 'saved: {0}'.format(keyfile)
    return key


def enc(data, **kwargs):
    '''
    Takes a key generated from `nacl.keygen` and encrypt some data.

    CLI Examples:

    .. code-block:: bash

        salt-run nacl.enc datatoenc
        salt-run nacl.enc datatoenc keyfile=/root/.nacl
        salt-run nacl.enc datatoenc key='cKEzd4kXsbeCE7/nLTIqXwnUiD1ulg4NoeeYcCFpd9k='
    '''
    key = _get_key(**kwargs)
    sk = base64.b64decode(key)
    b = libnacl.secret.SecretBox(sk)
    return base64.b64encode(b.encrypt(data))


def dec(data, **kwargs):
    '''
    Takes a key generated from `nacl.keygen` and decrypt some data.

    CLI Examples:

    .. code-block:: bash

        salt-run nacl.dec pEXHQM6cuaF7A=
        salt-run nacl.dec data='pEXHQM6cuaF7A=' keyfile=/root/.nacl
        salt-run nacl.dec data='pEXHQM6cuaF7A=' key='cKEzd4kXsbeCE7/nLTIqXwnUiD1ulg4NoeeYcCFpd9k='
    '''
    key = _get_key(**kwargs)
    sk = base64.b64decode(key)
    b = libnacl.secret.SecretBox(key=sk)
    return b.decrypt(base64.b64decode(data))
