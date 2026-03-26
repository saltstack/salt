import base64
import hashlib
import logging
from pathlib import Path

from cryptography.exceptions import InvalidSignature as CryptographyInvalidSig
from cryptography.hazmat.primitives.asymmetric import ec, padding, utils

from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.utils import x509
from salt.utils.hashutils import get_hash

log = logging.getLogger(__name__)

DEFAULT_HASHALG = "sha256"


class InvalidSignature(CommandExecutionError):
    """
    Raised when a signature is invalid.
    We save the file hash to avoid computing it multiple times for
    signed_by_any, if a path has been passed in and the signature algorithm
    supports prehashed data.
    """

    def __init__(self, *args, file_digest=None, data=None, pubkey=None):
        super().__init__(*args)
        self.file_digest = file_digest
        self.data = data
        self.pubkey = pubkey


def fingerprint(pubkey):
    """
    Return the SHA256 hexdigest of a pubkey's DER representation.

    pub
        The public key to calculate the fingerprint of.
        Can be any reference that can be passed to ``salt.utils.x509.load_pubkey``.
    """
    pubkey = x509.load_pubkey(pubkey)
    hsh = getattr(hashlib, DEFAULT_HASHALG)()
    hsh.update(x509.to_der(pubkey))
    return hsh.hexdigest()


def sign(privkey, data, digest=None, passphrase=None):
    """
    Sign data with a private key.

    privkey
        The private key to sign with. Can be any reference that can be passed
        to ``salt.utils.x509.load_privkey``.

    data
        The data to sign. Should be either ``str``, ``bytes`` or ``pathlib.Path`` object.

    digest
        The name of the hashing algorithm to use when creating signatures.
        Defaults to ``sha256``. Only relevant for ECDSA or RSA.

    passphrase
        If the private key is encrypted, the passphrase to decrypt it. Optional.
    """
    privkey = x509.load_privkey(privkey, passphrase=passphrase)
    key_type = x509.get_key_type(privkey)
    prehashed = False
    if isinstance(data, Path):
        if key_type in (x509.KEY_TYPE.RSA, x509.KEY_TYPE.EC):
            data = _get_file_digest(data, digest)
            prehashed = True
        else:
            data = data.read_bytes()
    elif isinstance(data, str):
        data = data.encode()
    if key_type == x509.KEY_TYPE.RSA:
        return _sign_rsa(privkey, data, digest, prehashed=prehashed)
    if key_type == x509.KEY_TYPE.EC:
        return _sign_ec(privkey, data, digest, prehashed=prehashed)
    if key_type == x509.KEY_TYPE.ED25519:
        return _sign_ed25519(privkey, data)
    if key_type == x509.KEY_TYPE.ED448:
        return _sign_ed448(privkey, data)
    raise CommandExecutionError(f"Unknown private key type: {privkey.__class__}")


def try_base64(data):
    """
    Check if the data is valid base64 and return the decoded
    bytes if so, otherwise return the data untouched.
    """
    try:
        if isinstance(data, str):
            data = data.encode("ascii", "strict")
        elif isinstance(data, bytes):
            pass
        else:
            raise CommandExecutionError("is_base64 only works with strings and bytes")
        decoded = base64.b64decode(data)
        if base64.b64encode(decoded) == data.replace(b"\n", b""):
            return decoded
        return data
    except (TypeError, ValueError):
        return data


def load_sig(sig):
    """
    Try to load an input that represents a signature into the signature's bytes.

    sig
        The reference to load. Can either be a base64-encoded string or a path
        to a local file in base64 encoding or raw bytes.
    """
    if x509.isfile(sig):
        sig = Path(sig).read_bytes()
    sig = try_base64(sig)
    if isinstance(sig, bytes):
        return sig
    raise CommandExecutionError(
        f"Failed loading signature '{sig}' as file and/or base64 string"
    )


