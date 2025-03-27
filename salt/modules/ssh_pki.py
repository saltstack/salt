"""
Manage OpenSSH keys and certificates
====================================

.. versionadded:: 3008.0


:depends: cryptography

.. note::

    * Certificate operations require at least cryptography release 40
    * Certificate operations with ``force-command`` and ``source-address``
      (or any critical option/extension with a value) should only be relied
      upon in releases >= 41.0.2 (https://github.com/pyca/cryptography/issues/9207)
    * Operations with encrypted private keys require the
      ``bcrypt`` module, which is installable as ``cryptography[ssh]`` as well.


Configuration
-------------
Peer communication
~~~~~~~~~~~~~~~~~~
To be able to remotely sign certificates, it is required to configure the Salt
master to allow :term:`Peer Communication`:

.. code-block:: yaml

    # /etc/salt/master.d/peer.conf

    peer:
      .*:
        - ssh_pki.sign_remote_certificate

In order for the :term:`Compound Matcher` to work with restricting signing
policies to a subset of minions, in addition calls to :py:func:`match.compound <salt.modules.match.compound>`
by the minion acting as the CA must be permitted:

.. code-block:: yaml

    # /etc/salt/master.d/peer.conf

    peer:
      .*:
        - ssh_pki.sign_remote_certificate

      ca_server:
        - match.compound

Signing policies
~~~~~~~~~~~~~~~~
In addition, the minion representing the CA needs to have at least one
signing policy configured, remote calls not referencing one are always
rejected.

The parameters specified in this signing policy override any
parameters passed from the minion requesting the certificate. It can be
configured in the CA minion's pillar, which takes precedence, or any
location :py:func:`config.get <salt.modules.config.get>` looks up in.
Signing policies are defined under ``ssh_signing_policies``.

Special handling
^^^^^^^^^^^^^^^^
In addition to forcing some arguments to a specific value, signing policies
can also specify default and allowed values.

allowed_critical_options
    A list of critical option names that can be requested to be set under
    this policy. Defaults to all (``["*"]``).

allowed_extensions
    A list of extension names that can be requested to be set under
    this policy. Defaults to all (``["*"]``).

allowed_valid_principals
    A list of principals that can be requested to be set under
    this policy. This is an alias for ``valid_principals`` since
    requesting less permissions is always possible.

default_critical_options
    Defines default critical options that can be overridden by the requester.

default_extensions
    Defines default extensions that can be overridden by the requester.

default_valid_principals
    Defines default principals that can be overridden by the requester.
    Defaults to ``allowed_valid_principals``

critical_options
    Values set here are forced as usual, but per critical option.

extensions
    Values set here are forced as usual, but per extension.

max_ttl
    The maximum TTL that can be requested under this policy.

ttl
    The default TTL that can be overridden by the requester.
    Defaults to ``max_ttl``.

Restricting requesters
^^^^^^^^^^^^^^^^^^^^^^
You can restrict which minions can request a certificate under a configured
signing policy by specifying a matcher in ``minions``. This can be a glob
or compound matcher (for the latter, see the notes above).

.. code-block:: yaml

    ssh_signing_policies:
      www_host:
        - minions: 'www*'
        - signing_private_key: /etc/pki/ssh/ca.key
        - ttl: 30d
        - copypath: /etc/pki/ssh/issued_certs/

.. _sshcert-setup:
"""

import base64
import copy
import logging
import os.path
from datetime import datetime, timedelta, timezone

try:
    from cryptography.hazmat.primitives import hashes, serialization

    import salt.utils.sshpki as sshpki
    import salt.utils.x509 as x509util

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

import salt.utils.atomicfile
import salt.utils.dictupdate
import salt.utils.files
import salt.utils.functools
import salt.utils.stringutils
import salt.utils.timeutil as time
from salt.exceptions import CommandExecutionError, SaltInvocationError

__virtualname__ = "ssh_pki"

log = logging.getLogger(__name__)


def __virtual__():
    if not HAS_CRYPTOGRAPHY:
        return (False, "Could not load cryptography")
    return __virtualname__


