# -*- coding: utf-8 -*-
'''
This module makes it simple to include encrypted passwords in pillars.
This is most helpfull if you wish to store your pillars in source control or
share your pillar data with others.

    salt-call cipher.enc mypasstoprotect
    75wCAZw2Dn-VEebq1TdWAC4RI-48HLDknIquXOxJ858=

    pillarexample:
        user: root
        password: {{ salt.cipher.dec('75wCAdWAC4HLDknIquXOxJ858=') }}


The default encode and decode password is the md5sum of:
   `/etc/salt/pki/master/master.pem` or the keyfile contents pending on cipher.

If you rather supply your own key use the argument `key` or `keyfile`
Echo adds a newline character. To stop that, use the `-n`

    echo -n 'decipher_password' > /root/.saltpass
    salt-call cipher.enc mypass keyfile=/root/.saltpass
    salt-call cipher.enc mypass key=decipher_password

For most ciphers the `key` and `keyfile` is limited to the first 32 bytes.
Anything longer will cause the first 32bytes of the md5 of the key to be used.
This is helpfull on 'pem' files because many have the same first 32bytes.

If you use the default key remember to keep a safe backup!

The following optional configurations can be defined in the
minion, master config or pillar.

    cipher.config:
        key: None
        keyfile: /root/.saltcipher

Also every call can override the above defaults:
If a `key` is defined it is used over a `keyfile`.


    salt-call cipher.enc 'mypassonlymastercandec' keyfile='/root/.saltcipher'
'''
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
        REQ_ERROR['crypto_rsa'] = 'python lib pycrypto is missing requirements. Likly need new version.'
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
        'keyfile': '/etc/salt/pki/master/master.pem',
    }
    if '__salt__' in globals():
        config_key = '{0}.config'.format(__virtualname__)
        config.update(__salt__['config.get'](config_key, {}))
    for k in set(config.keys()) & set(kwargs.keys()):
        config[k] = kwargs[k]
    return config


def _get_key(size_limit=None, trim_newline=False, **kwargs):
    config = _get_config(**kwargs)
    key = config['key']
    if not key:
        with open(config['keyfile'], 'rb') as keyf:
            key = keyf.read()
            if trim_newline:
                key = key.rstrip('\n')
    key = str(key)
    #key = key.encode('ascii','ignore')
    if size_limit and len(key) > size_limit:
        #m = base64.b64encode(hashlib.sha256(key).digest())
        m = base64.b64encode(hashlib.md5(key).digest())
        key = m[:size_limit]
    return key


def enc(data, **kwargs):
    '''
    alias for aes_enc

    CLI Examples:

    .. code-block:: bash

        salt-call cipher.enc
    '''
    return aes_enc(data=data, **kwargs)


def dec(data, **kwargs):
    '''
    alias for aes_dec

    CLI Examples:

    .. code-block:: bash

        salt-call cipher.dec
    '''
    return aes_dec(data=data, **kwargs)


def libnacl_keygen():
    '''
    Use libnacl to generate a private key

    CLI Examples:

    .. code-block:: bash

        salt-call --out=newline_values_only cipher.libnacl_keygen > /root/.naclkey
    '''
    if REQ_ERROR['libnacl']:
        raise Exception(REQ_ERROR['libnacl'])
    b = libnacl.secret.SecretBox()
    return base64.b64encode(b.sk)


def libnacl_enc(data, **kwargs):
    '''
    Takes a key generated from `cipher.libnacl_keygen` and encrypt some data.

    CLI Examples:

    .. code-block:: bash

        salt-call cipher.libnacl_enc datatoenc keyfile=/root/.naclkey
    '''
    if REQ_ERROR['libnacl']:
        raise Exception(REQ_ERROR['libnacl'])
    key = _get_key(**kwargs)
    sk = base64.b64decode(key)
    b = libnacl.secret.SecretBox(key=sk)
    return base64.b64encode(b.encrypt(data))


def libnacl_dec(data, **kwargs):
    '''
    Takes a key generated from `cipher.libnacl_keygen` and decrypt some data.

    CLI Examples:

    .. code-block:: bash

        salt-call cipher.libnacl_dec pEXHQM6cuaF7A= keyfile=/root/.naclkey
    '''
    if REQ_ERROR['libnacl']:
        raise Exception(REQ_ERROR['libnacl'])
    key = _get_key(**kwargs)
    sk = base64.b64decode(key)
    b = libnacl.secret.SecretBox(key=sk)
    return b.decrypt(base64.b64decode(data))


