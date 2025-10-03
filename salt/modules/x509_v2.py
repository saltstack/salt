"""
Manage X.509 certificates
=========================

:depends: cryptography

.. versionadded:: 3006.0

    This module represents a complete rewrite of the original ``x509`` modules
    and is named ``x509_v2`` since it introduces breaking changes.


.. note::

    * PKCS12-related operations require at least cryptography release 36.
    * PKCS12-related operations with Edwards-curve keys require at least cryptography release 37.
    * PKCS7-related operations require at least cryptography release 37.


Configuration
-------------
Explicit activation
~~~~~~~~~~~~~~~~~~~
Since this module uses the same virtualname as the previous ``x509`` modules,
but is incompatible with them, it needs to be explicitly activated on each
minion by including the following line in the minion configuration:

.. code-block:: yaml

    # /etc/salt/minion.d/x509.conf

    features:
      x509_v2: true

Peer communication
~~~~~~~~~~~~~~~~~~
To be able to remotely sign certificates, it is required to configure the Salt
master to allow :term:`Peer Communication`:

.. code-block:: yaml

    # /etc/salt/master.d/peer.conf

    peer:
      .*:
        - x509.sign_remote_certificate

In order for the :term:`Compound Matcher` to work with restricting signing
policies to a subset of minions, in addition calls to
:py:func:`match.compound_matches <salt.runners.match.compound_matches>`
by the minion acting as the CA must be permitted:

.. code-block:: yaml

    # /etc/salt/master.d/peer.conf

    peer:
      .*:
        - x509.sign_remote_certificate

    peer_run:
      ca_server:
        - match.compound_matches

.. note::

    When compound match expressions are employed, pillar values can only be matched
    literally. This is a barrier to enumeration attacks by the CA server.

    Also note that compound matching requires a minion data cache on the master.
    Any certificate signing request will be denied if :conf_master:`minion_data_cache` is
    disabled (it is enabled by default).

.. note::

    Since grain values are controlled by minions, you should avoid using them
    to restrict certificate issuance.

    See :ref:`Is Targeting using Grain Data Secure? <faq-grain-security>`.

.. versionchanged:: 3007.0

    Previously, a compound expression match was validated by the requesting minion
    itself via peer publishing, which did not protect from compromised minions.
    The new match validation takes place on the master using peer running.


Signing policies
~~~~~~~~~~~~~~~~
In addition, the minion representing the CA needs to have at least one
signing policy configured, remote calls not referencing one are always
rejected.

The parameters specified in this signing policy override any
parameters passed from the minion requesting the certificate. It can be
configured in the CA minion's pillar, which takes precedence, or any
location :py:func:`config.get <salt.modules.config.get>` looks up in.
Signing policies are defined under ``x509_signing_policies``.

You can restrict which minions can request a certificate under a configured
signing policy by specifying a matcher in ``minions``. This can be a glob
or compound matcher (for the latter, see the notes above).

.. code-block:: yaml

    x509_signing_policies:
      www:
        - minions: 'www*'
        - signing_private_key: /etc/pki/ca.key
        - signing_cert: /etc/pki/ca.crt
        - C: US
        - ST: Utah
        - L: Salt Lake City
        - basicConstraints: "critical, CA:false"
        - keyUsage: "critical, cRLSign, keyCertSign"
        - subjectKeyIdentifier: hash
        - authorityKeyIdentifier: keyid,issuer:always
        - days_valid: 90
        - copypath: /etc/pki/issued_certs/


.. note::

    The following semantics are applied regarding the order of preference
    for specifying the subject name:

    * If neither ``subject`` nor any name attributes (like ``CN``) are part of the policy,
      issued certificates can contain any requested ones.
    * If any name attributes are specified in the signing policy, ``subject`` contained
      in requests is ignored.
    * If ``subject`` is specified in the signing policy, any name attributes are ignored.
      If the request contains the same data type for ``subject`` as the signing policy
      (for dicts and lists, and only then), merging is performed, otherwise ``subject``
      is taken from the signing policy. Dicts are merged and list items are appended,
      with the items taken from the signing policy having priority.


Breaking changes versus the previous ``x509`` modules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* The output format has changed for all ``read_*`` functions as well as the state return dict.
* The formatting of some extension definitions might have changed, but should
  be stable for most basic use cases.
* The default ordering of RDNs/Name Attributes in the subject's Distinguished Name
  has been adapted to industry standards. This might cause a reissuance
  during the first state run.
* For ``x509.private_key_managed``, the file mode defaults to ``0400``. This should
  be considered a bug fix because writing private keys with world-readable
  permissions by default is a security issue.
* Restricting signing policies using compound match expressions requires peer run
  permissions instead of peer publishing permissions:

.. code-block:: yaml

    # x509, x509_v2 in 3006.*
    peer:
      ca_server:
        - match.compound

    # x509_v2 from 3007.0 onwards
    peer_run:
      ca_server:
        - match.compound_matches

Note that when a ``ca_server`` is involved, both peers must use the updated module version.

.. _x509-setup:
"""

import base64
import copy
import glob
import logging
import os.path
import re
import sys
from datetime import datetime, timedelta, timezone

try:
    import cryptography.x509 as cx509
    from cryptography.hazmat.primitives import hashes, serialization

    import salt.utils.x509 as x509util

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

import salt.utils.dictupdate
import salt.utils.files
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)


__virtualname__ = "x509"


def __virtual__():
    if not HAS_CRYPTOGRAPHY:
        return (False, "Could not load cryptography")
    # salt.features appears to not be setup when invoked via peer publishing
    if not __opts__.get("features", {}).get("x509_v2"):
        return (
            False,
            "x509_v2 needs to be explicitly enabled by setting `x509_v2: true` "
            "in the minion configuration value `features` until Salt 3008 (Argon).",
        )
    return __virtualname__


