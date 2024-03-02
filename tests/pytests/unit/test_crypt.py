import getpass
import logging
import os

import pytest
from cryptography.hazmat.primitives import serialization

import salt.crypt as crypt
import salt.utils.files
import salt.utils.stringutils
from salt.exceptions import InvalidKeyError

try:
    from M2Crypto import BIO, EVP, RSA

    HAS_M2 = True
except ImportError:
    HAS_M2 = False

if not HAS_M2:
    try:
        # from Cryptodome import Random
        # from Cryptodome.Cipher import AES, PKCS1_OAEP
        # from Cryptodome.Cipher import PKCS1_v1_5 as PKCS1_v1_5_CIPHER
        from Cryptodome.Hash import SHA
        from Cryptodome.PublicKey import RSA
        from Cryptodome.Signature import PKCS1_v1_5

        HAS_CRYPTO = True
    except ImportError:
        HAS_CRYPTO = False

if not HAS_M2 and not HAS_CRYPTO:
    try:
        # let this be imported, if possible
        # from Crypto import Random  # nosec
        # from Crypto.Cipher import AES, PKCS1_OAEP  # nosec
        # from Crypto.Cipher import PKCS1_v1_5 as PKCS1_v1_5_CIPHER  # nosec
        from Crypto.Hash import SHA  # nosec
        from Crypto.PublicKey import RSA  # nosec
        from Crypto.Signature import PKCS1_v1_5  # nosec

        HAS_CRYPTO = True
    except ImportError:
        HAS_CRYPTO = False

log = logging.getLogger(__name__)


def legacy_gen_keys(keydir, keyname, keysize, user=None, passphrase=None):
    """
    Generate a RSA public keypair for use with salt

    :param str keydir: The directory to write the keypair to
    :param str keyname: The type of salt server for whom this key should be written. (i.e. 'master' or 'minion')
    :param int keysize: The number of bits in the key
    :param str user: The user on the system who should own this keypair
    :param str passphrase: The passphrase which should be used to encrypt the private key

    :rtype: str
    :return: Path on the filesystem to the RSA private key
    """
    base = os.path.join(keydir, keyname)
    priv = f"{base}.pem"
    pub = f"{base}.pub"

    # gen = rsa.generate_private_key(e, keysize)
    if HAS_M2:
        gen = RSA.gen_key(keysize, 65537, lambda: None)
    else:
        salt.utils.crypt.reinit_crypto()
        gen = RSA.generate(bits=keysize, e=65537)

    if os.path.isfile(priv):
        # Between first checking and the generation another process has made
        # a key! Use the winner's key
        return priv

    # Do not try writing anything, if directory has no permissions.
    if not os.access(keydir, os.W_OK):
        raise OSError(
            'Write access denied to "{}" for user "{}".'.format(
                os.path.abspath(keydir), getpass.getuser()
            )
        )

    with salt.utils.files.set_umask(0o277):
        if HAS_M2:
            # if passphrase is empty or None use no cipher
            if not passphrase:
                gen.save_pem(priv, cipher=None)
            else:
                gen.save_pem(
                    priv,
                    cipher="des_ede3_cbc",
                    callback=lambda x: salt.utils.stringutils.to_bytes(passphrase),
                )
        else:
            with salt.utils.files.fopen(priv, "wb+") as f:
                f.write(gen.exportKey("PEM", passphrase))
    if HAS_M2:
        gen.save_pub_key(pub)
    else:
        with salt.utils.files.fopen(pub, "wb+") as f:
            f.write(gen.publickey().exportKey("PEM"))
    os.chmod(priv, 0o400)
    if user:
        try:
            import pwd

            uid = pwd.getpwnam(user).pw_uid
            os.chown(priv, uid, -1)
            os.chown(pub, uid, -1)
        except (KeyError, ImportError, OSError):
            # The specified user was not found, allow the backup systems to
            # report the error
            pass
    return priv


