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
import os
from collections.abc import Iterable, Mapping

import salt.utils.files

try:
    from cryptography import x509

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

__NOT_FOUND = object()

__virtualname__ = "pem"


def __virtual__():
    if not HAS_CRYPTOGRAPHY:
        return (False, "Could not load cryptography")
    return __virtualname__


log = logging.getLogger(__name__)


def _validate_str_list(arg, encoding=None):
    """
    ensure ``arg`` is a list of strings
    """
    if isinstance(arg, bytes):
        ret = [salt.utils.stringutils.to_unicode(arg, encoding=encoding)]
    elif isinstance(arg, str):
        ret = [arg]
    elif isinstance(arg, Iterable) and not isinstance(arg, Mapping):
        ret = []
        for item in arg:
            if isinstance(item, str):
                ret.append(item)
            else:
                ret.append(str(item))
    else:
        ret = [str(arg)]
    return ret


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
    template=None,
    allow_empty=False,
    contents=None,
    contents_pillar=None,
    contents_grains=None,
    contents_delimiter=":",
    contents_newline=True,
    encoding=None,
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
    source_content = None

    # contents, contents_pillar and content_grains management
    if contents_pillar is not None:
        if isinstance(contents_pillar, list):
            list_contents = []
            for nextp in contents_pillar:
                nextc = __salt__["pillar.get"](
                    nextp, __NOT_FOUND, delimiter=contents_delimiter
                )
                if nextc is __NOT_FOUND:
                    return _error(ret, f"Pillar {nextp} does not exist")
                list_contents.append(nextc)
            use_contents = os.linesep.join(list_contents)
        else:
            use_contents = __salt__["pillar.get"](
                contents_pillar, __NOT_FOUND, delimiter=contents_delimiter
            )
            if use_contents is __NOT_FOUND:
                return _error(ret, f"Pillar {contents_pillar} does not exist")

    elif contents_grains is not None:
        if isinstance(contents_grains, list):
            list_contents = []
            for nextg in contents_grains:
                nextc = __salt__["grains.get"](
                    nextg, __NOT_FOUND, delimiter=contents_delimiter
                )
                if nextc is __NOT_FOUND:
                    return _error(ret, f"Grain {nextc} does not exist")
                list_contents.append(nextc)
            use_contents = os.linesep.join(list_contents)
        else:
            use_contents = __salt__["grains.get"](
                contents_grains, __NOT_FOUND, delimiter=contents_delimiter
            )
            if use_contents is __NOT_FOUND:
                return _error(ret, f"Grain {contents_grains} does not exist")

    elif contents is not None:
        use_contents = contents

    else:
        use_contents = None

    if use_contents is not None:
        if not allow_empty and not use_contents:
            if contents_pillar:
                contents_id = f"contents_pillar {contents_pillar}"
            elif contents_grains:
                contents_id = f"contents_grains {contents_grains}"
            else:
                contents_id = "'contents'"
            return _error(
                ret,
                "{} value would result in empty contents. Set allow_empty "
                "to True to allow the managed file to be empty.".format(contents_id),
            )

        try:
            validated_contents = _validate_str_list(use_contents, encoding=encoding)
            if not validated_contents:
                return _error(
                    ret,
                    "Contents specified by contents/contents_pillar/"
                    "contents_grains is not a string or list of strings, and "
                    "is not binary data. SLS is likely malformed.",
                )
            source_content = ""
            for part in validated_contents:
                for line in part.splitlines():
                    source_content += line.rstrip("\n").rstrip("\r") + os.linesep
            if not contents_newline:
                # If source_content newline is set to False, strip out the newline
                # character and carriage return character
                source_content = source_content.rstrip("\n").rstrip("\r")

        except UnicodeDecodeError:
            # Either something terrible happened, or we have binary data.
            if template:
                return _error(
                    ret,
                    "Contents specified by source_content/contents_pillar/"
                    "contents_grains appears to be binary data, and"
                    " as will not be able to be treated as a Jinja"
                    " template.",
                )
            source_content = use_contents

    # If no contents specified, get content from salt
    if source_content is None:
        try:
            source_content = __salt__["cp.get_file_str"](
                path=source,
                saltenv=saltenv,
            )
        except Exception as exc:  # pylint: disable=broad-except
            ret["result"] = False
            ret["comment"] = f"Unable to get file str: {exc}"
            return ret

    # Apply template
    if template:
        source_content = __salt__["file.apply_template_on_contents"](
            source_content,
            template=template,
            context=context,
            defaults=defaults,
            saltenv=saltenv,
        )
        if not isinstance(source_content, str):
            if "result" in source_content:
                ret["result"] = source_content["result"]
            else:
                ret["result"] = False
            if "comment" in source_content:
                ret["comment"] = source_content["comment"]
            else:
                ret["comment"] = "Error while applying template on source_content"
            return ret

    if source_content is None:
        return _error(ret, "source_content is empty")

    try:
        new_cert = x509.load_pem_x509_certificate(source_content.encode())
        new_cert_info = f"+ Subject: {new_cert.subject.rfc4514_string()}\n+ Not valid after: {new_cert.not_valid_after}"
    except ValueError as val_err:
        # This is not a certificate, but we can still continue with file.managed backend
        log.debug("pem: %s", val_err)
        log.debug("pem: Value error found, continue normally as file.managed state")
        skip_conditions = True
    except Exception as exc:  # pylint: disable=broad-except
        ret["result"] = False
        ret["comment"] = f"Problem with source file: {exc}"
        return ret

    # Load existing certificate
    try:
        with salt.utils.files.fopen(name, "rb") as existing_cert_file:
            existing_cert = x509.load_pem_x509_certificate(existing_cert_file.read())
            existing_cert_info = f"- Subject: {existing_cert.subject.rfc4514_string()}\n- Not valid after: {existing_cert.not_valid_after}"
    except FileNotFoundError:
        # Old certificate initialy does not need to exist if it is a first time state is running
        skip_conditions = True
    except ValueError as val_err:
        # This is not a certificate, but we can still continue with file.managed backend
        log.debug("pem: %s", val_err)
        log.debug("pem: Value error found, continue normally as file.managed state")
        skip_conditions = True
    except Exception as exc:  # pylint: disable=broad-except
        ret["result"] = False
        ret["comment"] = f"Unable to determine existing file: {exc}"
        return ret

    if existing_cert_info == "" and new_cert_info == "":
        log.debug(
            "pem: No certificate information was found - state is running as normal file.managed state"
        )
    elif existing_cert_info != "" and new_cert_info != "":
        if (
            new_cert.subject.rfc4514_string() == existing_cert.subject.rfc4514_string()
            and new_cert.not_valid_after == existing_cert.not_valid_after
        ):
            ret["comment"] = f"Certificates are the same:\n{existing_cert_info}\n"
    elif existing_cert_info == "" and new_cert_info != "":
        ret["comment"] = f"New cert info:\n{new_cert_info}\n"
    else:
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
        template=template,
        allow_empty=allow_empty,
        contents=contents,
        contents_pillar=contents_pillar,
        contents_grains=contents_grains,
        contents_delimiter=contents_delimiter,
        contents_newline=contents_newline,
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