def create_certificate(
    ca_server=None,
    signing_policy=None,
    encoding="pem",
    append_certs=None,
    pkcs12_passphrase=None,
    pkcs12_encryption_compat=False,
    pkcs12_friendlyname=None,
    path=None,
    overwrite=True,
    raw=False,
    **kwargs,
):
    """
    Create an X.509 certificate and return an encoded version of it.

    .. note::

        All parameters that take a public key, private key or certificate
        can be specified either as a PEM/hex/base64 string or a path to a
        local file encoded in all supported formats for the type.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.create_certificate signing_private_key='/etc/pki/myca.key' csr='/etc/pki/my.csr'

    ca_server
        Request a remotely signed certificate from ca_server. For this to
        work, a ``signing_policy`` must be specified, and that same policy
        must be configured on the ca_server. See `Signing policies`_ for
        details. Also, the Salt master must permit peers to call the
        ``sign_remote_certificate`` function, see `Peer communication`_.

    signing_policy
        The name of a configured signing policy. Parameters specified in there
        are hardcoded and cannot be overridden. This is required for remote signing,
        otherwise optional. See `Signing policies`_ for details.

    encoding
        Specify the encoding of the resulting certificate. It can be returned
        as a ``pem`` (or ``pkcs7_pem``) string or several (base64-encoded)
        binary formats (``der``, ``pkcs7_der``, ``pkcs12``). Defaults to ``pem``.

    append_certs
        A list of additional certificates to append to the new one, e.g. to create a CA chain.

        .. note::

            Mind that when ``der`` encoding is in use, appending certificatees is prohibited.

    copypath
        Create a copy of the issued certificate in PEM format in this directory.
        The file will be named ``<serial_number>.crt`` if prepend_cn is False.

    prepend_cn
        When ``copypath`` is set, prepend the common name of the certificate to
        the file name like so: ``<CN>-<serial_number>.crt``. Defaults to false.

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

    path
        Instead of returning the certificate, write it to this file path.

    overwrite
        If ``path`` is specified and the file exists, overwrite it.
        Defaults to true.

    raw
        Return the encoded raw bytes instead of a string. Defaults to false.

    digest
        The hashing algorithm to use for the signature. Valid values are:
        sha1, sha224, sha256, sha384, sha512, sha512_224, sha512_256, sha3_224,
        sha3_256, sha3_384, sha3_512. Defaults to ``sha256``.
        This will be ignored for ``ed25519`` and ``ed448`` key types.

    private_key
        The private key corresponding to the public key the certificate should
        be issued for. This is one way of specifying the public key that will
        be included in the certificate, the other ones being ``public_key`` and ``csr``.

    private_key_passphrase
        If ``private_key`` is specified and encrypted, the passphrase to decrypt it.

    public_key
        The public key the certificate should be issued for. Other ways of passing
        the required information are ``private_key`` and ``csr``. If neither are set,
        the public key of the ``signing_private_key`` will be included, i.e.
        a self-signed certificate is generated.

    csr
        A certificate signing request to use as a base for generating the certificate.
        The following information will be respected, depending on configuration:
        * public key
        * extensions, if not otherwise specified (arguments, signing_policy)

    signing_cert
        The CA certificate to be used for signing the issued certificate.

    signing_private_key
        The private key corresponding to the public key in ``signing_cert``. Required.

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
        If unspecified, defaults to the current time plus ``days_valid`` days.

    days_valid
        If ``not_after`` is unspecified, the number of days from the time of issuance
        the certificate should be valid for. Defaults to ``30``.

    subject
        The subject's distinguished name embedded in the certificate. This is one way of
        passing this information (see ``kwargs`` below for the other).
        This argument will be preferred and allows to control the order of RDNs in the DN
        as well as to embed RDNs with multiple attributes.
        This can be specified as an RFC4514-encoded string (``CN=example.com,O=Example Inc,C=US``,
        mind that the rendered order is reversed from what is embedded), a list
        of RDNs encoded as in RFC4514 (``["C=US", "O=Example Inc", "CN=example.com"]``)
        or a dictionary (``{"CN": "example.com", "C": "US", "O": "Example Inc"}``,
        default ordering).
        Multiple name attributes per RDN are concatenated with a ``+``.

        .. note::

            Parsing of RFC4514 strings requires at least cryptography release 37.

    kwargs
        Embedded X.509v3 extensions and the subject's distinguished name can be
        controlled via supplemental keyword arguments. See the following for an overview.

    Subject properties in kwargs
        C, ST, L, STREET, O, OU, CN, MAIL, SN, GN, UID, SERIALNUMBER

    X.509v3 extensions in kwargs
        Most extensions can be configured using the same string format as OpenSSL,
        while some require adjustments. In general, since the strings are
        parsed to dicts/lists, you can always use the latter formats directly.
        Marking an extension as critical is done by including it at the beginning
        of the configuration string, in the list or as a key in the dictionary
        with the value ``true``.

        Examples (some showcase dict/list correspondance):

        basicConstraints
            ``critical, CA:TRUE, pathlen:1`` or

            .. code-block:: yaml

                - basicConstraints:
                    critical: true
                    ca: true
                    pathlen: 1

        keyUsage
            ``critical, cRLSign, keyCertSign`` or

            .. code-block:: yaml

                - keyUsage:
                    - critical
                    - cRLSign
                    - keyCertSign

        subjectKeyIdentifier
            This can be an explicit value or ``hash``, in which case the value
            will be set to the SHA1 hash of some encoding of the associated public key,
            depending on the underlying algorithm (RSA/ECDSA/EdDSA).

        authorityKeyIdentifier
            ``keyid:always, issuer``

        subjectAltName
            There is support for all OpenSSL-defined types except ``otherName``.

            ``email:me@example.com,DNS:example.com`` or

            .. code-block:: yaml

                # mind this being a list, not a dict
                - subjectAltName:
                    - email:me@example.com
                    - DNS:example.com

        issuerAltName
            The syntax is the same as for ``subjectAltName``, except that the additional
            value ``issuer:copy`` is supported, which will copy the values of
            ``subjectAltName`` in the issuer's certificate.

        authorityInfoAccess
            ``OCSP;URI:http://ocsp.example.com/,caIssuers;URI:http://myca.example.com/ca.cer``

        crlDistributionPoints
            When set to a string value, items are interpreted as fullnames:

            ``URI:http://example.com/myca.crl, URI:http://example.org/my.crl``

            There is also support for more attributes using the full form:

            .. code-block:: yaml

                - crlDistributionPoints:
                    - fullname: URI:http://example.com/myca.crl
                      crlissuer: DNS:example.org
                      reasons:
                        - keyCompromise
                    - URI:http://example.org/my.crl

        certificatePolicies
            ``critical, 1.2.4.5, 1.1.3.4``

            Again, there is support for more attributes using the full form:

            .. code-block:: yaml

                - certificatePolicies:
                    critical: true
                    1.2.3.4.5: https://my.ca.com/pratice_statement
                    1.2.4.5.6:
                      - https://my.ca.com/pratice_statement
                      - organization: myorg
                        noticeNumbers: [1, 2, 3]
                        text: mytext

        policyConstraints
            ``requireExplicitPolicy:3,inhibitPolicyMapping:1``

        inhibitAnyPolicy
            The value is just an integer: ``- inhibitAnyPolicy: 1``

        nameConstraints
            ``critical,permitted;IP:192.168.0.0/255.255.0.0,permitted;email:.example.com,excluded;email:.com``

            .. code-block:: yaml

                - nameConstraints:
                    critical: true
                    permitted:
                      - IP:192.168.0.0/24
                      - email:.example.com
                    excluded:
                      - email:.com
        noCheck
            This extension does not take any values, except ``critical``. Just the presence
            in the keyword args will include it.

        tlsfeature
            ``status_request``

        For more information, visit the `OpenSSL docs <https://www.openssl.org/docs/man3.0/man5/x509v3_config.html>`_.
    """
    # Deprecation checks vs the old x509 module
    if "algorithm" in kwargs:
        salt.utils.versions.warn_until(
            3009,
            "`algorithm` has been renamed to `digest`. Please update your code.",
        )
        kwargs["digest"] = kwargs.pop("algorithm")

    ignored_params = {"text", "version", "serial_bits"}.intersection(
        kwargs
    )  # path, overwrite
    if ignored_params:
        salt.utils.versions.kwargs_warn_until(ignored_params, "Potassium")
    kwargs = x509util.ensure_cert_kwargs_compat(kwargs)

    if "days_valid" not in kwargs and "not_after" not in kwargs:
        try:
            salt.utils.versions.warn_until(
                3009,
                "The default value for `days_valid` will change to 30. Please adapt your code accordingly.",
            )
            kwargs["days_valid"] = 365
        except RuntimeError:
            pass

    if encoding not in ["der", "pem", "pkcs7_der", "pkcs7_pem", "pkcs12"]:
        raise CommandExecutionError(
            f"Invalid value '{encoding}' for encoding. Valid: "
            "der, pem, pkcs7_der, pkcs7_pem, pkcs12"
        )
    if kwargs.get("digest", "sha256").lower() not in [
        "sha1",
        "sha224",
        "sha256",
        "sha384",
        "sha512",
        "sha512_224",
        "sha512_256",
        "sha3_224",
        "sha3_256",
        "sha3_384",
        "sha3_512",
    ]:
        raise CommandExecutionError(
            f"Invalid value '{kwargs['digest']}' for digest. Valid: sha1, sha224, "
            "sha256, sha384, sha512, sha512_224, sha512_256, sha3_224, sha3_256, "
            "sha3_384, sha3_512"
        )
    if encoding == "der" and append_certs:
        raise SaltInvocationError("Cannot encode a certificate chain in DER")
    if encoding == "pkcs12" and "private_key" not in kwargs:
        # The creation will work, but it will be listed in additional certs, not
        # as the main certificate. This might confuse other parts of the code.
        raise SaltInvocationError(
            "Creating a PKCS12-encoded certificate without embedded private key "
            "is unsupported"
        )
    if "signing_private_key" not in kwargs and not ca_server:
        raise SaltInvocationError(
            "Creating a certificate locally at least requires a signing private key."
        )

    if path and not overwrite and __salt__["file.file_exists"](path):
        return f"The file at {path} exists and overwrite was set to false"
    if ca_server:
        if signing_policy is None:
            raise SaltInvocationError(
                "signing_policy must be specified to request a certificate from "
                "a remote ca_server"
            )
        cert, private_key_loaded = _create_certificate_remote(
            ca_server, signing_policy, **kwargs
        )
    else:
        x509util.merge_signing_policy(_get_signing_policy(signing_policy), kwargs)
        cert, private_key_loaded = _create_certificate_local(**kwargs)

    if encoding == "pkcs12":
        out = encode_certificate(
            cert,
            append_certs=append_certs,
            encoding=encoding,
            private_key=private_key_loaded,
            pkcs12_passphrase=pkcs12_passphrase,
            pkcs12_encryption_compat=pkcs12_encryption_compat,
            pkcs12_friendlyname=pkcs12_friendlyname,
            raw=bool(path) or raw,
        )
    else:
        out = encode_certificate(
            cert, append_certs=append_certs, encoding=encoding, raw=bool(path) or raw
        )

    if path is None:
        return out

    if encoding == "pem":
        return write_pem(
            out.decode(), path, overwrite=overwrite, pem_type="CERTIFICATE"
        )
    with salt.utils.files.fopen(path, "wb") as fp_:
        fp_.write(out)
    return f"Certificate written to {path}"