class LegacyPrivateKey:
    def __init__(self, path, passphrase=None):
        if HAS_M2:
            self.key = RSA.load_key(path, lambda x: bytes(passphrase))
        else:
            with salt.utils.files.fopen(path) as f:
                self.key = RSA.importKey(f.read(), passphrase)

    def encrypt(self, data):
        if HAS_M2:
            return self.key.private_encrypt(data, salt.utils.rsax931.RSA_X931_PADDING)
        else:
            return salt.utils.rsax931.RSAX931Signer(self.key.exportKey("PEM")).sign(
                data
            )

    def sign(self, data):
        if HAS_M2:
            md = EVP.MessageDigest("sha1")
            md.update(salt.utils.stringutils.to_bytes(data))
            digest = md.final()
            return self.key.sign(digest)
        else:
            signer = PKCS1_v1_5.new(self.key)
            return signer.sign(SHA.new(salt.utils.stringutils.to_bytes(data)))


class LegacyPublicKey:
    def __init__(self, path, _HAS_M2=HAS_M2):
        self._HAS_M2 = _HAS_M2
        if self._HAS_M2:
            with salt.utils.files.fopen(path, "rb") as f:
                data = f.read().replace(b"RSA ", b"")
            bio = BIO.MemoryBuffer(data)
            try:
                self.key = RSA.load_pub_key_bio(bio)
            except RSA.RSAError:
                raise InvalidKeyError("Encountered bad RSA public key")
        else:
            with salt.utils.files.fopen(path) as f:
                try:
                    self.key = RSA.importKey(f.read())
                except (ValueError, IndexError, TypeError):
                    raise InvalidKeyError("Encountered bad RSA public key")

    def encrypt(self, data):
        bdata = salt.utils.stringutils.to_bytes(data)
        if self._HAS_M2:
            return self.key.public_encrypt(bdata, salt.crypt.RSA.pkcs1_oaep_padding)
        else:
            return salt.crypt.PKCS1_OAEP.new(self.key).encrypt(bdata)

    def verify(self, data, signature):
        if self._HAS_M2:
            md = EVP.MessageDigest("sha1")
            md.update(salt.utils.stringutils.to_bytes(data))
            digest = md.final()
            try:
                return self.key.verify(digest, signature)
            except RSA.RSAError as exc:
                log.debug("Signature verification failed: %s", exc.args[0])
                return False
        else:
            verifier = PKCS1_v1_5.new(self.key)
            return verifier.verify(
                SHA.new(salt.utils.stringutils.to_bytes(data)), signature
            )

    def decrypt(self, data):
        data = salt.utils.stringutils.to_bytes(data)
        if HAS_M2:
            return self.key.public_decrypt(data, salt.utils.rsax931.RSA_X931_PADDING)
        else:
            verifier = salt.utils.rsax931.RSAX931Verifier(self.key.exportKey("PEM"))
            return verifier.verify(data)


@pytest.fixture
def key_data():
    return [
        "-----BEGIN PUBLIC KEY-----",
        "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoe5QSDYRWKyknbVyRrIj",
        "rm1ht5HgKzAVUber0x54+b/UgxTd1cqI6I+eDlx53LqZSH3G8Rd5cUh8LHoGedSa",
        "E62vEiLAjgXa+RdgcGiQpYS8+Z2RvQJ8oIcZgO+2AzgBRHboNWHTYRRmJXCd3dKs",
        "9tcwK6wxChR06HzGqaOTixAuQlegWbOTU+X4dXIbW7AnuQBt9MCib7SxHlscrqcS",
        "cBrRvq51YP6cxPm/rZJdBqZhVrlghBvIpa45NApP5PherGi4AbEGYte4l+gC+fOA",
        "osEBis1V27djPpIyQS4qk3XAPQg6CYQMDltHqA4Fdo0Nt7SMScxJhfH0r6zmBFAe",
        "BQIDAQAB",
        "-----END PUBLIC KEY-----",
    ]


@pytest.fixture
def passphrase():
    return "pass1234"


@pytest.fixture
def private_key(passphrase, tmp_path):
    keypath = tmp_path / "keys"
    keypath.mkdir()
    keyname = "test"
    keysize = 2048
    return crypt.gen_keys(str(keypath), keyname, keysize, passphrase=passphrase)


@pytest.mark.parametrize("linesep", ["\r\n", "\r", "\n"])
def test__clean_key(key_data, linesep):
    tst_key = linesep.join(key_data)
    chk_key = "\n".join(key_data)
    assert crypt.clean_key(tst_key) == crypt.clean_key(chk_key)


