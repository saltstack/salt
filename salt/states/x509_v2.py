"""
Manage X.509 certificates
=========================

.. versionadded:: 3006.0

    This module represents a complete rewrite of the original ``x509`` modules
    and is named ``x509_v2`` since it introduces breaking changes.

:depends: cryptography

.. note::

    All parameters that take a public key, private key, certificate,
    CSR or CRL can be specified either as a PEM/hex/base64 string or
    a path to a local file encoded in all supported formats for the type.

Configuration instructions and general remarks are documented
in the :ref:`execution module docs <x509-setup>`.

For the list of breaking changes versus the previous ``x509`` modules,
please also refer to the :ref:`execution module docs <x509-setup>`.

About
-----
This module can enable managing a complete PKI infrastructure, including creating
private keys, CAs, certificates and CRLs. It includes the ability to generate a
private key on a server, and have the corresponding public key sent to a remote
CA to create a CA signed certificate. This can be done in a secure manner, where
private keys are always generated locally and never moved across the network.

Example
-------
Here is a simple example scenario. In this example ``ca`` is the ca server,
and ``www`` is a web server that needs a certificate signed by ``ca``.

.. note::

    Remote signing requires the setup of :term:`Peer Communication` and signing
    policies. Please see the :ref:`execution module docs <x509-setup>`.


/srv/salt/top.sls

.. code-block:: yaml

    base:
      '*':
        - cert
      'ca':
        - ca
      'www':
        - www

This state creates the CA key, certificate and signing policy. It also publishes
the certificate to the mine, where it can be easily retrieved by other minions.

.. code-block:: yaml

    # /srv/salt/ca.sls

    Configure the x509 module:
      file.managed:
        - name: /etc/salt/minion.d/x509.conf
        - source: salt://x509.conf

    Restart Salt minion:
      cmd.run:
        - name: 'salt-call service.restart salt-minion'
        - bg: true
        - onchanges:
          - file: /etc/salt/minion.d/x509.conf

    Ensure PKI directories exist:
      file.directory:
        - name: /etc/pki/issued_certs
        - makedirs: true

    Create CA private key:
      x509.private_key_managed:
        - name: /etc/pki/ca.key
        - keysize: 4096
        - backup: true
        - require:
          - file: /etc/pki/issued_certs

    Create self-signed CA certificate:
      x509.certificate_managed:
        - name: /etc/pki/ca.crt
        - signing_private_key: /etc/pki/ca.key
        - CN: ca.example.com
        - C: US
        - ST: Utah
        - L: Salt Lake City
        - basicConstraints: "critical, CA:true"
        - keyUsage: "critical, cRLSign, keyCertSign"
        - subjectKeyIdentifier: hash
        - authorityKeyIdentifier: keyid:always,issuer
        - days_valid: 3650
        - days_remaining: 0
        - backup: true
        - require:
          - x509: /etc/pki/ca.key

.. code-block:: yaml

    # /srv/salt/x509.conf

    # enable x509_v2
    features:
      x509_v2: true

    # publish the CA certificate to the mine
    mine_functions:
      x509.get_pem_entries: [/etc/pki/ca.crt]

    # define at least one signing policy for remote signing
    x509_signing_policies:
      www:
        - minions: 'www'
        - signing_private_key: /etc/pki/ca.key
        - signing_cert: /etc/pki/ca.crt
        - C: US
        - ST: Utah
        - L: Salt Lake City
        - basicConstraints: "critical CA:false"
        - keyUsage: "critical keyEncipherment"
        - subjectKeyIdentifier: hash
        - authorityKeyIdentifier: keyid:always,issuer
        - days_valid: 30
        - copypath: /etc/pki/issued_certs/


This example state will instruct all minions to trust certificates signed by
our new CA. Mind that this example works for Debian-based OS only.
Also note the Jinja call to encode the string to JSON, which will avoid
YAML issues with newline characters.

.. code-block:: jinja

    # /srv/salt/cert.sls

    Ensure the CA trust bundle exists:
      file.directory:
        - name: /usr/local/share/ca-certificates

    Ensure our self-signed CA certificate is included:
      x509.pem_managed:
        - name: /usr/local/share/ca-certificates/myca.crt
        - text: {{ salt["mine.get"]("ca", "x509.get_pem_entries")["ca"]["/etc/pki/ca.crt"] | json }}

This state creates a private key, then requests a certificate signed by our CA
according to the www policy.

.. code-block:: yaml

    # /srv/salt/www.sls

    Ensure PKI directory exists:
      file.directory:
        - name: /etc/pki

    Create private key for the certificate:
      x509.private_key_managed:
        - name: /etc/pki/www.key
        - keysize: 4096
        - backup: true
        - require:
          - file: /etc/pki

    Request certificate:
      x509.certificate_managed:
        - name: /etc/pki/www.crt
        - ca_server: ca
        - signing_policy: www
        - private_key: /etc/pki/www.key
        - CN: www.example.com
        - days_remaining: 7
        - backup: true
        - require:
          - x509: /etc/pki/www.key
"""

import base64
import copy
import logging
import os.path
from datetime import datetime, timedelta, timezone

import salt.utils.files
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.state import STATE_INTERNAL_KEYWORDS as _STATE_INTERNAL_KEYWORDS

try:
    import cryptography.x509 as cx509
    from cryptography.exceptions import UnsupportedAlgorithm
    from cryptography.hazmat.primitives import hashes

    import salt.utils.x509 as x509util

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


log = logging.getLogger(__name__)

__virtualname__ = "x509"


def __virtual__():
    if not HAS_CRYPTOGRAPHY:
        return (False, "Could not load cryptography")
    if not __opts__["features"].get("x509_v2"):
        return (
            False,
            "x509_v2 needs to be explicitly enabled by setting `x509_v2: true` "
            "in the minion configuration value `features` until Salt 3008 (Argon).",
        )
    return __virtualname__


