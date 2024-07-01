import getpass
import logging
import os

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
        from Cryptodome import Random
        from Cryptodome.Cipher import AES, PKCS1_OAEP
        from Cryptodome.Cipher import PKCS1_v1_5 as PKCS1_v1_5_CIPHER
        from Cryptodome.Hash import SHA
        from Cryptodome.PublicKey import RSA
        from Cryptodome.Signature import PKCS1_v1_5

        HAS_CRYPTO = True
    except ImportError:
        HAS_CRYPTO = False

if not HAS_M2 and not HAS_CRYPTO:
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
            return self.key.public_encrypt(bdata, RSA.pkcs1_oaep_padding)
        else:
            return PKCS1_OAEP.new(self.key).encrypt(bdata)

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


PRIVKEY_DATA = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "MIIEpAIBAAKCAQEA75GR6ZTv5JOv90Vq8tKhKC7YQnhDIo2hM0HVziTEk5R4UQBW\n"
    "a0CKytFMbTONY2msEDwX9iA0x7F5Lgj0X8eD4ZMsYqLzqjWMekLC8bjhxc+EuPo9\n"
    "Dygu3mJ2VgRC7XhlFpmdo5NN8J2E7B/CNB3R4hOcMMZNZdi0xLtFoTfwU61UPfFX\n"
    "14mV2laqLbvDEfQLJhUTDeFFV8EN5Z4H1ttLP3sMXJvc3EvM0JiDVj4l1TWFUHHz\n"
    "eFgCA1Im0lv8i7PFrgW7nyMfK9uDSsUmIp7k6ai4tVzwkTmV5PsriP1ju88Lo3MB\n"
    "4/sUmDv/JmlZ9YyzTO3Po8Uz3Aeq9HJWyBWHAQIDAQABAoIBAGOzBzBYZUWRGOgl\n"
    "IY8QjTT12dY/ymC05GM6gMobjxuD7FZ5d32HDLu/QrknfS3kKlFPUQGDAbQhbbb0\n"
    "zw6VL5NO9mfOPO2W/3FaG1sRgBQcerWonoSSSn8OJwVBHMFLG3a+U1Zh1UvPoiPK\n"
    "S734swIM+zFpNYivGPvOm/muF/waFf8tF/47t1cwt/JGXYQnkG/P7z0vp47Irpsb\n"
    "Yjw7vPe4BnbY6SppSxscW3KoV7GtJLFKIxAXbxsuJMF/rYe3O3w2VKJ1Sug1VDJl\n"
    "/GytwAkSUer84WwP2b07Wn4c5pCnmLslMgXCLkENgi1NnJMhYVOnckxGDZk54hqP\n"
    "9RbLnkkCgYEA/yKuWEvgdzYRYkqpzB0l9ka7Y00CV4Dha9Of6GjQi9i4VCJ/UFVr\n"
    "UlhTo5y0ZzpcDAPcoZf5CFZsD90a/BpQ3YTtdln2MMCL/Kr3QFmetkmDrt+3wYnX\n"
    "sKESfsa2nZdOATRpl1antpwyD4RzsAeOPwBiACj4fkq5iZJBSI0bxrMCgYEA8GFi\n"
    "qAjgKh81/Uai6KWTOW2kX02LEMVRrnZLQ9VPPLGid4KZDDk1/dEfxjjkcyOxX1Ux\n"
    "Klu4W8ZEdZyzPcJrfk7PdopfGOfrhWzkREK9C40H7ou/1jUecq/STPfSOmxh3Y+D\n"
    "ifMNO6z4sQAHx8VaHaxVsJ7SGR/spr0pkZL+NXsCgYEA84rIgBKWB1W+TGRXJzdf\n"
    "yHIGaCjXpm2pQMN3LmP3RrcuZWm0vBt94dHcrR5l+u/zc6iwEDTAjJvqdU4rdyEr\n"
    "tfkwr7v6TNlQB3WvpWanIPyVzfVSNFX/ZWSsAgZvxYjr9ixw6vzWBXOeOb/Gqu7b\n"
    "cvpLkjmJ0wxDhbXtyXKhZA8CgYBZyvcQb+hUs732M4mtQBSD0kohc5TsGdlOQ1AQ\n"
    "McFcmbpnzDghkclyW8jzwdLMk9uxEeDAwuxWE/UEvhlSi6qdzxC+Zifp5NBc0fVe\n"
    "7lMx2mfJGxj5CnSqQLVdHQHB4zSXkAGB6XHbBd0MOUeuvzDPfs2voVQ4IG3FR0oc\n"
    "3/znuwKBgQChZGH3McQcxmLA28aUwOVbWssfXKdDCsiJO+PEXXlL0maO3SbnFn+Q\n"
    "Tyf8oHI5cdP7AbwDSx9bUfRPjg9dKKmATBFr2bn216pjGxK0OjYOCntFTVr0psRB\n"
    "CrKg52Qrq71/2l4V2NLQZU40Dr1bN9V+Ftd9L0pvpCAEAWpIbLXGDw==\n"
    "-----END RSA PRIVATE KEY-----"
)

