"""
.. versionadded:: 3008.0

Low-level asymmetric cryptographic operations.

:depends: cryptography

.. note::

    All parameters that take a public key or private key can be specified either
    as a PEM/hex/base64 string or a path to a local file encoded in all supported
    formats for the type.

    A signature can be specified as a base64 string or a path to a file with the
    raw signature or its base64 encoding.

    Public keys and signatures can additionally be specified as a URL that can be
    retrieved using :py:func:`cp.cache_file <salt.modules.cp.cache_file>`.
"""

import base64
import logging
from pathlib import Path
from urllib.parse import urlparse

import salt.utils.files
from salt.exceptions import CommandExecutionError, SaltInvocationError

try:
    from salt.utils import asymmetric as asym
    from salt.utils import x509

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

log = logging.getLogger(__name__)

__virtualname__ = "asymmetric"


def __virtual__():
    if HAS_CRYPTOGRAPHY:
        return __virtualname__
    return False, "Missing `cryptography` library"


def sign(
    privkey, passphrase=None, text=None, filename=None, digest=None, raw=None, path=None
):
    """
    Sign a file or text using an (RSA|ECDSA|Ed25519|Ed448) private key.
    You can employ :py:func:`x509.create_private_key <salt.modules.x509_v2.create_private_key>`
    to generate one. Returns the signature encoded in base64 by default.

    CLI Example:

    .. code-block:: bash

        salt '*' asymmetric.sign /root/my_privkey.pem text='I like you'
        salt '*' asymmetric.sign /root/my_privkey.pem filename=/data/to/be/signed

    privkey
        The private key to sign with.

    passphrase
        If the private key is encrypted, the passphrase to decrypt it. Optional.

    text
        Pass the text to sign. Either this or ``filename`` is required.

    filename
        Pass the path of a file to sign. Either this or ``text`` is required.

    digest
        The name of the hashing algorithm to use when creating signatures.
        Defaults to ``sha256``. Only relevant for ECDSA or RSA.

    raw
        Return the raw bytes instead of encoding them to base64. Defaults to false.

    path
        Instead of returning the data, write it to a path on the local filesystem.
        Optional.
    """
    if text is not None:
        try:
            data = text.encode()
        except AttributeError:
            data = text
    elif filename:
        data = Path(filename)
    else:
        raise SaltInvocationError("Either `text` or `filename` is required")
    raw = raw if raw is not None else bool(path)
    sig = asym.sign(privkey, data, digest, passphrase=passphrase)
    mode = "wb"
    if not raw:
        sig = base64.b64encode(sig).decode()
        mode = "w"
    if path:
        with salt.utils.files.fopen(path, mode) as out:
            out.write(sig)
        return f"Signature written to '{path}'"
    return sig


