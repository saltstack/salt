"""
Manage OpenSSH certificates
===========================

.. versionadded:: 3008.0


:depends: cryptography

Configuration instructions and general remarks are documented
in the :ref:`execution module docs <sshcert-setup>`.

About
-----
This module can enable managing a complete SSH PKI infrastructure, including creating
private keys, CAs and certificates. It includes the ability to generate a
private key on a server, and have the corresponding public key sent to a remote
CA to create a CA-signed certificate. This can be done in a secure manner, where
private keys are always generated locally and never moved across the network.

.. note::

    In addition to the native Salt backend (the ``ssh_pki`` execution module),
    you can have the state module call a different (compatible) execution module
    using the ``backend`` parameter.

Example
-------
Here is a simple example scenario. In this example, ``ca`` is the CA server
and ``www`` is a web server that needs a certificate signed by ``ca``.

.. note::

    Remote signing using the native Salt backend requires the setup of
    :term:`Peer Communication` and signing policies. Please see the
    :ref:`execution module docs <sshcert-setup>`.


/srv/salt/top.sls

.. code-block:: yaml

    base:
      '*':
        - cert
      'ca':
        - ca
      'www':
        - www

This state creates the CA key and signing policy. It also publishes
the public key to the mine, where it can be easily retrieved by other minions.

.. code-block:: yaml

    # /srv/salt/ca.sls

    Ensure SSH PKI directories exist:
      file.directory:
        - name: /etc/pki/ssh/issued_certs
        - makedirs: true

    Create CA private key:
      ssh_pki.private_key_managed:
        - name: /etc/pki/ssh/ca.key
        - algo: ed25519
        - backup: true
        - require:
          - file: /etc/pki/ssh/issued_certs

    Write CA public key:
      ssh_pki.public_key_managed:
        - name: /etc/pki/ssh/ca.pub
        - public_key_source: /etc/pki/ssh/ca.key
        - require:
          - ssh_pki: /etc/pki/ssh/ca.key

.. code-block:: yaml

    # /srv/salt/ssh_pki.conf

    # publish the CA certificate to the mine
    mine_functions:
      ssh_ca:
        - mine_function: ssh_pki.get_public_key
        - /etc/pki/ssh/ca.key

    # define at least one signing policy for remote signing
    ssh_signing_policies:
      www_host:
        - minions: 'www'
        - signing_private_key: /etc/pki/ssh/ca.key
        - cert_type: host
        - ttl: 7d
        - copypath: /etc/pki/ssh/issued_certs/


This example state will instruct minion SSH servers to trust certificates
signed by our new CA. Mind that the specifics depend on the OS.

.. code-block:: jinja

    # /srv/salt/cert.sls

    Write the trusted CA file:
      file.managed:
        - name: /etc/ssh/trusted-user-ca-keys.pem
        - contents: {{ salt["mine.get"]("ca", "ssh_ca")["ca"] | json }}
        - user: root
        - group: root

    Ensure SSH is configured to trust the CA:
      file.managed:
        - name: /etc/ssh/sshd_config.d/salt_ca_trust.conf
        - contents: |
            TrustedUserCAKeys /etc/ssh/trusted-user-ca-keys.pem
        - require:
          - file: /etc/ssh/trusted-user-ca-keys.pem

This state creates a private key to use as the host key, then requests
a certificate signed by our CA according to the ``www_host`` policy and configures
the SSH server to use it.

.. code-block:: yaml

    # /srv/salt/www.sls

    Create host private key:
      ssh_pki.private_key_managed:
        - name: /etc/ssh/ssh_host_rsa_key
        - algo: ed25519
        - backup: true

    Request certificate:
      ssh_pki.certificate_managed:
        - name: /etc/ssh/ssh_host_rsa_key.pub
        - ca_server: ca
        - signing_policy: www_host
        - private_key: /etc/ssh/ssh_host_rsa_key
        - backup: true
        - require:
          - ssh_pki: /etc/ssh/ssh_host_rsa_key

    Ensure SSH is configured to use the certificate:
      file.managed:
        - name: /etc/ssh/sshd_config.d/host_cert.conf
        - contents: |
            HostKey /etc/ssh/ssh_host_rsa_key
            HostCertificate /etc/ssh/ssh_host_rsa_key-cert.pub
        - require:
          - ssh_pki: /etc/ssh/ssh_host_rsa_key
          - ssh_pki: /etc/ssh/ssh_host_rsa_key.pub
"""

import logging
import os.path

import salt.utils.atomicfile
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.state import STATE_INTERNAL_KEYWORDS as _STATE_INTERNAL_KEYWORDS

try:
    import salt.utils.sshpki as sshpki
    import salt.utils.x509 as x509util

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


log = logging.getLogger(__name__)