PUBKEY_DATA = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA75GR6ZTv5JOv90Vq8tKh\n"
    "KC7YQnhDIo2hM0HVziTEk5R4UQBWa0CKytFMbTONY2msEDwX9iA0x7F5Lgj0X8eD\n"
    "4ZMsYqLzqjWMekLC8bjhxc+EuPo9Dygu3mJ2VgRC7XhlFpmdo5NN8J2E7B/CNB3R\n"
    "4hOcMMZNZdi0xLtFoTfwU61UPfFX14mV2laqLbvDEfQLJhUTDeFFV8EN5Z4H1ttL\n"
    "P3sMXJvc3EvM0JiDVj4l1TWFUHHzeFgCA1Im0lv8i7PFrgW7nyMfK9uDSsUmIp7k\n"
    "6ai4tVzwkTmV5PsriP1ju88Lo3MB4/sUmDv/JmlZ9YyzTO3Po8Uz3Aeq9HJWyBWH\n"
    "AQIDAQAB\n"
    "-----END PUBLIC KEY-----"
)

MSG = b"It's me, Mario"

SIG = (
    b"\x07\xf3\xb1\xe7\xdb\x06\xf4_\xe2\xdc\xcb!F\xfb\xbex{W\x1d\xe4E"
    b"\xd3\r\xc5\x90\xca(\x05\x1d\x99\x8b\x1aug\x9f\x95>\x94\x7f\xe3+"
    b"\x12\xfa\x9c\xd4\xb8\x02]\x0e\xa5\xa3LL\xc3\xa2\x8f+\x83Z\x1b\x17"
    b'\xbfT\xd3\xc7\xfd\x0b\xf4\xd7J\xfe^\x86q"I\xa3x\xbc\xd3$\xe9M<\xe1'
    b"\x07\xad\xf2_\x9f\xfa\xf7g(~\xd8\xf5\xe7\xda-\xa3Ko\xfc.\x99\xcf"
    b"\x9b\xb9\xc1U\x97\x82'\xcb\xc6\x08\xaa\xa0\xe4\xd0\xc1+\xfc\x86"
    b'\r\xe4y\xb1#\xd3\x1dS\x96D28\xc4\xd5\r\xd4\x98\x1a44"\xd7\xc2\xb4'
    b"]\xa7\x0f\xa7Db\x85G\x8c\xd6\x94!\x8af1O\xf6g\xd7\x03\xfd\xb3\xbc"
    b"\xce\x9f\xe7\x015\xb8\x1d]AHK\xa0\x14m\xda=O\xa7\xde\xf2\xff\x9b"
    b"\x8e\x83\xc8j\x11\x1a\x98\x85\xde\xc5\x91\x07\x84!\x12^4\xcb\xa8"
    b"\x98\x8a\x8a&#\xb9(#?\x80\x15\x9eW\xb5\x12\xd1\x95S\xf2<G\xeb\xf1"
    b"\x14H\xb2\xc4>\xc3A\xed\x86x~\xcfU\xd5Q\xfe~\x10\xd2\x9b"
)