def certificate_managed(
    name,
    days_remaining=None,
    ca_server=None,
    signing_policy=None,
    encoding="pem",
    append_certs=None,
    copypath=None,
    prepend_cn=False,
    digest="sha256",
    signing_private_key=None,
    signing_private_key_passphrase=None,
    signing_cert=None,
    public_key=None,
    private_key=None,
    private_key_passphrase=None,
    csr=None,
    subject=None,
    serial_number=None,
    not_before=None,
    not_after=None,
    days_valid=None,
    pkcs12_passphrase=None,
    pkcs12_encryption_compat=False,
    pkcs12_friendlyname=None,
    **kwargs,
):
    """
    Ensure an X.509 certificate is present as specified.

    This function accepts the same arguments as :py:func:`x509.create_certificate <salt.modules.x509_v2.create_certificate>`,
    as well as most ones for `:py:func:`file.managed <salt.states.file.managed>`.

    name
        The path the certificate should be present at.

    days_remaining
        The certificate will be recreated once the remaining certificate validity
        period is less than this number of days.
        Defaults to ``90`` (until v3009) or ``7`` (from v3009 onwards).

    ca_server
        Request a remotely signed certificate from ca_server. For this to
        work, a ``signing_policy`` must be specified, and that same policy
        must be configured on the ca_server.  Also, the Salt master must
        permit peers to call the ``x509.sign_remote_certificate`` function.
        See the :ref:`execution module docs <x509-setup>` for details.

    signing_policy
        The name of a configured signing policy. Parameters specified in there
        are hardcoded and cannot be overridden. This is required for remote signing,
        otherwise optional.

    encoding
        Specify the encoding of the resulting certificate. It can be serialized
        as a ``pem`` (or ``pkcs7_pem``) text file or in several binary formats
        (``der``, ``pkcs7_der``, ``pkcs12``). Defaults to ``pem``.

    append_certs
        A list of additional certificates to append to the new one, e.g. to create a CA chain.

        .. note::

            Mind that when ``der`` encoding is in use, appending certificatees is prohibited.

    copypath
        Create a copy of the issued certificate in PEM format in this directory.
        The file will be named ``<serial_number>.crt`` if prepend_cn is false.

    prepend_cn
        When ``copypath`` is set, prepend the common name of the certificate to
        the file name like so: ``<CN>-<serial_number>.crt``. Defaults to false.

    digest
        The hashing algorithm to use for the signature. Valid values are:
        sha1, sha224, sha256, sha384, sha512, sha512_224, sha512_256, sha3_224,
        sha3_256, sha3_384, sha3_512. Defaults to ``sha256``.
        This will be ignored for ``ed25519`` and ``ed448`` key types.

    signing_private_key
        The private key corresponding to the public key in ``signing_cert``. Required.

    signing_private_key_passphrase
        If ``signing_private_key`` is encrypted, the passphrase to decrypt it.

    signing_cert
        The CA certificate to be used for signing the issued certificate.

    public_key
        The public key the certificate should be issued for. Other ways of passing
        the required information are ``private_key`` and ``csr``. If neither are set,
        the public key of the ``signing_private_key`` will be included, i.e.
        a self-signed certificate is generated.

    private_key
        The private key corresponding to the public key the certificate should
        be issued for. This is one way of specifying the public key that will
        be included in the certificate, the other ones being ``public_key`` and ``csr``.

    private_key_passphrase
        If ``private_key`` is specified and encrypted, the passphrase to decrypt it.

    csr
        A certificate signing request to use as a base for generating the certificate.
        The following information will be respected, depending on configuration:

        * public key
        * extensions, if not otherwise specified (arguments, signing_policy)

    subject
        The subject's distinguished name embedded in the certificate. This is one way of
        passing this information (see ``kwargs`` below for the other).
        This argument will be preferred and allows to control the order of RDNs in the DN
        as well as to embed RDNs with multiple attributes.
        This can be specified as a RFC4514-encoded string (``CN=example.com,O=Example Inc,C=US``,
        mind that the rendered order is reversed from what is embedded), a list
        of RDNs encoded as in RFC4514 (``["C=US", "O=Example Inc", "CN=example.com"]``)
        or a dictionary (``{"CN": "example.com", "C": "US", "O": "Example Inc"}``,
        default ordering).
        Multiple name attributes per RDN are concatenated with a ``+``.

        .. note::

            Parsing of RFC4514 strings requires at least cryptography release 37.

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
        If unspecified, defaults to the current time plus ``days_valid`` days.

    days_valid
        If ``not_after`` is unspecified, the number of days from the time of issuance
        the certificate should be valid for.
        Defaults to ``365`` (until v3009) or ``30`` (from v3009 onwards).

    pkcs12_passphrase
        When encoding a certificate as ``pkcs12``, encrypt it with this passphrase.

        .. note::

            PKCS12 encryption is very weak and `should not be relied on for security <https://cryptography.io/en/stable/hazmat/primitives/asymmetric/serialization/#cryptography.hazmat.primitives.serialization.pkcs12.serialize_key_and_certificates>`_.

    pkcs12_encryption_compat
        OpenSSL 3 and cryptography v37 switched to a much more secure default
        encryption for PKCS12, which might be incompatible with some systems.
        This forces the legacy encryption. Defaults to False.

    pkcs12_friendlyname
        When encoding a certificate as ``pkcs12``, a name for the certificate can be included.

    kwargs
        Embedded X.509v3 extensions and the subject's distinguished name can be
        controlled via supplemental keyword arguments. See
        :py:func:`x509.create_certificate <salt.modules.x509_v2.create_certificate>`
        for an overview.
    """
    # Deprecation checks vs the old x509 module
    if days_valid is None and not_after is None:
        try:
            salt.utils.versions.warn_until(
                3009,
                "The default value for `days_valid` will change to 30. Please adapt your code accordingly.",
            )
            days_valid = 365
        except RuntimeError:
            days_valid = 30

    if days_remaining is None:
        try:
            salt.utils.versions.warn_until(
                3009,
                "The default value for `days_remaining` will change to 7. Please adapt your code accordingly.",
            )
            days_remaining = 90
        except RuntimeError:
            days_remaining = 7

    if "algorithm" in kwargs:
        salt.utils.versions.warn_until(
            3009,
            "`algorithm` has been renamed to `digest`. Please update your code.",
        )
        digest = kwargs.pop("algorithm")
    kwargs = x509util.ensure_cert_kwargs_compat(kwargs)

    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "The certificate is in the correct state",
    }
    current = current_encoding = None
    changes = {}
    verb = "create"
    file_args, cert_args = _split_file_kwargs(_filter_state_internal_kwargs(kwargs))
    append_certs = append_certs or []
    if not isinstance(append_certs, list):
        append_certs = [append_certs]

    try:
        # check file.managed changes early to avoid using unnecessary resources
        file_managed_test = _file_managed(name, test=True, replace=False, **file_args)
        if file_managed_test["result"] is False:
            ret["result"] = False
            ret["comment"] = (
                "Problem while testing file.managed changes, see its output"
            )
            _add_sub_state_run(ret, file_managed_test)
            return ret

        if "is not present and is not set for creation" in file_managed_test["comment"]:
            _add_sub_state_run(ret, file_managed_test)
            return ret

        real_name = name
        replace = False

        # handle follow_symlinks
        if __salt__["file.is_link"](name):
            if file_args.get("follow_symlinks", True):
                real_name = os.path.realpath(name)
            else:
                # workaround https://github.com/saltstack/salt/issues/31802
                __salt__["file.remove"](name)
                replace = True

        if __salt__["file.file_exists"](real_name):
            try:
                (
                    current,
                    current_encoding,
                    current_chain,
                    current_extra,
                ) = x509util.load_cert(
                    real_name, passphrase=pkcs12_passphrase, get_encoding=True
                )
            except SaltInvocationError as err:
                if "Bad decrypt" in str(err):
                    changes["pkcs12_passphrase"] = True
                elif any(
                    (
                        "Could not deserialize binary data" in str(err),
                        "Could not load PEM-encoded" in str(err),
                    )
                ):
                    replace = True
                else:
                    raise
            else:
                if encoding != current_encoding:
                    changes["encoding"] = encoding
                elif encoding == "pkcs12" and current_extra.cert.friendly_name != (
                    salt.utils.stringutils.to_bytes(pkcs12_friendlyname)
                    if pkcs12_friendlyname
                    else None
                ):
                    changes["pkcs12_friendlyname"] = pkcs12_friendlyname
                try:
                    curr_not_after = current.not_valid_after_utc
                except AttributeError:
                    # naive datetime object, release <42 (it's always UTC)
                    curr_not_after = current.not_valid_after.replace(
                        tzinfo=timezone.utc
                    )

                if curr_not_after < datetime.now(tz=timezone.utc) + timedelta(
                    days=days_remaining
                ):
                    changes["expiration"] = True

                current_chain = current_chain or []
                ca_chain = [x509util.load_cert(x) for x in append_certs]
                if not _compare_ca_chain(current_chain, ca_chain):
                    changes["additional_certs"] = True

                (
                    builder,
                    private_key_loaded,
                    signing_cert_loaded,
                    final_kwargs,
                ) = _build_cert(
                    ca_server=ca_server,
                    signing_policy=signing_policy,
                    digest=digest,  # passed because of signing_policy merging
                    signing_private_key=signing_private_key,
                    signing_private_key_passphrase=signing_private_key_passphrase,
                    signing_cert=signing_cert,
                    public_key=public_key,
                    private_key=private_key,
                    private_key_passphrase=private_key_passphrase,
                    csr=csr,
                    subject=subject,
                    serial_number=serial_number,
                    not_before=not_before,
                    not_after=not_after,
                    days_valid=days_valid,
                    **cert_args,
                )

                try:
                    if current.signature_hash_algorithm is not None and not isinstance(
                        current.signature_hash_algorithm,
                        type(x509util.get_hashing_algorithm(final_kwargs["digest"])),
                    ):
                        # ed25519, ed448 do not use a separate hash for signatures, hence algo is None
                        changes["digest"] = digest
                except UnsupportedAlgorithm:
                    # this eg happens with sha3 in cryptography < v39
                    log.warning(
                        "Could not determine signature hash algorithm of '%s'. "
                        "Continuing anyways",
                        name,
                    )

                changes.update(
                    _compare_cert(
                        current,
                        builder,
                        signing_cert=signing_cert_loaded,
                        serial_number=serial_number,
                        not_before=not_before,
                        not_after=not_after,
                    )
                )
        else:
            changes["created"] = name

        if replace:
            changes["replaced"] = name

        if (
            not changes
            and file_managed_test["result"]
            and not file_managed_test["changes"]
        ):
            _add_sub_state_run(ret, file_managed_test)
            return ret

        ret["changes"] = changes
        if current and changes:
            verb = "recreate"

        if __opts__["test"]:
            ret["result"] = None if changes else True
            ret["comment"] = (
                f"The certificate would have been {verb}d"
                if changes
                else ret["comment"]
            )
            _add_sub_state_run(ret, file_managed_test)
            return ret

        if changes:
            if not set(changes) - {
                "additional_certs",
                "encoding",
                "pkcs12_friendlyname",
            }:
                # do not reissue if only metaparameters changed
                if encoding == "pkcs12":
                    cert = __salt__["x509.encode_certificate"](
                        current,
                        append_certs=append_certs,
                        encoding=encoding,
                        private_key=private_key_loaded,
                        pkcs12_passphrase=pkcs12_passphrase,
                        pkcs12_encryption_compat=pkcs12_encryption_compat,
                        pkcs12_friendlyname=pkcs12_friendlyname,
                    )
                else:
                    cert = __salt__["x509.encode_certificate"](
                        current, encoding=encoding, append_certs=append_certs
                    )
            else:
                # request a new certificate otherwise
                cert = __salt__["x509.create_certificate"](
                    ca_server=ca_server,
                    signing_policy=signing_policy,
                    encoding=encoding,
                    append_certs=append_certs,
                    pkcs12_passphrase=pkcs12_passphrase,
                    pkcs12_encryption_compat=pkcs12_encryption_compat,
                    pkcs12_friendlyname=pkcs12_friendlyname,
                    digest=digest,
                    signing_private_key=signing_private_key,
                    signing_private_key_passphrase=signing_private_key_passphrase,
                    signing_cert=signing_cert,
                    public_key=public_key,
                    private_key=private_key,
                    private_key_passphrase=private_key_passphrase,
                    csr=csr,
                    subject=subject,
                    serial_number=serial_number,
                    not_before=not_before,
                    not_after=not_after,
                    days_valid=days_valid,
                    **cert_args,
                )
            ret["comment"] = f"The certificate has been {verb}d"
            if encoding not in ["pem", "pkcs7_pem"]:
                # file.managed does not support binary contents, so create
                # an empty file first (makedirs). This will not work with check_cmd!
                file_managed_ret = _file_managed(name, replace=False, **file_args)
                _add_sub_state_run(ret, file_managed_ret)
                if not _check_file_ret(file_managed_ret, ret, current):
                    return ret
                _safe_atomic_write(
                    real_name, base64.b64decode(cert), file_args.get("backup", "")
                )

        if not changes or encoding in ["pem", "pkcs7_pem"]:
            replace = bool(encoding in ["pem", "pkcs7_pem"] and changes)
            contents = cert if replace else None
            file_managed_ret = _file_managed(
                name, contents=contents, replace=replace, **file_args
            )
            _add_sub_state_run(ret, file_managed_ret)
            if not _check_file_ret(file_managed_ret, ret, current):
                return ret

    except (CommandExecutionError, SaltInvocationError) as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def crl_managed(
    name,
    signing_private_key,
    revoked,
    days_remaining=None,
    signing_cert=None,
    signing_private_key_passphrase=None,
    include_expired=False,
    days_valid=None,
    digest="sha256",
    encoding="pem",
    extensions=None,
    **kwargs,
):
    """
    Ensure a certificate revocation list is present as specified.

    This function accepts the same arguments as :py:func:`x509.create_crl <salt.modules.x509_v2.create_crl>`,
    as well as most ones for `:py:func:`file.managed <salt.states.file.managed>`.

    name
        The path the certificate revocation list should be present at.

    signing_private_key
        Your certificate authority's private key. It will be used to sign
        the CRL. Required.

    revoked
        A list of dicts containing all the certificates to revoke. Each dict
        represents one certificate. A dict must contain either the key
        ``serial_number`` with the value of the serial number to revoke, or
        ``certificate`` with some reference to the certificate to revoke.

        The dict can optionally contain the ``revocation_date`` key. If this
        key is omitted, the revocation date will be set to now. It should be a
        string in the format ``%Y-%m-%d %H:%M:%S``.

        The dict can also optionally contain the ``not_after`` key. This is
        redundant if the ``certificate`` key is included. If the
        ``certificate`` key is not included, this can be used for the logic
        behind the ``include_expired`` parameter. It should be a string in
        the format ``%Y-%m-%d %H:%M:%S``.

        The dict can also optionally contain the ``extensions`` key, which
        allows to set CRL entry-specific extensions. The following extensions
        are supported:

        certificateIssuer
            Identifies the certificate issuer associated with an entry in an
            indirect CRL. The format is the same as for subjectAltName.

        CRLReason
            Identifies the reason for certificate revocation.
            Available choices are ``unspecified``, ``keyCompromise``, ``CACompromise``,
            ``affiliationChanged``, ``superseded``, ``cessationOfOperation``,
            ``certificateHold``, ``privilegeWithdrawn``, ``aACompromise`` and
            ``removeFromCRL``.

        invalidityDate
            Provides the date on which the certificate became invalid.
            The value should be a string in the same format as ``revocation_date``.

    days_remaining
        The certificate revocation list will be recreated once the remaining
        CRL validity period is less than this number of days.
        Defaults to ``30`` (until v3009) or ``3`` (from v3009 onwards).
        Set to 0 to disable automatic renewal without anything changing.

    signing_cert
        The CA certificate to be used for signing the issued certificate.

    signing_private_key_passphrase
        If ``signing_private_key`` is encrypted, the passphrase to decrypt it.

    include_expired
        Also include already expired certificates in the CRL. Defaults to false.

    days_valid
        The number of days that the CRL should be valid for. This sets the ``Next Update``
        field in the CRL. Defaults to ``100`` (until v3009) or ``7`` (from v3009 onwards).

    digest
        The hashing algorithm to use for the signature. Valid values are:
        sha1, sha224, sha256, sha384, sha512, sha512_224, sha512_256, sha3_224,
        sha3_256, sha3_384, sha3_512. Defaults to ``sha256``.
        This will be ignored for ``ed25519`` and ``ed448`` key types.

    encoding
        Specify the encoding of the resulting certificate revocation list.
        It can be serialized as a ``pem`` text or binary ``der`` file.
        Defaults to ``pem``.

    extensions
        Add CRL extensions. See :py:func:`x509.create_crl <salt.modules.x509_v2.create_crl>`
        for details.

        .. note::

            For ``cRLNumber``, in addition the value ``auto`` is supported, which
            automatically increases the counter every time a new CRL is issued.

    Example:

    .. code-block:: yaml

        Manage CRL:
          x509.crl_managed:
            - name: /etc/pki/ca.crl
            - signing_private_key: /etc/pki/myca.key
            - signing_cert: /etc/pki/myca.crt
            - revoked:
              - certificate: /etc/pki/certs/badweb.crt
                revocation_date: 2022-11-01 00:00:00
                extensions:
                  CRLReason: keyCompromise
              - serial_number: D6:D2:DC:D8:4D:5C:C0:F4
                not_after: 2023-03-14 00:00:00
                revocation_date: 2022-10-25 00:00:00
                extensions:
                  CRLReason: cessationOfOperation
            - extensions:
                cRLNumber: auto
    """
    if "text" in kwargs:
        salt.utils.versions.kwargs_warn_until(["text"], "Potassium")
        kwargs.pop("text")

    if days_valid is None:
        try:
            salt.utils.versions.warn_until(
                3009,
                "The default value for `days_valid` will change to 7. Please adapt your code accordingly.",
            )
            days_valid = 100
        except RuntimeError:
            days_valid = 7

    if days_remaining is None:
        try:
            salt.utils.versions.warn_until(
                3009,
                "The default value for `days_remaining` will change to 3. Please adapt your code accordingly.",
            )
            days_remaining = 30
        except RuntimeError:
            days_remaining = 3

    revoked_parsed = []
    for rev in revoked:
        parsed = {}
        if len(rev) == 1 and isinstance(rev[next(iter(rev))], list):
            salt.utils.versions.warn_until(
                3009,
                "Revoked certificates should be specified as a simple list of dicts.",
            )
            for val in rev[next(iter(rev))]:
                parsed.update(val)
        if "reason" in (parsed or rev):
            salt.utils.versions.warn_until(
                3009,
                "The `reason` parameter for revoked certificates should be specified in extensions:CRLReason.",
            )
            salt.utils.dictupdate.set_dict_key_value(
                (parsed or rev), "extensions:CRLReason", (parsed or rev).pop("reason")
            )
        revoked_parsed.append(parsed or rev)
    revoked = revoked_parsed

    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "The certificate revocation list is in the correct state",
    }
    current = current_encoding = None
    changes = {}
    verb = "create"
    file_args, extra_args = _split_file_kwargs(_filter_state_internal_kwargs(kwargs))
    extensions = extensions or {}
    if extra_args:
        raise SaltInvocationError(f"Unrecognized keyword arguments: {list(extra_args)}")

    try:
        # check file.managed changes early to avoid using unnecessary resources
        file_managed_test = _file_managed(name, test=True, replace=False, **file_args)

        if file_managed_test["result"] is False:
            ret["result"] = False
            ret["comment"] = (
                "Problem while testing file.managed changes, see its output"
            )
            _add_sub_state_run(ret, file_managed_test)
            return ret

        if "is not present and is not set for creation" in file_managed_test["comment"]:
            _add_sub_state_run(ret, file_managed_test)
            return ret

        real_name = name
        replace = False

        # handle follow_symlinks
        if __salt__["file.is_link"](name):
            if file_args.get("follow_symlinks", True):
                real_name = os.path.realpath(name)
            else:
                # workaround https://github.com/saltstack/salt/issues/31802
                __salt__["file.remove"](name)
                replace = True

        if __salt__["file.file_exists"](real_name):
            try:
                current, current_encoding = x509util.load_crl(
                    real_name, get_encoding=True
                )
            except SaltInvocationError as err:
                if any(
                    (
                        "Could not load PEM-encoded" in str(err),
                        "Could not load DER-encoded" in str(err),
                    )
                ):
                    replace = True
                else:
                    raise
            else:
                try:
                    if current.signature_hash_algorithm is not None and not isinstance(
                        current.signature_hash_algorithm,
                        type(x509util.get_hashing_algorithm(digest)),
                    ):
                        # ed25519, ed448 do not use a separate hash for signatures, hence algo is None
                        # although CA certificates should not be using those currently
                        changes["digest"] = digest
                except UnsupportedAlgorithm:
                    # this eg happens with sha3 digest in cryptography < v39
                    log.warning(
                        "Could not determine signature hash algorithm of '%s'. "
                        "Continuing anyways",
                        name,
                    )

                if encoding != current_encoding:
                    changes["encoding"] = encoding
                try:
                    curr_next_update = current.next_update_utc
                except AttributeError:
                    # naive datetime object, release <42 (it's always UTC)
                    curr_next_update = current.next_update.replace(tzinfo=timezone.utc)
                if days_remaining and (
                    curr_next_update
                    < datetime.now(tz=timezone.utc) + timedelta(days=days_remaining)
                ):
                    changes["expiration"] = True

                # "auto" is a value that is managed in this function and cannot not be compared
                crl_auto = extensions.get("cRLNumber") == "auto"
                if crl_auto:
                    extensions.pop("cRLNumber")

                builder, sig_privkey = x509util.build_crl(
                    signing_private_key,
                    revoked,
                    signing_cert=signing_cert,
                    signing_private_key_passphrase=signing_private_key_passphrase,
                    include_expired=include_expired,
                    days_valid=days_valid,
                    extensions=extensions,
                )
                changes.update(_compare_crl(current, builder, sig_privkey.public_key()))
                if crl_auto:
                    # put cRLNumber = auto back if it was set
                    extensions["cRLNumber"] = "auto"
                    changes["extensions"]["removed"].pop(
                        changes["extensions"]["removed"].index("cRLNumber")
                    )
                    if not any(changes["extensions"].values()):
                        changes.pop("extensions")
        else:
            changes["created"] = name

        if replace:
            changes["replaced"] = name

        if (
            not changes
            and file_managed_test["result"]
            and not file_managed_test["changes"]
        ):
            _add_sub_state_run(ret, file_managed_test)
            return ret

        ret["changes"] = changes
        if current and changes:
            verb = "recreate"

        if __opts__["test"]:
            ret["result"] = None if changes else True
            ret["comment"] = (
                f"The certificate revocation list would have been {verb}d"
                if changes
                else ret["comment"]
            )
            _add_sub_state_run(ret, file_managed_test)
            return ret

        if changes:
            if not set(changes) - {"encoding"}:
                # do not regenerate if only metaparameters changed
                crl = __salt__["x509.encode_crl"](current, encoding=encoding)
            else:
                # autoincrease cRLNumber counter, if requested
                if extensions.get("cRLNumber") == "auto":
                    try:
                        extensions["cRLNumber"] = (
                            current.extensions.get_extension_for_class(
                                cx509.CRLNumber
                            ).value.crl_number
                            + 1
                        )
                    except (AttributeError, cx509.ExtensionNotFound):
                        extensions["cRLNumber"] = 1
                crl = __salt__["x509.create_crl"](
                    signing_private_key,
                    revoked,
                    signing_cert=signing_cert,
                    signing_private_key_passphrase=signing_private_key_passphrase,
                    include_expired=include_expired,
                    days_valid=days_valid,
                    digest=digest,
                    encoding=encoding,
                    extensions=extensions,
                )
            ret["comment"] = f"The certificate revocation list has been {verb}d"
            if encoding == "der":
                # file.managed does not support binary contents, so create
                # an empty file first (makedirs). This will not work with check_cmd!
                file_managed_ret = _file_managed(name, replace=False, **file_args)
                _add_sub_state_run(ret, file_managed_ret)
                if not _check_file_ret(file_managed_ret, ret, current):
                    return ret
                _safe_atomic_write(
                    real_name, base64.b64decode(crl), file_args.get("backup", "")
                )

        if not changes or encoding == "pem":
            replace = bool((encoding == "pem") and changes)
            contents = crl if replace else None
            file_managed_ret = _file_managed(
                name, contents=contents, replace=replace, **file_args
            )
            _add_sub_state_run(ret, file_managed_ret)
            if not _check_file_ret(file_managed_ret, ret, current):
                return ret
    except (CommandExecutionError, SaltInvocationError) as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def csr_managed(
    name,
    private_key,
    private_key_passphrase=None,
    digest="sha256",
    encoding="pem",
    subject=None,
    **kwargs,
):
    """
    Ensure a certificate signing request is present as specified.

    This function accepts the same arguments as :py:func:`x509.create_csr <salt.modules.x509_v2.create_csr>`,
    as well as most ones for :py:func:`file.managed <salt.states.file.managed>`.

    name
        The path the certificate signing request should be present at.

    private_key
        The private key corresponding to the public key the certificate should
        be issued for. The CSR will be signed by it. Required.

    private_key_passphrase
        If ``private_key`` is encrypted, the passphrase to decrypt it.

    digest
        The hashing algorithm to use for the signature. Valid values are:
        sha1, sha224, sha256, sha384, sha512, sha512_224, sha512_256, sha3_224,
        sha3_256, sha3_384, sha3_512. Defaults to ``sha256``.
        This will be ignored for ``ed25519`` and ``ed448`` key types.

    encoding
        Specify the encoding of the resulting certificate revocation list.
        It can be serialized as a ``pem`` text or binary ``der`` file.
        Defaults to ``pem``.

    kwargs
        Embedded X.509v3 extensions and the subject's distinguished name can be
        controlled via supplemental keyword arguments.
        See :py:func:`x509.create_certificate <salt.modules.x509_v2.create_certificate>`
        for an overview. Mind that some extensions are not available for CSR
        (``authorityInfoAccess``, ``authorityKeyIdentifier``,
        ``issuerAltName``, ``crlDistributionPoints``).
    """
    # Deprecation checks vs the old x509 module
    if "algorithm" in kwargs:
        salt.utils.versions.warn_until(
            3009,
            "`algorithm` has been renamed to `digest`. Please update your code.",
        )
        digest = kwargs.pop("algorithm")
    kwargs = x509util.ensure_cert_kwargs_compat(kwargs)

    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "The certificate signing request is in the correct state",
    }
    current = current_encoding = None
    changes = {}
    verb = "create"
    file_args, csr_args = _split_file_kwargs(_filter_state_internal_kwargs(kwargs))

    try:
        # check file.managed changes early to avoid using unnecessary resources
        file_managed_test = _file_managed(name, test=True, replace=False, **file_args)

        if file_managed_test["result"] is False:
            ret["result"] = False
            ret["comment"] = (
                "Problem while testing file.managed changes, see its output"
            )
            _add_sub_state_run(ret, file_managed_test)
            return ret

        if "is not present and is not set for creation" in file_managed_test["comment"]:
            _add_sub_state_run(ret, file_managed_test)
            return ret

        real_name = name
        replace = False

        # handle follow_symlinks
        if __salt__["file.is_link"](name):
            if file_args.get("follow_symlinks", True):
                real_name = os.path.realpath(name)
            else:
                # workaround https://github.com/saltstack/salt/issues/31802
                __salt__["file.remove"](name)
                replace = True

        if __salt__["file.file_exists"](real_name):
            try:
                current, current_encoding = x509util.load_csr(
                    real_name, get_encoding=True
                )
            except SaltInvocationError as err:
                if any(
                    (
                        "Could not load PEM-encoded" in str(err),
                        "Could not load DER-encoded" in str(err),
                    )
                ):
                    replace = True
                else:
                    raise
            except cx509.InvalidVersion:
                # by default, the previous x509 modules generated CSR with
                # invalid versions, which leads to an exception in cryptography >= v38
                changes["invalid_version"] = True
                replace = True
            else:
                try:
                    if current.signature_hash_algorithm is not None and not isinstance(
                        current.signature_hash_algorithm,
                        type(x509util.get_hashing_algorithm(digest)),
                    ):
                        # ed25519, ed448 do not use a separate hash for signatures, hence algo is None
                        changes["digest"] = digest
                except UnsupportedAlgorithm:
                    # this eg happens with sha3 digest in cryptography < v39
                    log.warning(
                        "Could not determine signature hash algorithm of '%s'. "
                        "Continuing anyways",
                        name,
                    )

                if encoding != current_encoding:
                    changes["encoding"] = encoding

                builder, privkey = x509util.build_csr(
                    private_key,
                    private_key_passphrase=private_key_passphrase,
                    subject=subject,
                    **csr_args,
                )
                if not x509util.is_pair(current.public_key(), privkey):
                    changes["private_key"] = True
                changes.update(_compare_csr(current, builder))
        else:
            changes["created"] = name

        if replace:
            changes["replaced"] = name

        if (
            not changes
            and file_managed_test["result"]
            and not file_managed_test["changes"]
        ):
            _add_sub_state_run(ret, file_managed_test)
            return ret

        ret["changes"] = changes
        if current and changes:
            verb = "recreate"

        if __opts__["test"]:
            ret["result"] = None if changes else True
            ret["comment"] = (
                f"The certificate signing request would have been {verb}d"
                if changes
                else ret["comment"]
            )
            _add_sub_state_run(ret, file_managed_test)
            return ret

        if changes:
            if not set(changes) - {"encoding"}:
                # do not regenerate if only metaparameters changed
                csr = __salt__["x509.encode_csr"](current, encoding=encoding)
            else:
                csr = __salt__["x509.create_csr"](
                    private_key,
                    private_key_passphrase=private_key_passphrase,
                    digest=digest,
                    encoding=encoding,
                    subject=subject,
                    **csr_args,
                )
            ret["comment"] = f"The certificate signing request has been {verb}d"
            if encoding == "der":
                # file.managed does not support binary contents, so create
                # an empty file first (makedirs). This will not work with check_cmd!
                file_managed_ret = _file_managed(name, replace=False, **file_args)
                _add_sub_state_run(ret, file_managed_ret)
                if not _check_file_ret(file_managed_ret, ret, current):
                    return ret
                _safe_atomic_write(
                    real_name, base64.b64decode(csr), file_args.get("backup", "")
                )
        if not changes or encoding == "pem":
            replace = bool((encoding == "pem") and changes)
            contents = csr if replace else None
            file_managed_ret = _file_managed(
                name, contents=contents, replace=replace, **file_args
            )
            _add_sub_state_run(ret, file_managed_ret)
            if not _check_file_ret(file_managed_ret, ret, current):
                return ret

    except (CommandExecutionError, SaltInvocationError) as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def pem_managed(name, text, **kwargs):
    """
    Manage the contents of a PEM file directly with the content in text,
    ensuring correct formatting.

    name
        The path to the file to manage.

    text
        The PEM-formatted text to write.

    kwargs
        Most arguments supported by :py:func:`file.managed <salt.states.file.managed>` are passed through.
    """
    file_args, extra_args = _split_file_kwargs(kwargs)
    if extra_args:
        raise SaltInvocationError(f"Unrecognized keyword arguments: {list(extra_args)}")

    try:
        file_args["contents"] = __salt__["x509.get_pem_entry"](text=text)
    except (CommandExecutionError, SaltInvocationError) as err:
        return {"name": name, "result": False, "comment": str(err), "changes": {}}
    return _file_managed(name, **file_args)