__virtualname__ = "ssh_pki"


def __virtual__():
    if not HAS_CRYPTOGRAPHY:
        return (False, "Could not load cryptography")
    return __virtualname__


def certificate_managed(
    name,
    ttl_remaining=None,
    ca_server=None,
    backend=None,
    backend_args=None,
    signing_policy=None,
    copypath=None,
    cert_type=None,
    signing_private_key=None,
    signing_private_key_passphrase=None,
    public_key=None,
    private_key=None,
    private_key_passphrase=None,
    serial_number=None,
    not_before=None,
    not_after=None,
    ttl=None,
    critical_options=None,
    extensions=None,
    valid_principals=None,
    all_principals=False,
    key_id=None,
    **kwargs,
):
    """
    Ensure an OpenSSH certificate is present as specified.

    This function accepts the same arguments as
    :py:func:`ssh_pki.create_certificate <salt.modules.ssh_pki.create_certificate>`,
    as well as most ones for `:py:func:`file.managed <salt.states.file.managed>`.

    .. note::

        Since ``file.managed`` also has an ``encoding`` param, it can be passed
        as ``file_encoding`` instead.

    name
        The path the certificate should be present at.

    ttl_remaining
        The certificate will be recreated once the remaining certificate validity
        period is less than this number of seconds. Can also be specified as a
        time string like ``12d`` or ``1.5h``.
        Defaults to ``30d`` for host keys and ``1h`` for user keys.

    ca_server
        Request a remotely signed certificate from another minion acting as
        a CA server via the ``ssh_pki`` execution module. For this to
        work, a ``signing_policy`` must be specified, and that same policy
        must be configured on the ca_server.  Also, the Salt master must
        permit peers to call the ``ssh_pki.sign_remote_certificate`` function.
        See the :ref:`execution module docs <sshcert-setup>` for details.

    backend
        Instead of using the ``ssh_pki`` execution module for certificate
        creation, use this backend. It must provide a compatible API for
        ``create_certificate`` and ``get_signing_policy``.

    backend_args
        If ``backend`` is specified, pass these additional keyword arguments
        to it. Must be a mapping (dict).

    signing_policy
        The name of a configured signing policy. Parameters specified in there
        are hardcoded and cannot be overridden. This is required for remote signing,
        otherwise optional.

    copypath
        Create a copy of the issued certificate in this directory.
        The file will be named ``<serial_number>.crt``.

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

    extensions
        A mapping of extension name to extension value to set on the certificate.
        If an extension does not take a value, specify it as ``true``.

    valid_principals
        A list of valid principals.

    all_principals
        Allow any principals. Defaults to false.

    key_id
        Specify a string-valued key ID for the signed public key.
        When the certificate is used for authentication, this value will be
        logged in plaintext.
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "The certificate is in the correct state",
    }
    current = None
    changes = {}
    verb = "create"
    backend = backend or "ssh_pki"
    backend_args = backend_args or {}

    file_args, unknown_args = sshpki.split_file_kwargs(
        _filter_state_internal_kwargs(kwargs)
    )
    invalid_args = [key for key in unknown_args if not key.startswith("_")]
    if invalid_args:
        raise SaltInvocationError(
            f"The following keyword arguments are invalid: {', '.join(invalid_args)}"
        )
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
            signing_policy_contents = __salt__[f"{backend}.get_signing_policy"](
                signing_policy, ca_server=ca_server, **(backend_args or {})
            )
            current, checked_changes, replace = sshpki.check_cert_changes(
                real_name,
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
                ttl_remaining=ttl_remaining,
                critical_options=critical_options,
                extensions=extensions,
                valid_principals=valid_principals,
                all_principals=all_principals,
                key_id=key_id,
            )
            changes.update(checked_changes)
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
            # request a new certificate otherwise
            cert = __salt__[f"{backend}.create_certificate"](
                cert_type=cert_type,
                ca_server=ca_server,
                signing_policy=signing_policy,
                signing_private_key=signing_private_key,
                signing_private_key_passphrase=signing_private_key_passphrase,
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
                **backend_args,
            )
            ret["comment"] = f"The certificate has been {verb}d"

        replace = bool(changes)
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


def private_key_managed(
    name,
    algo="rsa",
    keysize=None,
    passphrase=None,
    new=False,
    overwrite=False,
    **kwargs,
):
    """
    Ensure a private key is present as specified.

    This function accepts the same arguments as
    :py:func:`ssh_pki.create_private_key <salt.modules.ssh_pki.create_private_key>`,
    as well as most ones for :py:func:`file.managed <salt.states.file.managed>`.

    .. note::

        If ``mode`` is unspecified, it will default to ``0400``.

    name
        The path the private key should be present at.

    algo
        The digital signature scheme the private key should be based on.
        Available: ``rsa``, ``ec``, ``ed25519``. Defaults to ``rsa``.

    keysize
        For ``rsa``, specifies the bitlength of the private key (2048, 3072, 4096).
        For ``ec``, specifies the NIST curve to use (256, 384, 521).
        Irrelevant for ``ed25519``.
        Defaults to 2048 for RSA and 256 for EC.

    passphrase
        If this is specified, the private key will be encrypted using this
        passphrase. The encryption algorithm cannot be selected, it will be
        determined automatically as the best available one.

    new
        Always create a new key. Defaults to false.
        Combining new with :mod:`prereq <salt.states.requisites.prereq>`
        can allow key rotation whenever a new certificate is generated.

    overwrite
        Overwrite an existing private key if the provided passphrase cannot decrypt it.
        Defaults to false.

    Example:

    The Jinja templating in this example ensures a new private key is generated
    if the file does not exist and whenever the associated certificate
    is to be renewed.

    .. code-block:: jinja

        Manage www private key:
          ssh_pki.private_key_managed:
            - name: /root/.ssh/www
            - keysize: 4096
            - new: true
        {%- if salt["file.file_exists"]("/root/.ssh/www") %}
            - prereq:
              - ssh_pki: /root/.ssh/www.crt
        {%- endif %}
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "The private key is in the correct state",
    }
    current = None
    changes = {}
    verb = "create"
    file_args, unknown_args = sshpki.split_file_kwargs(
        _filter_state_internal_kwargs(kwargs)
    )
    invalid_args = [key for key in unknown_args if not key.startswith("_")]
    if invalid_args:
        raise SaltInvocationError(
            f"The following keyword arguments are invalid: {', '.join(invalid_args)}"
        )

    if not file_args.get("mode"):
        # ensure secure defaults
        file_args["mode"] = "0400"

    try:
        if keysize and algo == "ed25519":
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
                current = sshpki.load_privkey(real_name, passphrase=passphrase)
                current_has_passphrase = False
                if passphrase:
                    try:
                        # The SSH key logic does not complain when a
                        # passphrase was specified, but the key is not encrypted
                        sshpki.load_privkey(real_name, passphrase=None)
                    except (
                        CommandExecutionError,
                        SaltInvocationError,
                    ) as err:  # pylint: disable=broad-except
                        if "Bad decrypt" not in str(err):
                            raise
                        current_has_passphrase = True

            except (CommandExecutionError, SaltInvocationError) as err:
                if "Bad decrypt" in str(err):
                    if not overwrite:
                        raise CommandExecutionError(
                            "The provided passphrase cannot decrypt the private key. "
                            "Pass overwrite: true to force regeneration"
                        ) from err
                    changes["passphrase"] = True
                elif "Private key is encrypted" in str(err):
                    if not overwrite:
                        raise CommandExecutionError(
                            "The current key is encrypted with a passphrase. "
                            "Pass overwrite: true to force regeneration"
                        ) from err
                    changes["passphrase"] = True
                elif any(
                    (
                        "Could not deserialize binary data" in str(err),
                        "Could not load OpenSSH" in str(err),
                    )
                ):
                    if not overwrite:
                        raise CommandExecutionError(
                            "The existing file does not seem to be a private key. "
                            "Pass overwrite: true to force regeneration"
                        ) from err
                    replace = True
                else:
                    raise
        if current:
            key_type = x509util.get_key_type(current)
            check_keysize = keysize
            if check_keysize is None:
                if algo == "rsa":
                    check_keysize = 3072
                elif algo == "ec":
                    check_keysize = 256
            if any(
                (
                    (algo == "rsa" and not key_type == x509util.KEY_TYPE.RSA),
                    (algo == "ec" and not key_type == x509util.KEY_TYPE.EC),
                    (algo == "ed25519" and not key_type == x509util.KEY_TYPE.ED25519),
                )
            ):
                changes["algo"] = algo
            if (
                "algo" not in changes
                and algo in ("rsa", "ec")
                and current.key_size != check_keysize
            ):
                changes["keysize"] = check_keysize
            if passphrase and not current_has_passphrase:
                # Removing a passphrase currently has to be forced with overwrite since
                # cryptography does not report if the file is a valid private key
                changes["passphrase"] = True

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
            if set(changes) == {"passphrase"}:
                pk = __salt__["ssh_pki.encode_private_key"](
                    current, passphrase=passphrase
                )
                verb = "encrypte"
            else:
                pk = __salt__["ssh_pki.create_private_key"](
                    algo=algo,
                    keysize=keysize,
                    passphrase=passphrase,
                )["private_key"]
            ret["comment"] = f"The private key has been {verb}d"

        replace = bool(changes)
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