def rsa_keygen(keysize=1024, passphrase=None):
    '''
    Use PyCrypto to generate a RSA PEM.

    CLI Examples:

    .. code-block:: bash

        salt-call --out=newline_values_only cipher.rsa_keygen > /root/.rsakey
        salt-call --out=newline_values_only cipher.rsa_keygen keysize=1024 > /root/.rsakey
        salt-call --out=newline_values_only cipher.rsa_keygen passphrase=pp > /root/.rsakey
    '''
    if REQ_ERROR['crypto_rsa']:
        raise Exception(REQ_ERROR['crypto_rsa'])
    key = RSA.generate(keysize, os.urandom)
    return key.exportKey('PEM', passphrase=passphrase)


def rsa_enc(data, passphrase=None, **kwargs):
    '''
    Takes a key generated from `cipher.rsa_keygen` and encrypt data.

    CLI Examples:

    .. code-block:: bash

        salt-call cipher.rsa_enc datatoenc keyfile=/root/.rsakey
        salt-call cipher.rsa_enc datatoenc passphrase=pp keyfile=/root/.rsakey
    '''
    if REQ_ERROR['crypto_rsa']:
        raise Exception(REQ_ERROR['crypto_rsa'])
    key = _get_key(**kwargs)
    #conf = _get_config(**kwargs)
    rsakey = RSA.importKey(key, passphrase=passphrase)
    rsapubkey = rsakey.publickey()
    c = rsapubkey.encrypt(data, None)[0]
    return base64.b64encode(c)


def rsa_dec(data, passphrase=None, **kwargs):
    '''
    Takes a key generated from `cipher.rsa_keygen` and decrypt data.

    CLI Examples:

    .. code-block:: bash

        salt-call cipher.rsa_dec pEXHQM6cuaF7A= keyfile=/root/.rsakey
    '''
    if REQ_ERROR['crypto_rsa']:
        raise Exception(REQ_ERROR['crypto_rsa'])
    key = _get_key(**kwargs)
    data = base64.b64decode(data)
    conf = _get_config(**kwargs)
    key = RSA.importKey(conf['keyfile'], passphrase=passphrase)
    return key.decrypt(data)


def aes_enc(data, **kwargs):
    '''
    Use PyCrypto to encrypt data as AES.

    CLI Examples:

    .. code-block:: bash

        salt-call cipher.aes_enc datatoenc
        salt-call cipher.aes_enc datatoenc key=nevertell
        salt-call cipher.aes_enc datatoenc keyfile=/root/.strkey
    '''
    # https://github.com/ryanlim/totp-manager/blob/master/totp.py
    if REQ_ERROR['crypto']:
        raise Exception(REQ_ERROR['crypto'])
    key = _get_key(**kwargs)
    key = hashlib.sha256(key).digest()
    data_pad = 16 - len(data) % 16
    data = data + (data_pad * chr(data_pad))
    iv_bytes = os.urandom(16)
    cypher = AES.new(key, AES.MODE_CBC, iv_bytes)
    data = iv_bytes + cypher.encrypt(data)
    return base64.b64encode(data)


def aes_dec(data, **kwargs):
    '''
    Use PyCrypto to decrypt AES data.

    CLI Examples:

    .. code-block:: bash

        salt-call cipher.aes_dec U2FsdGVkX1mDwGjiVk3wpt3uQ=
        salt-call cipher.aes_dec data='U2FsdGVkX1+uNjiVk3wpt3uQ=' keyfile=/root/.strkey
        salt-call cipher.aes_dec data='KZQFJEAoUQBIAsyNpxXX57Gs=' key=nevertell
    '''
    if REQ_ERROR['crypto']:
        raise Exception(REQ_ERROR['crypto'])
    key = _get_key(**kwargs)
    key = hashlib.sha256(key).digest()
    data = base64.b64decode(data)
    iv_bytes = data[:16]
    data = data[16:]
    cypher = AES.new(key, AES.MODE_CBC, iv_bytes)
    data = cypher.decrypt(data)
    return data[:-ord(data[-1])]