def private_key_managed(
    name,
    algo="rsa",
    keysize=None,
    passphrase=None,
    encoding="pem",
    new=False,
    overwrite=False,
    pkcs12_encryption_compat=False,
    **kwargs,
):
    """
    Ensure a private key is present as specified.

    This function accepts the same arguments as :py:func:`x509.create_private_key <salt.modules.x509_v2.create_private_key>`,
    as well as most ones for :py:func:`file.managed <salt.states.file.managed>`.

    .. note::

        If ``mode`` is unspecified, it will default to ``0400``.

    name
        The path the private key should be present at.

    algo
        The digital signature scheme the private key should be based on.
        Available: ``rsa``, ``ec``, ``ed25519``, ``ed448``. Defaults to ``rsa``.

    keysize
        For ``rsa``, specifies the bitlength of the private key (2048, 3072, 4096).
        For ``ec``, specifies the NIST curve to use (256, 384, 521).
        Irrelevant for Edwards-curve schemes (``ed25519``, ``ed448``).
        Defaults to 2048 for RSA and 256 for EC.

    passphrase
        If this is specified, the private key will be encrypted using this
        passphrase. The encryption algorithm cannot be selected, it will be
        determined automatically as the best available one.

    encoding
        Specify the encoding of the resulting private key. It can be serialized
        as a ``pem`` text, binary ``der`` or ``pkcs12`` file.
        Defaults to ``pem``.

    new
        Always create a new key. Defaults to false.
        Combining new with :mod:`prereq <salt.states.requisites.prereq>`
        can allow key rotation whenever a new certificate is generated.

    overwrite
        Overwrite an existing private key if the provided passphrase cannot decrypt it.
        Defaults to false.

    pkcs12_encryption_compat
        Some operating systems are incompatible with the encryption defaults
        for PKCS12 used since OpenSSL v3. This switch triggers a fallback to
        ``PBESv1SHA1And3KeyTripleDESCBC``.
        Please consider the `notes on PKCS12 encryption <https://cryptography.io/en/stable/hazmat/primitives/asymmetric/serialization/#cryptography.hazmat.primitives.serialization.pkcs12.serialize_key_and_certificates>`_.

    Example:

    The Jinja templating in this example ensures a new private key is generated
    if the file does not exist and whenever the associated certificate
    is to be renewed.

    .. code-block:: jinja

        Manage www private key:
          x509.private_key_managed:
            - name: /etc/pki/www.key
            - keysize: 4096
            - new: true
        {%- if salt["file.file_exists"]("/etc/pki/www.key") %}
            - prereq:
              - x509: /etc/pki/www.crt
        {%- endif %}
    """
    # Deprecation checks vs the old x509 module
    if "bits" in kwargs:
        salt.utils.versions.warn_until(
            3009,
            "`bits` has been renamed to `keysize`. Please update your code.",
        )
        keysize = kwargs.pop("bits")

    ignored_params = {"cipher", "verbose", "text"}.intersection(
        kwargs
    )  # path, overwrite
    if ignored_params:
        salt.utils.versions.kwargs_warn_until(ignored_params, "Potassium")
        for x in ignored_params:
            kwargs.pop(x)

    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "The private key is in the correct state",
    }
    current = current_encoding = None
    changes = {}
    verb = "create"
    file_args, extra_args = _split_file_kwargs(kwargs)

    if extra_args:
        raise SaltInvocationError(f"Unrecognized keyword arguments: {list(extra_args)}")

    if not file_args.get("mode"):
        # ensure secure defaults
        file_args["mode"] = "0400"

    try:
        if keysize and algo in ["ed25519", "ed448"]:
            raise SaltInvocationError(f"keysize is an invalid parameter for {algo}")

        # check file.managed changes early to avoid using unnecessary resources
        file_managed_test = _file_managed(name, test=True, replace=False, **file_args)

        if file_managed_test["result"] is False:
            ret["result"] = False
            ret["comment"] = (
                "Problem while testing file.managed changes, see its output"
            )
            _add_sub_state_run(ret, file_managed_test)
            return ret

        if "is not present and is not set for creation" in file_managed_test["comment"]:
            _add_sub_state_run(ret, file_managed_test)
            return ret

        real_name = name
        replace = False

        # handle follow_symlinks
        if __salt__["file.is_link"](name):
            if file_args.get("follow_symlinks", True):
                real_name = os.path.realpath(name)
            else:
                # workaround https://github.com/saltstack/salt/issues/31802
                __salt__["file.remove"](name)
                replace = True

        file_exists = __salt__["file.file_exists"](real_name)

        if file_exists and not new:
            try:
                current, current_encoding, _ = x509util.load_privkey(
                    real_name, passphrase=passphrase, get_encoding=True
                )
            except SaltInvocationError as err:
                if "Bad decrypt" in str(err):
                    if not overwrite:
                        raise CommandExecutionError(
                            "The provided passphrase cannot decrypt the private key. "
                            "Pass overwrite: true to force regeneration"
                        ) from err
                    changes["passphrase"] = True
                elif any(
                    (
                        "Could not deserialize binary data" in str(err),
                        "Could not load DER-encoded" in str(err),
                        "Could not load PEM-encoded" in str(err),
                    )
                ):
                    if not overwrite:
                        raise CommandExecutionError(
                            "The existing file does not seem to be a private key "
                            "formatted as DER, PEM or embedded in PKCS12. "
                            "Pass overwrite: true to force regeneration"
                        ) from err
                    replace = True
                elif "Private key is unencrypted" in str(err):
                    changes["passphrase"] = True
                    current, current_encoding, _ = x509util.load_privkey(
                        real_name, passphrase=None, get_encoding=True
                    )
                elif "Private key is encrypted" in str(err) and not passphrase:
                    if not overwrite:
                        raise CommandExecutionError(
                            "The existing file is encrypted. Pass overwrite: true "
                            "to force regeneration without passphrase"
                        ) from err
                    changes["passphrase"] = True
                else:
                    raise
        if current:
            key_type = x509util.get_key_type(current)
            check_keysize = keysize
            if check_keysize is None:
                if algo == "rsa":
                    check_keysize = 2048
                elif algo == "ec":
                    check_keysize = 256
            if any(
                (
                    (algo == "rsa" and not key_type == x509util.KEY_TYPE.RSA),
                    (algo == "ec" and not key_type == x509util.KEY_TYPE.EC),
                    (algo == "ed25519" and not key_type == x509util.KEY_TYPE.ED25519),
                    (algo == "ed448" and not key_type == x509util.KEY_TYPE.ED448),
                )
            ):
                changes["algo"] = algo
            if (
                "algo" not in changes
                and algo in ("rsa", "ec")
                and current.key_size != check_keysize
            ):
                changes["keysize"] = check_keysize
            if encoding != current_encoding:
                changes["encoding"] = encoding
        elif file_exists and new:
            changes["replaced"] = name
        else:
            changes["created"] = name

        if (
            not changes
            and file_managed_test["result"]
            and not file_managed_test["changes"]
        ):
            _add_sub_state_run(ret, file_managed_test)
            return ret

        ret["changes"] = changes
        if file_exists and changes:
            verb = "recreate"

        if __opts__["test"]:
            ret["result"] = None if changes else True
            ret["comment"] = (
                f"The private key would have been {verb}d"
                if changes
                else ret["comment"]
            )
            _add_sub_state_run(ret, file_managed_test)
            return ret

        if changes:
            if not set(changes) - {"encoding", "passphrase"}:
                # do not regenerate if only metaparameters changed
                pk = __salt__["x509.encode_private_key"](
                    current, passphrase=passphrase, encoding=encoding
                )
            else:
                pk = __salt__["x509.create_private_key"](
                    algo=algo,
                    keysize=keysize,
                    passphrase=passphrase,
                    encoding=encoding,
                    pkcs12_encryption_compat=pkcs12_encryption_compat,
                )
            ret["comment"] = f"The private key has been {verb}d"
            if encoding != "pem":
                # file.managed does not support binary contents, so create
                # an empty file first (makedirs). This will not work with check_cmd!
                file_managed_ret = _file_managed(name, replace=False, **file_args)
                _add_sub_state_run(ret, file_managed_ret)
                if not _check_file_ret(file_managed_ret, ret, current):
                    return ret
                _safe_atomic_write(
                    real_name, base64.b64decode(pk), file_args.get("backup", "")
                )

        if not changes or encoding == "pem":
            replace = bool((encoding == "pem") and changes)
            contents = pk if replace else None
            file_managed_ret = _file_managed(
                name, contents=contents, replace=replace, **file_args
            )
            _add_sub_state_run(ret, file_managed_ret)
            if not _check_file_ret(file_managed_ret, ret, current):
                return ret
    except (CommandExecutionError, SaltInvocationError) as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def _filter_state_internal_kwargs(kwargs):
    # check_cmd is a valid argument to file.managed
    ignore = set(_STATE_INTERNAL_KEYWORDS) - {"check_cmd"}
    return {k: v for k, v in kwargs.items() if k not in ignore}