SIGNATURE = (
    b"w\xac\xfe18o\xeb\xfb\x14+\x9e\xd1\xb7\x7fe}\xec\xd6\xe1P\x9e\xab"
    b"\xb5\x07\xe0\xc1\xfd\xda#\x04Z\x8d\x7f\x0b\x1f}:~\xb2s\x860u\x02N"
    b'\xd4q"\xb7\x86*\x8f\x1f\xd0\x9d\x11\x92\xc5~\xa68\xac>\x12H\xc2%y,'
    b"\xe6\xceU\x1e\xa3?\x0c,\xf0u\xbb\xd0[g_\xdd\x8b\xb0\x95:Y\x18\xa5*"
    b"\x99\xfd\xf3K\x92\x92 ({\xd1\xff\xd9F\xc8\xd6K\x86e\xf9\xa8\xad\xb0z"
    b"\xe3\x9dD\xf5k\x8b_<\xe7\xe7\xec\xf3\"'\xd5\xd2M\xb4\xce\x1a\xe3$"
    b"\x9c\x81\xad\xf9\x11\xf6\xf5>)\xc7\xdd\x03&\xf7\x86@ks\xa6\x05\xc2"
    b"\xd0\xbd\x1a7\xfc\xde\xe6\xb0\xad!\x12#\xc86Y\xea\xc5\xe3\xe2\xb3"
    b"\xc9\xaf\xfa\x0c\xf2?\xbf\x93w\x18\x9e\x0b\xa2a\x10:M\x05\x89\xe2W.Q"
    b"\xe8;yGT\xb1\xf2\xc6A\xd2\xc4\xbeN\xb3\xcfS\xaf\x03f\xe2\xb4)\xe7\xf6"
    b'\xdbs\xd0Z}8\xa4\xd2\x1fW*\xe6\x1c"\x8b\xd0\x18w\xb9\x7f\x9e\x96\xa3'
    b"\xd9v\xf7\x833\x8e\x01"
)

TEST_KEY = (
    "-----BEGIN RSA PUBLIC KEY-----\n"
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzLtFhsvfbFDFaUgulSEX\n"
    "Gl12XriL1DT78Ef2/u8HHaSMmPie37BLWas/zaHwI6066bIyYQJ/nUCahTaoHM7L\n"
    "GlWc0wOU6zyfpihCRQHil05Y6F+olFBoZuYbFPvtp7/hJx/D7I/0n2o/c7M5i3Y2\n"
    "3sBxAYNooIQHXHUmPQW6C9iu95ylZDW8JQzYy/EI4vCC8yQMdTK8jK1FQV0Sbwny\n"
    "qcMxSyAWDoFbnhh2P2TnO8HOWuUOaXR8ZHOJzVcDl+a6ew+medW090x3K5O1f80D\n"
    "+WjgnG6b2HG7VQpOCfM2GALD/FrxicPilvZ38X1aLhJuwjmVE4LAAv8DVNJXohaO\n"
    "WQIDAQAB\n"
    "-----END RSA PUBLIC KEY-----\n"
)