def _openssl_get_key_and_iv(password, salt, klen=32, ilen=16):
    '''
    CITATION: http://stackoverflow.com/questions/13907841/implement-openssl-aes-encryption-in-python
    '''
    maxlen = klen + ilen
    keyiv = hashlib.md5(password + salt).digest()
    tmp = [keyiv]
    while len(tmp) < maxlen:
        tmp.append(hashlib.md5(tmp[-1] + password + salt).digest())
        keyiv += tmp[-1]
        key = keyiv[:klen]
        iv = keyiv[klen:klen+ilen]
    return key, iv


def aes_openssl_enc(data, **kwargs):
    '''
    Use PyCrypto to encrypt data in openssl aes-256-cbc compatible format.

    If the `key` is larger than 32 bytes.
    The md5sum of the key will be used as the password.

    CLI Examples:

    .. code-block:: bash

        salt-call cipher.aes_openssl_enc datatoenc
        salt-call cipher.aes_openssl_enc datatoenc key=nevertell
        salt-call cipher.aes_openssl_enc datatoenc keyfile=/root/.strkey
    '''
    # https://github.com/ryanlim/totp-manager/blob/master/totp.py
    if REQ_ERROR['crypto']:
        raise Exception(REQ_ERROR['crypto'])
    key = _get_key(size_limit=32, trim_newline=True, **kwargs)
    salt = os.urandom(8)
    key, iv = _openssl_get_key_and_iv(key, salt)
    if key is None:
        return None
    data_pad = 16 - len(data) % 16
    data = data + (data_pad * chr(data_pad))
    cypher = AES.new(key, AES.MODE_CBC, iv)
    data = 'Salted__' + salt + cypher.encrypt(data)
    return base64.b64encode(data)


def aes_openssl_dec(data, **kwargs):
    '''
    Use PyCrypto to decrypt data in openssl aes-256-cbc format.

    If the `key` is larger than 32 bytes.
    The md5sum of the key will be used as the password.

    CLI Examples:

    .. code-block:: bash

        salt-call cipher.aes_openssl_dec U2FsdGVkX1DhmDwGjiVk3wpt3uQ=
        salt-call cipher.aes_openssl_dec data='U2FsdGVkX1+uNmDwGjiVk3wpt3uQ=' keyfile=/root/.strkey
        salt-call cipher.aes_openssl_dec data='KZQFJEAoUQBIA6iOxsyNpxXX57Gs=' key=nevertell
    '''
    if REQ_ERROR['crypto']:
        raise Exception(REQ_ERROR['crypto'])
    key = _get_key(size_limit=32, trim_newline=True, **kwargs)
    data = base64.b64decode(data)
    assert data[:8] == 'Salted__'
    salt = data[8:16]
    key, iv = _openssl_get_key_and_iv(key, salt)
    if key is None:
        return None
    ciphertext = data[16:]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_plaintext = cipher.decrypt(ciphertext)
    padding_len = ord(padded_plaintext[-1])
    plaintext = padded_plaintext[:-padding_len]
    return plaintext


def openssl_enc(data, **kwargs):
    '''
    Use openssl to encrypt AES data.
    Prefer `cipher.aes_enc`

    If the `key` is larger than 32 bytes.
    The md5sum of the key will be used as the password.
    If the key is not of block size 16 use PKCS#5 padding

    CLI Examples:

    .. code-block:: bash

        salt-call cipher.openssl_enc datatoenc
        salt-call cipher.openssl_enc datatoenc key=nevertell
        salt-call cipher.openssl_enc datatoenc keyfile=/root/.strkey
    '''
    if REQ_ERROR['openssl']:
        raise Exception(REQ_ERROR['openssl'])
    key = _get_key(size_limit=32, trim_newline=True, **kwargs)
    cmd = 'openssl enc -e -base64 -aes-256-cbc -pass env:passwd'
    r = __salt__['cmd.run'](env={'passwd': key}, stdin=data, cmd=cmd)
    return r