def _create_certificate_remote(
    ca_server, signing_policy, private_key=None, private_key_passphrase=None, **kwargs
):
    private_key_loaded = None
    if private_key:
        private_key_loaded = x509util.load_privkey(
            private_key, passphrase=private_key_passphrase
        )
        kwargs["public_key"] = x509util.to_der(private_key_loaded.public_key())
    elif kwargs.get("public_key"):
        kwargs["public_key"] = x509util.to_der(
            x509util.load_pubkey(kwargs["public_key"])
        )
    if kwargs.get("csr"):
        kwargs["csr"] = x509util.to_der(x509util.load_csr(kwargs["csr"]))

    result = _query_remote(ca_server, signing_policy, kwargs)
    try:
        return x509util.load_cert(result), private_key_loaded
    except (CommandExecutionError, SaltInvocationError) as err:
        raise CommandExecutionError(
            f"ca_server did not return a certificate: {result}"
        ) from err


def _create_certificate_local(
    digest="sha256", copypath=None, prepend_cn=False, **kwargs
):
    builder, signing_private_key, private_key_loaded, _ = x509util.build_crt(**kwargs)
    algorithm = None
    if x509util.get_key_type(signing_private_key) not in [
        x509util.KEY_TYPE.ED25519,
        x509util.KEY_TYPE.ED448,
    ]:
        algorithm = x509util.get_hashing_algorithm(digest)
    cert = builder.sign(signing_private_key, algorithm=algorithm)

    if copypath:
        prepend = ""
        if prepend_cn:
            try:
                prepend = (
                    cert.subject.get_attributes_for_oid(x509util.NAME_ATTRS_OID["CN"])[
                        0
                    ].value
                    + "-"
                )
            except IndexError:
                pass
        write_pem(
            text=x509util.to_pem(cert),
            path=os.path.join(copypath, f"{prepend}{cert.serial_number:x}.crt"),
            pem_type="CERTIFICATE",
        )
    return cert, private_key_loaded


def encode_certificate(
    certificate,
    encoding="pem",
    append_certs=None,
    private_key=None,
    private_key_passphrase=None,
    pkcs12_passphrase=None,
    pkcs12_encryption_compat=False,
    pkcs12_friendlyname=None,
    raw=False,
):
    """
    Create an encoded representation of a certificate, optionally including
    other structures. This can be used to create certificate chains, convert
    a certificate into a different encoding or embed the corresponding
    private key (for ``pkcs12``).

    CLI Example:

    .. code-block:: bash

        salt '*' x509.encode_certificate /etc/pki/my.crt pem /etc/pki/ca.crt

    certificate
        The certificate to encode.

    encoding
        Specify the encoding of the resulting certificate. It can be returned
        as a ``pem`` (or ``pkcs7_pem``) string or several (base64-encoded)
        binary formats (``der``, ``pkcs7_der``, ``pkcs12``). Defaults to ``pem``.

    append_certs
        A list of additional certificates to encode with the new one, e.g. to create a CA chain.

        .. note::

            Mind that when ``der`` encoding is in use, appending certificatees is prohibited.

    private_key
        For ``pkcs12``, the private key corresponding to the public key of the ``certificate``
        to be embedded.

    private_key_passphrase
        For ``pkcs12``, if the private key to embed is encrypted, specify the corresponding
        passphrase.

    pkcs12_passphrase
        For ``pkcs12``, the container can be encrypted. Specify the passphrase to use here.
        Mind that PKCS12 encryption should not be relied on for security purposes, see
        note above in :py:func:`x509.create_certificate <salt.modules.x509_v2.create_certificate>`.

    pkcs12_encryption_compat
        OpenSSL 3 and cryptography v37 switched to a much more secure default
        encryption for PKCS12, which might be incompatible with some systems.
        This forces the legacy encryption. Defaults to False.

    pkcs12_friendlyname
        When encoding a certificate as ``pkcs12``, a name for the certificate can be included.

    raw
        Return the encoded raw bytes instead of a string. Defaults to false.
    """
    if encoding not in ["der", "pem", "pkcs7_der", "pkcs7_pem", "pkcs12"]:
        raise CommandExecutionError(
            f"Invalid value '{encoding}' for encoding. Valid: "
            "der, pem, pkcs7_der, pkcs7_pem, pkcs12"
        )
    if encoding == "der" and append_certs:
        raise SaltInvocationError("Cannot encode a certificate chain in DER")
    if encoding != "pkcs12" and private_key:
        raise SaltInvocationError(
            "Embedding private keys is only supported for pkcs12 encoding"
        )
    if encoding == "pkcs12" and not private_key:
        # The creation will work, but it will be listed in additional certs, not
        # as the main certificate. This might confuse other parts of the code.
        raise SaltInvocationError(
            "Creating a PKCS12-encoded certificate without embedded private key "
            "is unsupported"
        )

    append_certs = append_certs or []
    if not isinstance(append_certs, list):
        append_certs = [append_certs]

    cert = x509util.load_cert(certificate)
    append_certs = [x509util.load_cert(x) for x in append_certs]

    if encoding in ["der", "pem"]:
        crt_encoding = getattr(serialization.Encoding, encoding.upper())
        crt_bytes = cert.public_bytes(crt_encoding)
        for append_cert in append_certs:
            # this can only happen for PEM, checked in the beginning
            crt_bytes += b"\n" + append_cert.public_bytes(crt_encoding)
    elif encoding == "pkcs12":
        private_key = x509util.load_privkey(
            private_key, passphrase=private_key_passphrase
        )
        if pkcs12_passphrase is None:
            cipher = serialization.NoEncryption()
        else:
            if isinstance(pkcs12_passphrase, str):
                pkcs12_passphrase = pkcs12_passphrase.encode()
            if pkcs12_encryption_compat:
                cipher = (
                    serialization.PrivateFormat.PKCS12.encryption_builder()
                    .kdf_rounds(50000)
                    .key_cert_algorithm(
                        serialization.pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC
                    )
                    .hmac_hash(hashes.SHA1())
                    .build(pkcs12_passphrase)
                )
            else:
                cipher = serialization.BestAvailableEncryption(pkcs12_passphrase)
        crt_bytes = serialization.pkcs12.serialize_key_and_certificates(
            name=(
                salt.utils.stringutils.to_bytes(pkcs12_friendlyname)
                if pkcs12_friendlyname
                else None
            ),
            key=private_key,
            cert=cert,
            cas=append_certs,
            encryption_algorithm=cipher,
        )
    else:  # pkcs7, requires cryptography v37
        try:
            crt_bytes = serialization.pkcs7.serialize_certificates(
                [cert] + append_certs,
                encoding=getattr(
                    serialization.Encoding, "PEM" if encoding == "pkcs7_pem" else "DER"
                ),
            )
        except AttributeError as err:
            raise CommandExecutionError(
                "Serialization to pkcs7 requires at least cryptography release 37."
            ) from err

    if raw:
        return crt_bytes
    if encoding in ["pem", "pkcs7_pem"]:
        return crt_bytes.decode()
    return base64.b64encode(crt_bytes).decode()