def public_key_managed(name, public_key_source, passphrase=None, **kwargs):
    """
    Ensure a public key is present as specified.

    This function accepts most arguments for :py:func:`file.managed <salt.states.file.managed>`.

    .. note::

        If ``mode`` is unspecified, it will default to ``0400``.

    name
        The path the public key should be present at.

    public_key_source
        The certificate (or any reference that can be passed
        to ``get_public_key``) to retrieve the public key from.

    passphrase
        If ``public_key_source`` is an encrypted private key,
        specify its passphrase here.
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "The public key is in the correct state",
    }
    current = None
    verb = "create"
    file_args, unknown_args = sshpki.split_file_kwargs(
        _filter_state_internal_kwargs(kwargs)
    )
    invalid_args = [key for key in unknown_args if not key.startswith("_")]
    if invalid_args:
        raise SaltInvocationError(
            f"The following keyword arguments are invalid: {', '.join(invalid_args)}"
        )

    try:
        real_name = name
        replace = True

        # handle follow_symlinks
        if __salt__["file.is_link"](name):
            if file_args.get("follow_symlinks", True):
                real_name = os.path.realpath(name)
            else:
                # workaround https://github.com/saltstack/salt/issues/31802
                __salt__["file.remove"](name)

        try:
            public_key = __salt__["ssh_pki.get_public_key"](
                public_key_source, passphrase=passphrase
            )
        except CommandExecutionError as err:
            if not __opts__["test"] or "Could not load key as" not in str(err):
                raise
            public_key = None
        file_exists = __salt__["file.file_exists"](real_name)

        if file_exists:
            current = sshpki.load_pubkey(real_name)
            if public_key and x509util.match_pubkey(
                sshpki.load_pubkey(public_key), current
            ):
                replace = False
            else:
                verb = "update"

        if replace:
            ret["changes"][f"{verb}d"] = name
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"] = f"The public key would have been {verb}d"
                if not public_key:
                    ret["comment"] += (
                        ". Note that the source could not be loaded, so this "
                        "assessment relies on the source being created beforehand"
                    )
                return ret
        file_managed_ret = _file_managed(
            name, contents=public_key if replace else None, replace=replace, **file_args
        )
        _add_sub_state_run(ret, file_managed_ret)
        if not _check_file_ret(file_managed_ret, ret, current):
            return ret
        if replace:
            ret["comment"] = f"The public key has been {verb}d"
    except (CommandExecutionError, SaltInvocationError) as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def certificate_managed_ssh(
    name, result, comment, changes, encoding=None, contents=None, **kwargs
):
    """
    Helper for the SSH wrapper module.
    This receives a certificate and dumps the data to the target.
    A ``file.managed`` sub-state run will be performed.
    """
    ret = {"name": name, "result": result, "comment": comment, "changes": changes}
    if not result:
        return ret
    file_managed_ret = _file_managed(name, replace=False, **kwargs)
    _add_sub_state_run(ret, file_managed_ret)
    if not _check_file_ret(file_managed_ret, ret, __salt__["file.file_exists"](name)):
        return ret
    if contents is not None:
        if __opts__["test"]:
            ret["comment"] += (
                '. The file was not actually updated - please pass test=opts.get("test") '
                "into the wrapper to enable proper test mode support."
            )
            return ret
        contents = contents.encode()
        salt.utils.atomicfile.safe_atomic_write(
            name,
            contents,
            __salt__["config.backup_mode"](kwargs.get("backup", "")),
            __opts__["cachedir"],
        )
    return ret


def private_key_managed_ssh(name, result, comment, changes, tempfile=None, **kwargs):
    """
    Helper for the SSH wrapper module to report the correct return and
    perform a ``file.managed`` sub-state run.
    """
    ret = {"name": name, "result": result, "comment": comment, "changes": changes}
    if not result:
        return ret
    file_managed_ret = _file_managed(name, replace=False, **kwargs)
    if tempfile is not None:
        if __opts__["test"]:
            ret["comment"] += (
                '. The file was not actually updated - please pass test=opts.get("test") '
                "into the wrapper to enable proper test mode support."
            )
            try:
                __salt__["file.remove"](tempfile)
            except Exception:  # pylint: disable=broad-except
                pass
            return ret
        try:
            # This will replace symlinks with the file
            __salt__["file.move"](tempfile, name)
        except Exception as err:  # pylint: disable=broad-except
            ret["result"] = False
            ret["comment"] += f". But: Failed moving the private key into place: {err}"
            ret["changes"] = {}
            return ret
    _add_sub_state_run(ret, file_managed_ret)
    return ret


def _filter_state_internal_kwargs(kwargs):
    # check_cmd is a valid argument to file.managed
    ignore = set(_STATE_INTERNAL_KEYWORDS) - {"check_cmd"}
    return {k: v for k, v in kwargs.items() if k not in ignore}


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