def create_certificate(
    ca_server=None,
    signing_policy=None,
    path=None,
    overwrite=False,
    raw=False,
    **kwargs,
):
    """
    Create an OpenSSH certificate and return an encoded version of it.

    .. note::

        All parameters that take a public key or private key
        can be specified either as a string or a path to a
        local file encoded for OpenSSH.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh_pki.create_certificate private_key=/root/.ssh/id_rsa signing_private_key='/etc/pki/ssh/myca.key'

    ca_server
        Request a remotely signed certificate from another minion acting as
        a CA server. For this to work, a ``signing_policy`` must be specified,
        and that same policy must be configured on the ca_server. See `Signing policies`_
        for details. Also, the Salt master must permit peers to call the
        ``sign_remote_certificate`` function, see `Peer communication`_.

    signing_policy
        The name of a configured signing policy. Parameters specified in there
        are hardcoded and cannot be overridden. This is required for remote signing,
        otherwise optional. See `Signing policies`_ for details.

    copypath
        Create a copy of the issued certificate in this directory.
        The file will be named ``<serial_number>.crt``.

    path
        Instead of returning the certificate, write it to this file path.

    overwrite
        If ``path`` is specified and the file exists, do not overwrite it.
        Defaults to false.

    raw
        Return the encoded raw bytes instead of a string. Defaults to false.

    cert_type
        The certificate type to generate. Either ``user`` or ``host``.
        Required if not specified in the signing policy.

    private_key
        The private key corresponding to the public key the certificate should
        be issued for. Either this or ``public_key`` is required.

    private_key_passphrase
        If ``private_key`` is specified and encrypted, the passphrase to decrypt it.

    public_key
        The public key the certificate should be issued for. Either this or
        ``private_key`` is required.

    signing_private_key
        The private key of the CA that should be used to sign the certificate. Required.

    signing_private_key_passphrase
        If ``signing_private_key`` is encrypted, the passphrase to decrypt it.

    serial_number
        A serial number to be embedded in the certificate. If unspecified, will
        autogenerate one. This should be an integer, either in decimal or
        hexadecimal notation.

    not_before
        Set a specific date the certificate should not be valid before.
        The format should follow ``%Y-%m-%d %H:%M:%S`` and will be interpreted as GMT/UTC.
        Defaults to the time of issuance.

    not_after
        Set a specific date the certificate should not be valid after.
        The format should follow ``%Y-%m-%d %H:%M:%S`` and will be interpreted as GMT/UTC.
        If unspecified, defaults to the current time plus ``ttl``.

    ttl
        If ``not_after`` is unspecified, a time string (like ``30d`` or ``12h``)
        or the number of seconds from the time of issuance the certificate
        should be valid for. Defaults to ``30d`` for host certificates
        and ``24h`` for client certificates.

    critical_options
        A mapping of critical option name to option value to set on the certificate.
        If an option does not take a value, specify it as ``true``.

        Example:

        .. code-block:: bash

            salt-call ssh_pki.create_certificate [...] \
              critical_options='{"force-command": "/usr/bin/id", "verify-required": true}'

    extensions
        A mapping of extension name to extension value to set on the certificate.
        If an extension does not take a value, specify it as ``true``.

        Example:

        .. code-block:: bash

            salt-call ssh_pki.create_certificate [...] \
              extensions='{"custom-option@my.org": "foobar", "permit-pty": true}'

    valid_principals
        A list of valid principals.

    all_principals
        Allow any principals. Defaults to false.

    key_id
        Specify a string-valued key ID for the signed public key.
        When the certificate is used for authentication, this value will be
        logged in plaintext.
    """
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_")}

    if not kwargs.get("signing_private_key") and not ca_server:
        raise SaltInvocationError(
            "Creating a certificate locally at least requires a signing private key."
        )

    if path and not overwrite and __salt__["file.file_exists"](path):
        raise CommandExecutionError(
            f"The file at {path} exists and overwrite was set to false"
        )
    if ca_server:
        if signing_policy is None:
            raise SaltInvocationError(
                "signing_policy must be specified to request a certificate from "
                "a remote ca_server"
            )
        cert = _create_certificate_remote(ca_server, signing_policy, **kwargs)
    else:
        sshpki.merge_signing_policy(_get_signing_policy(signing_policy), kwargs)
        cert = _create_certificate_local(**kwargs)

    out = cert.public_bytes()

    if path is None:
        if raw:
            return out
        return out.decode()

    with salt.utils.files.fopen(path, "wb") as fp_:
        fp_.write(out)
    return f"Certificate written to {path}"


