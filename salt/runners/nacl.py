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
    define (pillar or config files) Avoid storing private keys in pillars! Ensure master does not have `pillar_opts=True`:

    .. code-block:: python

        # cat /etc/salt/master.d/nacl.conf
        nacl.config:
            # NOTE: `key` and `key_file` have been renamed to `sk`, `sk_file`
            # also `box_type` default changed from secretbox to sealedbox.
            box_type: sealedbox                     (default)
            sk_file: /etc/salt/pki/master/nacl      (default)
            pk_file: /etc/salt/pki/master/nacl.pub  (default)
            sk: None
            pk: None

    Usage can override the config defaults:

    .. code-block:: bash

        salt-call nacl.enc sk_file=/etc/salt/pki/master/nacl pk_file=/etc/salt/pki/master/nacl.pub


The nacl lib uses 32byte keys, these keys are base64 encoded to make your life more simple.
To generate your `sk_file` and `pk_file` use:

.. code-block:: bash

    salt-call --local nacl.keygen sk_file=/etc/salt/pki/master/nacl
    # or if you want to work without files.
    salt-call --local nacl.keygen
    local:
        ----------
        pk:
            /kfGX7PbWeu099702PBbKWLpG/9p06IQRswkdWHCDk0=
        sk:
            SVWut5SqNpuPeNzb1b9y6b2eXg2PLIog43GBzp48Sow=

Now with your keypair, you can encrypt data:

You have two option, `sealedbox` or `secretbox`.

SecretBox is data encrypted using private key `pk`. Sealedbox is encrypted using public key `pk`.

Recommend using Sealedbox because the one way encryption permits developers to encrypt data for source control but not decrypt.
Sealedbox only has one key that is for both encryption and decryption.

.. code-block:: bash

    salt-call --local nacl.enc asecretpass pk=/kfGX7PbWeu099702PBbKWLpG/9p06IQRswkdWHCDk0=
    tqXzeIJnTAM9Xf0mdLcpEdklMbfBGPj2oTKmlgrm3S1DTVVHNnh9h8mU1GKllGq/+cYsk6m5WhGdk58=

To decrypt the data:

.. code-block:: bash

    salt-call --local nacl.dec data='tqXzeIJnTAM9Xf0mdLcpEdklMbfBGPj2oTKmlgrm3S1DTVVHNnh9h8mU1GKllGq/+cYsk6m5WhGdk58=' \
        sk='SVWut5SqNpuPeNzb1b9y6b2eXg2PLIog43GBzp48Sow='

When the keys are defined in the master config you can use them from the nacl runner
without extra parameters:

.. code-block:: python

    # cat /etc/salt/master.d/nacl.conf
    nacl.config:
        sk_file: /etc/salt/pki/master/nacl
        pk: 'cTIqXwnUiD1ulg4kXsbeCE7/NoeKEzd4nLeYcCFpd9k='

.. code-block:: bash

    salt-run nacl.enc 'asecretpass'
    salt-run nacl.dec 'tqXzeIJnTAM9Xf0mdLcpEdklMbfBGPj2oTKmlgrm3S1DTVVHNnh9h8mU1GKllGq/+cYsk6m5WhGdk58='

.. code-block:: yaml

    # a salt developers minion could have pillar data that includes a nacl public key
    nacl.config:
        pk: '/kfGX7PbWeu099702PBbKWLpG/9p06IQRswkdWHCDk0='

The developer can then use a less-secure system to encrypt data.

.. code-block:: bash

    salt-call --local nacl.enc apassword


Pillar files can include protected data that the salt master decrypts:

.. code-block:: jinja

    pillarexample:
        user: root
        password1: {{salt.nacl.dec('DRB7Q6/X5gGSRCTpZyxS6hlbWj0llUA+uaVyvou3vJ4=')|json}}
        cert_key: {{salt.nacl.dec_file('/srv/salt/certs/example.com/key.nacl')|json}}
        cert_key2: {{salt.nacl.dec_file('salt:///certs/example.com/key.nacl')|json}}

Larger files like certificates can be encrypted with:

.. code-block:: bash

    salt-call nacl.enc_file /tmp/cert.crt out=/tmp/cert.nacl
    # or more advanced
    cert=$(cat /tmp/cert.crt)
    salt-call --out=newline_values_only nacl.enc_pub data="$cert" > /tmp/cert.nacl

In pillars rended with jinja be sure to include `|json` so line breaks are encoded:

.. code-block:: jinja

    cert: "{{salt.nacl.dec('S2uogToXkgENz9...085KYt')|json}}"

In states rendered with jinja it is also good pratice to include `|json`:

.. code-block:: jinja

    {{sls}} private key:
        file.managed:
            - name: /etc/ssl/private/cert.key
            - mode: 700
            - contents: "{{pillar['pillarexample']['cert_key']|json}}"


Optional small program to encrypt data without needing salt modules.

.. code-block:: python

    #!/bin/python3
    import sys, base64, libnacl.sealed
    pk = base64.b64decode('YOURPUBKEY')
    b = libnacl.sealed.SealedBox(pk)
    data = sys.stdin.buffer.read()
    print(base64.b64encode(b.encrypt(data)).decode())

.. code-block:: bash

    echo 'apassword' | nacl_enc.py

'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import base64
import os

# Import Salt libs
import salt.utils.files
import salt.utils.platform
import salt.utils.win_functions
import salt.utils.win_dacl
import salt.syspaths

# Import 3rd-party libs
from salt.ext import six

REQ_ERROR = None
try:
    import libnacl.secret
    import libnacl.sealed
except (ImportError, OSError) as e:
    REQ_ERROR = 'libnacl import error, perhaps missing python libnacl package or should update.'

__virtualname__ = 'nacl'


def __virtual__():
    return (REQ_ERROR is None, REQ_ERROR)