def _split_file_kwargs(kwargs):
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
        "encoding",
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
    return file_args, extra_args


def _add_sub_state_run(ret, sub):
    sub["low"] = {
        "name": ret["name"],
        "state": "file",
        "__id__": __low__["__id__"],
        "fun": "managed",
    }
    if "sub_state_run" not in ret:
        ret["sub_state_run"] = []
    ret["sub_state_run"].append(sub)


def _file_managed(name, test=None, **kwargs):
    if test not in [None, True]:
        raise SaltInvocationError("test param can only be None or True")
    # work around https://github.com/saltstack/salt/issues/62590
    test = test or __opts__["test"]
    res = __salt__["state.single"]("file.managed", name, test=test, **kwargs)
    return res[next(iter(res))]


def _check_file_ret(fret, ret, current):
    if fret["result"] is False:
        ret["result"] = False
        ret["comment"] = (
            f"Could not {'create' if not current else 'update'} file, see file.managed output"
        )
        ret["changes"] = {}
        return False
    return True


def _build_cert(
    ca_server=None, signing_policy=None, signing_private_key=None, **kwargs
):
    final_kwargs = copy.deepcopy(kwargs)
    final_kwargs["signing_private_key"] = signing_private_key
    x509util.merge_signing_policy(
        __salt__["x509.get_signing_policy"](signing_policy, ca_server=ca_server),
        final_kwargs,
    )
    signing_private_key = final_kwargs.pop("signing_private_key")

    builder, _, private_key_loaded, signing_cert = x509util.build_crt(
        signing_private_key,
        skip_load_signing_private_key=ca_server is not None,
        **final_kwargs,
    )
    return builder, private_key_loaded, signing_cert, final_kwargs