def create_crl(
    signing_private_key,
    revoked,
    signing_cert=None,
    signing_private_key_passphrase=None,
    include_expired=False,
    days_valid=None,
    digest="sha256",
    encoding="pem",
    extensions=None,
    path=None,
    raw=False,
    **kwargs,
):
    """
    Create a certificate revocation list.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.create_crl signing_cert=/etc/pki/ca.crt \
                signing_private_key=/etc/pki/ca.key \
                revoked="[{'certificate': '/etc/pki/certs/www1.crt', 'revocation_date': '2015-03-01 00:00:00'}]"

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
        string in the format "%Y-%m-%d %H:%M:%S".

        The dict can also optionally contain the ``not_after`` key. This is
        redundant if the ``certificate`` key is included, since it will be
        sourced from the certificate. If the ``certificate`` key is not included,
        this can be used for the logic behind the ``include_expired`` parameter.
        It should be a string in the format "%Y-%m-%d %H:%M:%S".

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
            Provides the date on which the certificate likely became invalid.
            The value should be a string in the same format as ``revocation_date``.

    signing_cert
        The CA certificate to be used for signing the CRL.

    signing_private_key_passphrase
        If ``signing_private_key`` is encrypted, the passphrase to decrypt it.

    include_expired
        Also include already expired certificates in the CRL. Defaults to false.

    days_valid
        The number of days the CRL should be valid for. This sets the ``Next Update``
        field. Defaults to ``100`` (until v3009) or ``7`` (from v3009 onwards).

    digest
        The hashing algorithm to use for the signature. Valid values are:
        sha1, sha224, sha256, sha384, sha512, sha512_224, sha512_256, sha3_224,
        sha3_256, sha3_384, sha3_512. Defaults to ``sha256``.
        This will be ignored for ``ed25519`` and ``ed448`` key types.

    encoding
        Specify the encoding of the resulting certificate revocation list.
        It can be returned as a ``pem`` string or base64-encoded ``der``.
        Defaults to ``pem``.

    extensions
        Add CRL extensions. The following are available:

        authorityKeyIdentifier
            See :py:func:`x509.create_certificate <salt.modules.x509_v2.create_certificate>`.

        authorityInfoAccess
            See :py:func:`x509.create_certificate <salt.modules.x509_v2.create_certificate>`.

        cRLNumber
            Specifies a sequential number for each CRL issued by a CA.
            Values must be integers.

        deltaCRLIndicator
            If the CRL is a delta CRL, this value points to the cRLNumber
            of the base cRL. Values must be integers.

        freshestCRL
            Identifies how delta CRL information is obtained. The format
            is the same as ``crlDistributionPoints``.

        issuerAltName
            See :py:func:`x509.create_certificate <salt.modules.x509_v2.create_certificate>`.

        issuingDistributionPoint
            Identifies the CRL distribution point for a particular CRL and
            indicates what kinds of revocation it covers. The format is
            comparable to ``crlDistributionPoints``. Specify as follows:

            .. code-block:: yaml

                issuingDistributionPoint:
                  fullname:  # or relativename with RDN
                    - URI:http://example.com/myca.crl
                  onlysomereasons:
                    - keyCompromise
                  onlyuser: true
                  onlyCA: true
                  onlyAA: true
                  indirectCRL: false
    path
        Instead of returning the CRL, write it to this file path.

    raw
        Return the encoded raw bytes instead of a string. Defaults to false.
    """
    # Deprecation checks vs the old x509 module
    if kwargs:
        if "text" in kwargs:
            salt.utils.versions.kwargs_warn_until(["text"], "Potassium")
            kwargs.pop("text")

        unknown = [kwarg for kwarg in kwargs if not kwarg.startswith("_")]
        if unknown:
            raise SaltInvocationError(
                f"Unrecognized keyword arguments: {list(unknown)}"
            )

    if days_valid is None:
        try:
            salt.utils.versions.warn_until(
                3009,
                "The default value for `days_valid` will change to 7. Please adapt your code accordingly.",
            )
            days_valid = 100
        except RuntimeError:
            days_valid = 7

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

    if encoding not in ["der", "pem"]:
        raise CommandExecutionError(
            f"Invalid value '{encoding}' for encoding. Valid: der, pem"
        )
    if digest.lower() not in [
        "sha1",
        "sha224",
        "sha256",
        "sha384",
        "sha512",
        "sha512_224",
        "sha512_256",
        "sha3_224",
        "sha3_256",
        "sha3_384",
        "sha3_512",
    ]:
        raise CommandExecutionError(
            f"Invalid value '{digest}' for digest. Valid: sha1, sha224, sha256, "
            "sha384, sha512, sha512_224, sha512_256, sha3_224, sha3_256, sha3_384, "
            "sha3_512"
        )
    builder, signing_private_key = x509util.build_crl(
        signing_private_key,
        revoked,
        signing_cert=signing_cert,
        signing_private_key_passphrase=signing_private_key_passphrase,
        include_expired=include_expired,
        days_valid=days_valid,
        extensions=extensions,
    )
    algorithm = None
    if x509util.get_key_type(signing_private_key) not in [
        x509util.KEY_TYPE.ED25519,
        x509util.KEY_TYPE.ED448,
    ]:
        algorithm = x509util.get_hashing_algorithm(digest)
    crl = builder.sign(signing_private_key, algorithm=algorithm)
    out = encode_crl(crl, encoding=encoding, raw=bool(path) or raw)

    if path is None:
        return out

    if encoding == "pem":
        return write_pem(out.decode(), path, pem_type="X509 CRL")
    with salt.utils.files.fopen(path, "wb") as fp_:
        fp_.write(out)
    return f"CRL written to {path}"


def encode_crl(crl, encoding="pem", raw=False):
    """
    Create an encoded representation of a certificate revocation list.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.encode_crl /etc/pki/my.crl der

    crl
        The certificate revocation list to encode.

    encoding
        Specify the encoding of the resulting certificate revocation list.
        It can be returned as a ``pem`` string or base64-encoded ``der``.
        Defaults to ``pem``.

    raw
        Return the encoded raw bytes instead of a string. Defaults to false.
    """
    if encoding not in ["der", "pem"]:
        raise CommandExecutionError(
            f"Invalid value '{encoding}' for encoding. Valid: der, pem"
        )

    crl = x509util.load_crl(crl)
    crl_encoding = getattr(serialization.Encoding, encoding.upper())
    crl_bytes = crl.public_bytes(crl_encoding)

    if raw:
        return crl_bytes

    if encoding == "pem":
        return crl_bytes.decode()
    return base64.b64encode(crl_bytes).decode()


