"""
Manage OpenSSH certificates
===========================

.. versionadded:: 3008.0

:depends: cryptography

Wraps the ``ssh_pki`` execution module for salt-ssh. This is required for
remote signing via peer publishing.

Additionally, this module provides a wrapper for ``ssh_pki.certificate_managed``
analog to a sophisticated Jinja macro. This allows to statefully manage certificates,
even if the certificate creation backend does not work on the managed remote.

General configuration instructions and general remarks are documented
in the :ref:`execution module docs <x509-setup>`.

.. note::

    The dependent modules must be present on the remote, they are not delivered
    with the Salt-SSH thin tarball.
    Operations with encrypted private keys additionally require the ``bcrypt``
    Python module.
"""

import copy
import logging

from salt.exceptions import CommandExecutionError, SaltInvocationError

try:
    import salt.utils.sshpki as sshpki

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


log = logging.getLogger(__name__)

__virtualname__ = "ssh_pki"


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

        salt-ssh '*' ssh_pki.create_certificate private_key=/root/.ssh/id_rsa signing_private_key='/etc/pki/ssh/myca.key'

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

            salt-ssh '*' ssh_pki.create_certificate [...] \
              critical_options='{"force-command": "/usr/bin/id", "verify-required": true}'

    extensions
        A mapping of extension name to extension value to set on the certificate.
        If an extension does not take a value, specify it as ``true``.

        Example:

        .. code-block:: bash

            salt-ssh '*' ssh_pki.create_certificate [...] \
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

    if not ca_server:
        return _check_ret(
            __salt__["ssh_pki.create_certificate_ssh"](
                signing_policy=signing_policy,
                path=path,
                overwrite=overwrite,
                raw=raw,
                **kwargs,
            )
        )

    if path and not overwrite and _check_ret(__salt__["file.file_exists"](path)):
        raise CommandExecutionError(
            f"The file at {path} exists and overwrite was set to false"
        )
    if signing_policy is None:
        raise SaltInvocationError(
            "signing_policy must be specified to request a certificate from "
            "a remote ca_server"
        )
    cert = _create_certificate_remote(ca_server, signing_policy, **kwargs)

    out = cert.public_bytes()

    if path is None:
        if raw:
            return out
        return out.decode()
    _check_ret(__salt__["file.write"](*out.decode().splitlines()))
    return f"Certificate written to {path}"


def _create_certificate_remote(
    ca_server, signing_policy, private_key=None, private_key_passphrase=None, **kwargs
):
    if private_key:
        kwargs["public_key"] = _check_ret(
            __salt__["ssh_pki.get_public_key"](
                private_key, passphrase=private_key_passphrase
            )
        )
    elif kwargs.get("public_key"):
        kwargs["public_key"] = _check_ret(
            __salt__["ssh_pki.get_public_key"](kwargs["public_key"])
        )

    result = _query_remote(ca_server, signing_policy, kwargs)
    try:
        return sshpki.load_cert(result)
    except (CommandExecutionError, SaltInvocationError) as err:
        raise CommandExecutionError(
            f"ca_server did not return a certificate: {result}"
        ) from err