def _compare_cert(current, builder, signing_cert, serial_number, not_before, not_after):
    changes = {}

    if (
        serial_number is not None
        and _getattr_safe(builder, "_serial_number") != current.serial_number
    ):
        changes["serial_number"] = serial_number

    if not x509util.match_pubkey(
        _getattr_safe(builder, "_public_key"), current.public_key()
    ):
        changes["private_key"] = True

    if signing_cert and not x509util.verify_signature(
        current, signing_cert.public_key()
    ):
        changes["signing_private_key"] = True

    if _getattr_safe(builder, "_subject_name") != current.subject:
        changes["subject_name"] = _getattr_safe(
            builder, "_subject_name"
        ).rfc4514_string()

    if _getattr_safe(builder, "_issuer_name") != current.issuer:
        changes["issuer_name"] = _getattr_safe(builder, "_issuer_name").rfc4514_string()

    ext_changes = _compare_exts(current, builder)
    if any(ext_changes.values()):
        changes["extensions"] = ext_changes
    return changes


def _compare_csr(current, builder):
    changes = {}

    # if _getattr_safe(builder, "_subject_name") != current.subject:
    if not _compareattr_safe(builder, "_subject_name", current.subject):
        changes["subject_name"] = _getattr_safe(
            builder, "_subject_name"
        ).rfc4514_string()

    ext_changes = _compare_exts(current, builder)
    if any(ext_changes.values()):
        changes["extensions"] = ext_changes
    return changes


