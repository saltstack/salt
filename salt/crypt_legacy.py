"""
Cryptographic implimentation using legacy libraries. The pycrypto and
pycryptodomex implimentations are being preserved for use with salt-ssh's thin
directory.
"""

import hashlib
import hmac
import logging
import os

import salt.utils.crypt
import salt.utils.files
import salt.utils.stringutils
from salt.exceptions import AuthenticationError, InvalidKeyError

try:
    from Cryptodome import Random
    from Cryptodome.Cipher import AES, PKCS1_OAEP
    from Cryptodome.Cipher import PKCS1_v1_5 as PKCS1_v1_5_CIPHER
    from Cryptodome.Hash import SHA
    from Cryptodome.PublicKey import RSA
    from Cryptodome.Signature import PKCS1_v1_5

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

if not HAS_CRYPTO:
    try:
        # let this be imported, if possible
        from Crypto import Random  # nosec
        from Crypto.Cipher import AES, PKCS1_OAEP  # nosec
        from Crypto.Cipher import PKCS1_v1_5 as PKCS1_v1_5_CIPHER  # nosec
        from Crypto.Hash import SHA  # nosec
        from Crypto.PublicKey import RSA  # nosec
        from Crypto.Signature import PKCS1_v1_5  # nosec

        HAS_CRYPTO = True
    except ImportError:
        HAS_CRYPTO = False

log = logging.getLogger(__name__)

if HAS_CRYPTO:

    def pwdata_decrypt(rsa_key, pwdata):
        dsize = SHA.digest_size
        sentinel = Random.new().read(15 + dsize)
        key_obj = RSA.importKey(rsa_key)
        key_obj = PKCS1_v1_5_CIPHER.new(key_obj)
        password = key_obj.decrypt(pwdata, sentinel)
        return salt.utils.stringutils.to_unicode(password)

    def generate_private_key(size, e):
        salt.utils.crypt.reinit_crypto()
        return RSA.generate(bits=size, e=65537)

    def public_from_private(private_key):
        return private_key.publickey()

    def save_private_key(path, key, passphrase=None):
        with salt.utils.files.fopen(path, "wb+") as f:
            f.write(key.exportKey("PEM", passphrase))

    def save_public_key(path, key):
        with salt.utils.files.fopen(path, "wb+") as f:
            f.write(key.exportKey("PEM"))

    def aes_encrypt(aes_key, hmac_key, data, block_size=16):
        pad = block_size - len(data) % block_size
        data = data + salt.utils.stringutils.to_bytes(pad * chr(pad))
        iv_bytes = os.urandom(block_size)
        cypher = AES.new(aes_key, AES.MODE_CBC, iv_bytes)
        encr = cypher.encrypt(data)
        data = iv_bytes + encr
        sig = hmac.new(hmac_key, data, hashlib.sha256).digest()
        return data + sig

    def aes_decrypt(
        aes_key, hmac_key, data, block_size=16, sig_size=hashlib.sha256().digest_size
    ):
        sig = data[-sig_size:]
        data = data[:-sig_size]
        if not isinstance(data, bytes):
            data = salt.utils.stringutils.to_bytes(data)
        mac_bytes = hmac.new(hmac_key, data, hashlib.sha256).digest()
        if len(mac_bytes) != len(sig):
            log.debug("Failed to authenticate message")
            raise AuthenticationError("message authentication failed")
        result = 0
        for zipped_x, zipped_y in zip(mac_bytes, sig):
            result |= zipped_x ^ zipped_y
        if result != 0:
            log.debug("Failed to authenticate message")
            raise AuthenticationError("message authentication failed")
        iv_bytes = data[:block_size]
        data = data[block_size:]
        cypher = AES.new(aes_key, AES.MODE_CBC, iv_bytes)
        data = cypher.decrypt(data)
        return data[: -data[-1]]

    class PrivateKey:
        def __init__(self, path, passphrase=None):
            with salt.utils.files.fopen(path) as f:
                self.key = RSA.importKey(f.read(), passphrase)

        def encrypt(self, data):
            return salt.utils.rsax931.RSAX931Signer(self.key.exportKey("PEM")).sign(
                data
            )

        def sign(self, data):
            signer = PKCS1_v1_5.new(self.key)
            return signer.sign(SHA.new(salt.utils.stringutils.to_bytes(data)))

        def decrypt(self, data):
            cipher = PKCS1_OAEP.new(self.key)
            return cipher.decrypt(data)

    class PublicKey:
        def __init__(self, path):
            with salt.utils.files.fopen(path) as f:
                try:
                    self.key = RSA.importKey(f.read())
                except (ValueError, IndexError, TypeError):
                    raise InvalidKeyError("Encountered bad RSA public key")

        def encrypt(self, data):
            bdata = salt.utils.stringutils.to_bytes(data)
            return PKCS1_OAEP.new(self.key).encrypt(bdata)

        def verify(self, data, signature):
            verifier = PKCS1_v1_5.new(self.key)
            return verifier.verify(
                SHA.new(salt.utils.stringutils.to_bytes(data)), signature
            )

        def decrypt(self, data):
            data = salt.utils.stringutils.to_bytes(data)
            verifier = salt.utils.rsax931.RSAX931Verifier(self.key.exportKey("PEM"))
            return verifier.verify(data)