def _query_remote(ca_server, signing_policy, kwargs, get_signing_policy_only=False):
    result = __salt__["publish.publish"](
        ca_server,
        "ssh_pki.sign_remote_certificate",
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


def _check_ret(ret):
    # Failing unwrapped calls to the minion always return a result dict
    # and do not throw exceptions currently.
    if isinstance(ret, dict) and ret.get("stderr"):
        raise CommandExecutionError(ret["stderr"])
    return ret


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


def _get_signing_policy(name):
    if name is None:
        return {}
    policies = __salt__["pillar.get"]("ssh_signing_policies", {}).get(name)
    policies = policies or __salt__["config.get"]("ssh_signing_policies", {}).get(name)
    return policies or {}


def certificate_managed_wrapper(
    name,
    ca_server,
    signing_policy,
    backend=None,
    backend_args=None,
    private_key_managed=None,
    private_key=None,
    private_key_passphrase=None,
    public_key=None,
    certificate_managed=None,
    test=None,
):
    """
    This function essentially behaves like a sophisticated Jinja macro.
    It is intended to provide a replacement for the ``ssh_pki.certificate_managed``
    state with peer publishing or some backends, which does not work via salt-ssh.
    It performs necessary checks during rendering and returns an appropriate
    highstate structure that does work via salt-ssh (if a certificate needs to be
    reissued, it is done during rendering and the actual state just manages the file).

    Required arguments are ``name``, ``ca_server`` and ``signing_policy``.
    If you want this function to manage a private key, it should be specified
    in ``private_key_managed``, which should contain all arguments to the
    respective state. Note that the private key will not be checked for changes.
    If you want to use a public key as a source, it must exist during state
    rendering and you cannot manage a private key.

    All optional keyword arguments to ``certificate_managed`` can be specified
    in the dict param ``certificate_managed``.
    Key rotation can be activated by including ``new: true`` in the dict for
    ``private_key_managed``.

    As an example, for Jinja templates, you can serialize this function's output
    directly into the state file. Note that you need to pass ``opts.get("test")``
    explicitly for test mode to work reliably!

    .. code-block:: jinja

        {%- set private_key_params = {
                "name": "/root/.ssh/id_foo",
                "algo": "ed25519",
                "new": true
        } %}
        {%- set certificate_params = {
                "ttl_remaining": "7d",
                "ttl": "30d",
                "valid_principals": ["min.ion.example.org"]
        } %}
        {{
            salt["ssh_pki.certificate_managed_wrapper"](
                "/root/.ssh/id_foo.crt",
                ca_server="ca_minion",
                signing_policy="user_cert",
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

    backend
        Instead of using the ``ssh_pki`` execution module for certificate
        creation, use this backend. It must provide a compatible API for
        ``create_certificate`` and ``get_signing_policy``.
        It should have a wrapper module for this function to make sense,
        otherwise you can just use the state module directly.

    backend_args
        If ``backend`` is specified, pass these additional keyword arguments
        to it. Must be a mapping (dict).

    private_key_managed
        A dictionary of keyword arguments to ``ssh_pki.private_key_managed``.
        This is required if ``private_key`` or ``public_key``
        have not been specified.
        Key rotation will be performed automatically if ``new: true``.
        Note that the specified file path must not be a symlink.

    private_key
        The path of a private key to use for public key derivation
        (it will not be managed).
        Does not accept the key itself. Mutually exclusive with
        ``private_key_managed`` and ``public_key``.

    private_key_passphrase
        If the specified private key needs a passphrase, specify it here.

    public_key
        The path of a public key to use.
        Does not accept the key itself. Mutually exclusive with
        ``private_key_managed`` and ``private_key``.

    certificate_managed
        A dictionary of keyword arguments to ``ssh_pki.certificate_managed``.

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
        will always be ``ssh_pki``.

        Private keys will not leave the remote machine.
    """
    if not (private_key_managed or private_key or public_key):
        raise SaltInvocationError(
            "Need to specify either private_key_managed, private_key or public_key"
        )

    backend = backend or "ssh_pki"
    create_private_key = False
    recreate_private_key = False
    new_certificate = False
    certificate_managed = certificate_managed or {}
    private_key_managed = private_key_managed or {}
    public_key = None

    cert_file_args, cert_args = sshpki.split_file_kwargs(certificate_managed)
    pk_file_args, pk_args = sshpki.split_file_kwargs(private_key_managed)
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
            public_key = _check_ret(__salt__["ssh_pki.get_public_key"](public_key))

        if create_private_key:
            # A missing private key means we need to create a certificate regardless
            new_certificate = True
        elif not _check_ret(__salt__["file.file_exists"](name)):
            new_certificate = True
        else:
            # We check the certificate the same way the state does
            crt = _check_ret(__salt__["file.read"](name))
            signing_policy_contents = _check_ret(
                __salt__[f"{backend}.get_signing_policy"](
                    signing_policy, ca_server=ca_server, **(backend_args or {})
                )
            )
            current, cert_changes, replace = sshpki.check_cert_changes(
                crt,
                **cert_args,
                ca_server=ca_server,
                signing_policy_contents=signing_policy_contents,
                backend=backend,
                public_key=public_key,
            )
            new_certificate = new_certificate or replace

        if pk_args and pk_args.get("new") and not create_private_key:
            if new_certificate or cert_changes:
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
                    "ssh_pki.private_key_managed_ssh": [
                        {k: v} for k, v in pk_ret.items()
                    ]
                }
                ret[pk_args["name"] + "_key"]["ssh_pki.private_key_managed_ssh"].extend(
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
            elif cert_changes:
                cert_ret["comment"] = "The certificate would have been updated"
                cert_ret["changes"] = cert_changes
            else:
                cert_ret["comment"] = "The certificate is in the correct state"
                cert_ret["changes"] = {}

            ret[name + "_crt"] = {
                "ssh_pki.certificate_managed_ssh": [{k: v} for k, v in cert_ret.items()]
            }
            ret[name + "_crt"]["ssh_pki.certificate_managed_ssh"].extend(
                {k: v} for k, v in cert_file_args.items()
            )
            return ret

        if create_private_key or recreate_private_key:
            pk_temp_file = _check_ret(__salt__["temp.file"]())
            _check_ret(__salt__["file.set_mode"](pk_temp_file, "0600"))
            cpk_args = {"path": pk_temp_file, "overwrite": True}
            for arg in (
                "algo",
                "keysize",
                "passphrase",
            ):
                if arg in pk_args:
                    cpk_args[arg] = pk_args[arg]
            _check_ret(__salt__["ssh_pki.create_private_key"](**cpk_args))
            public_key = _check_ret(
                __salt__["ssh_pki.get_public_key"](
                    pk_temp_file, pk_args.get("passphrase")
                )
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
                "ssh_pki.private_key_managed_ssh": [{k: v} for k, v in pk_ret.items()]
            }
            ret[pk_args["name"] + "_key"]["ssh_pki.private_key_managed_ssh"].extend(
                {k: v} for k, v in pk_file_args.items()
            )
            ret[pk_args["name"] + "_key"]["ssh_pki.private_key_managed_ssh"].append(
                {"tempfile": pk_temp_file}
            )

        cert_ret = {
            "name": name,
            "result": True,
            "changes": {},
        }
        if new_certificate or cert_changes:
            pp = ("re" if current else "") + "created"
            cert_ret["contents"] = _check_ret(
                __salt__[f"{backend}.create_certificate"](
                    **_filter_cert_managed_state_args(cert_args),
                    **(backend_args or {}),
                    ca_server=ca_server,
                    signing_policy=signing_policy,
                    public_key=public_key,
                )
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
            "ssh_pki.certificate_managed_ssh": [{k: v} for k, v in cert_ret.items()]
        }
        ret[name + "_crt"]["ssh_pki.certificate_managed_ssh"].append(
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
                "ssh_pki.certificate_managed_ssh": [
                    {"name": name},
                    {"result": False},
                    {"comment": str(err)},
                    {"changes": {}},
                ]
            }
        }
        if pk_args and "name" in pk_args:
            ret[pk_args["name"] + "_key"] = {
                "ssh_pki.private_key_managed_ssh": [
                    {"name": pk_args["name"]},
                    {"result": False},
                    {"comment": str(err)},
                    {"changes": {}},
                ]
            }
    return ret


def _filter_cert_managed_state_args(kwargs):
    return {k: v for k, v in kwargs.items() if k != "ttl_remaining"}


def _load_privkey(pk, passphrase, overwrite=False):
    public_key = None
    create_private_key = False
    try:
        public_key = _check_ret(
            __salt__["ssh_pki.get_public_key"](
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