create_certificate_ssh = salt.utils.functools.alias_function(
    create_certificate, "create_certificate_ssh"
)


def _create_certificate_remote(
    ca_server, signing_policy, private_key=None, private_key_passphrase=None, **kwargs
):
    private_key_loaded = None
    if private_key:
        private_key_loaded = sshpki.load_privkey(
            private_key, passphrase=private_key_passphrase
        )
        kwargs["public_key"] = sshpki.encode_public_key(private_key_loaded.public_key())
    elif kwargs.get("public_key"):
        kwargs["public_key"] = sshpki.encode_public_key(
            sshpki.load_pubkey(kwargs["public_key"])
        )

    result = _query_remote(ca_server, signing_policy, kwargs)
    try:
        return sshpki.load_cert(result)
    except (CommandExecutionError, SaltInvocationError) as err:
        raise CommandExecutionError(
            f"ca_server did not return a certificate: {result}"
        ) from err


def _create_certificate_local(copypath=None, **kwargs):
    builder, signing_private_key = sshpki.build_crt(**kwargs)
    cert = builder.sign(signing_private_key)

    if copypath:
        with salt.utils.files.fopen(
            os.path.join(copypath, f"{cert.serial:x}.crt"), "wb"
        ) as fp_:
            fp_.write(cert.public_bytes())
    return cert


def create_private_key(
    algo="rsa",
    keysize=None,
    passphrase=None,
    path=None,
    pubkey_suffix=".pub",
    overwrite=False,
    raw=False,
    **kwargs,
):
    """
    Create a private key.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh_pki.create_private_key algo=ec keysize=384

    algo
        The digital signature scheme the private key should be based on.
        Available: ``rsa``, ``ec``, ``ed25519``. Defaults to ``rsa``.

    keysize
        For ``rsa``, specifies the bitlength of the private key (2048, 3072, 4096).
        For ``ec``, specifies the NIST curve to use (256, 384, 521).
        Irrelevant for ``ed25519``.
        Defaults to 3072 for RSA and 256 for EC.

    passphrase
        If this is specified, the private key will be encrypted using this
        passphrase. The encryption algorithm cannot be selected, it will be
        determined automatically as the best available one.

    path
        Instead of returning the private key, write it to this file path.
        The file will be written with ``0600`` permissions if it does not exist.

    pubkey_suffix
        If ``path`` is specified, write the corresponding pubkey to the same path
        as the private key with this suffix. Set this to false to skip
        writing the public key. Defaults to ``.pub``.

    overwrite
        If ``path`` is specified and the file exists, overwrite it.
        Defaults to false.

    raw
        Return the encoded raw bytes instead of a string. Defaults to false.
    """
    if algo == "rsa" and keysize is None:
        keysize = 3072

    if path and not overwrite and __salt__["file.file_exists"](path):
        raise CommandExecutionError(
            f"The file at {path} exists and overwrite was set to false"
        )

    out = encode_private_key(
        _generate_pk(algo=algo, keysize=keysize),
        passphrase=passphrase,
    )

    if path is None:
        if raw:
            return out.encode()
        return {
            "private_key": out,
            "public_key": get_public_key(out, passphrase=passphrase),
        }

    salt.utils.atomicfile.safe_atomic_write(path, out)
    return f"Private key written to {path}"


def encode_private_key(
    private_key,
    private_key_passphrase=None,
    passphrase=None,
    raw=False,
):
    """
    Create an encoded representation of a private key.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh_ppki.encode_private_key /root/.ssh/id_rsa passphrase=hunter1

    private_key
        The private key to encode.

    private_key_passphrase
        The passphrase that protects the private key.
        Leave unspecified if there is none currently.

    passphrase
        If this is specified, the private key will be encrypted using this
        passphrase. The encryption algorithm cannot be selected, it will be
        determined automatically as the best available one.

    raw
        Return the encoded raw bytes instead of a string. Defaults to false.
    """
    private_key = sshpki.load_privkey(private_key, passphrase=private_key_passphrase)
    if passphrase is None:
        cipher = serialization.NoEncryption()
    else:
        if isinstance(passphrase, str):
            passphrase = passphrase.encode()
        cipher = serialization.BestAvailableEncryption(passphrase)

    pk_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=cipher,
    )

    if raw:
        return pk_bytes
    return pk_bytes.decode()