def _compare_crl(current, builder, sig_pubkey):
    # these are necessary because the classes do not have the required method
    def _get_revoked_certificate_by_serial_number(revoked, serial):
        try:
            return [x for x in revoked if x.serial_number == serial][0]
        except IndexError:
            return None

    def _get_extension_for_oid(extensions, oid):
        try:
            return [x for x in extensions if x.oid == oid][0]
        except IndexError:
            return None

    changes = {}

    if _getattr_safe(builder, "_issuer_name") != current.issuer:
        changes["issuer_name"] = _getattr_safe(builder, "_issuer_name").rfc4514_string()
    if not current.is_signature_valid(sig_pubkey):
        changes["public_key"] = True

    rev_changes = {"added": [], "changed": [], "removed": []}
    revoked = _getattr_safe(builder, "_revoked_certificates")
    for rev in revoked:
        cur = current.get_revoked_certificate_by_serial_number(rev.serial_number)
        if cur is None:
            # certificate was not revoked before
            rev_changes["added"].append(x509util.dec2hex(rev.serial_number))
            continue

        for ext in rev.extensions:
            cur_ext = _get_extension_for_oid(cur.extensions, ext.oid)
            # revoked certificate's extensions have changed (added/changed)
            if any(
                (
                    cur_ext is None,
                    cur_ext.critical != ext.critical,
                    cur_ext.value != ext.value,
                )
            ):
                rev_changes["changed"].append(x509util.dec2hex(rev.serial_number))

        for cur_ext in cur.extensions:
            if _get_extension_for_oid(rev.extensions, cur_ext.oid) is None:
                # an extension was removed from from the revoked certificate
                rev_changes["changed"].append(x509util.dec2hex(rev.serial_number))

    for rev in current:
        # certificate was removed from the CRL, probably because it was outdated anyways
        if (
            _get_revoked_certificate_by_serial_number(revoked, rev.serial_number)
            is None
        ):
            rev_changes["removed"].append(x509util.dec2hex(rev.serial_number))

    if any(rev_changes.values()):
        changes["revocations"] = rev_changes

    ext_changes = _compare_exts(current, builder)
    if any(ext_changes.values()):
        changes["extensions"] = ext_changes
    return changes


