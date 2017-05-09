# -*- coding: utf-8 -*-
'''
This module makes it simple to include encrypted passwords in pillars.
This is most helpfull if you wish to store your pillars in source control.

    salt-call cipher.enc mypasstoprotect
    75wCAZw2Dn-VEebq1TdWAC4RI-48HLDknIquXOxJ858=

    pillarexample:
        user: root
        password: {{ salt.cipher.dec('75wCAdWAC4HLDknIquXOxJ858=') }}


The default encode and decode password is the md5sum of:
   `/etc/salt/pki/master/master.pem` or the file contents pending on cipher.

If you rather supply your own key use the argument `key` or `keyfile`

    echo 'decipher_password' > /root/.saltpass
    salt-call cipher.enc mypass keyfile=/root/.saltpass
    salt-call cipher.enc mypass key=decipher_password

For most ciphers the `key` and `keyfile` is limited to the first 32 bytes.
Anything longer will cause the 32bytes of the md5 of the key to be used.
This is helpfull on 'pem' files because many have the same 32bytes.

If you use the default key remember to keep a safe backup!

The following optional configurations can be define in the
minion, master config or pillar.

    cipher.config:
        key: None
        keyfile: /etc/salt/pki/master/master.pem
        keyfile_use_md5: '.pem'

Also every call can override the above defaults:
If a `key` is defined it is used over a `keyfile`.


    salt-call cipher.enc 'mypassonlymastercandec' keyfile='/root/.saltcipher'
'''

# Note: not includeing salt stuff so this python lib is not tied down.

import base64
import hashlib
import os
import salt.utils

REQ_ERROR = {
    'crypto': None,
    'crypto_rsa': None,
    'openssl': None,
    'libnacl': None,
}

__virtualname__ = 'cipher'

try:
    import libnacl.secret
except ImportError as e:
    REQ_ERROR['libnacl'] = 'libnacl import error, perhaps missing python libnacl package'

try:
    from Crypto.Cipher import AES
    from Crypto.Cipher import XOR
except ImportError as e:
    try:
        # windows and mac might have lowercase crypto ?
        from crypto.cipher import AES
    except ImportError as e:
        REQ_ERROR['crypto'] = 'import error, missing python Crypto package (install pycrypto)'

try:
    from Crypto.PublicKey import RSA
    if 'importKey' not in dir(RSA):
        REQ_ERROR['crypto_rsa'] = 'python lib pycrypto is missing requirements. You likly need to update'
except ImportError as e:
    REQ_ERROR['crypto_rsa'] = 'import error, missing python Crypto package'


if salt.utils.is_windows() or salt.utils.which('openssl') is None:
    REQ_ERROR['openssl'] = 'missing binary openssl'


def _get_config(**kwargs):
    '''
    Return configuration
    '''
    config = {
        'key': None,
        'keyfile': '/root/.pass',
            #'/etc/salt/pki/master/master.pem',
    }
    if '__salt__' in globals():
        config_key = '{0}.config'.format(__virtualname__)
        config.update(__salt__['config.get'](config_key, {}))
    for k in set(config.keys()) & set(kwargs.keys()):
        config[k] = kwargs[k]
    return config


def _get_key(size_limit=None, **kwargs):
    config = _get_config(**kwargs)
    key = config['key']
    if not key:
        with open(config['keyfile'], 'rb') as keyf:
            key = keyf.read().rstrip('\n')
    if size_limit and len(key) > size_limit:
        m = base64.b64encode(hashlib.md5(key).digest())
        key = m[:size_limit]
    return key


def enc(data, **kwargs):
    '''
    alias for aes_enc
    '''
    return aes_enc(data=data, **kwargs)


def dec(data, **kwargs):
    '''
    alias for aes_dec
    '''
    return aes_dec(data=data, **kwargs)


def libnacl_keygen():
    '''
    Use libnacl to generate a private key

    apt-get install python-libnacl
    yum install libsodium
    pip install libnacl

    salt-call cipher.libnacl_keygen > /root/.naclkey
    '''
    if REQ_ERROR['libnacl']:
        raise Exception(REQ_ERROR['libnacl'])
    b = libnacl.secret.SecretBox()
    return base64.b64encode(b.sk)


def libnacl_enc(data, **kwargs):
    '''
    Takes a key generated from libnacl_keygen and
    encrypt some data.

        salt-call cipher.libnacl_keygen
        salt-call cipher.enc somthingtoenc keyfile=/root/.naclkey
    '''
    if REQ_ERROR['libnacl']:
        raise Exception(REQ_ERROR['libnacl'])
    key = _get_key(**kwargs)
    sk = base64.b64decode(key)
    b = libnacl.secret.SecretBox(key=sk)
    return base64.b64encode(b.encrypt(data))


def libnacl_dec(data, **kwargs):
    '''
    Takes a key generated from libnacl_keygen and
    encrypt some data.

        salt-call cipher.libnacl_keygen
        salt-call cipher.dec somthingtoenc keyfile=/root/.naclkey
    '''
    if REQ_ERROR['libnacl']:
        raise Exception(REQ_ERROR['libnacl'])
    key = _get_key(**kwargs)
    sk = base64.b64decode(key)
    b = libnacl.secret.SecretBox(key=sk)
    return b.decrypt(base64.b64decode(data))


def rsa_keygen(key_size=1024):
    '''
    TODO: untested
    yum -y update gmp pip install --upgrade PyCrypto
    generate rsa key
    http://www.laurentluce.com/posts/python-and-cryptography-with-pycrypto/
    '''
    if REQ_ERROR['crypto_rsa']:
        raise Exception(REQ_ERROR['crypto_rsa'])
    key = RSA.generate(key_size, os.urandom)
    return key.exportKey('PEM')