def expires(certificate, ttl=0):
    """
    Determine whether a certificate will expire or has expired already.
    Returns a boolean only.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh_pki.expires /root/.ssh/id_rsa.crt days=7

    certificate
        The certificate to check.

    ttl
        If specified, determine expiration x seconds in the future.
        Can also be specified as a time string like ``30d`` or ``1.5h``.
        Defaults to ``0``, which checks for the current time.
    """
    cert = sshpki.load_cert(certificate)
    # dates are encoded in UTC/GMT, they are returned as a naive datetime object
    return datetime.fromtimestamp(cert.valid_before, tz=timezone.utc) <= datetime.now(
        tz=timezone.utc
    ) + timedelta(seconds=time.timestring_map(ttl))


def get_private_key_size(private_key, passphrase=None):
    """
    Return information about the key size of a private key (RSA/EC).

    CLI Example:

    .. code-block:: bash

        salt '*' ssh_pki.get_private_key_size /root/.ssh/id_rsa

    private_key
        The private key to check.

    passphrase
        If ``private_key`` is encrypted, the passphrase to decrypt it.
    """
    privkey = sshpki.load_privkey(private_key, passphrase=passphrase)
    if not hasattr(privkey, "key_size"):
        # Edwards-curve keys
        return None
    return privkey.key_size


def get_public_key(key, passphrase=None):
    """
    Returns a public key derived from some reference.
    The reference should be a public key, certificate or private key.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh_pki.get_public_key /root/.ssh/id_rsa

    key
        A reference to the structure to look the public key up for.

    passphrase
        If ``key`` is encrypted, the passphrase to decrypt it.
    """
    return sshpki.get_public_key(key, passphrase=passphrase)


def get_signing_policy(signing_policy, ca_server=None):
    """
    Returns the specified named signing policy.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh_pki.get_signing_policy www

    signing_policy
        The name of the signing policy to return.

    ca_server
        If this is set, the CA server will be queried for the
        signing policy instead of looking it up locally.
    """
    if ca_server is None:
        return _get_signing_policy(signing_policy)
    # Cache signing policies from remote during this run
    # to reduce unnecessary resource usage.
    ckey = "_ssh_pki_policies"
    if ckey not in __context__:
        __context__[ckey] = {}
    if ca_server not in __context__[ckey]:
        __context__[ckey][ca_server] = {}
    if signing_policy not in __context__[ckey][ca_server]:
        policy_ = _query_remote(
            ca_server, signing_policy, {}, get_signing_policy_only=True
        )
        __context__[ckey][ca_server][signing_policy] = policy_
    # only hand out copies of the cached policy
    return copy.deepcopy(__context__[ckey][ca_server][signing_policy])


