r"""
.. _`AWS KMS Envelope Encryption`: https://docs.aws.amazon.com/kms/latest/developerguide/workflow.html

Renderer that will decrypt ciphers encrypted using `AWS KMS Envelope Encryption`_.

Any key in the data to be rendered can be a urlsafe_b64encoded string, and this renderer will attempt
to decrypt it before passing it off to Salt. This allows you to safely store secrets in
source control, in such a way that only your Salt master can decrypt them and
distribute them only to the minions that need them.

The typical use-case would be to use ciphers in your pillar data, and keep the encrypted
data key on your master. This way developers with appropriate AWS IAM privileges can add new secrets
quickly and easily.

This renderer requires the boto3_ Python library.

.. _boto3: https://boto3.readthedocs.io/

Setup
-----

First, set up your AWS client. For complete instructions on configuration the AWS client,
please read the `boto3 configuration documentation`_. By default, this renderer will use
the default AWS profile. You can override the profile name in salt configuration.
For example, if you have a profile in your aws client configuration named "salt",
you can add the following salt configuration:

.. code-block:: yaml

    aws_kms:
      profile_name: salt

.. _boto3 configuration documentation: https://boto3.readthedocs.io/en/latest/guide/configuration.html

The rest of these instructions assume that you will use the default profile for key generation
and setup. If not, export AWS_PROFILE and set it to the desired value.

Once the aws client is configured, generate a KMS customer master key and use that to generate
a local data key.

.. code-block:: bash

    # data_key=$(aws kms generate-data-key --key-id your-key-id --key-spec AES_256
                 --query 'CiphertextBlob' --output text)
    # echo 'aws_kms:'
    # echo '  data_key: !!binary "%s"\n' "$data_key" >> config/master

To apply the renderer on a file-by-file basis add the following line to the
top of any pillar with gpg data in it:

.. code-block:: yaml

    #!yaml|aws_kms

Now with your renderer configured, you can include your ciphers in your pillar
data like so:

.. code-block:: yaml

    #!yaml|aws_kms

    a-secret: gAAAAABaj5uzShPI3PEz6nL5Vhk2eEHxGXSZj8g71B84CZsVjAAtDFY1mfjNRl-1Su9YVvkUzNjI4lHCJJfXqdcTvwczBYtKy0Pa7Ri02s10Wn1tF0tbRwk=
"""

import base64
import logging

import salt.utils.stringio
from salt.exceptions import SaltConfigurationError

try:
    import botocore.exceptions
    import boto3

    logging.getLogger("boto3").setLevel(logging.CRITICAL)
except ImportError:
    pass

try:
    import cryptography.fernet as fernet

    HAS_FERNET = True
except ImportError:
    HAS_FERNET = False


def __virtual__():
    """
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    """
    return HAS_FERNET and salt.utils.versions.check_boto_reqs()


log = logging.getLogger(__name__)


def _cfg(key, default=None):
    """
    Return the requested value from the aws_kms key in salt configuration.

    If it's not set, return the default.
    """
    root_cfg = __salt__.get("config.get", __opts__.get)
    kms_cfg = root_cfg("aws_kms", {})
    return kms_cfg.get(key, default)


def _cfg_data_key():
    """
    Return the encrypted KMS data key from configuration.

    Raises SaltConfigurationError if not set.
    """
    data_key = _cfg("data_key", "")
    if data_key:
        return data_key
    raise SaltConfigurationError("aws_kms:data_key is not set")


def _session():
    """
    Return the boto3 session to use for the KMS client.

    If aws_kms:profile_name is set in the salt configuration, use that profile.
    Otherwise, fall back on the default aws profile.

    We use the boto3 profile system to avoid having to duplicate
    individual boto3 configuration settings in salt configuration.
    """
    profile_name = _cfg("profile_name")
    if profile_name:
        log.info('Using the "%s" aws profile.', profile_name)
    else:
        log.info(
            "aws_kms:profile_name is not set in salt. Falling back on default profile."
        )
    try:
        return boto3.Session(profile_name=profile_name)
    except botocore.exceptions.ProfileNotFound as orig_exc:
        raise SaltConfigurationError(
            'Boto3 could not find the "{}" profile configured in Salt.'.format(
                profile_name or "default"
            )
        ) from orig_exc
    except botocore.exceptions.NoRegionError as orig_exc:
        raise SaltConfigurationError(
            "Boto3 was unable to determine the AWS "
            "endpoint region using the {} profile.".format(profile_name or "default")
        ) from orig_exc