def verify(pubkey, sig, data, digest=None, file_digest=None):
    """
    Verify a signature against a public key.

    On success, returns a tuple of (data, file_digest), which can reused
    by the callee when multiple signatures are checked against the same file.
    This avoids reading the file/calculating the digest multiple times.

    On failure, raises an InvalidSignature exception which carries
    ``data`` and ``file_digest`` attributes with the corresponding values.

    pub
        The public key to verify the signature against.
        Can be any reference that can be passed to ``salt.utils.x509.load_pubkey``.

    sig
        The signature to verify.
        Can be any reference that can be passed to ``salt.utils.asymmetric.load_sig``.

    data
        The data to sign. Should be either ``str``, ``bytes`` or ``pathlib.Path`` object.
        Ignored when ``file_digest`` is passed and the signing algorithm is either
        ECDSA or RSA.

    digest
        The name of the hashing algorithm to use when creating signatures.
        Defaults to ``sha256``. Only relevant for ECDSA or RSA.

    file_digest
        The ECDSA and RSA algorithms can be invoked with a precalculated digest
        in order to avoid loading the whole file into memory. This happens automatically
        during the execution of this function, but when checking multiple signatures,
        you can cache the calculated value and pass it back in.
    """
    pubkey = x509.load_pubkey(pubkey)
    signature = load_sig(sig)
    key_type = x509.get_key_type(pubkey)
    sig_data = data
    if key_type in (x509.KEY_TYPE.RSA, x509.KEY_TYPE.EC):
        if file_digest:
            sig_data = file_digest
        elif isinstance(data, Path):
            file_digest = sig_data = _get_file_digest(data, digest)
        elif isinstance(data, str):
            sig_data = data.encode()
    elif isinstance(data, Path):
        data = sig_data = data.read_bytes()
    elif isinstance(data, str):
        data = sig_data = data.encode()

    try:
        if key_type == x509.KEY_TYPE.RSA:
            _verify_rsa(
                pubkey,
                signature,
                sig_data,
                digest or DEFAULT_HASHALG,
                prehashed=bool(file_digest),
            )
            return data, file_digest
        if key_type == x509.KEY_TYPE.EC:
            _verify_ec(
                pubkey,
                signature,
                sig_data,
                digest or DEFAULT_HASHALG,
                prehashed=bool(file_digest),
            )
            return data, file_digest
        if key_type == x509.KEY_TYPE.ED25519:
            _verify_ed25519(pubkey, signature, sig_data)
            return data, file_digest
        if key_type == x509.KEY_TYPE.ED448:
            _verify_ed448(pubkey, signature, sig_data)
            return data, file_digest
    except CryptographyInvalidSig as err:
        raise InvalidSignature(
            f"Invalid signature for key {fingerprint(pubkey)}",
            file_digest=file_digest,
            data=data,
            pubkey=pubkey,
        ) from err
    raise SaltInvocationError(f"Unknown public key type: {pubkey.__class__}")


def _sign_rsa(priv, data, digest, prehashed=False):
    pad_hashalg = sig_hashalg = x509.get_hashing_algorithm(digest or DEFAULT_HASHALG)
    if prehashed:
        sig_hashalg = utils.Prehashed(sig_hashalg)
    return priv.sign(
        data,
        padding.PSS(mgf=padding.MGF1(pad_hashalg), salt_length=padding.PSS.MAX_LENGTH),
        sig_hashalg,
    )


def _sign_ec(priv, data, digest, prehashed=False):
    hashalg = x509.get_hashing_algorithm(digest or DEFAULT_HASHALG)
    if prehashed:
        hashalg = utils.Prehashed(hashalg)
    return priv.sign(data, ec.ECDSA(hashalg))


def _sign_ed25519(priv, data):
    return priv.sign(data)


def _sign_ed448(priv, data):
    return priv.sign(data)


def _verify_rsa(pub, sig, data, digest=DEFAULT_HASHALG, prehashed=False):
    pad_hashalg = sig_hashalg = x509.get_hashing_algorithm(digest)
    if prehashed:
        sig_hashalg = utils.Prehashed(sig_hashalg)
    # Technically, scheme hash function and the MGF hash function can be different,
    # but that's not common practice.
    pad = padding.PSS(mgf=padding.MGF1(pad_hashalg), salt_length=padding.PSS.AUTO)
    pub.verify(sig, data, pad, sig_hashalg)


def _verify_ec(pub, sig, data, digest=DEFAULT_HASHALG, prehashed=False):
    hashalg = x509.get_hashing_algorithm(digest)
    if prehashed:
        hashalg = utils.Prehashed(hashalg)
    pub.verify(sig, data, ec.ECDSA(hashalg))


def _verify_ed25519(pub, sig, data):
    pub.verify(sig, data)


def _verify_ed448(pub, sig, data):
    pub.verify(sig, data)


def _get_file_digest(file, digest):
    hexdigest = get_hash(file, digest or DEFAULT_HASHALG)
    return bytes.fromhex(hexdigest)