PRIV_KEY = """
-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEAoAsMPt+4kuIG6vKyw9r3+OuZrVBee/2vDdVetW+Js5dTlgrJ
aghWWn3doGmKlEjqh7E4UTa+t2Jd6w8RSLnyHNJ/HpVhMG0M07MF6FMfILtDrrt8
ZX7eDVt8sx5gCEpYI+XG8Y07Ga9i3Hiczt+fu6HYwu96HggmG2pqkOrn3iGfqBvV
YVFJzSZYe7e4c1PeEs0xYcrA4k+apyGsMtpef8vRUrNicRLc7dAcvfhtgt2DXEZ2
d72t/CR4ygtUvPXzisaTPW0G7OWAheCloqvTIIPQIjR8htFxGTz02STVXfnhnJ0Z
k8KhqKF2v1SQvIYxsZU7jaDgl5i3zpeh58cYOwIDAQABAoIBABZUJEO7Y91+UnfC
H6XKrZEZkcnH7j6/UIaOD9YhdyVKxhsnax1zh1S9vceNIgv5NltzIsfV6vrb6v2K
Dx/F7Z0O0zR5o+MlO8ZncjoNKskex10gBEWG00Uqz/WPlddiQ/TSMJTv3uCBAzp+
S2Zjdb4wYPUlgzSgb2ygxrhsRahMcSMG9PoX6klxMXFKMD1JxiY8QfAHahPzQXy9
F7COZ0fCVo6BE+MqNuQ8tZeIxu8mOULQCCkLFwXmkz1FpfK/kNRmhIyhxwvCS+z4
JuErW3uXfE64RLERiLp1bSxlDdpvRO2R41HAoNELTsKXJOEt4JANRHm/CeyA5wsh
NpscufUCgYEAxhgPfcMDy2v3nL6KtkgYjdcOyRvsAF50QRbEa8ldO+87IoMDD/Oe
osFERJ5hhyyEO78QnaLVegnykiw5DWEF02RKMhD/4XU+1UYVhY0wJjKQIBadsufB
2dnaKjvwzUhPh5BrBqNHl/FXwNCRDiYqXa79eWCPC9OFbZcUWWq70s8CgYEAztOI
61zRfmXJ7f70GgYbHg+GA7IrsAcsGRITsFR82Ho0lqdFFCxz7oK8QfL6bwMCGKyk
nzk+twh6hhj5UNp18KN8wktlo02zTgzgemHwaLa2cd6xKgmAyuPiTgcgnzt5LVNG
FOjIWkLwSlpkDTl7ZzY2QSy7t+mq5d750fpIrtUCgYBWXZUbcpPL88WgDB7z/Bjg
dlvW6JqLSqMK4b8/cyp4AARbNp12LfQC55o5BIhm48y/M70tzRmfvIiKnEc/gwaE
NJx4mZrGFFURrR2i/Xx5mt/lbZbRsmN89JM+iKWjCpzJ8PgIi9Wh9DIbOZOUhKVB
9RJEAgo70LvCnPTdS0CaVwKBgDJW3BllAvw/rBFIH4OB/vGnF5gosmdqp3oGo1Ik
jipmPAx6895AH4tquIVYrUl9svHsezjhxvjnkGK5C115foEuWXw0u60uiTiy+6Pt
2IS0C93VNMulenpnUrppE7CN2iWFAiaura0CY9fE/lsVpYpucHAWgi32Kok+ZxGL
WEttAoGAN9Ehsz4LeQxEj3x8wVeEMHF6OsznpwYsI2oVh6VxpS4AjgKYqeLVcnNi
TlZFsuQcqgod8OgzA91tdB+Rp86NygmWD5WzeKXpCOg9uA+y/YL+0sgZZHsuvbK6
PllUgXdYxqClk/hdBFB7v9AQoaj7K9Ga22v32msftYDQRJ94xOI=
-----END RSA PRIVATE KEY-----
"""


