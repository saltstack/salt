"""
Manage X.509 certificates
=========================

.. versionadded:: 3007.0

General configuration instructions and general remarks are documented
in the :ref:`execution module docs <x509-setup>`.

Configuration
-------------
Explicit activation
~~~~~~~~~~~~~~~~~~~
Since this module uses the same virtualname as the previous ``x509`` modules,
but is incompatible with them, it needs to be explicitly activated on each
SSH minion **and the master itself** (the latter one is a technical limitation/
bordering a bug: The wrapper modules are loaded with the master opts the first time
and only those that were registered successfully will be reloaded with the
merged opts after).

.. code-block:: yaml

    # /etc/salt/master.d/x509.conf

    features:
      x509_v2: true
    ssh_minion_opts:
      features:
        x509_v2: true

.. note::

    Compound matching allowed callers is **not supported** with salt-ssh
    minions. They will always be denied.
"""
import copy
import logging
from pathlib import Path

try:
    import salt.utils.x509 as x509util

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

import salt.utils.dictupdate
import salt.utils.files
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError, SaltInvocationError

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
    if raw:
        # returns are json-serialized, which does not support bytes
        raise SaltInvocationError("salt-ssh does not support the `raw` parameter")

    kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_")}

    if not ca_server:
        return _check_ret(
            __salt__["x509.create_certificate_ssh"](
                signing_policy=signing_policy,
                encoding=encoding,
                append_certs=append_certs,
                pkcs12_passphrase=pkcs12_passphrase,
                pkcs12_encryption_compat=pkcs12_encryption_compat,
                pkcs12_friendlyname=pkcs12_friendlyname,
                path=path,
                overwrite=overwrite,
                raw=raw,
                **kwargs,
            )
        )

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

    if path and not overwrite and _check_ret(__salt__["file.file_exists"](path)):
        return f"The file at {path} exists and overwrite was set to false"
    if signing_policy is None:
        raise SaltInvocationError(
            "signing_policy must be specified to request a certificate from "
            "a remote ca_server"
        )
    cert, private_key_loaded = _create_certificate_remote(
        ca_server, signing_policy, **kwargs
    )

    if encoding == "pkcs12":
        out = _check_ret(
            __salt__["x509.encode_certificate"](
                x509util.to_pem(cert).decode(),
                append_certs=append_certs,
                encoding=encoding,
                private_key=private_key_loaded,
                pkcs12_passphrase=pkcs12_passphrase,
                pkcs12_encryption_compat=pkcs12_encryption_compat,
                pkcs12_friendlyname=pkcs12_friendlyname,
                raw=False,
            )
        )
    else:
        out = _check_ret(
            __salt__["x509.encode_certificate"](
                x509util.to_pem(cert).decode(),
                append_certs=append_certs,
                encoding=encoding,
                raw=False,
            )
        )

    if path is None:
        return out

    if encoding == "pem":
        return _check_ret(
            __salt__["x509.write_pem"](
                out, path, overwrite=overwrite, pem_type="CERTIFICATE"
            )
        )
    _check_ret(__salt__["hashutil.base64_decodefile"](out, path))
    return f"Certificate written to {path}"


