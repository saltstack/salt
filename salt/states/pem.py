"""
Provide easier operations on certificate files
=====================================================================

Provides human-readable information regarding changes of files containing certificates.

Requires `cryptography` python package.

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
    Manage certificates as files and provide certificate expiration and common name in the comment.

    It can handle one certificate or full privkey->cert->chain files.

    Conditions provides an easy way to match against the certificate's Common Name
    or to make sure that only newer certificates are copied down.

    State can handle everything that file.managed can handle,
    because it is used underneath to process changes to files.

    For all parameters refer to file.managed documentation:
    https://docs.saltproject.io/en/master/ref/states/all/salt.states.file.html#salt.states.file.managed

    Args:

        skip_conditions (bool): Do not check expiration or Common name match (default: False)
                                Also pillar can be used: pillar="{skip_conditions: True}"
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
            ] += "New certificate expires sooner than existing one (skip with pillar='{skip_conditions: True}')\n"
            failed_conditions = True
        if new_cert.subject.rfc4514_string() != existing_cert.subject.rfc4514_string():
            ret[
                "comment"
            ] += "Certificates CN does not match (skip with pillar='{skip_conditions: True}')\n"
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