def read_certificate(certificate):
    """
    Returns a dict containing details of a certificate.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh_pki.read_certificate /root/.ssh/id_rsa.crt

    certificate
        The certificate to read.
    """
    cert = sshpki.load_cert(certificate)
    key_type = x509util.get_key_type(cert.public_key(), as_string=True)
    cert_type = None
    if cert.type == serialization.SSHCertificateType.USER:
        cert_type = "user"
    elif cert.type == serialization.SSHCertificateType.HOST:
        cert_type = "host"

    ret = {
        "cert_type": cert_type,
        "valid_principals": (
            "all"
            if cert.valid_principals == []
            else [p.decode() for p in cert.valid_principals]
        ),
        "key_id": cert.key_id.decode(),
        "key_size": cert.public_key().key_size if key_type in ["ec", "rsa"] else None,
        "key_type": key_type,
        "serial_number": x509util.dec2hex(cert.serial),
        "issuer_public_key": sshpki.encode_public_key(cert.signature_key()).decode(),
        "not_before": datetime.fromtimestamp(
            cert.valid_after, tz=timezone.utc
        ).strftime(x509util.TIME_FMT),
        "not_after": datetime.fromtimestamp(
            cert.valid_before, tz=timezone.utc
        ).strftime(x509util.TIME_FMT),
        "public_key": sshpki.encode_public_key(cert.public_key()).decode(),
        "critical_options": _parse_options(cert),
        "extensions": _parse_extensions(cert),
    }

    for pubkey in ("issuer_public_key", "public_key"):
        pubkey_raw = base64.b64decode(ret[pubkey].split(" ")[1])
        pubkey_sha256 = hashes.Hash(hashes.SHA256())
        pubkey_sha256.update(pubkey_raw)
        pubkey_sha256_digest = pubkey_sha256.finalize()
        ret[f"{pubkey}_fingerprints"] = {
            "sha256": base64.b64encode(pubkey_sha256_digest).decode()
        }

        if __opts__["fips_mode"] is False:
            pubkey_md5 = hashes.Hash(hashes.MD5())
            pubkey_md5.update(pubkey_raw)
            pubkey_md5_fingerprint = pubkey_md5.finalize().hex()  # nosec
            ret[f"{pubkey}_fingerprints"]["md5"] = x509util.pretty_hex(
                pubkey_md5_fingerprint
            ).lower()
    return ret


def sign_remote_certificate(
    signing_policy, kwargs, get_signing_policy_only=False, **more_kwargs
):
    """
    Request a certificate to be remotely signed according to a signing policy.
    This is mostly for internal use and does not make much sense on the CLI.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh_pki.sign_remote_certificate www kwargs="{'public_key': '/etc/pki/ssh/www.key'}"

    signing_policy
        The name of the signing policy to use. Required.

    kwargs
        A dict containing all the arguments to be passed into the
        :py:func:`ssh_pki.create_certificate <salt.modules.x509_v2.create_certificate>` function.

    get_signing_policy_only
        Only return the named signing policy. Defaults to false.
    """
    ret = {"data": None, "errors": []}
    try:
        signing_policy = _get_signing_policy(signing_policy)
        if not signing_policy:
            ret["errors"].append(
                "signing_policy must be specified and defined on signing minion"
            )
            return ret
        if "minions" in signing_policy:
            if "__pub_id" not in more_kwargs:
                ret["errors"].append(
                    "minion sending this request could not be identified"
                )
                return ret
            # also pop "minions" to avoid leaking more details than necessary
            if not _match_minions(
                signing_policy.pop("minions"), more_kwargs["__pub_id"]
            ):
                ret["errors"].append(
                    "minion not permitted to use specified signing policy"
                )
                return ret

        if get_signing_policy_only:
            # This is relevant for the state module to be able to check for changes
            # without generating and signing a new certificate every time.
            # remove unnecessary sensitive information
            signing_private_key = signing_policy.pop("signing_private_key", None)
            signing_private_key_passphrase = signing_policy.pop(
                "signing_private_key_passphrase", None
            )
            # ensure to deliver the signing public key as well, not a file path
            if signing_private_key is not None:
                try:
                    signing_private_key = sshpki.load_privkey(
                        signing_private_key, passphrase=signing_private_key_passphrase
                    )
                except (CommandExecutionError, SaltInvocationError) as err:
                    ret["data"] = None
                    ret["errors"].append(str(err))
                    return ret
                signing_policy["signing_public_key"] = sshpki.encode_public_key(
                    signing_private_key.public_key()
                )
            ret["data"] = signing_policy
            return ret
        sshpki.merge_signing_policy(signing_policy, kwargs)
        # ensure the certificate will be issued from this minion
        kwargs.pop("ca_server", None)
    except Exception as err:  # pylint: disable=broad-except
        log.error(str(err))
        return {
            "data": None,
            "errors": [
                "Failed building the signing policy. See CA server log for details."
            ],
        }
    try:
        cert = _create_certificate_local(**kwargs)
        ret["data"] = cert.public_bytes()
        return ret
    except Exception as err:  # pylint: disable=broad-except
        ret["data"] = None
        ret["errors"].append(str(err))
        return ret

    err_message = "Internal error. This is most likely a bug."
    log.error(err_message)
    return {"data": None, "errors": [err_message]}