def _get_config(**kwargs):
    '''
    Return configuration
    '''
    config = {
        'box_type': 'sealedbox',
        'sk': None,
        'sk_file': '/etc/salt/pki/master/nacl',
        'pk': None,
        'pk_file': '/etc/salt/pki/master/nacl.pub',
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


def _get_sk(**kwargs):
    '''
    Return sk
    '''
    config = _get_config(**kwargs)
    key = config['sk']
    sk_file = config['sk_file']
    if not key and sk_file:
        with salt.utils.files.fopen(sk_file, 'rb') as keyf:
            key = six.text_type(keyf.read()).rstrip('\n')
    if key is None:
        raise Exception('no key or sk_file found')
    return base64.b64decode(key)


def _get_pk(**kwargs):
    '''
    Return pk
    '''
    config = _get_config(**kwargs)
    pubkey = config['pk']
    pk_file = config['pk_file']
    if not pubkey and pk_file:
        with salt.utils.files.fopen(pk_file, 'rb') as keyf:
            pubkey = six.text_type(keyf.read()).rstrip('\n')
    if pubkey is None:
        raise Exception('no pubkey or pk_file found')
    pubkey = six.text_type(pubkey)
    return base64.b64decode(pubkey)


def keygen(sk_file=None, pk_file=None):
    '''
    Use libnacl to generate a keypair.

    If no `sk_file` is defined return a keypair.

    If only the `sk_file` is defined `pk_file` will use the same name with a postfix `.pub`.

    When the `sk_file` is already existing, but `pk_file` is not. The `pk_file` will be generated
    using the `sk_file`.

    CLI Examples:

    .. code-block:: bash

        salt-call nacl.keygen
        salt-call nacl.keygen sk_file=/etc/salt/pki/master/nacl
        salt-call nacl.keygen sk_file=/etc/salt/pki/master/nacl pk_file=/etc/salt/pki/master/nacl.pub
        salt-call --local nacl.keygen
    '''
    if sk_file is None:
        kp = libnacl.public.SecretKey()
        return {'sk': base64.b64encode(kp.sk), 'pk': base64.b64encode(kp.pk)}

    if pk_file is None:
        pk_file = '{0}.pub'.format(sk_file)

    if sk_file and pk_file is None:
        if not os.path.isfile(sk_file):
            kp = libnacl.public.SecretKey()
            with salt.utils.files.fopen(sk_file, 'w') as keyf:
                keyf.write(base64.b64encode(kp.sk))
            if salt.utils.platform.is_windows():
                cur_user = salt.utils.win_functions.get_current_user()
                salt.utils.win_dacl.set_owner(sk_file, cur_user)
                salt.utils.win_dacl.set_permissions(sk_file, cur_user, 'full_control', 'grant', reset_perms=True, protected=True)
            else:
                # chmod 0600 file
                os.chmod(sk_file, 1536)
            return 'saved sk_file: {0}'.format(sk_file)
        else:
            raise Exception('sk_file:{0} already exist.'.format(sk_file))

    if sk_file is None and pk_file:
        raise Exception('sk_file: Must be set inorder to generate a public key.')

    if os.path.isfile(sk_file) and os.path.isfile(pk_file):
        raise Exception('sk_file:{0} and pk_file:{1} already exist.'.format(sk_file, pk_file))

    if os.path.isfile(sk_file) and not os.path.isfile(pk_file):
        # generate pk using the sk
        with salt.utils.files.fopen(sk_file, 'rb') as keyf:
            sk = six.text_type(keyf.read()).rstrip('\n')
            sk = base64.b64decode(sk)
        kp = libnacl.public.SecretKey(sk)
        with salt.utils.files.fopen(pk_file, 'w') as keyf:
            keyf.write(base64.b64encode(kp.pk))
        return 'saved pk_file: {0}'.format(pk_file)

    kp = libnacl.public.SecretKey()
    with salt.utils.files.fopen(sk_file, 'w') as keyf:
        keyf.write(base64.b64encode(kp.sk))
    if salt.utils.platform.is_windows():
        cur_user = salt.utils.win_functions.get_current_user()
        salt.utils.win_dacl.set_owner(sk_file, cur_user)
        salt.utils.win_dacl.set_permissions(sk_file, cur_user, 'full_control', 'grant', reset_perms=True, protected=True)
    else:
        # chmod 0600 file
        os.chmod(sk_file, 1536)
    with salt.utils.files.fopen(pk_file, 'w') as keyf:
        keyf.write(base64.b64encode(kp.pk))
    return 'saved sk_file:{0}  pk_file: {1}'.format(sk_file, pk_file)


def enc(data, **kwargs):
    '''
    Alias to `{box_type}_encrypt`

    box_type: secretbox, sealedbox(default)
    '''
    box_type = _get_config(**kwargs)['box_type']
    if box_type == 'sealedbox':
        return sealedbox_encrypt(data, **kwargs)
    if box_type == 'secretbox':
        return secretbox_encrypt(data, **kwargs)
    return sealedbox_encrypt(data, **kwargs)


def enc_file(name, out=None, **kwargs):
    '''
    This is a helper function to encrypt a file and return its contents.

    You can provide an optional output file using `out`

    `name` can be a local file or when not using `salt-run` can be a url like `salt://`, `https://` etc.

    CLI Examples:

    .. code-block:: bash

        salt-run nacl.enc_file name=/tmp/id_rsa
        salt-call nacl.enc_file name=salt://crt/mycert out=/tmp/cert
        salt-run nacl.enc_file name=/tmp/id_rsa box_type=secretbox \
            sk_file=/etc/salt/pki/master/nacl.pub
    '''
    try:
        data = __salt__['cp.get_file_str'](name)
    except Exception as e:
        # likly using salt-run so fallback to local filesystem
        with salt.utils.files.fopen(name, 'rb') as f:
            data = f.read()
    d = enc(data, **kwargs)
    if out:
        if os.path.isfile(out):
            raise Exception('file:{0} already exist.'.format(out))
        with salt.utils.files.fopen(out, 'wb') as f:
            f.write(d)
        return 'Wrote: {0}'.format(out)
    return d


def dec(data, **kwargs):
    '''
    Alias to `{box_type}_decrypt`

    box_type: secretbox, sealedbox(default)
    '''
    box_type = _get_config(**kwargs)['box_type']
    if box_type == 'sealedbox':
        return sealedbox_decrypt(data, **kwargs)
    if box_type == 'secretbox':
        return secretbox_decrypt(data, **kwargs)
    return sealedbox_decrypt(data, **kwargs)


def dec_file(name, out=None, **kwargs):
    '''
    This is a helper function to decrypt a file and return its contents.

    You can provide an optional output file using `out`

    `name` can be a local file or when not using `salt-run` can be a url like `salt://`, `https://` etc.

    CLI Examples:

    .. code-block:: bash

        salt-run nacl.dec_file name=/tmp/id_rsa.nacl
        salt-call nacl.dec_file name=salt://crt/mycert.nacl out=/tmp/id_rsa
        salt-run nacl.dec_file name=/tmp/id_rsa.nacl box_type=secretbox \
            sk_file=/etc/salt/pki/master/nacl.pub
    '''
    try:
        data = __salt__['cp.get_file_str'](name)
    except Exception as e:
        # likly using salt-run so fallback to local filesystem
        with salt.utils.files.fopen(name, 'rb') as f:
            data = f.read()
    d = dec(data, **kwargs)
    if out:
        if os.path.isfile(out):
            raise Exception('file:{0} already exist.'.format(out))
        with salt.utils.files.fopen(out, 'wb') as f:
            f.write(d)
        return 'Wrote: {0}'.format(out)
    return d


def sealedbox_encrypt(data, **kwargs):
    '''
    Encrypt data using a public key generated from `nacl.keygen`.
    The encryptd data can be decrypted using `nacl.sealedbox_decrypt` only with the secret key.

    CLI Examples:

    .. code-block:: bash

        salt-run nacl.sealedbox_encrypt datatoenc
        salt-call --local nacl.sealedbox_encrypt datatoenc pk_file=/etc/salt/pki/master/nacl.pub
        salt-call --local nacl.sealedbox_encrypt datatoenc pk='vrwQF7cNiNAVQVAiS3bvcbJUnF0cN6fU9YTZD9mBfzQ='
    '''
    pk = _get_pk(**kwargs)
    b = libnacl.sealed.SealedBox(pk)
    return base64.b64encode(b.encrypt(data))


def sealedbox_decrypt(data, **kwargs):
    '''
    Decrypt data using a secret key that was encrypted using a public key with `nacl.sealedbox_encrypt`.

    CLI Examples:

    .. code-block:: bash

        salt-call nacl.sealedbox_decrypt pEXHQM6cuaF7A=
        salt-call --local nacl.sealedbox_decrypt data='pEXHQM6cuaF7A=' sk_file=/etc/salt/pki/master/nacl
        salt-call --local nacl.sealedbox_decrypt data='pEXHQM6cuaF7A=' sk='YmFkcGFzcwo='
    '''
    if data is None:
        return None
    sk = _get_sk(**kwargs)
    keypair = libnacl.public.SecretKey(sk)
    b = libnacl.sealed.SealedBox(keypair)
    return b.decrypt(base64.b64decode(data))


def secretbox_encrypt(data, **kwargs):
    '''
    Encrypt data using a secret key generated from `nacl.keygen`.
    The same secret key can be used to decrypt the data using `nacl.secretbox_decrypt`.

    CLI Examples:

    .. code-block:: bash

        salt-run nacl.secretbox_encrypt datatoenc
        salt-call --local nacl.secretbox_encrypt datatoenc sk_file=/etc/salt/pki/master/nacl
        salt-call --local nacl.secretbox_encrypt datatoenc sk='YmFkcGFzcwo='
    '''
    sk = _get_sk(**kwargs)
    b = libnacl.secret.SecretBox(sk)
    return base64.b64encode(b.encrypt(data))


def secretbox_decrypt(data, **kwargs):
    '''
    Decrypt data that was encrypted using `nacl.secretbox_encrypt` using the secret key
    that was generated from `nacl.keygen`.

    CLI Examples:

    .. code-block:: bash

        salt-call nacl.secretbox_decrypt pEXHQM6cuaF7A=
        salt-call --local nacl.secretbox_decrypt data='pEXHQM6cuaF7A=' sk_file=/etc/salt/pki/master/nacl
        salt-call --local nacl.secretbox_decrypt data='pEXHQM6cuaF7A=' sk='YmFkcGFzcwo='
    '''
    if data is None:
        return None
    key = _get_sk(**kwargs)
    b = libnacl.secret.SecretBox(key=key)
    return b.decrypt(base64.b64decode(data))