PUB_KEY = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoAsMPt+4kuIG6vKyw9r3
+OuZrVBee/2vDdVetW+Js5dTlgrJaghWWn3doGmKlEjqh7E4UTa+t2Jd6w8RSLny
HNJ/HpVhMG0M07MF6FMfILtDrrt8ZX7eDVt8sx5gCEpYI+XG8Y07Ga9i3Hiczt+f
u6HYwu96HggmG2pqkOrn3iGfqBvVYVFJzSZYe7e4c1PeEs0xYcrA4k+apyGsMtpe
f8vRUrNicRLc7dAcvfhtgt2DXEZ2d72t/CR4ygtUvPXzisaTPW0G7OWAheCloqvT
IIPQIjR8htFxGTz02STVXfnhnJ0Zk8KhqKF2v1SQvIYxsZU7jaDgl5i3zpeh58cY
OwIDAQAB
-----END PUBLIC KEY-----
"""

PRIV_KEY2 = """
-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEAp+8cTxguO6Vg+YO92VfHgNld3Zy8aM3JbZvpJcjTnis+YFJ7
Zlkcc647yPRRwY9nYBNywahnt5kIeuT1rTvTsMBZWvmUoEVUj1Xg8XXQkBvb9Ozy
Gqy/G/p8KDDpzMP/U+XCnUeHiXTZrgnqgBIc2cKeCVvWFqDi0GRFGzyaXLaX3PPm
M7DJ0MIPL1qgmcDq6+7Ze0gJ9SrDYFAeLmbuT1OqDfufXWQl/82JXeiwU2cOpqWq
7n5fvPOWim7l1tzQ+dSiMRRm0xa6uNexCJww3oJSwvMbAmgzvOhqqhlqv+K7u0u7
FrFFojESsL36Gq4GBrISnvu2tk7u4GGNTYYQbQIDAQABAoIBAADrqWDQnd5DVZEA
lR+WINiWuHJAy/KaIC7K4kAMBgbxrz2ZbiY9Ok/zBk5fcnxIZDVtXd1sZicmPlro
GuWodIxdPZAnWpZ3UtOXUayZK/vCP1YsH1agmEqXuKsCu6Fc+K8VzReOHxLUkmXn
FYM+tixGahXcjEOi/aNNTWitEB6OemRM1UeLJFzRcfyXiqzHpHCIZwBpTUAsmzcG
QiVDkMTKubwo/m+PVXburX2CGibUydctgbrYIc7EJvyx/cpRiPZXo1PhHQWdu4Y1
SOaC66WLsP/wqvtHo58JQ6EN/gjSsbAgGGVkZ1xMo66nR+pLpR27coS7o03xCks6
DY/0mukCgYEAuLIGgBnqoh7YsOBLd/Bc1UTfDMxJhNseo+hZemtkSXz2Jn51322F
Zw/FVN4ArXgluH+XsOhvG/MFFpojwZSrb0Qq5b1MRdo9qycq8lGqNtlN1WHqosDQ
zW29kpL0tlRrSDpww3wRESsN9rH5XIrJ1b3ZXuO7asR+KBVQMy/+NcUCgYEA6MSC
c+fywltKPgmPl5j0DPoDe5SXE/6JQy7w/vVGrGfWGf/zEJmhzS2R+CcfTTEqaT0T
Yw8+XbFgKAqsxwtE9MUXLTVLI3sSUyE4g7blCYscOqhZ8ItCUKDXWkSpt++rG0Um
1+cEJP/0oCazG6MWqvBC4NpQ1nzh46QpjWqMwokCgYAKDLXJ1p8rvx3vUeUJW6zR
dfPlEGCXuAyMwqHLxXgpf4EtSwhC5gSyPOtx2LqUtcrnpRmt6JfTH4ARYMW9TMef
QEhNQ+WYj213mKP/l235mg1gJPnNbUxvQR9lkFV8bk+AGJ32JRQQqRUTbU+yN2MQ
HEptnVqfTp3GtJIultfwOQKBgG+RyYmu8wBP650izg33BXu21raEeYne5oIqXN+I
R5DZ0JjzwtkBGroTDrVoYyuH1nFNEh7YLqeQHqvyufBKKYo9cid8NQDTu+vWr5UK
tGvHnwdKrJmM1oN5JOAiq0r7+QMAOWchVy449VNSWWV03aeftB685iR5BXkstbIQ
EVopAoGAfcGBTAhmceK/4Q83H/FXBWy0PAa1kZGg/q8+Z0KY76AqyxOVl0/CU/rB
3tO3sKhaMTHPME/MiQjQQGoaK1JgPY6JHYvly2KomrJ8QTugqNGyMzdVJkXAK2AM
GAwC8ivAkHf8CHrHa1W7l8t2IqBjW1aRt7mOW92nfG88Hck0Mbo=
-----END RSA PRIVATE KEY-----
"""


PUB_KEY2 = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAp+8cTxguO6Vg+YO92VfH
gNld3Zy8aM3JbZvpJcjTnis+YFJ7Zlkcc647yPRRwY9nYBNywahnt5kIeuT1rTvT
sMBZWvmUoEVUj1Xg8XXQkBvb9OzyGqy/G/p8KDDpzMP/U+XCnUeHiXTZrgnqgBIc
2cKeCVvWFqDi0GRFGzyaXLaX3PPmM7DJ0MIPL1qgmcDq6+7Ze0gJ9SrDYFAeLmbu
T1OqDfufXWQl/82JXeiwU2cOpqWq7n5fvPOWim7l1tzQ+dSiMRRm0xa6uNexCJww
3oJSwvMbAmgzvOhqqhlqv+K7u0u7FrFFojESsL36Gq4GBrISnvu2tk7u4GGNTYYQ
bQIDAQAB
-----END PUBLIC KEY-----
"""
