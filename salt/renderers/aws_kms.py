# -*- coding: utf-8 -*-
r'''
Renderer that will decrypt ciphers encrypted using `AWS KMS Envelope Encryption`_.

.. _`AWS KMS Envelope Encryption`: https://docs.aws.amazon.com/kms/latest/developerguide/workflow.html

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

To set things up, first generate a KMS key.
https://docs.aws.amazon.com/kms/latest/developerguide/create-keys.html

Then generate a local data key from that KMS key and store it in your master config:

.. code-block:: bash

    # data_key=$(aws kms generate-data-key --key-id your-key-id --key-spec AES_256 --query 'CiphertextBlob' --output text)
    # printf 'aws_kms_data_key: !!binary "%s"\n' "$data_key" >> config/master

To apply the renderer on a file-by-file basis add the following line to the
top of any pillar with gpg data in it:

.. code-block:: yaml

    #!yaml|aws_kms

Now with your renderer configured, you can include your ciphers in your pillar
data like so:

.. code-block:: yaml

    #!yaml|aws_kms

    a-secret: gAAAAABaj5uzShPI3PEz6nL5Vhk2eEHxGXSZj8g71B84CZsVjAAtDFY1mfjNRl-1Su9YVvkUzNjI4lHCJJfXqdcTvwczBYtKy0Pa7Ri02s10Wn1tF0tbRwk=

'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import base64

# Import salt libs
import salt.utils.stringio
import salt.utils.decorators as decorators

# Import 3rd-party libs
from salt.ext import six

try:
    import botocore.exceptions
    import boto3
    logging.getLogger('boto3').setLevel(logging.CRITICAL)
except ImportError:
    pass

try:
    import cryptography.fernet as fernet
    HAS_FERNET = True
except ImportError:
    HAS_FERNET = False


def __virtual__():
    '''
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    '''
    return HAS_FERNET and salt.utils.versions.check_boto_reqs()

log = logging.getLogger(__name__)


@decorators.memoize
def _get_data_key():
    '''
    Return the configured KMS data key decrypted and encoded in urlsafe base64.

    Memoize the result to minimize API calls to AWS.
    '''
    get_config = __salt__['config.get'] if 'config.get' in __salt__ else __opts__.get
    data_key = get_config('aws_kms_data_key', '')
    if not data_key:
        raise salt.exceptions.SaltConfigurationError('aws_kms_data_key is not set')
    client = boto3.client('kms')
    try:
        response = client.decrypt(CiphertextBlob=data_key)
    except botocore.exceptions.ClientError as orig_exc:
        error_code = orig_exc.response.get("Error", {}).get("Code", "")
        if error_code == 'InvalidCiphertextException':
            err_msg = 'aws_kms_data_key is not a valid KMS data key'
            config_error = salt.exceptions.SaltConfigurationError(err_msg)
            six.raise_from(config_error, orig_exc)
        raise

    log.debug('Using key %s', response['KeyId'])
    clear_data_key = response['Plaintext']
    return base64.urlsafe_b64encode(clear_data_key)


def _decrypt_ciphertext(cipher, translate_newlines=False):
    '''
    Given a blob of ciphertext as a bytestring, try to decrypt
    the cipher and return the decrypted string. If the cipher cannot be
    decrypted, log the error, and return the ciphertext back out.
    '''
    if translate_newlines:
        cipher = cipher.replace(r'\n', '\n')
    if six.PY3:
        cipher = cipher.encode(__salt_system_encoding__)

    # Decryption
    data_key = _get_data_key()
    plain_text = fernet.Fernet(data_key).decrypt(cipher)
    if six.PY3 and isinstance(plain_text, bytes):
        plain_text = plain_text.decode(__salt_system_encoding__)
    return six.text_type(plain_text)


def _decrypt_object(obj, translate_newlines=False):
    '''
    Recursively try to decrypt any object.
    Recur on objects that are not strings.
    Decrypt strings that are valid Fernet tokens.
    Return the rest unchanged.
    '''
    if salt.utils.stringio.is_readable(obj):
        return _decrypt_object(obj.getvalue(), translate_newlines)
    if isinstance(obj, six.string_types):
        try:
            return _decrypt_ciphertext(obj,
                                       translate_newlines=translate_newlines)
        except (fernet.InvalidToken, TypeError):
            return obj

    elif isinstance(obj, dict):
        for key, value in six.iteritems(obj):
            obj[key] = _decrypt_object(value,
                                       translate_newlines=translate_newlines)
        return obj
    elif isinstance(obj, list):
        for key, value in enumerate(obj):
            obj[key] = _decrypt_object(value,
                                       translate_newlines=translate_newlines)
        return obj
    else:
        return obj


def render(gpg_data, saltenv='base', sls='', argline='', **kwargs):  # pylint: disable=unused-argument
    '''
    Create a gpg object given a gpg_keydir, and then use it to try to decrypt
    the data to be rendered.
    '''
    translate_newlines = kwargs.get('translate_newlines', False)
    return _decrypt_object(gpg_data, translate_newlines=translate_newlines)