def create_csr(
    private_key,
    private_key_passphrase=None,
    digest="sha256",
    encoding="pem",
    path=None,
    raw=False,
    **kwargs,
):
    """
    Create a certificate signing request.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.create_csr private_key='/etc/pki/myca.key' CN='My Cert'

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
        Specify the encoding of the resulting certificate signing request.
        It can be returned as a ``pem`` string or base64-encoded ``der``.
        Defaults to ``pem``.

    path
        Instead of returning the CSR, write it to this file path.

    raw
        Return the encoded raw bytes instead of a string. Defaults to false.

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

    ignored_params = {"text", "version"}.intersection(kwargs)  # path, overwrite
    if ignored_params:
        salt.utils.versions.kwargs_warn_until(ignored_params, "Potassium")
    kwargs = x509util.ensure_cert_kwargs_compat(kwargs)

    if encoding not in ["der", "pem"]:
        raise CommandExecutionError(
            f"Invalid value '{encoding}' for encoding. Valid: der, pem"
        )
    if digest.lower() not in [
        "sha1",
        "sha224",
        "sha256",
        "sha384",
        "sha512",
        "sha512_224",
        "sha512_256",
        "sha3_224",
        "sha3_256",
        "sha3_384",
        "sha3_512",
    ]:
        raise CommandExecutionError(
            f"Invalid value '{digest}' for digest. Valid: sha1, sha224, sha256, "
            "sha384, sha512, sha512_224, sha512_256, sha3_224, sha3_256, sha3_384, "
            "sha3_512"
        )
    builder, private_key = x509util.build_csr(
        private_key, private_key_passphrase=private_key_passphrase, **kwargs
    )
    algorithm = None
    if x509util.get_key_type(private_key) not in [
        x509util.KEY_TYPE.ED25519,
        x509util.KEY_TYPE.ED448,
    ]:
        algorithm = x509util.get_hashing_algorithm(digest)
    csr = builder.sign(private_key, algorithm=algorithm)
    out = encode_csr(csr, encoding=encoding, raw=bool(path) or raw)

    if path is None:
        return out

    if encoding == "pem":
        return write_pem(out.decode(), path, pem_type="CERTIFICATE REQUEST")
    with salt.utils.files.fopen(path, "wb") as fp_:
        fp_.write(out)
    return f"CSR written to {path}"


def encode_csr(csr, encoding="pem", raw=False):
    """
    Create an encoded representation of a certificate signing request.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.encode_csr /etc/pki/my.csr der

    csr
        The certificate signing request to encode.

    encoding
        Specify the encoding of the resulting certificate signing request.
        It can be returned as a ``pem`` string or base64-encoded ``der``.
        Defaults to ``pem``.

    raw
        Return the encoded raw bytes instead of a string. Defaults to false.
    """
    if encoding not in ["der", "pem"]:
        raise CommandExecutionError(
            f"Invalid value '{encoding}' for encoding. Valid: der, pem"
        )

    csr = x509util.load_csr(csr)
    csr_encoding = getattr(serialization.Encoding, encoding.upper())
    csr_bytes = csr.public_bytes(csr_encoding)

    if raw:
        return csr_bytes
    if encoding == "pem":
        return csr_bytes.decode()
    return base64.b64encode(csr_bytes).decode()


def create_private_key(
    algo="rsa",
    keysize=None,
    passphrase=None,
    encoding="pem",
    pkcs12_encryption_compat=False,
    path=None,
    raw=False,
    **kwargs,
):
    """
    Create a private key.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.create_private_key algo=ec keysize=384

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
        Specify the encoding of the resulting private key. It can be returned
        as a ``pem`` string, base64-encoded ``der`` or base64-encoded ``pkcs12``.
        Defaults to ``pem``.

    pkcs12_encryption_compat
        Some operating systems are incompatible with the encryption defaults
        for PKCS12 used since OpenSSL v3. This switch triggers a fallback to
        ``PBESv1SHA1And3KeyTripleDESCBC``.
        Please consider the `notes on PKCS12 encryption <https://cryptography.io/en/stable/hazmat/primitives/asymmetric/serialization/#cryptography.hazmat.primitives.serialization.pkcs12.serialize_key_and_certificates>`_.

    path
        Instead of returning the private key, write it to this file path.
        Note that this does not use safe permissions and should be avoided.

    raw
        Return the encoded raw bytes instead of a string. Defaults to false.
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

    unknown = [kwarg for kwarg in kwargs if not kwarg.startswith("_")]
    if unknown:
        raise SaltInvocationError(f"Unrecognized keyword arguments: {list(unknown)}")

    if encoding not in ["der", "pem", "pkcs12"]:
        raise CommandExecutionError(
            f"Invalid value '{encoding}' for encoding. Valid: der, pem, pkcs12"
        )

    out = encode_private_key(
        _generate_pk(algo=algo, keysize=keysize),
        encoding=encoding,
        passphrase=passphrase,
        pkcs12_encryption_compat=pkcs12_encryption_compat,
        raw=bool(path) or raw,
    )

    if path is None:
        return out

    if encoding == "pem":
        return write_pem(
            out.decode(), path, pem_type="(?:(RSA|ENCRYPTED) )?PRIVATE KEY"
        )
    with salt.utils.files.fopen(path, "wb") as fp_:
        fp_.write(out)
    return


def encode_private_key(
    private_key,
    encoding="pem",
    passphrase=None,
    private_key_passphrase=None,
    pkcs12_encryption_compat=False,
    raw=False,
):
    """
    Create an encoded representation of a private key.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.encode_private_key /etc/pki/my.key der

    private_key
        The private key to encode.

    encoding
        Specify the encoding of the resulting private key. It can be returned
        as a ``pem`` string, base64-encoded ``der`` and base64-encoded ``pkcs12``.
        Defaults to ``pem``.

    passphrase
        If this is specified, the private key will be encrypted using this
        passphrase. The encryption algorithm cannot be selected, it will be
        determined automatically as the best available one.

    private_key_passphrase
        .. versionadded:: 3006.2

        If the current ``private_key`` is encrypted, the passphrase to
        decrypt it.

    pkcs12_encryption_compat
        Some operating systems are incompatible with the encryption defaults
        for PKCS12 used since OpenSSL v3. This switch triggers a fallback to
        ``PBESv1SHA1And3KeyTripleDESCBC``.
        Please consider the `notes on PKCS12 encryption <https://cryptography.io/en/stable/hazmat/primitives/asymmetric/serialization/#cryptography.hazmat.primitives.serialization.pkcs12.serialize_key_and_certificates>`_.

    raw
        Return the encoded raw bytes instead of a string. Defaults to false.
    """
    if encoding not in ["der", "pem", "pkcs12"]:
        raise CommandExecutionError(
            f"Invalid value '{encoding}' for encoding. Valid: der, pem, pkcs12"
        )
    private_key = x509util.load_privkey(private_key, passphrase=private_key_passphrase)
    if passphrase is None:
        cipher = serialization.NoEncryption()
    else:
        if isinstance(passphrase, str):
            passphrase = passphrase.encode()
        if encoding == "pkcs12" and pkcs12_encryption_compat:
            cipher = (
                serialization.PrivateFormat.PKCS12.encryption_builder()
                .kdf_rounds(50000)
                .key_cert_algorithm(
                    serialization.pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC
                )
                .hmac_hash(hashes.SHA1())
                .build(passphrase)
            )
        else:
            cipher = serialization.BestAvailableEncryption(passphrase)

    if encoding in ["der", "pem"]:
        pk_encoding = getattr(serialization.Encoding, encoding.upper())
        pk_bytes = private_key.private_bytes(
            encoding=pk_encoding,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=cipher,
        )
    else:
        pk_bytes = serialization.pkcs12.serialize_key_and_certificates(
            name=None, key=private_key, cert=None, cas=None, encryption_algorithm=cipher
        )

    if raw:
        return pk_bytes
    if encoding == "pem":
        return pk_bytes.decode()
    return base64.b64encode(pk_bytes).decode()