def _query_remote(ca_server, signing_policy, kwargs, get_signing_policy_only=False):
    result = __salt__["publish.publish"](
        ca_server,
        "x509.sign_remote_certificate",
        arg=[signing_policy, kwargs, get_signing_policy_only],
        regular_minions=True,
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


def _create_certificate_remote(
    ca_server, signing_policy, private_key=None, private_key_passphrase=None, **kwargs
):
    private_key_loaded = None
    if private_key:
        kwargs["public_key"] = _check_ret(
            __salt__["x509.get_public_key"](
                private_key, passphrase=private_key_passphrase
            )
        )
    elif kwargs.get("public_key"):
        kwargs["public_key"] = _check_ret(
            __salt__["x509.get_public_key"](kwargs["public_key"])
        )

    if kwargs.get("csr"):
        try:
            # Check if the data can be interpreted as a Path at all
            Path(kwargs["csr"])
        except TypeError:
            pass
        else:
            if _check_ret(__salt__["file.file_exists"](kwargs["csr"])):
                kwargs["csr"] = _check_ret(
                    __salt__["hashutil.base64_encodefile"](kwargs["csr"])
                )

    result = _query_remote(ca_server, signing_policy, kwargs)
    try:
        return x509util.load_cert(result), private_key_loaded
    except (CommandExecutionError, SaltInvocationError) as err:
        raise CommandExecutionError(
            f"ca_server did not return a certificate: {result}"
        ) from err


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


def _check_ret(ret):
    # Failing unwrapped calls to the minion always return a result dict
    # and do not throw exceptions currently.
    if isinstance(ret, dict) and ret.get("stderr"):
        raise CommandExecutionError(ret["stderr"])
    return ret


def certificate_managed_wrapper(
    name,
    ca_server,
    signing_policy,
    private_key_managed=None,
    private_key=None,
    private_key_passphrase=None,
    csr=None,
    public_key=None,
    certificate_managed=None,
    test=None,
):
    """
    This function essentially behaves like a sophisticated Jinja macro.
    It is intended to provide a replacement for the ``x509.certificate_managed``
    state with peer publishing, which does not work via salt-ssh.
    It performs necessary checks during rendering and returns an appropriate
    highstate structure that does work via salt-ssh (if a certificate needs to be
    reissued, it is done during rendering and the actual state just manages the file).

    Required arguments are ``name``, ``ca_server`` and ``signing_policy``.
    If you want this function to manage a private key, it should be specified
    in ``private_key_managed``, which should contain all arguments to the
    respective state. Note that the private key will not be checked for changes.
    If you want to use a CSR or a public key as a source,
    it must exist during state rendering and you cannot manage a private key.

    All optional keyword arguments to ``certificate_managed`` can be specified
    in the dict param ``certificate_managed``.
    Key rotation can be activated by including ``new: true`` in the dict for
    ``private_key_managed``.

    As an example, for Jinja templates, you can serialize this function's output
    directly into the state file. Note that you need to pass ``opts.get("test")``
    explicitly for test mode to work reliably!

    .. code-block:: jinja

        {%- set private_key_params = {
                "name": "/opt/app/certs/app.key",
                "algo": "ed25519",
                "new": true
        } %}
        {%- set certificate_params = {
                "basicConstraints": "critical, CA:false",
                "subjectKeyIdentifier": "hash",
                "authorityKeyIdentifier": "keyid:always",
                "subjectAltName": ["DNS:my.minion.example.com"],
                "CN": "my.minion.example.com",
                "days_remaining": 7,
                "days_valid": 30
        } %}
        {{
            salt["x509.certificate_managed_wrapper"](
                "/opt/app/certs/app.crt",
                ca_server="ca_minion",
                signing_policy="www",
                private_key_managed=private_key_params,
                certificate_managed=certificate_params,
                test=opts.get("test")
            ) | yaml(false)
        }}


    name
        The path of the certificate to manage.

    ca_server
        The CA server to contact. This is required since this function
        is not necessary for locally signed certificates.

    signing_policy
        The name of the signing policy to use. Required since remotely
        signing a certificate requires a policy.

    private_key_managed
        A dictionary of keyword arguments to ``x509.private_key_managed``.
        This is required if ``private_key``, ``csr`` or ``public_key``
        have not been specified.
        Key rotation will be performed automatically if ``new: true``.
        Note that the specified file path must not be a symlink.

    private_key
        The path of a private key to use for public key derivation
        (it will not be managed).
        Does not accept the key itself. Mutually exclusive with ``private_key_managed``,
        ``csr`` and ``public_key``.

    private_key_passphrase
        If the specified private key needs a passphrase, specify it here.

    csr
        The path of a CSR to use for public key derivation.
        Does not accept the CSR itself. Mutually exclusive with ``private_key_managed``,
        ``private_key`` and ``public_key``.

    public_key
        The path of a public key to use.
        Does not accept the key itself. Mutually exclusive with ``private_key_managed``,
        ``private_key`` and ``csr``.

    certificate_managed
        A dictionary of keyword arguments to ``x509.certificate_managed``.

    test
        Run in test mode. This should be passed explicitly because the value
        is not loaded into wrapper modules (reliably?). Pass it like
        ``test=opts.get("test")``.
        If this is forgotten, the files on the remote will still not be updated,
        but a certificate might be issued unnecessarily.

    .. note::

        This function does not claim feature parity, but it uses the same
        change check as the regular state module. Special handling for symlinks
        and other edge cases is not implemented.

        There will be one or two resulting states, depending on the presence of
        ``private_key_managed``. Both states will have the managed file path as
        their state ID (suffixed with either _key or _crt), the state module
        will always be ``x509``.

        Private keys will not leave the remote machine, unless you're managing
        PKCS12 certificates.
    """
    if not (private_key_managed or private_key or csr or public_key):
        raise SaltInvocationError(
            "Need to specify either private_key_managed, private_key, csr or public_key"
        )

    create_private_key = False
    recreate_private_key = False
    new_certificate = False
    reencode_certificate = False
    certificate_managed = certificate_managed or {}
    private_key_managed = private_key_managed or {}
    public_key = None
    cm_defaults = {
        "days_remaining": 7,
        "days_valid": 30,
        "not_before": None,
        "not_after": None,
        "encoding": "pem",
        "append_certs": [],
        "digest": "sha256",
    }
    for param, val in cm_defaults.items():
        certificate_managed.setdefault(param, val)

    cert_file_args, cert_args = x509util.split_file_kwargs(certificate_managed)
    pk_file_args, pk_args = x509util.split_file_kwargs(private_key_managed)
    ret = {}
    current = None
    cert_changes = {}
    pk_changes = {}
    pk_temp_file = None

    try:
        # Check if we have a source for a public key
        if pk_args:
            private_key = pk_args["name"]
            if not _check_ret(__salt__["file.file_exists"](private_key)):
                create_private_key = True
            elif __salt__["file.is_link"](private_key):
                if not pk_args.get("overwrite"):
                    raise CommandExecutionError(
                        "Specified private key path exists, but is a symlink, "
                        "which is disallowed. Either specify the target path of "
                        "the link or pass overwrite: true to force regeneration"
                    )
                if not (test or __opts__.get("test")):
                    # The link would be written over anyways by `file.move`, but
                    # let's remove it here in case that assumption fails
                    __salt__["file.remove"](private_key)
                pk_changes["removed_link"] = pk_args["name"]
                create_private_key = True
            else:
                public_key, create_private_key = _load_privkey(
                    pk_args["name"],
                    pk_args.get("passphrase"),
                    pk_args.get("overwrite", False),
                )
        elif private_key:
            if not _check_ret(__salt__["file.file_exists"](private_key)):
                raise SaltInvocationError("Specified private key does not exist")
            public_key, _ = _load_privkey(private_key, private_key_passphrase)
        elif public_key:
            # todo usually can be specified as the key itself
            if not _check_ret(__salt__["file.file_exists"](public_key)):
                raise SaltInvocationError("Specified public key does not exist")
            public_key = _check_ret(__salt__["x509.get_public_key"](public_key))
        elif csr:
            # todo usually can be specified as the csr itself
            if not _check_ret(__salt__["file.file_exists"](csr)):
                raise SaltInvocationError("Specified csr does not exist")
            csr = _check_ret(__salt__["hashutil.base64_encodefile"](csr))

        if create_private_key:
            # A missing private key means we need to create a certificate regardless
            new_certificate = True
        elif not _check_ret(__salt__["file.file_exists"](name)):
            new_certificate = True
        else:
            # We check the certificate the same way the state does
            crt = _check_ret(__salt__["hashutil.base64_encodefile"](name))
            signing_policy_contents = get_signing_policy(
                signing_policy, ca_server=ca_server
            )
            current, cert_changes, replace, _ = x509util.check_cert_changes(
                crt,
                **cert_args,
                ca_server=ca_server,
                signing_policy_contents=signing_policy_contents,
                public_key=public_key,
                csr=csr,
            )
            new_certificate = new_certificate or replace
            reencode_certificate = bool(cert_changes) and not bool(
                set(cert_changes)
                - {
                    "additional_certs",
                    "encoding",
                    "pkcs12_friendlyname",
                }
            )

        if pk_args and pk_args.get("new") and not create_private_key:
            if new_certificate or (cert_changes and not reencode_certificate):
                recreate_private_key = True

        if test or __opts__.get("test"):
            if pk_args:
                pk_ret = {
                    "name": pk_args["name"],
                    "result": True,
                    "comment": "The private key is in the correct state",
                    "changes": {},
                    "require_in": [
                        name + "_crt",
                    ],
                }
                if create_private_key or recreate_private_key:
                    pp = "created" if not recreate_private_key else "recreated"
                    pk_ret["changes"] = pk_changes
                    pk_ret["changes"][pp] = pk_args["name"]
                    pk_ret["comment"] = f"The private key would have been {pp}"
                ret[pk_args["name"] + "_key"] = {
                    "x509.private_key_managed_ssh": [{k: v} for k, v in pk_ret.items()]
                }
                ret[pk_args["name"] + "_key"]["x509.private_key_managed_ssh"].extend(
                    {k: v} for k, v in pk_file_args.items()
                )

            cert_ret = {
                "name": name,
                "result": True,
                "changes": {},
            }
            if new_certificate:
                pp = ("re" if current else "") + "created"
                cert_ret["comment"] = f"The certificate would have been {pp}"
                cert_ret["changes"][pp] = name
            elif reencode_certificate:
                cert_ret["comment"] = "The certificate would have been reencoded"
                cert_ret["changes"] = cert_changes
            elif cert_changes:
                cert_ret["comment"] = "The certificate would have been updated"
                cert_ret["changes"] = cert_changes
            else:
                cert_ret["comment"] = "The certificate is in the correct state"
                cert_ret["changes"] = {}

            ret[name + "_crt"] = {
                "x509.certificate_managed_ssh": [{k: v} for k, v in cert_ret.items()]
            }
            ret[name + "_crt"]["x509.certificate_managed_ssh"].extend(
                {k: v} for k, v in cert_file_args.items()
            )
            return ret

        if create_private_key or recreate_private_key:
            pk_temp_file = _check_ret(__salt__["temp.file"]())
            _check_ret(__salt__["file.set_mode"](pk_temp_file, "0600"))
            cpk_args = {"path": pk_temp_file}
            for arg in (
                "algo",
                "keysize",
                "passphrase",
                "encoding",
                "pkcs12_encryption_compat",
            ):
                if arg in pk_args:
                    cpk_args[arg] = pk_args[arg]
            _check_ret(__salt__["x509.create_private_key"](**cpk_args))
            public_key = _check_ret(
                __salt__["x509.get_public_key"](pk_temp_file, pk_args.get("passphrase"))
            )
        if pk_args:
            pk_ret = {
                "name": pk_args["name"],
                "result": True,
                "comment": "The private key is in the correct state",
                "changes": {},
                "require_in": [
                    name + "_crt",
                ],
            }
            if create_private_key or recreate_private_key:
                pp = "created" if not recreate_private_key else "recreated"
                pk_ret["changes"] = pk_changes
                pk_ret["changes"][pp] = pk_args["name"]
                pk_ret["comment"] = f"The private key has been {pp}"
            ret[pk_args["name"] + "_key"] = {
                "x509.private_key_managed_ssh": [{k: v} for k, v in pk_ret.items()]
            }
            ret[pk_args["name"] + "_key"]["x509.private_key_managed_ssh"].extend(
                {k: v} for k, v in pk_file_args.items()
            )
            ret[pk_args["name"] + "_key"]["x509.private_key_managed_ssh"].append(
                {"tempfile": pk_temp_file}
            )

        cert_ret = {
            "name": name,
            "result": True,
            "changes": {},
            "encoding": certificate_managed["encoding"],
        }
        if reencode_certificate:
            cert_ret["contents"] = _check_ret(
                __salt__["x509.encode_certificate"](
                    x509util.to_pem(current),
                    encoding=certificate_managed["encoding"],
                    append_certs=certificate_managed["append_certs"],
                    private_key=pk_args["name"] if pk_args else private_key,
                    private_key_passphrase=pk_args.get("passphrase")
                    if pk_args
                    else private_key,
                    pkcs12_passphrase=certificate_managed.get("pkcs12_passphrase"),
                    pkcs12_encryption_compat=certificate_managed.get(
                        "pkcs12_encryption_compat"
                    ),
                    pkcs12_friendlyname=certificate_managed.get("pkcs12_friendlyname"),
                    raw=False,
                )
            )
            cert_ret["comment"] = "The certificate has been reencoded"
            cert_ret["changes"] = cert_changes
        elif new_certificate or cert_changes:
            pp = ("re" if current else "") + "created"
            cert_ret["contents"] = create_certificate(
                **_filter_cert_managed_state_args(cert_args),
                ca_server=ca_server,
                signing_policy=signing_policy,
                csr=csr,
                public_key=public_key,
            )
            cert_ret["comment"] = f"The certificate has been {pp}"
            if not cert_changes:
                cert_ret["changes"][pp] = name
            else:
                cert_ret["changes"] = cert_changes
        else:
            cert_ret["comment"] = "The certificate is in the correct state"
            cert_ret["changes"] = {}

        ret[name + "_crt"] = {
            "x509.certificate_managed_ssh": [{k: v} for k, v in cert_ret.items()]
        }
        ret[name + "_crt"]["x509.certificate_managed_ssh"].append(
            {k: v} for k, v in cert_file_args.items()
        )
    except (CommandExecutionError, SaltInvocationError) as err:
        if pk_temp_file:
            if _check_ret(__salt__["file.file_exists"](pk_temp_file)):
                try:
                    # otherwise, get rid of it
                    _check_ret(__salt__["file.remove"](pk_temp_file))
                except Exception as err:  # pylint: disable=broad-except
                    log.error(str(err), exc_info_on_loglevel=logging.DEBUG)
        ret = {
            name
            + "_crt": {
                "x509.certificate_managed_ssh": [
                    {"name": name},
                    {"result": False},
                    {"comment": str(err)},
                    {"changes": {}},
                ]
            }
        }
        if pk_args and "name" in pk_args:
            ret[pk_args["name"] + "_key"] = {
                "x509.private_key_managed_ssh": [
                    {"name": pk_args["name"]},
                    {"result": False},
                    {"comment": str(err)},
                    {"changes": {}},
                ]
            }
    return ret


def _filter_cert_managed_state_args(kwargs):
    return {k: v for k, v in kwargs.items() if k != "days_remaining"}


def _load_privkey(pk, passphrase, overwrite=False):
    public_key = None
    create_private_key = False
    try:
        public_key = _check_ret(
            __salt__["x509.get_public_key"](
                pk,
                passphrase,
            )
        )
    except CommandExecutionError as err:
        # All errors currently get mangled into this one.
        # TODO: Subclass more specific errors to CommandExecutionError
        # and reraise them in get_public_key
        if "Could not load key as" in str(err):
            if not overwrite:
                raise CommandExecutionError(
                    "The private key file could not be loaded. This can either mean "
                    "the file is encrypted and the provided passphrase is wrong "
                    "or the file is not a private key at all. Either way, you can "
                    "pass overwrite: true to force regeneration if the file is managed"
                )
            create_private_key = True
        else:
            raise
    return public_key, create_private_key