@pytest.mark.parametrize("linesep", ["\r\n", "\r", "\n"])
def test__clean_key_mismatch(key_data, linesep):
    tst_key = linesep.join(key_data)
    tst_key = tst_key.replace("5", "4")
    chk_key = "\n".join(key_data)
    assert crypt.clean_key(tst_key) != crypt.clean_key(chk_key)


def test_gen_keys_legacy(tmp_path):
    keypath = tmp_path / "keys"
    keypath.mkdir()
    passphrase = "pass1234"
    keyname = "test"
    keysize = 2048
    ret = legacy_gen_keys(str(keypath), keyname, keysize, passphrase=passphrase)
    with salt.utils.files.fopen(ret, "rb") as fp:
        keybytes = fp.read()
        assert keybytes.startswith(b"-----BEGIN RSA PRIVATE KEY-----\n")
        priv = serialization.load_pem_private_key(keybytes, passphrase.encode())
    with salt.utils.files.fopen(ret.replace(".pem", ".pub"), "rb") as fp:
        keybytes = fp.read()
        assert keybytes.startswith(b"-----BEGIN PUBLIC KEY-----\n")


def test_gen_keys(tmp_path):
    keypath = tmp_path / "keys"
    keypath.mkdir()
    passphrase = "pass1234"
    keyname = "test"
    keysize = 2048
    ret = crypt.gen_keys(str(keypath), keyname, keysize, passphrase=passphrase)
    with salt.utils.files.fopen(ret, "rb") as fp:
        keybytes = fp.read()
        assert keybytes.startswith(b"-----BEGIN RSA PRIVATE KEY-----\n")
        priv = serialization.load_pem_private_key(keybytes, passphrase.encode())
    with salt.utils.files.fopen(ret.replace(".pem", ".pub"), "rb") as fp:
        keybytes = fp.read()
        assert keybytes.startswith(b"-----BEGIN PUBLIC KEY-----\n")


def test_legacy_private_key_loading(private_key, passphrase):
    priv = LegacyPrivateKey(private_key, passphrase)
    assert priv.key


def test_private_key_loading(private_key, passphrase):
    priv = crypt.PrivateKey(private_key, passphrase)
    assert priv.key


def test_private_key_signing(private_key, passphrase):
    lpriv = LegacyPrivateKey(private_key, passphrase)
    priv = crypt.PrivateKey(private_key, passphrase)
    data = b"meh"
    signature = priv.sign(data)
    lsignature = lpriv.sign(data)
    assert lsignature == signature


def test_legacy_public_key_verify(private_key, passphrase):
    lpriv = crypt.PrivateKey(private_key, passphrase)
    data = b"meh"
    signature = lpriv.sign(data)
    pubkey = LegacyPublicKey(private_key.replace(".pem", ".pub"))
    assert pubkey.verify(data, signature)


def test_public_key_verify(private_key, passphrase):
    lpriv = LegacyPrivateKey(private_key, passphrase)
    data = b"meh"
    signature = lpriv.sign(data)
    pubkey = crypt.PublicKey(private_key.replace(".pem", ".pub"))
    assert pubkey.verify(data, signature)


def test_public_key_encrypt(private_key, passphrase):
    pubkey = crypt.PublicKey(private_key.replace(".pem", ".pub"))
    data = b"meh"
    enc = pubkey.encrypt(data)

    lpriv = LegacyPrivateKey(private_key, passphrase)
    if crypt.HAS_M2:
        dec = lpriv.key.private_decrypt(enc, crypt.RSA.pkcs1_oaep_padding)
    else:
        cipher = crypt.PKCS1_OAEP.new(lpriv.key)
        dec = cipher.decrypt(enc)

    assert data == dec


def test_private_key_decrypt(private_key, passphrase):
    lpubkey = LegacyPublicKey(private_key.replace(".pem", ".pub"))
    data = b"meh"
    enc = lpubkey.encrypt(data)
    priv = crypt.PrivateKey(private_key, passphrase)
    dec = priv.key.decrypt(
        enc,
        crypt.padding.OAEP(
            mgf=crypt.padding.MGF1(algorithm=crypt.hashes.SHA1()),
            algorithm=crypt.hashes.SHA1(),
            label=None,
        ),
    )

    assert data == dec