def expires(certificate, days=0):
    """
    Determine whether a certificate will expire or has expired already.
    Returns a boolean only.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.expires /etc/pki/my.crt days=7

    certificate
        The certificate to check.

    days
        If specified, determine expiration x days in the future.
        Defaults to ``0``, which checks for the current time.
    """
    cert = x509util.load_cert(certificate)
    try:
        not_after = cert.not_valid_after_utc
    except AttributeError:
        # naive datetime object, release <42 (it's always UTC)
        not_after = cert.not_valid_after.replace(tzinfo=timezone.utc)
    return not_after <= datetime.now(tz=timezone.utc) + timedelta(days=days)


def expired(certificate):
    """
    Returns a dict containing limited details of a
    certificate and whether the certificate has expired.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.expired /etc/pki/mycert.crt

    certificate
        The certificate to check.
    """
    ret = {}

    if x509util.isfile(certificate):
        ret["path"] = certificate
    cert = x509util.load_cert(certificate)
    try:
        ret["cn"] = cert.subject.get_attributes_for_oid(x509util.NAME_ATTRS_OID["CN"])[
            0
        ].value
    except IndexError:
        pass
    ret["expired"] = expires(certificate)
    return ret


def get_pem_entries(glob_path):
    """
    Returns a dict containing PEM entries in files matching a glob.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.get_pem_entries "/etc/pki/*.crt"

    glob_path
        A path representing certificates to be read and returned.
    """
    ret = {}

    for path in glob.glob(glob_path):
        if os.path.isfile(path):
            try:
                ret[path] = get_pem_entry(text=path)
            except ValueError:
                pass

    return ret


def get_pem_entry(text, pem_type=None):
    """
    Returns a properly formatted PEM string from the input text,
    fixing any whitespace or line-break issues.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.get_pem_entry "-----BEGIN CERTIFICATE REQUEST-----MIICyzCC Ar8CAQI...-----END CERTIFICATE REQUEST"

    text
        Text containing the X509 PEM entry to be returned or path to
        a file containing the text.

    pem_type
        If specified, this function will only return a pem of a certain type,
        for example 'CERTIFICATE' or 'CERTIFICATE REQUEST'.
    """
    text = x509util.load_file_or_bytes(text).decode()
    # Replace encoded newlines
    text = text.replace("\\n", "\n")

    if (
        len(text.splitlines()) == 1
        and text.startswith("-----")
        and text.endswith("-----")
    ):
        # mine.get returns the PEM on a single line, we fix this
        pem_fixed = []
        pem_temp = text
        while len(pem_temp) > 0:
            if pem_temp.startswith("-----"):
                # Grab ----(.*)---- blocks
                pem_fixed.append(pem_temp[: pem_temp.index("-----", 5) + 5])
                pem_temp = pem_temp[pem_temp.index("-----", 5) + 5 :]
            else:
                # grab base64 chunks
                if pem_temp[:64].count("-") == 0:
                    pem_fixed.append(pem_temp[:64])
                    pem_temp = pem_temp[64:]
                else:
                    pem_fixed.append(pem_temp[: pem_temp.index("-")])
                    pem_temp = pem_temp[pem_temp.index("-") :]
        text = "\n".join(pem_fixed)

    errmsg = f"PEM text not valid:\n{text}"
    if pem_type:
        errmsg = f"PEM does not contain a single entry of type {pem_type}:\n{text}"

    _match = _valid_pem(text, pem_type)
    if not _match:
        raise SaltInvocationError(errmsg)

    _match_dict = _match.groupdict()
    pem_header = _match_dict["pem_header"]
    proc_type = _match_dict["proc_type"]
    dek_info = _match_dict["dek_info"]
    pem_footer = _match_dict["pem_footer"]
    pem_body = _match_dict["pem_body"]

    # Remove all whitespace from body
    pem_body = "".join(pem_body.split())

    # Generate correctly formatted pem
    ret = pem_header + "\n"
    if proc_type:
        ret += proc_type + "\n"
    if dek_info:
        ret += dek_info + "\n" + "\n"
    for i in range(0, len(pem_body), 64):
        ret += pem_body[i : i + 64] + "\n"
    ret += pem_footer + "\n"

    return salt.utils.stringutils.to_bytes(ret, encoding="ascii")


def get_private_key_size(private_key, passphrase=None):
    """
    Return information about the keysize of a private key (RSA/EC).

    CLI Example:

    .. code-block:: bash

        salt '*' x509.get_private_key_size /etc/pki/my.key

    private_key
        The private key to check.

    passphrase
        If ``private_key`` is encrypted, the passphrase to decrypt it.
    """
    privkey = x509util.load_privkey(private_key, passphrase=passphrase)
    if not hasattr(privkey, "key_size"):
        # Edwards-curve keys
        return None
    return privkey.key_size


def get_public_key(key, passphrase=None, asObj=None):
    """
    Returns a PEM-encoded public key derived from some reference.
    The reference should be a public key, certificate, private key or CSR.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.get_public_key /etc/pki/my.key

    key
        A reference to the structure to look the public key up for.

    passphrase
        If ``key`` is encrypted, the passphrase to decrypt it.
    """
    # Deprecation checks vs the old x509 module
    if asObj is not None:
        salt.utils.versions.kwargs_warn_until(["asObj"], "Potassium")

    try:
        return x509util.to_pem(x509util.load_pubkey(key)).decode()
    except (CommandExecutionError, SaltInvocationError):
        pass
    try:
        return x509util.to_pem(
            x509util.load_cert(key, passphrase=passphrase).public_key()
        ).decode()
    except (CommandExecutionError, SaltInvocationError):
        pass
    try:
        return x509util.to_pem(
            x509util.load_privkey(key, passphrase=passphrase).public_key()
        ).decode()
    except (CommandExecutionError, SaltInvocationError):
        pass
    try:
        return x509util.to_pem(x509util.load_csr(key).public_key()).decode()
    except SaltInvocationError:
        pass
    raise CommandExecutionError(
        "Could not load key as certificate, public key, private key or CSR"
    )


def get_signing_policy(signing_policy, ca_server=None):
    """
    Returns the specified named signing policy.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.get_signing_policy www

    signing_policy
        The name of the signing policy to return.

    ca_server
        If this is set, the CA server will be queried for the
        signing policy instead of looking it up locally.
    """
    if ca_server is None:
        policy = _get_signing_policy(signing_policy)
    else:
        # Cache signing policies from remote during this run
        # to reduce unnecessary resource usage.
        ckey = "_x509_policies"
        if ckey not in __context__:
            __context__[ckey] = {}
        if ca_server not in __context__[ckey]:
            __context__[ckey][ca_server] = {}
        if signing_policy not in __context__[ckey][ca_server]:
            policy_ = _query_remote(
                ca_server, signing_policy, {}, get_signing_policy_only=True
            )
            if "signing_cert" in policy_:
                policy_["signing_cert"] = x509util.to_pem(
                    x509util.load_cert(policy_["signing_cert"])
                ).decode()
            __context__[ckey][ca_server][signing_policy] = policy_
        # only hand out copies of the cached policy
        policy = copy.deepcopy(__context__[ckey][ca_server][signing_policy])

    # Don't immediately break for the long form of name attributes
    for name, long_names in x509util.NAME_ATTRS_ALT_NAMES.items():
        for long_name in long_names:
            if long_name in policy:
                salt.utils.versions.warn_until(
                    3009,
                    f"Found {long_name} in {signing_policy}. Please migrate to the short name: {name}",
                )
                policy[name] = policy.pop(long_name)

    # Don't immediately break for the long form of extensions
    for extname, long_names in x509util.EXTENSIONS_ALT_NAMES.items():
        for long_name in long_names:
            if long_name in policy:
                salt.utils.versions.warn_until(
                    3009,
                    f"Found {long_name} in {signing_policy}. Please migrate to the short name: {extname}",
                )
                policy[extname] = policy.pop(long_name)
    return policy


