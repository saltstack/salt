import copy
import datetime
import logging
import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed25519, rsa

import salt.utils.files
import salt.utils.timeutil as time

try:
    from cryptography.hazmat.primitives.serialization import (
        SSHCertificate,
        SSHCertificateBuilder,
        SSHCertificateType,
        load_ssh_private_key,
        load_ssh_public_identity,
        load_ssh_public_key,
    )

    CERT_SUPPORT = True
except ImportError:
    CERT_SUPPORT = False
    from cryptography.hazmat.primitives.serialization import (
        load_ssh_private_key,
        load_ssh_public_key,
    )

from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.utils import x509

SSH_PRIVKEYS = (
    ec.EllipticCurvePrivateKey,
    rsa.RSAPrivateKey,
    dsa.DSAPrivateKey,
    ed25519.Ed25519PrivateKey,
)

SSH_PUBKEYS = (
    ec.EllipticCurvePublicKey,
    rsa.RSAPublicKey,
    dsa.DSAPublicKey,
    ed25519.Ed25519PublicKey,
)

log = logging.getLogger(__name__)


def build_crt(
    signing_private_key,
    cert_type,
    valid_principals=None,
    all_principals=False,
    skip_load_signing_private_key=False,
    signing_private_key_passphrase=None,
    public_key=None,
    private_key=None,
    private_key_passphrase=None,
    serial_number=None,
    key_id=None,
    not_before=None,
    not_after=None,
    ttl=None,
    critical_options=None,
    extensions=None,
):
    """
    Parse the input into an SSHCertificateBuilder, which can be used
    to sign the certificate or be inspected for changes.

    Also returns the signing private key (if available).
    """
    if CERT_SUPPORT is False:
        raise CommandExecutionError(
            "Certificate support requires at least cryptography release 40"
        )
    if cert_type == "user":
        cert_type = SSHCertificateType.USER
        ttl = ttl if ttl is not None else 86400  # 1d
    elif cert_type == "host":
        cert_type = SSHCertificateType.HOST
        ttl = ttl if ttl is not None else 2592000  # 30d
    else:
        raise SaltInvocationError(
            f"Cert type needs to be either `user` or `host`, got '{cert_type}'"
        )

    if not skip_load_signing_private_key:
        # Skipping this is necessary for the state module to be able to check
        # for changes when issuing certificates from a remote.
        signing_private_key = load_privkey(
            signing_private_key, passphrase=signing_private_key_passphrase
        )
    else:
        signing_private_key = None
    serial_number = _get_serial_number(serial_number)

    if private_key:
        private_key_loaded = load_privkey(
            private_key, passphrase=private_key_passphrase
        )
        public_key = private_key_loaded.public_key()
    elif public_key:
        public_key = load_pubkey(public_key)
    else:
        raise SaltInvocationError(
            "Need public_key or private_key to derive public key to sign"
        )

    builder = (
        SSHCertificateBuilder()
        .public_key(public_key)
        .serial(serial_number)
        .type(cert_type)
    )
    if key_id is not None:
        if isinstance(key_id, str):
            key_id = key_id.encode()
        builder = builder.key_id(key_id)

    if valid_principals:
        builder = builder.valid_principals(
            [
                principal.encode() if isinstance(principal, str) else principal
                for principal in (valid_principals or [])
            ]
        )
    elif all_principals:
        builder = builder.valid_for_all_principals()
    else:
        raise SaltInvocationError(
            "Must either set all_principals to true or specify principals to allow"
        )

    not_before = (
        datetime.datetime.strptime(not_before, x509.TIME_FMT).timestamp()
        if not_before
        else datetime.datetime.utcnow().timestamp()
    )
    not_after = (
        datetime.datetime.strptime(not_after, x509.TIME_FMT).timestamp()
        if not_after
        else (
            datetime.datetime.utcnow()
            + datetime.timedelta(seconds=time.timestring_map(ttl))
        ).timestamp()
    )
    builder = builder.valid_after(not_before).valid_before(not_after)

    for opt, val in (critical_options or {}).items():
        if val:
            if val is True:
                val = ""
            builder = builder.add_critical_option(opt.encode(), val.encode())
    for ext, extval in (extensions or {}).items():
        if extval:
            if extval is True:
                extval = ""
            builder = builder.add_extension(ext.encode(), extval.encode())

    return builder, signing_private_key


def _get_serial_number(sn=None):
    """
    Parses a serial number into bytes, or returns a random one.
    The serial number must be < 2**64.
    """
    if sn is None:
        return int.from_bytes(os.urandom(8), "big") >> 1

    if isinstance(sn, int):
        return sn
    try:
        sn = bytes.fromhex(sn.replace(":", ""))
    except (AttributeError, TypeError, ValueError):
        pass
    if isinstance(sn, bytes):
        return int.from_bytes(sn, "big")
    raise CommandExecutionError(f"Could not parse serial number {sn}")


def load_privkey(pk, passphrase=None):
    """
    Return an SSH private key instance from
    * a class instance
    * a file path on the local system
    * a string
    * bytes
    """
    if hasattr(pk, "private_bytes"):
        if isinstance(pk, SSH_PRIVKEYS):
            return pk
        raise SaltInvocationError(
            f"Passed object is not an SSH private key, but {pk.__class__.__name__}"
        )
    pk = load_file_or_bytes(pk)
    passphrase = passphrase.encode() if passphrase is not None else None
    try:
        return load_ssh_private_key(pk, password=passphrase)
    except ValueError as err:
        if "Key is password-protected" in str(err):
            raise SaltInvocationError(
                "Private key is encrypted. Please provide a password."
            ) from err
        if "Corrupt data: broken checksum" in str(err):
            raise SaltInvocationError("Bad decrypt - is the password correct?") from err
        raise CommandExecutionError("Could not load OpenSSH private key") from err