def verify(
    text=None,
    filename=None,
    pubkey=None,
    signature=None,
    digest=None,
    signed_by_any=None,
    signed_by_all=None,
    **kwargs,  # pylint: disable=unused-argument
):
    """
    Verify signatures on a specific input against (RSA|ECDSA|Ed25519|Ed448) public keys.

    .. note::

        This function is supposed to be compatible with the same interface
        as :py:func:`gpg.verify <salt.modules.gpg.verify>`` regarding keyword
        arguments and return value format.

    CLI Example:

    .. code-block:: bash

        salt '*' asymmetric.verify pubkey=/root/my_pubkey.pem text='I like you' signature=/root/ilikeyou.sig
        salt '*' asymmetric.verify pubkey=/root/my_pubkey.pem path=/root/confidential signature=/root/confidential.sig

    text
        The text to verify. Either this or ``filename`` is required.

    filename
        The path of a file to verify. Either this or ``text`` is required.

    pubkey
        The single public key to verify ``signature`` against. Specify either
        this or make use of ``signed_by_any``/``signed_by_all`` for compound checks.

    signature
        If ``pubkey`` is specified, the single signature to verify.
        If ``signed_by_any`` and/or ``signed_by_all`` is specified, this can be
        a list of multiple signatures to check against the provided keys.
        Required.

    digest
        The name of the hashing algorithm to use when verifying signatures.
        Defaults to ``sha256``. Only relevant for ECDSA or RSA.

    signed_by_any
        A list of pubkeys from which any valid signature will mark verification
        as passed. If none of the listed pubkeys provided a signature,
        verification fails. Works with ``signed_by_all``, but mutually
        exclusive with ``pubkey``.

    signed_by_all
        A list of pubkeys, all of which must provide a signature for verification
        to pass. If a single one of the listed pubkeys did not provide a signature,
        verification fails. Works with ``signed_by_any``, but mutually
        exclusive with ``pubkey``.
    """
    # Basic compatibility with gpg.verify
    ret = {"res": False, "message": "internal error"}

    signed_by_any = signed_by_any or []
    signed_by_all = signed_by_all or []
    if text and filename:
        raise SaltInvocationError(
            "`text` and `filename` arguments are mutually exclusive"
        )
    if not signature:
        raise SaltInvocationError("Missing `signature` parameter")
    # We're constrained by compatibility with gpg.verify, so ensure the parameters
    # are as expected.
    multi_check = bool(signed_by_any or signed_by_all)
    if multi_check:
        if pubkey:
            raise SaltInvocationError(
                "Either specify pubkey + signature or signed_by_(any|all)"
            )
        if isinstance(signature, (str, bytes)):
            signature = [signature]
        if not isinstance(signed_by_any, list):
            signed_by_any = [signed_by_any]
        if not isinstance(signed_by_all, list):
            signed_by_all = [signed_by_all]
    elif not pubkey:
        raise SaltInvocationError("Missing pubkey(s) to check against")
    elif not isinstance(signature, (str, bytes)):
        raise SaltInvocationError(
            "`signature` must be a string or bytes when verifying a single signing `pubkey`"
        )
    else:
        signed_by_all = [pubkey]
    if not isinstance(signature, list):
        signature = [signature]

    file_digest = None
    if text:
        try:
            data = text.encode()
        except AttributeError:
            data = text
    elif filename:
        data = Path(filename)
        if not data.exists():
            raise CommandExecutionError(f"Path '{filename}' does not exist")
    else:
        raise SaltInvocationError(
            "Missing data to verify. Either specify `text` or `filename`"
        )
    any_check = all_check = False
    sigs = []
    for sig in signature:
        try:
            sigs.append(_fetch(sig))
        except CommandExecutionError as err:
            if pubkey:
                return {"res": False, "message": str(err)}
            log.error(str(err), exc_info_on_loglevel=logging.DEBUG)
    if not sigs:
        raise CommandExecutionError("Unable to locate any of the provided signatures")
    if signed_by_any:
        for signer in signed_by_any:
            try:
                # Since we don't know if the signature algorithm supports
                # `prehashed` (only rsa/ec), don't calculate it early, but
                # cache it once it has been calculated. If a verification fails,
                # it throws an exception.
                _, data, file_digest = _verify_pubkey_against_list(
                    signer, sigs, data, digest, file_digest=file_digest
                )
                any_check = True
                break
            except asym.InvalidSignature as err:
                log.info(str(err), exc_info_on_loglevel=logging.DEBUG)
                if err.file_digest is not None:
                    file_digest = err.file_digest
                if err.data is not None:
                    data = err.data
            except Exception as err:  # pylint: disable=broad-except
                log.error(str(err), exc_info_on_loglevel=logging.DEBUG)
        else:
            ret["res"] = False
            ret["message"] = (
                "None of the public keys listed in signed_by_any provided a valid signature"
            )
            return ret

    if signed_by_all:
        all_sigs = sigs.copy()
        for signer in signed_by_all:
            try:
                match, data, file_digest = _verify_pubkey_against_list(
                    signer, all_sigs, data, digest, file_digest=file_digest
                )
                # Remove already associated signatures from list of possible ones
                # Since pubkeys can be specified in different ways, this fails if
                # the user passes in the same pubkey twice
                all_sigs = list(set(all_sigs).difference(match))
                continue
            except Exception as err:  # pylint: disable=broad-except
                log.error(str(err), exc_info_on_loglevel=logging.DEBUG)
                ret["res"] = False
                if pubkey:
                    ret["message"] = f"Failed checking signature: {err}"
                else:
                    ret["message"] = f"Failed while checking `signed_by_all`: {err}"
                return ret
        all_check = True

    if bool(signed_by_any) is any_check and bool(signed_by_all) is all_check:
        ret["res"] = True
        if pubkey:
            ret["message"] = "The signature is valid"
        else:
            ret["message"] = "All required keys have provided a signature"
        return ret
    # This should never be reached
    ret["res"] = False
    return ret


def _verify_pubkey_against_list(pub, sigs, data, digest, file_digest=None):
    pubkey = _fetch(pub)
    pubkey = x509.load_pubkey(pubkey)
    match = []
    for sig in sigs:
        try:
            data, file_digest = asym.verify(
                pubkey, sig, data, digest, file_digest=file_digest
            )
            match.append(sig)
        except asym.InvalidSignature as err:
            if err.file_digest is not None:
                file_digest = err.file_digest
            if err.data is not None:
                data = err.data
    if not match:
        raise asym.InvalidSignature(
            f"Invalid signature for key {asym.fingerprint(pubkey)}",
            file_digest=file_digest,
            data=data,
            pubkey=pubkey,
        )
    return match, data, file_digest


def _fetch(url):
    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return url
    sfn = None
    if parsed.scheme == "":
        sfn = url
    elif parsed.scheme == "file":
        sfn = parsed.path
    else:
        sfn = __salt__["cp.cache_file"](url)
    if not sfn:
        raise CommandExecutionError(f"Failed fetching '{url}'")
    if parsed.scheme != "":
        if not Path(sfn).exists():
            raise CommandExecutionError(f"Failed fetching '{url}'")
    return sfn