def read_certificate(certificate):
    """
    Returns a dict containing details of a certificate.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.read_certificate /etc/pki/mycert.crt

    certificate
        The certificate to read.
    """
    cert = x509util.load_cert(certificate)
    key_type = x509util.get_key_type(cert.public_key(), as_string=True)

    try:
        not_before = cert.not_valid_before_utc
        not_after = cert.not_valid_after_utc
    except AttributeError:
        # naive datetime object, release <42 (it's always UTC)
        not_before = cert.not_valid_before.replace(tzinfo=timezone.utc)
        not_after = cert.not_valid_after.replace(tzinfo=timezone.utc)
    ret = {
        "version": cert.version.value + 1,  # 0-indexed
        "key_size": cert.public_key().key_size if key_type in ["ec", "rsa"] else None,
        "key_type": key_type,
        "serial_number": x509util.dec2hex(cert.serial_number),
        "fingerprints": {
            "sha1": x509util.pretty_hex(cert.fingerprint(algorithm=hashes.SHA1())),
            "sha256": x509util.pretty_hex(cert.fingerprint(algorithm=hashes.SHA256())),
        },
        "subject": _parse_dn(cert.subject),
        "subject_hash": x509util.pretty_hex(_get_name_hash(cert.subject)),
        "subject_str": cert.subject.rfc4514_string(),
        "issuer": _parse_dn(cert.issuer),
        "issuer_hash": x509util.pretty_hex(_get_name_hash(cert.issuer)),
        "issuer_str": cert.issuer.rfc4514_string(),
        "not_before": not_before.strftime(x509util.TIME_FMT),
        "not_after": not_after.strftime(x509util.TIME_FMT),
        "public_key": get_public_key(cert),
        "extensions": _parse_extensions(cert.extensions),
    }

    try:
        ret["signature_algorithm"] = cert.signature_algorithm_oid._name
    except AttributeError:
        try:
            for name, oid in cx509.SignatureAlgorithmOID.items():
                if oid == cert.signature_algorithm_oid:
                    ret["signature_algorithm"] = name
                    break
        except AttributeError:
            pass

    if "signature_algorithm" not in ret:
        ret["signature_algorithm"] = cert.signature_algorithm_oid.dotted_string

    if __opts__["fips_mode"] is False:
        ret["fingerprints"]["md5"] = x509util.pretty_hex(
            cert.fingerprint(algorithm=hashes.MD5())
        )

    return ret


def read_certificates(glob_path):
    """
    Returns a dict containing details of all certificates matching a glob.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.read_certificates "/etc/pki/*.crt"

    glob_path
        A path to certificates to be read and returned.
    """
    ret = {}

    for path in glob.glob(glob_path):
        if os.path.isfile(path):
            try:
                ret[path] = read_certificate(certificate=path)
            except ValueError:
                pass

    return ret


def read_crl(crl):
    """
    Returns a dict containing details of a certificate revocation list.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.read_crl /etc/pki/my.crl

    crl
        The certificate revocation list to read.
    """
    crl = x509util.load_crl(crl)
    try:
        last_update = crl.last_update_utc
        next_update = crl.next_update_utc
    except AttributeError:
        last_update = crl.last_update.replace(tzinfo=timezone.utc)
        next_update = crl.next_update.replace(tzinfo=timezone.utc)
    ret = {
        "issuer": _parse_dn(crl.issuer),
        "last_update": last_update.strftime(x509util.TIME_FMT),
        "next_update": next_update.strftime(x509util.TIME_FMT),
        "revoked_certificates": {},
        "extensions": _parse_extensions(crl.extensions),
    }

    try:
        ret["signature_algorithm"] = crl.signature_algorithm_oid._name
    except AttributeError:
        try:
            for name, oid in cx509.SignatureAlgorithmOID.items():
                if oid == crl.signature_algorithm_oid:
                    ret["signature_algorithm"] = name
                    break
        except AttributeError:
            pass

    if "signature_algorithm" not in ret:
        ret["signature_algorithm"] = crl.signature_algorithm_oid.dotted_string

    for revoked in crl:
        try:
            revocation_date = revoked.revocation_date_utc
        except AttributeError:
            # naive datetime object, release <42 (it's always UTC)
            revocation_date = revoked.revocation_date.replace(tzinfo=timezone.utc)
        ret["revoked_certificates"].update(
            {
                x509util.dec2hex(revoked.serial_number).replace(":", ""): {
                    "revocation_date": revocation_date.strftime(x509util.TIME_FMT),
                    "extensions": _parse_crl_entry_extensions(revoked.extensions),
                }
            }
        )
    return ret


def read_csr(csr):
    """
    Returns a dict containing details of a certificate signing request.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.read_csr /etc/pki/mycert.csr

    csr
        The certificate signing request to read.
    """
    csr = x509util.load_csr(csr)
    key_type = x509util.get_key_type(csr.public_key(), as_string=True)

    return {
        "key_size": csr.public_key().key_size if key_type in ["ec", "rsa"] else None,
        "key_type": key_type,
        "subject": _parse_dn(csr.subject),
        "subject_hash": x509util.pretty_hex(_get_name_hash(csr.subject)),
        "subject_str": csr.subject.rfc4514_string(),
        "public_key_hash": x509util.pretty_hex(
            cx509.SubjectKeyIdentifier.from_public_key(csr.public_key()).digest
        ),
        "extensions": _parse_extensions(csr.extensions),
    }