def _query_remote(ca_server, signing_policy, kwargs, get_signing_policy_only=False):
    result = __salt__["publish.publish"](
        ca_server,
        "ssh_pki.sign_remote_certificate",
        arg=[signing_policy, kwargs, get_signing_policy_only],
    )

    if not result:
        raise SaltInvocationError(
            "ca_server did not respond."
            " Salt master must permit peers to"
            " call the sign_remote_certificate function."
        )
    result = result[next(iter(result))]
    if not isinstance(result, dict) or "data" not in result:
        log.error(f"Received invalid return value from ca_server: {result}")
        raise CommandExecutionError(
            "Received invalid return value from ca_server. See minion log for details"
        )
    if result.get("errors"):
        raise CommandExecutionError(
            "ca_server reported errors:\n" + "\n".join(result["errors"])
        )
    return result["data"]


def verify_private_key(private_key, public_key, passphrase=None):
    """
    Verify that a private key belongs to the specified public key.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh_pki.verify_private_key /root/.ssh/id_rsa /root/.ssh/id_rsa.crt

    private_key
        The private key to check.

    public_key
        The certificate (or any reference that can be passed
        to ``get_public_key``) to retrieve the public key from.

    passphrase
        If ``private_key`` is encrypted, the passphrase to decrypt it.
    """
    privkey = sshpki.load_privkey(private_key, passphrase=passphrase)
    pubkey = sshpki.load_pubkey(get_public_key(public_key))
    return x509util.is_pair(pubkey, privkey)


def verify_signature(certificate, signing_pub_key, signing_pub_key_passphrase=None):
    """
    Verify that a signature on a certificate was made
    by the private key corresponding to the public key associated
    with the specified certificate.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh_pki.verify_signature /root/.ssh/id_rsa.crt /etc/pki/ssh/myca.pub

    certificate
        The certificate to check the signature on.

    signing_pub_key
        Any reference that can be passed to ``get_public_key`` to retrieve
        the public key of the signing entity from.

    signing_pub_key_passphrase
        If ``signing_pub_key`` is encrypted, the passphrase to decrypt it.
    """
    return sshpki.verify_signature(
        certificate,
        signing_pub_key,
        signing_pub_key_passphrase=signing_pub_key_passphrase,
    )


def _generate_pk(algo="rsa", keysize=None):
    if algo == "rsa":
        return x509util.generate_rsa_privkey(keysize=keysize or 2048)
    if algo == "ec":
        return x509util.generate_ec_privkey(keysize=keysize or 256)
    if algo == "ed25519":
        return x509util.generate_ed25519_privkey()
    raise SaltInvocationError(
        f"Invalid algorithm specified for generating private key: {algo}. Valid: "
        "rsa, ec, ed25519, ed448"
    )


def _get_signing_policy(name):
    if name is None:
        return {}
    policies = __salt__["pillar.get"]("ssh_signing_policies", {}).get(name)
    policies = policies or __salt__["config.get"]("ssh_signing_policies", {}).get(name)
    return policies or {}


def _parse_extensions(cert):
    ret = {}
    for ext, val in cert.extensions.items():
        try:
            val = val.decode()
            ret[ext.decode()] = val if val != "" else True
        except UnicodeDecodeError as err:
            log.warning(f"Failed decoding extension: {err}")
    return ret


def _parse_options(cert):
    ret = {}
    for ext, val in cert.critical_options.items():
        try:
            val = val.decode()
            ret[ext.decode()] = val if val != "" else True
        except UnicodeDecodeError as err:
            log.warning(f"Failed decoding option: {err}")
    return ret


def _match_minions(test, minion):
    if "@" in test:
        # Ask the master if the requesting minion matches a compound expression.
        match = __salt__["publish.runner"]("match.compound_matches", arg=[test, minion])
        if match is None:
            raise CommandExecutionError(
                "Could not check minion match for compound expression. "
                "Is this minion allowed to run `match.compound_matches` on the master?"
            )
        try:
            return match["res"] == minion
        except (KeyError, TypeError) as err:
            raise CommandExecutionError(
                "Invalid return value of match.compound_matches."
            ) from err
        # The following line should never be reached.
        return False
    return __salt__["match.glob"](test, minion)
