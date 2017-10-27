# -*- coding: utf-8 -*-
'''
This module helps include encrypted passwords in pillars, grains and salt state files.

:depends: libnacl, https://github.com/saltstack/libnacl

This is often useful if you wish to store your pillars in source control or
share your pillar data with others that you trust. I don't advise making your pillars public
regardless if they are encrypted or not.

When generating keys and encrypting passwords use --local when using salt-call for extra
security. Also consider using just the salt runner nacl when encrypting pillar passwords.

The nacl lib uses 32byte keys, these keys are base64 encoded to make your life more simple.
To generate your `key` or `keyfile` you can use:

.. code-block:: bash

    salt-call --local nacl.keygen keyfile=/root/.nacl

Now with your key, you can encrypt some data:

.. code-block:: bash

    salt-call --local nacl.enc mypass keyfile=/root/.nacl
    DRB7Q6/X5gGSRCTpZyxS6hXO5LnlJIIJ4ivbmUlbWj0llUA+uaVyvou3vJ4=

To decrypt the data:

.. code-block:: bash

    salt-call --local nacl.dec data='DRB7Q6/X5gGSRCTpZyxS6hXO5LnlJIIJ4ivbmUlbWj0llUA+uaVyvou3vJ4=' keyfile=/root/.nacl
    mypass

The following optional configurations can be defined in the
minion or master config. Avoid storing the config in pillars!

.. code-block:: yaml

    cat /etc/salt/master.d/nacl.conf
    nacl.config:
        key: 'cKEzd4kXsbeCE7/nLTIqXwnUiD1ulg4NoeeYcCFpd9k='
        keyfile: /root/.nacl

When the key is defined in the master config you can use it from the nacl runner:

.. code-block:: bash

    salt-run nacl.enc 'myotherpass'

Now you can create a pillar with protected data like:

.. code-block:: jinja

    pillarexample:
        user: root
        password: {{ salt.nacl.dec('DRB7Q6/X5gGSRCTpZyxS6hXO5LnlJIIJ4ivbmUlbWj0llUA+uaVyvou3vJ4=') }}

Or do something interesting with grains like:

.. code-block:: jinja

    salt-call nacl.enc minionname:dbrole
    AL24Z2C5OlkReer3DuQTFdrNLchLuz3NGIhGjZkLtKRYry/b/CksWM8O9yskLwH2AGVLoEXI5jAa

    salt minionname grains.setval role 'AL24Z2C5OlkReer3DuQTFdrNLchLuz3NGIhGjZkLtKRYry/b/CksWM8O9yskLwH2AGVLoEXI5jAa'

    {%- set r = grains.get('role') %}
    {%- set role = None %}
    {%- if r and 'nacl.dec' in salt %}
        {%- set r = salt['nacl.dec'](r,keyfile='/root/.nacl').split(':') %}
        {%- if opts['id'] == r[0] %}
            {%- set role = r[1] %}
        {%- endif %}
    {%- endif %}
    base:
        {%- if role %}
        '{{ opts['id'] }}':
            - {{ role }}
        {%- endif %}

Multi-line text items like certificates require a bit of extra work. You have to strip the new lines
and replace them with '/n' characters. Certificates specifically require some leading white space when
calling nacl.enc so that the '--' in the first line (commonly -----BEGIN CERTIFICATE-----) doesn't get
interpreted as an argument to nacl.enc. For instance if you have a certificate file that lives in cert.crt:

.. code-block:: bash

    cert=$(cat cert.crt |awk '{printf "%s\\n",$0} END {print ""}'); salt-run nacl.enc "  $cert"

Pillar data should look the same, even though the secret will be quite long. However, when calling
multiline encrypted secrets from pillar in a state, use the following format to avoid issues with /n
creating extra whitespace at the beginning of each line in the cert file:

.. code-block:: jinja

    secret.txt:
        file.managed:
            - template: jinja
            - user: user
            - group: group
            - mode: 700
            - contents: "{{- salt['pillar.get']('secret') }}"

The '{{-' will tell jinja to strip the whitespace from the beginning of each of the new lines.
'''

from __future__ import absolute_import
import base64
import os
import salt.utils
import salt.syspaths


REQ_ERROR = None
try:
    import libnacl.secret
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
    }
    config_key = '{0}.config'.format(__virtualname__)
    config.update(__salt__['config.get'](config_key, {}))
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

        salt-call --local nacl.keygen
        salt-call --local nacl.keygen keyfile=/root/.nacl
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
            return 'saved: {0}'.format(keyfile)
    return key


def enc(data, **kwargs):
    '''
    Takes a key generated from `nacl.keygen` and encrypt some data.

    CLI Examples:

    .. code-block:: bash

        salt-call --local nacl.enc datatoenc
        salt-call --local nacl.enc datatoenc keyfile=/root/.nacl
        salt-call --local nacl.enc datatoenc key='cKEzd4kXsbeCE7/nLTIqXwnUiD1ulg4NoeeYcCFpd9k='
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

        salt-call --local nacl.dec pEXHQM6cuaF7A=
        salt-call --local nacl.dec data='pEXHQM6cuaF7A=' keyfile=/root/.nacl
        salt-call --local nacl.dec data='pEXHQM6cuaF7A=' key='cKEzd4kXsbeCE7/nLTIqXwnUiD1ulg4NoeeYcCFpd9k='
    '''
    key = _get_key(**kwargs)
    sk = base64.b64decode(key)
    b = libnacl.secret.SecretBox(key=sk)
    return b.decrypt(base64.b64decode(data))