def sign_remote_certificate(
    signing_policy, kwargs, get_signing_policy_only=False, **more_kwargs
):
    """
    Request a certificate to be remotely signed according to a signing policy.
    This is mostly for internal use and does not make much sense on the CLI.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.sign_remote_certificate www kwargs="{'public_key': '/etc/pki/www.key'}"

    signing_policy
        The name of the signing policy to use. Required.

    kwargs
        A dict containing all the arguments to be passed into the
        :py:func:`x509.create_certificate <salt.modules.x509_v2.create_certificate>` function.

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
            signing_policy.pop("signing_private_key", None)
            signing_policy.pop("signing_private_key_passphrase", None)
            # ensure to deliver the signing cert as well, not a file path
            if "signing_cert" in signing_policy:
                try:
                    signing_policy["signing_cert"] = x509util.to_der(
                        x509util.load_cert(signing_policy["signing_cert"])
                    )
                except (CommandExecutionError, SaltInvocationError) as err:
                    ret["data"] = None
                    ret["errors"].append(str(err))
                    return ret
            ret["data"] = signing_policy
            return ret
        x509util.merge_signing_policy(signing_policy, kwargs)
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
        cert, _ = _create_certificate_local(**kwargs)
        ret["data"] = x509util.to_der(cert)
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
        "x509.sign_remote_certificate",
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
        log.error("Received invalid return value from ca_server: %s", result)
        raise CommandExecutionError(
            "Received invalid return value from ca_server. See minion log for details"
        )
    if result.get("errors"):
        raise CommandExecutionError(
            "ca_server reported errors:\n" + "\n".join(result["errors"])
        )
    return result["data"]


def verify_crl(crl, cert):
    """
    Verify that a signature on a certificate revocation list was made
    by the private key corresponding to the public key associated
    with the specified certificate.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.verify_crl /etc/pki/my.crl /etc/pki/my.crt

    crl
        The certificate revocation list to check the signature on.

    cert
        The certificate (or any reference that can be passed
        to ``get_public_key``) to retrieve the public key from.
    """
    crl = x509util.load_crl(crl)
    pubkey = x509util.load_pubkey(get_public_key(cert))
    return crl.is_signature_valid(pubkey)


def verify_private_key(private_key, public_key, passphrase=None):
    """
    Verify that a private key belongs to the specified public key.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.verify_private_key /etc/pki/my.key /etc/pki/my.crt

    private_key
        The private key to check.

    public_key
        The certificate (or any reference that can be passed
        to ``get_public_key``) to retrieve the public key from.

    passphrase
        If ``private_key`` is encrypted, the passphrase to decrypt it.
    """
    privkey = x509util.load_privkey(private_key, passphrase=passphrase)
    pubkey = x509util.load_pubkey(get_public_key(public_key))
    return x509util.is_pair(pubkey, privkey)


def verify_signature(
    certificate, signing_pub_key=None, signing_pub_key_passphrase=None
):
    """
    Verify that a signature on a certificate was made
    by the private key corresponding to the public key associated
    with the specified certificate.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.verify_signature /etc/pki/my.key /etc/pki/my.crt

    certificate
        The certificate to check the signature on.

    signing_pub_key
        Any reference that can be passed to ``get_public_key`` to retrieve
        the public key of the signing entity from. If unspecified, will
        take the public key of ``certificate``, i.e. verify a self-signed
        certificate.

    signing_pub_key_passphrase

        If ``signing_pub_key`` is encrypted, the passphrase to decrypt it.
    """
    cert = x509util.load_cert(certificate)
    pubkey = x509util.load_pubkey(
        get_public_key(
            signing_pub_key or certificate, passphrase=signing_pub_key_passphrase
        )
    )
    return x509util.verify_signature(cert, pubkey)


def will_expire(certificate, days):
    """
    Returns a dict containing details of a certificate and whether
    the certificate will expire in the specified number of days.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.will_expire "/etc/pki/mycert.crt" days=30

    certificate
        The certificate to check.

    days
        The number of days in the future to check the validity for.
    """
    ret = {"check_days": days}

    if x509util.isfile(certificate):
        ret["path"] = certificate
    cert = x509util.load_cert(certificate)
    try:
        ret["cn"] = cert.subject.get_attributes_for_oid(x509util.NAME_ATTRS_OID["CN"])[
            0
        ].value
    except IndexError:
        pass
    ret["will_expire"] = expires(certificate, days)
    return ret


def write_pem(text, path, overwrite=True, pem_type=None):
    """
    Writes out a PEM string, fixing any formatting or whitespace
    issues before writing.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.write_pem "-----BEGIN CERTIFICATE-----MIIGMzCCBBugA..." path=/etc/pki/mycert.crt

    text
        PEM string input to be written out.

    path
        Path of the file to write the PEM out to.

    overwrite
        If ``True`` (default), write_pem will overwrite the entire PEM file.
        Set to ``False`` to preserve existing private keys and DH params that may
        exist in the PEM file.

    pem_type
        The PEM type to be saved, for example ``CERTIFICATE`` or
        ``PUBLIC KEY``. Adding this will allow the function to take
        input that may contain multiple PEM types.
    """
    text = get_pem_entry(text, pem_type=pem_type)
    with salt.utils.files.set_umask(0o077):
        _dhparams = ""
        _private_key = ""
        if (
            pem_type
            and pem_type == "CERTIFICATE"
            and os.path.isfile(path)
            and not overwrite
        ):
            _filecontents = x509util.load_file_or_bytes(path).decode()
            try:
                _dhparams = get_pem_entry(_filecontents, "DH PARAMETERS")
            except SaltInvocationError as err:
                log.debug("Error while retrieving DH PARAMETERS: %s", err)
                log.trace(err, exc_info=err)
            try:
                _private_key = get_pem_entry(_filecontents, "(?:RSA )?PRIVATE KEY")
            except SaltInvocationError as err:
                log.debug("Error while retrieving PRIVATE KEY: %s", err)
                log.trace(err, exc_info=err)
        with salt.utils.files.fopen(path, "w") as _fp:
            if pem_type and pem_type == "CERTIFICATE" and _private_key:
                _fp.write(salt.utils.stringutils.to_str(_private_key))
            _fp.write(salt.utils.stringutils.to_str(text))
            if pem_type and pem_type == "CERTIFICATE" and _dhparams:
                _fp.write(salt.utils.stringutils.to_str(_dhparams))
    return f"PEM written to {path}"


def _make_pem_regex(pem_type):
    """
    Dynamically generate a regex to match pem_type
    """
    return re.compile(
        rf"\s*(?P<pem_header>-----BEGIN {pem_type}-----)\s+"
        r"(?:(?P<proc_type>Proc-Type: 4,ENCRYPTED)\s*)?"
        r"(?:(?P<dek_info>DEK-Info:"
        r" (?:DES-[3A-Z\-]+,[0-9A-F]{{16}}|[0-9A-Z\-]+,[0-9A-F]{{32}}))\s*)?"
        r"(?P<pem_body>.+?)\s+(?P<pem_footer>"
        rf"-----END {pem_type}-----)\s*",
        re.DOTALL,
    )


def _valid_pem(pem, pem_type=None):
    pem_type = "[0-9A-Z ]+" if pem_type is None else pem_type
    _dregex = _make_pem_regex(pem_type)
    for _match in _dregex.finditer(pem):
        if _match:
            return _match
    return None


def _generate_pk(algo="rsa", keysize=None):
    if algo == "rsa":
        return x509util.generate_rsa_privkey(keysize=keysize or 2048)
    if algo == "ec":
        return x509util.generate_ec_privkey(keysize=keysize or 256)
    if algo == "ed25519":
        return x509util.generate_ed25519_privkey()
    if algo == "ed448":
        return x509util.generate_ed448_privkey()
    raise SaltInvocationError(
        f"Invalid algorithm specified for generating private key: {algo}. Valid: "
        "rsa, ec, ed25519, ed448"
    )


def _get_signing_policy(name):
    if name is None:
        return {}
    policies = __salt__["pillar.get"]("x509_signing_policies", {}).get(name)
    policies = policies or __salt__["config.get"]("x509_signing_policies", {}).get(name)
    if isinstance(policies, list):
        dict_ = {}
        for item in policies:
            dict_.update(item)
        policies = dict_
    return policies or {}


def _parse_dn(subject):
    """
    Returns a dict containing all values in an X509 Subject
    """
    ret = OrderedDict()
    for nid_name, oid in x509util.NAME_ATTRS_OID.items():
        try:
            ret[nid_name] = subject.get_attributes_for_oid(oid)[0].value
        except IndexError:
            continue
    return ret


def _get_name_hash(name, digest="sha1"):
    """
    Returns the OpenSSL name hash.
    This is the first four bytes of the SHA1 (pre v1: MD5) hash
    of the DER-encoded form of name. On little-endian systems,
    OpenSSL inverts the bytes.
    """
    if digest.lower() not in ["sha1", "md5"]:
        raise ValueError(
            f"Invalid hashing algorithm for name hash: {digest}. "
            "Only SHA1 and MD5 are allowed"
        )
    hsh = hashes.Hash(x509util.get_hashing_algorithm(digest))
    hsh.update(name.public_bytes())
    res = hsh.finalize()[:4]
    if sys.byteorder == "little":
        res = res[::-1]
    return res


def _parse_extensions(extensions):
    ret = {}
    for extname, oid in x509util.EXTENSIONS_OID.items():
        try:
            ext = extensions.get_extension_for_oid(oid)
        except cx509.ExtensionNotFound:
            continue
        ret[extname] = x509util.render_extension(ext)
    return ret


def _parse_crl_entry_extensions(extensions):
    ret = {}
    for extname, oid in x509util.EXTENSIONS_CRL_ENTRY_OID.items():
        try:
            ext = extensions.get_extension_for_oid(oid)
        except cx509.ExtensionNotFound:
            continue
        ret[extname] = x509util.render_extension(ext)
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