def openssl_dec(data, **kwargs):
    '''
    Use openssl to decrypt AES data.
    Prefer `cipher.aes_dec`

    If the `key` is larger than 32 bytes.
    The md5sum of the key will be used as the password.

    CLI Examples:

    .. code-block:: bash

        salt-call cipher.openssl_dec U2FsdGVkX13uQ=
        salt-call cipher.openssl_dec data='U2FsdGVkX13uQ=' key=nevertell
        salt-call cipher.openssl_dec data='U2FsdGVkX13uQ=' keyfile=/root/.strkey
    '''
    if REQ_ERROR['openssl']:
        raise Exception(REQ_ERROR['openssl'])
    key = _get_key(size_limit=32, trim_newline=True, **kwargs)
    #cmd = 'openssl enc -d -base64 -aes-256-cbc -pass env:passwd'
    #r = __salt__['cmd.run'](env={'passwd': key}, stdin=data, cmd=cmd)
    ## TDO: stdin gives .. error reading input file
    cmd = ' echo -e "{0}" | openssl enc -d -base64 -aes-256-cbc -pass env:passwd'
    r = __salt__['cmd.shell'](env={'passwd': key}, cmd=cmd.format(data))
    if 'bad decrypt' in r or 'bad magic number' in r:
        raise Exception(r)
    return r


def xor_enc(data, **kwargs):
    '''
    Use PyCrypto to XOR encode data.

    A weak crypto!
    Prefer `cipher.vigenere_enc`

    If the `key` is larger than 32 bytes.
    The md5sum of the key will be used as the password.

    CLI Examples:

    .. code-block:: bash

        salt-call cipher.xor_enc datatoenc
        salt-call cipher.xor_enc datatoenc key=nevertell
        salt-call cipher.xor_enc datatoenc keyfile=/root/.strkey
    '''
    if REQ_ERROR['crypto']:
        raise Exception(REQ_ERROR['crypto'])
    key = _get_key(**kwargs)
    key = hashlib.sha256(key).digest()
    cipher = XOR.new(key)
    return base64.b64encode(cipher.encrypt(data))


def xor_dec(data, **kwargs):
    '''
    Use PyCrypto to XOR decode data.

    A weak crypto!
    Prefer `cipher.vigenere_dec`

    CLI Examples:

    .. code-block:: bash

        salt-call cipher.xor_dec SUxZTFktICkq
        salt-call cipher.xor_dec data='SUxZTFktICkq=' key=nevertell
        salt-call cipher.xor_dec data='SUxZTFktICkq=' keyfile=/root/.strkey
    '''
    if REQ_ERROR['crypto']:
        raise Exception(REQ_ERROR['crypto'])
    key = _get_key(**kwargs)
    key = hashlib.sha256(key).digest()
    cipher = XOR.new(key)
    return cipher.decrypt(base64.b64decode(data))


def vigenere_enc(data, **kwargs):
    '''
    Use vigenere cipher to encode data that can be decoded using vigenere_dec.

    This is a weak crypto. However there is little dependicies
    and it provides basic protection.

    CLI Examples:

    .. code-block:: bash

        salt-call cipher.vigenere_enc datatoenc
        salt-call cipher.vigenere_enc datatoenc key=nevertell
        salt-call cipher.vigenere_enc datatoenc keyfile=/root/.strkey
    '''
    key = _get_key(**kwargs)
    key = hashlib.sha256(key).digest()
    d = []
    for i in range(len(data)):
        kc = key[i % len(key)]
        dc = chr((ord(data[i]) + ord(kc)) % 256)
        d.append(dc)
    return base64.b64encode("".join(d))


def vigenere_dec(data, **kwargs):
    '''
    Use vigenere cipher to decode output from vigenere_enc.

    This is a weak crypto. However there is little dependicies
    and it provides basic protection.

    CLI Examples:

    .. code-block:: bash

        salt-call cipher.vigenere_dec 26vmuZ+7tuGu
        salt-call cipher.vigenere_dec data='26vmuZ+7tuGu' key=nevertell
        salt-call cipher.vigenere_dec data='26vmuZ+7tuGu' keyfile=/root/.strkey
    '''
    key = _get_key(**kwargs)
    key = hashlib.sha256(key).digest()
    d = []
    data = base64.b64decode(data)
    for i in range(len(data)):
        kc = key[i % len(key)]
        dc = chr((256 + ord(data[i]) - ord(kc)) % 256)
        d.append(dc)
    return "".join(d)
