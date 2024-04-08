"""
Provide easier operations on certificate files
=====================================================================

Main purpose for this is to provide easier and human readable info
regarding changes if files contains certificates.

Requirement is `cryptography` python package.

.. code-block:: yaml

/etc/ssl/postfix/mydomain/mydomain.pem:
  pem.managed:
    - source: salt://files/etc/ssl/mydomain.pem
    - user: root
    - group: postfix
    - dir_mode: 711
    - makedirs: True
    - template: jinja
"""

import logging

import salt.utils.files

try:
    from cryptography import x509

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

__virtualname__ = "pem"


def __virtual__():
    if not HAS_CRYPTOGRAPHY:
        return (False, "Could not load cryptography")
    return __virtualname__


log = logging.getLogger(__name__)


def managed(
    name,
    source=None,
    source_hash=None,
    source_hash_name=None,
    user=None,
    group=None,
    mode=None,
    skip_verify=None,
    defaults=None,
    attrs=None,
    context=None,
    saltenv="base",
    skip_conditions=False,
    **kwargs,
):
    """
    State manage certificates as files and provide minimal overview of
    expiration and common name in comment.

    It can handle one certificate or full privkey->cert->chain files.

    Conditions can provide easy way how to match agains Common name,
    or make sure that only newer certificates will be salted.
    If conditions are not required use this as argument to state:
    `skip_conditions=True`
    Or set pillar in same manner on command line:
    `salt-call state.apply some_other_state pillar="{skip_conditions: True}"`

    State can handle everything that file.managed can handle,
    because it is used underneat to process changes to files.
    """

    skip_conditions = __pillar__.get("skip_conditions", skip_conditions)
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    existing_cert_info = ""
    new_cert_info = ""

    # Load existing certificate
    try:
        with salt.utils.files.fopen(name, "rb") as existing_cert_file:
            existing_cert = x509.load_pem_x509_certificate(existing_cert_file.read())
            existing_cert_info = f"- Subject: {existing_cert.subject.rfc4514_string()}\n- Not valid after: {existing_cert.not_valid_after}"
    except FileNotFoundError:
        # Old certificate initialy does not need to exist if it is a first time state is running
        skip_conditions = True

    try:
        tmp_local_file, source_sum, comment_ = __salt__["file.get_managed"](
            name,
            source=source,
            source_hash=source_hash,
            source_hash_name=source_hash_name,
            user=user,
            group=group,
            mode=mode,
            attrs=attrs,
            saltenv=saltenv,
            defaults=defaults,
            skip_verify=skip_verify,
            context=context,
            **kwargs,
        )
    except Exception as exc:  # pylint: disable=broad-except
        ret["result"] = False
        ret["comment"] = f"Unable to manage file: {exc}"
        return ret

    if not tmp_local_file:
        return _error(ret, f"Source file {source} not found")

    try:
        with salt.utils.files.fopen(tmp_local_file, "rb") as new_cert_file:
            new_cert = x509.load_pem_x509_certificate(new_cert_file.read())
            new_cert_info = f"+ Subject: {new_cert.subject.rfc4514_string()}\n+ Not valid after: {new_cert.not_valid_after}"
    except FileNotFoundError:
        return _error(ret, f"New cached file {tmp_local_file} not found")

    ret["comment"] = (
        f"Existing cert info:\n{existing_cert_info}\nNew cert info:\n{new_cert_info}\n"
    )

    # Conditions when certificates are salted
    if skip_conditions:
        log.debug("pem: Certificate conditions are skipped")
    else:
        failed_conditions = False

        if new_cert.not_valid_after < existing_cert.not_valid_after:
            ret[
                "comment"
            ] += "New certificate expires sooner than existing one (skip with pillar='{skip_conditions: True}')."
            failed_conditions = True
        if new_cert.subject.rfc4514_string() != existing_cert.subject.rfc4514_string():
            ret[
                "comment"
            ] += "Certificates CN does not match (skip with pillar='{skip_conditions: True}')."
            failed_conditions = True

        if failed_conditions:
            ret["result"] = False
            return ret

    result = __states__["file.managed"](
        name=name,
        source=source,
        source_hash=source_hash,
        source_hash_name=source_hash_name,
        user=user,
        group=group,
        mode=mode,
        skip_verify=skip_verify,
        defaults=defaults,
        attrs=attrs,
        context=context,
        **kwargs,
    )

    ret["changes"] = result["changes"]
    ret["result"] = result["result"]
    ret["comment"] += result["comment"]

    return ret


def _error(ret, err_msg):
    ret["result"] = False
    ret["comment"] = err_msg
    return ret
