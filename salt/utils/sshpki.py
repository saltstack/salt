import copy
import logging
import os
from datetime import datetime, timedelta, timezone

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed25519, rsa

import salt.utils.files
import salt.utils.timeutil as time
import salt.utils.x509 as x509util

try:
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
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
        Encoding,
        PublicFormat,
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
        datetime.strptime(not_before, x509.TIME_FMT).timestamp()
        if not_before
        else datetime.now(tz=timezone.utc).timestamp()
    )
    not_after = (
        datetime.strptime(not_after, x509.TIME_FMT).timestamp()
        if not_after
        else (
            datetime.now(tz=timezone.utc) + timedelta(seconds=time.timestring_map(ttl))
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


def check_cert_changes(
    name,
    signing_policy_contents,
    ca_server=None,
    ttl=None,
    ttl_remaining=None,
    backend=None,
    signing_private_key=None,
    signing_private_key_passphrase=None,
    cert_type=None,
    public_key=None,
    private_key=None,
    private_key_passphrase=None,
    serial_number=None,
    not_before=None,
    not_after=None,
    critical_options=None,
    extensions=None,
    valid_principals=None,
    all_principals=None,
    key_id=None,
):
    """
    Check if the on-disk certificate needs to be updated.
    Extracted from the state module to be able to use this in the SSH wrapper.
    """
    if CERT_SUPPORT is False:
        raise CommandExecutionError(
            "Certificate support requires at least cryptography release 40"
        )
    current = None
    changes = {}
    replace = False

    try:
        current = load_cert(name)
    except CommandExecutionError as err:
        if any(
            (
                "Could not deserialize binary data" in str(err),
                "Could not load OpenSSH certificate" in str(err),
            )
        ):
            replace = True
        else:
            raise
    else:
        if current.type == SSHCertificateType.USER:
            ttl_remaining = ttl_remaining if ttl_remaining is not None else 3600  # 1h
        elif current.type == SSHCertificateType.HOST:
            ttl_remaining = ttl_remaining if ttl_remaining is not None else 604800  # 7d
        else:
            raise CommandExecutionError(f"Unknown cert_type: {current.type}")
        if datetime.fromtimestamp(current.valid_before, tz=timezone.utc) < datetime.now(
            tz=timezone.utc
        ) + timedelta(seconds=time.timestring_map(ttl_remaining)):
            changes["expiration"] = True

        (builder, _), signing_pubkey = _build_cert_with_policy(
            ca_server=ca_server,
            backend=backend,
            signing_policy_contents=signing_policy_contents,
            signing_private_key=signing_private_key,
            signing_private_key_passphrase=signing_private_key_passphrase,
            cert_type=cert_type,
            public_key=public_key,
            private_key=private_key,
            private_key_passphrase=private_key_passphrase,
            serial_number=serial_number,
            not_before=not_before,
            not_after=not_after,
            ttl=ttl,
            critical_options=critical_options,
            extensions=extensions,
            valid_principals=valid_principals,
            all_principals=all_principals,
            key_id=key_id,
        )

        changes.update(
            _compare_cert(
                current,
                builder,
                serial_number=serial_number,
                not_before=not_before,
                not_after=not_after,
                signing_pubkey=signing_pubkey,
            )
        )
    return current, changes, replace


def _build_cert_with_policy(
    ca_server,
    signing_policy_contents,
    signing_private_key,
    backend=None,
    **kwargs,
):
    backend = backend or "ssh_pki"
    skip_load_signing_private_key = False
    final_kwargs = copy.deepcopy(kwargs)
    merge_signing_policy(signing_policy_contents, final_kwargs)
    signing_pubkey = final_kwargs.pop("signing_public_key", None)
    if ca_server is None and backend == "ssh_pki":
        if not signing_private_key:
            raise SaltInvocationError(
                "signing_private_key is required - this is most likely a bug"
            )
        signing_pubkey = load_privkey(
            signing_private_key, passphrase=kwargs.get("signing_private_key_passphrase")
        )
    elif signing_pubkey is None:
        raise SaltInvocationError(
            "The remote CA server or backend module did not deliver the CA pubkey"
        )
    else:
        skip_load_signing_private_key = True

    return (
        build_crt(
            signing_private_key,
            skip_load_signing_private_key=skip_load_signing_private_key,
            **final_kwargs,
        ),
        signing_pubkey,
    )


def _compare_cert(
    current, builder, serial_number, not_before, not_after, signing_pubkey
):
    changes = {}

    if (
        serial_number is not None
        and _getattr_safe(builder, "_serial") != current.serial
    ):
        changes["serial_number"] = serial_number

    if not x509util.match_pubkey(
        _getattr_safe(builder, "_public_key"), current.public_key()
    ):
        changes["private_key"] = True

    if not verify_signature(current, signing_pubkey):
        changes["signing_private_key"] = True

    # Some backends might compute the key ID themselves,
    # so only report changes if it was set.
    if (
        _getattr_safe(builder, "_key_id") is not None
        and builder._key_id != current.key_id
    ):
        changes["key_id"] = {
            "old": current.key_id.decode(),
            "new": builder._key_id.decode(),
        }

    new_cert_type = _getattr_safe(builder, "_type")
    if current.type is not new_cert_type:
        changes["cert_type"] = (
            "user" if new_cert_type is SSHCertificateType.USER else "host"
        )

    ext_changes = _compare_exts(current, builder)
    if any(ext_changes.values()):
        changes["extensions"] = ext_changes
    opt_changes = _compare_opts(current, builder)
    if any(opt_changes.values()):
        changes["critical_options"] = opt_changes
    added_principals = []
    removed_principals = []
    valid_new_principals = _getattr_safe(builder, "_valid_principals")
    if valid_new_principals == []:
        if current.valid_principals:
            added_principals = "*ALL*"
    else:
        added_principals = [
            x.decode()
            for x in set(valid_new_principals) - set(current.valid_principals)
        ]
        removed_principals = [
            x.decode()
            for x in set(current.valid_principals) - set(valid_new_principals)
        ]
        if current.valid_principals == []:
            removed_principals = "*ALL*"
    if added_principals or removed_principals:
        changes["principals"] = {
            "added": added_principals,
            "removed": removed_principals,
        }

    return changes


def _compare_exts(current, builder):
    added = []
    changed = []
    removed = []

    builder_extensions = _getattr_safe(builder, "_extensions")

    for ext, extval in builder_extensions:
        try:
            if current.extensions[ext] != extval:
                changed.append(ext.decode())
        except KeyError:
            added.append(ext.decode())

    for ext in current.extensions:
        if not any(x[0] == ext for x in builder_extensions):
            removed.append(ext.decode())

    return {"added": added, "changed": changed, "removed": removed}


def _compare_opts(current, builder):
    added = []
    changed = []
    removed = []

    builder_options = _getattr_safe(builder, "_critical_options")

    for opt, optval in builder_options:
        try:
            if current.critical_options[opt] != optval:
                changed.append(opt.decode())
        except KeyError:
            added.append(opt.decode())

    for opt in current.critical_options:
        if not any(x[0] == opt for x in builder_options):
            removed.append(opt.decode())

    return {"added": added, "changed": changed, "removed": removed}


def _getattr_safe(obj, attr):
    try:
        return getattr(obj, attr)
    except AttributeError as err:
        # Since we cannot get the certificate object without signing,
        # we need to compare attributes marked as internal. At least
        # convert possible exceptions into some description.
        raise CommandExecutionError(
            f"Could not get attribute {attr} from {obj.__class__.__name__}. "
            "Did the internal API of cryptography change?"
        ) from err


def get_public_key(key, passphrase=None):
    """
    Returns a public key derived from some reference.
    The reference should be a public key, certificate or private key.

    key
        A reference to the structure to look the public key up for.

    passphrase
        If ``key`` is encrypted, the passphrase to decrypt it.
    """
    try:
        return encode_public_key(load_pubkey(key)).decode()
    except (CommandExecutionError, SaltInvocationError, UnsupportedAlgorithm):
        pass
    try:
        return encode_public_key(load_cert(key).public_key()).decode()
    except (CommandExecutionError, SaltInvocationError, UnsupportedAlgorithm):
        pass
    try:
        return encode_public_key(
            load_privkey(key, passphrase=passphrase).public_key()
        ).decode()
    except (CommandExecutionError, SaltInvocationError):
        pass
    except UnsupportedAlgorithm as err:
        if "Need bcrypt module" in str(err):
            raise CommandExecutionError(str(err))
    raise CommandExecutionError(
        "Could not load key as certificate, public key or private key"
    )


def encode_public_key(public_key):
    """
    Serializes a public key object into a string
    """
    return public_key.public_bytes(
        encoding=Encoding.OpenSSH,
        format=PublicFormat.OpenSSH,
    )


def verify_signature(certificate, signing_pub_key, signing_pub_key_passphrase=None):
    """
    Verify that a signature on a certificate was made
    by the private key corresponding to the public key associated
    with the specified certificate.

    certificate
        The certificate to check the signature on.

    signing_pub_key
        Any reference that can be passed to ``get_public_key`` to retrieve
        the public key of the signing entity from.

    signing_pub_key_passphrase
        If ``signing_pub_key`` is encrypted, the passphrase to decrypt it.
    """
    cert = load_cert(certificate, verify=False)
    pubkey = load_pubkey(
        get_public_key(signing_pub_key, passphrase=signing_pub_key_passphrase)
    )
    try:
        cert.verify_cert_signature()
    except InvalidSignature:
        return False
    return x509util.match_pubkey(cert.signature_key(), pubkey)


def split_file_kwargs(kwargs):
    """
    From given kwargs, split valid arguments for file.managed
    and return two dicts, the split args and the rest.
    """
    valid_file_args = [
        "user",
        "group",
        "mode",
        "attrs",
        "makedirs",
        "dir_mode",
        "backup",
        "create",
        "follow_symlinks",
        "check_cmd",
        "tmp_dir",
        "tmp_ext",
        "selinux",
        "file_encoding",
        "encoding_errors",
        "win_owner",
        "win_perms",
        "win_deny_perms",
        "win_inheritance",
        "win_perms_reset",
    ]
    file_args = {"show_changes": False}
    extra_args = {}
    for k, v in kwargs.items():
        if k in valid_file_args:
            file_args[k] = v
        else:
            extra_args[k] = v
    if "file_encoding" in file_args:
        file_args["encoding"] = file_args.pop("file_encoding")
    return file_args, extra_args


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