def _kms():
    """
    Return the boto3 client for the KMS API.
    """
    session = _session()
    return session.client("kms")


def _api_decrypt():
    """
    Return the response dictionary from the KMS decrypt API call.
    """
    kms = _kms()
    data_key = _cfg_data_key()
    try:
        return kms.decrypt(CiphertextBlob=data_key)
    except botocore.exceptions.ClientError as orig_exc:
        error_code = orig_exc.response.get("Error", {}).get("Code", "")
        if error_code != "InvalidCiphertextException":
            raise
        raise SaltConfigurationError(
            "aws_kms:data_key is not a valid KMS data key"
        ) from orig_exc


def _plaintext_data_key():
    """
    Return the configured KMS data key decrypted and encoded in urlsafe base64.

    Cache the result to minimize API calls to AWS.
    """
    response = getattr(_plaintext_data_key, "response", None)
    cache_hit = response is not None
    if not cache_hit:
        response = _api_decrypt()
        setattr(_plaintext_data_key, "response", response)
    key_id = response["KeyId"]
    plaintext = response["Plaintext"]
    if hasattr(plaintext, "encode"):
        plaintext = plaintext.encode(__salt_system_encoding__)
    log.debug("Using key %s from %s", key_id, "cache" if cache_hit else "api call")
    return plaintext


def _base64_plaintext_data_key():
    """
    Return the configured KMS data key decrypted and encoded in urlsafe base64.
    """
    plaintext_data_key = _plaintext_data_key()
    return base64.urlsafe_b64encode(plaintext_data_key)


def _decrypt_ciphertext(cipher, translate_newlines=False):
    """
    Given a blob of ciphertext as a bytestring, try to decrypt
    the cipher and return the decrypted string. If the cipher cannot be
    decrypted, log the error, and return the ciphertext back out.
    """
    if translate_newlines:
        cipher = cipher.replace(r"\n", "\n")
    if hasattr(cipher, "encode"):
        cipher = cipher.encode(__salt_system_encoding__)

    # Decryption
    data_key = _base64_plaintext_data_key()
    plain_text = fernet.Fernet(data_key).decrypt(cipher)
    if hasattr(plain_text, "decode"):
        plain_text = plain_text.decode(__salt_system_encoding__)
    return str(plain_text)


def _decrypt_object(obj, translate_newlines=False):
    """
    Recursively try to decrypt any object.
    Recur on objects that are not strings.
    Decrypt strings that are valid Fernet tokens.
    Return the rest unchanged.
    """
    if salt.utils.stringio.is_readable(obj):
        return _decrypt_object(obj.getvalue(), translate_newlines)
    if isinstance(obj, (str, bytes)):
        try:
            return _decrypt_ciphertext(obj, translate_newlines=translate_newlines)
        except (fernet.InvalidToken, TypeError):
            return obj

    elif isinstance(obj, dict):
        for key, value in obj.items():
            obj[key] = _decrypt_object(value, translate_newlines=translate_newlines)
        return obj
    elif isinstance(obj, list):
        for key, value in enumerate(obj):
            obj[key] = _decrypt_object(value, translate_newlines=translate_newlines)
        return obj
    else:
        return obj


def render(data, saltenv="base", sls="", argline="", **kwargs):
    """
    Decrypt the data to be rendered that was encrypted using AWS KMS envelope encryption.
    """
    translate_newlines = kwargs.get("translate_newlines", False)
    return _decrypt_object(data, translate_newlines=translate_newlines)