def _compare_exts(current, builder):
    def getextname(ext):
        try:
            return ext.oid._name
        except AttributeError:
            return ext.oid.dotted_string

    added = []
    changed = []
    removed = []
    builder_extensions = cx509.Extensions(_getattr_safe(builder, "_extensions"))

    # iter is unnecessary, but avoids a pylint < 2.13.6 crash
    for ext in iter(builder_extensions):
        try:
            cur_ext = current.extensions.get_extension_for_oid(ext.value.oid)
            if cur_ext.critical != ext.critical or cur_ext.value != ext.value:
                changed.append(getextname(ext))
        except cx509.ExtensionNotFound:
            added.append(getextname(ext))

    for ext in current.extensions:
        try:
            builder_extensions.get_extension_for_oid(ext.value.oid)
        except cx509.ExtensionNotFound:
            removed.append(getextname(ext))

    return {"added": added, "changed": changed, "removed": removed}


def _compare_ca_chain(current, new):
    if not len(current) == len(new):
        return False
    for i, new_cert in enumerate(new):
        if new_cert.fingerprint(hashes.SHA256()) != current[i].fingerprint(
            hashes.SHA256()
        ):
            return False
    return True


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


def _compareattr_safe(obj, attr, comp):
    try:
        return getattr(obj, attr) == comp
    except AttributeError:
        return False


def _safe_atomic_write(dst, data, backup):
    """
    Create a temporary file with only user r/w perms and atomically
    copy it to the destination, honoring ``backup``.
    """
    tmp = salt.utils.files.mkstemp(prefix=salt.utils.files.TEMPFILE_PREFIX)
    with salt.utils.files.fopen(tmp, "wb") as tmp_:
        tmp_.write(data)
    salt.utils.files.copyfile(
        tmp, dst, __salt__["config.backup_mode"](backup), __opts__["cachedir"]
    )
    salt.utils.files.safe_rm(tmp)