def load_pubkey(pk):
    """
    Return a public key instance from
    * a class instance
    * a file path on the local system
    * a string
    * bytes
    """
    if hasattr(pk, "public_bytes"):
        if isinstance(pk, SSH_PUBKEYS):
            return pk
        raise SaltInvocationError(
            f"Passed object is not an SSH public key, but {pk.__class__.__name__}"
        )

    pk = load_file_or_bytes(pk)
    try:
        return load_ssh_public_key(pk)
    except ValueError as err:
        raise CommandExecutionError("Could not load OpenSSH public key.") from err


def load_file_or_bytes(fob):
    """
    Tries to load a reference and return its bytes.
    Can be a file path on the local system, a string and bytes (hex/base64-encoded, raw)
    """
    if x509.isfile(fob):
        with salt.utils.files.fopen(fob, "rb") as f:
            fob = f.read()
    if isinstance(fob, str):
        fob = fob.encode()
    if not isinstance(fob, bytes):
        raise SaltInvocationError(
            "Could not load provided source. You need to pass an existing file, "
            "string or raw bytes."
        )
    return fob


def load_cert(cert, verify=True):
    """
    Return a certificate instance from
    * a class instance
    * a file path on the local system
    * a string
    * bytes
    """
    if CERT_SUPPORT is False:
        raise CommandExecutionError(
            "Certificate support requires at least cryptography release 40"
        )
    if isinstance(cert, SSHCertificate):
        return cert
    cert = load_file_or_bytes(cert)
    try:
        ret = load_ssh_public_identity(cert)
    except ValueError as err:
        raise CommandExecutionError("Could not load OpenSSH certificate.") from err
    if isinstance(ret, SSHCertificate):
        try:
            if verify:
                ret.verify_cert_signature()
            return ret
        except InvalidSignature as err:
            raise CommandExecutionError(
                "The signature on the SSH certificate was invalid"
            ) from err
    raise SaltInvocationError(
        f"The data decoded to a {ret.__class__.__name__}, not SSHCertificate"
    )


def merge_signing_policy(policy, kwargs):
    """
    Merge a signing policy.

    This is found in utils since the state module needs
    access as well to check for expected changes.
    """
    if not policy:
        return kwargs

    # Ensure we don't modify data that is used elsewhere.
    policy = copy.deepcopy(policy)

    # These are handled separately.
    forced_opts = policy.pop("critical_options", None) or {}
    default_opts = policy.pop("default_critical_options", None) or {}
    allowed_opts = policy.pop("allowed_critical_options", ["*"])
    all_opts_allowed = "*" in allowed_opts

    forced_exts = policy.pop("extensions", None) or {}
    default_exts = policy.pop("default_extensions", None) or {}
    allowed_exts = policy.pop("allowed_extensions", ["*"])
    all_exts_allowed = "*" in allowed_exts

    allowed_principals = policy.pop(
        "allowed_valid_principals", policy.pop("valid_principals", None)
    )
    default_principals = policy.pop("default_valid_principals", allowed_principals)

    default_ttl = time.timestring_map(policy.pop("ttl", None))
    max_ttl = time.timestring_map(policy.pop("max_ttl", default_ttl))
    requested_ttl = time.timestring_map(kwargs.pop("ttl", None))
    requested_days_valid = kwargs.pop("days_valid", None)

    final_opts = default_opts
    for opt, optval in (kwargs.get("critical_options") or {}).items():
        if all_opts_allowed or opt in allowed_opts:
            final_opts[opt] = optval
    final_opts.update(forced_opts)
    kwargs["critical_options"] = final_opts or None

    final_exts = default_exts
    for ext, extval in (kwargs.get("extensions") or {}).items():
        if all_exts_allowed or ext in allowed_exts:
            final_exts[ext] = extval
    final_exts.update(forced_exts)
    kwargs["extensions"] = final_exts or None

    # Ensure valid_principals can only be a subset of
    # the ones defined in the policy.
    if allowed_principals is not None:
        if kwargs.get("valid_principals"):
            kwargs["valid_principals"] = (
                list(
                    set(allowed_principals).intersection(
                        set(kwargs["valid_principals"])
                    )
                )
                or default_principals
            )
        elif kwargs.pop("all_principals", None):
            kwargs["valid_principals"] = allowed_principals
        else:
            kwargs["valid_principals"] = default_principals

    if requested_days_valid is not None and requested_ttl is None:
        requested_ttl = time.timestring_map(f"{requested_days_valid}d")
    if requested_ttl is None:
        kwargs["ttl"] = default_ttl if default_ttl is not None else max_ttl
    elif max_ttl is not None:
        if requested_ttl > max_ttl:
            kwargs["ttl"] = max_ttl
        else:
            kwargs["ttl"] = requested_ttl
    else:
        kwargs["ttl"] = requested_ttl

    # Update the kwargs with the remaining signing policy
    kwargs.update(policy)

    return kwargs