def rsa_enc(data, **kwargs):
    '''
    TODO: untested
    salt-call cipher.encipher passwordToHide
    '''
    if REQ_ERROR['crypto_rsa']:
        raise Exception(REQ_ERROR['crypto_rsa'])
    key = _get_key(**kwargs)
    conf = _get_config(**kwargs)
    key = RSA.importKey(conf['keyfile'], passphrase=key)
    r = key.PublicKey().encrypt(data, os.urandom(16))
    return r


def rsa_dec(data, **kwargs):
    '''
    TODO: untested
    salt-call cipher.decipher U2FsdGVkX1+uNDhmDwGjiVk3wpt3uQ=
    '''
    if REQ_ERROR['crypto_rsa']:
        raise Exception(REQ_ERROR['crypto_rsa'])
    key = _get_key(**kwargs)
    conf = _get_config(**kwargs)
    key = RSA.importKey(conf['keyfile'], passphrase=key)
    r = key.decrypt(data)
    return r


def aes_enc(data, **kwargs):
    '''
    If the `key` is grater than 32 bytes.
    The md5sum of the key will be used as the password.

    salt-call cipher.encipher passwordToHide
    '''
    if REQ_ERROR['crypto']:
        raise Exception(REQ_ERROR['crypto'])
    key = _get_key(size_limit=32, **kwargs)
    block_size = 16
    key_pad = block_size - len(key) % block_size
    key_padded = key + (key_pad * chr(key_pad))
    data_pad = block_size - len(data) % block_size
    data = data + (data_pad * chr(data_pad))
    iv_bytes = os.urandom(block_size)
    cypher = AES.new(key_padded, AES.MODE_CBC, iv_bytes)
    data = iv_bytes + cypher.encrypt(data)
    return base64.b64encode(data)


def aes_dec(data, **kwargs):
    '''
    If the `key` is grater than 32 bytes.
    The md5sum of the key will be used as the password.

    salt-call cipher.dec U2FsdGVkX1+uNDhmDwGjiVk3wpt3uQ=
    '''
    if REQ_ERROR['crypto']:
        raise Exception(REQ_ERROR['crypto'])
    key = _get_key(size_limit=32, **kwargs)
    data = base64.b64decode(data)
    block_size = 16
    key_pad = block_size - len(key) % block_size
    key_padded = key + key_pad * chr(key_pad)
    iv_bytes = data[:block_size]
    data = data[block_size:]
    cypher = AES.new(key_padded, AES.MODE_CBC, iv_bytes)
    data = cypher.decrypt(data)
    return data[:-ord(data[-1])]


def openssl_enc(data, **kwargs):
    '''
    If the `key` is grater than 32 bytes.
    The md5sum of the key will be used as the password.

    echo 'decipher_password' > /etc/sat/key
    salt-call openssl.encipher passwordToHide
    '''
    if REQ_ERROR['openssl']:
        raise Exception(REQ_ERROR['openssl'])
    key = _get_key(size_limit=32, **kwargs)
    # TODO: is this safe... can people see the raw call in ps?
    cmd = 'echo -e "{0}" | openssl enc -aes-256-cbc -a -k "{1}"'
    r = __salt__['cmd.shell'](cmd.format(data, key))
    return r


def openssl_dec(data, **kwargs):
    '''
    If the `key` is grater than 32 bytes.
    The md5sum of the key will be used as the password.

    salt-call openssl.decipher U2FsdGVkX1+uNDhmDwGjiVk3wpt3uQ=
    '''
    if REQ_ERROR['openssl']:
        raise Exception(REQ_ERROR['openssl'])
    key = _get_key(size_limit=32, **kwargs)
    # TODO: is this safe... can people see the raw call in ps?
    cmd = 'echo -e "{0}" | openssl enc -aes-256-cbc -a -d -k "{1}"'
    r = __salt__['cmd.shell'](cmd.format(data, key))
    if 'bad decipher' in r:
        raise Exception(r)
    return r


def xor_enc(data, **kwargs):
    '''
    A vary weak crypto!
    Prefer vigenere_enc
    '''
    if REQ_ERROR['crypto']:
        raise Exception(REQ_ERROR['crypto'])
    key = _get_key(**kwargs)
    cipher = XOR.new(key)
    return base64.b64encode(cipher.encrypt(data))


def xor_dec(data, **kwargs):
    '''
    A vary weak crypto!
    Prefer vigenere_dec
    '''
    if REQ_ERROR['crypto']:
        raise Exception(REQ_ERROR['crypto'])
    key = _get_key(**kwargs)
    cipher = XOR.new(key)
    return cipher.decrypt(base64.b64decode(data))


def vigenere_enc(data, **kwargs):
    '''
    A weak crypto.
    However this has little dependicies and provide basic protection.
    '''
    key = _get_key(**kwargs)
    d = []
    for i in range(len(data)):
        kc = key[i % len(key)]
        dc = chr((ord(data[i]) + ord(kc)) % 256)
        d.append(dc)
    return base64.b64encode("".join(d))


def vigenere_dec(data, **kwargs):
    '''
    A weak crypto.
    However this has little dependicies and provide basic protection.
    '''
    key = _get_key(**kwargs)
    d = []
    data = base64.b64decode(data)
    for i in range(len(data)):
        kc = key[i % len(key)]
        dc = chr((256 + ord(data[i]) - ord(kc)) % 256)
        d.append(dc)
    return "".join(d)
