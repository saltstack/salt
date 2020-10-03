"""
Connection module for Amazon KMS

.. versionadded:: 2015.8.0

:configuration: This module accepts explicit kms credentials but can also utilize
    IAM roles assigned to the instance through Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at::

       http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file::

        kms.keyid: GKTADJGHEIQSXMKKRBJ08H
        kms.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration::

        kms.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto
"""
# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602


import logging

import salt.serializers.json
import salt.utils.compat
import salt.utils.odict as odict
import salt.utils.versions

log = logging.getLogger(__name__)

try:
    # pylint: disable=unused-import
    import boto
    import boto.kms

    # pylint: enable=unused-import
    logging.getLogger("boto").setLevel(logging.CRITICAL)
    HAS_BOTO = True
except (ImportError, AttributeError):
    HAS_BOTO = False


def __virtual__():
    """
    Only load if boto libraries exist.
    """
    return salt.utils.versions.check_boto_reqs(boto_ver="2.38.0", check_boto3=False)


def __init__(opts):
    if HAS_BOTO:
        __utils__["boto.assign_funcs"](__name__, "kms", pack=__salt__)


def create_alias(
    alias_name, target_key_id, region=None, key=None, keyid=None, profile=None
):
    """
    Create a display name for a key.

    CLI example::

        salt myminion boto_kms.create_alias 'alias/mykey' key_id
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        conn.create_alias(alias_name, target_key_id)
        r["result"] = True
    except boto.exception.BotoServerError as e:
        r["result"] = False
        r["error"] = __utils__["boto.get_error"](e)
    return r


def create_grant(
    key_id,
    grantee_principal,
    retiring_principal=None,
    operations=None,
    constraints=None,
    grant_tokens=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Adds a grant to a key to specify who can access the key and under what
    conditions.

    CLI example::

        salt myminion boto_kms.create_grant 'alias/mykey' 'arn:aws:iam::1111111:/role/myrole' operations='["Encrypt","Decrypt"]'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if key_id.startswith("alias/"):
        key_id = _get_key_id(key_id)
    r = {}
    try:
        r["grant"] = conn.create_grant(
            key_id,
            grantee_principal,
            retiring_principal=retiring_principal,
            operations=operations,
            constraints=constraints,
            grant_tokens=grant_tokens,
        )
    except boto.exception.BotoServerError as e:
        r["error"] = __utils__["boto.get_error"](e)
    return r


def create_key(
    policy=None,
    description=None,
    key_usage=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Creates a master key.

    CLI example::

        salt myminion boto_kms.create_key '{"Statement":...}' "My master key"
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    _policy = salt.serializers.json.serialize(policy)
    try:
        key_metadata = conn.create_key(
            _policy, description=description, key_usage=key_usage
        )
        r["key_metadata"] = key_metadata["KeyMetadata"]
    except boto.exception.BotoServerError as e:
        r["error"] = __utils__["boto.get_error"](e)
    return r


def decrypt(
    ciphertext_blob,
    encryption_context=None,
    grant_tokens=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Decrypt ciphertext.

    CLI example::

        salt myminion boto_kms.decrypt encrypted_ciphertext
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        plaintext = conn.decrypt(
            ciphertext_blob,
            encryption_context=encryption_context,
            grant_tokens=grant_tokens,
        )
        r["plaintext"] = plaintext["Plaintext"]
    except boto.exception.BotoServerError as e:
        r["error"] = __utils__["boto.get_error"](e)
    return r


def key_exists(key_id, region=None, key=None, keyid=None, profile=None):
    """
    Check for the existence of a key.

    CLI example::

        salt myminion boto_kms.key_exists 'alias/mykey'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        key = conn.describe_key(key_id)
        # TODO: add to context cache
        r["result"] = True
    except boto.exception.BotoServerError as e:
        if isinstance(e, boto.kms.exceptions.NotFoundException):
            r["result"] = False
            return r
        r["error"] = __utils__["boto.get_error"](e)
    return r


def _get_key_id(alias, region=None, key=None, keyid=None, profile=None):
    """
    From an alias, get a key_id.
    """
    key_metadata = describe_key(alias, region, key, keyid, profile)["key_metadata"]
    return key_metadata["KeyId"]


def describe_key(key_id, region=None, key=None, keyid=None, profile=None):
    """
    Get detailed information about a key.

    CLI example::

        salt myminion boto_kms.describe_key 'alias/mykey'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        key = conn.describe_key(key_id)
        # TODO: add to context cache
        r["key_metadata"] = key["KeyMetadata"]
    except boto.exception.BotoServerError as e:
        r["error"] = __utils__["boto.get_error"](e)
    return r


def disable_key(key_id, region=None, key=None, keyid=None, profile=None):
    """
    Mark key as disabled.

    CLI example::

        salt myminion boto_kms.disable_key 'alias/mykey'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        key = conn.disable_key(key_id)
        r["result"] = True
    except boto.exception.BotoServerError as e:
        r["result"] = False
        r["error"] = __utils__["boto.get_error"](e)
    return r


def disable_key_rotation(key_id, region=None, key=None, keyid=None, profile=None):
    """
    Disable key rotation for specified key.

    CLI example::

        salt myminion boto_kms.disable_key_rotation 'alias/mykey'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        key = conn.disable_key_rotation(key_id)
        r["result"] = True
    except boto.exception.BotoServerError as e:
        r["result"] = False
        r["error"] = __utils__["boto.get_error"](e)
    return r


def enable_key(key_id, region=None, key=None, keyid=None, profile=None):
    """
    Mark key as enabled.

    CLI example::

        salt myminion boto_kms.enable_key 'alias/mykey'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        key = conn.enable_key(key_id)
        r["result"] = True
    except boto.exception.BotoServerError as e:
        r["result"] = False
        r["error"] = __utils__["boto.get_error"](e)
    return r


def enable_key_rotation(key_id, region=None, key=None, keyid=None, profile=None):
    """
    Disable key rotation for specified key.

    CLI example::

        salt myminion boto_kms.enable_key_rotation 'alias/mykey'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        key = conn.enable_key_rotation(key_id)
        r["result"] = True
    except boto.exception.BotoServerError as e:
        r["result"] = False
        r["error"] = __utils__["boto.get_error"](e)
    return r


def encrypt(
    key_id,
    plaintext,
    encryption_context=None,
    grant_tokens=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Encrypt plaintext into cipher text using specified key.

    CLI example::

        salt myminion boto_kms.encrypt 'alias/mykey' 'myplaindata' '{"aws:username":"myuser"}'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        ciphertext = conn.encrypt(
            key_id,
            plaintext,
            encryption_context=encryption_context,
            grant_tokens=grant_tokens,
        )
        r["ciphertext"] = ciphertext["CiphertextBlob"]
    except boto.exception.BotoServerError as e:
        r["error"] = __utils__["boto.get_error"](e)
    return r


def generate_data_key(
    key_id,
    encryption_context=None,
    number_of_bytes=None,
    key_spec=None,
    grant_tokens=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Generate a secure data key.

    CLI example::

        salt myminion boto_kms.generate_data_key 'alias/mykey' number_of_bytes=1024 key_spec=AES_128
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        data_key = conn.generate_data_key(
            key_id,
            encryption_context=encryption_context,
            number_of_bytes=number_of_bytes,
            key_spec=key_spec,
            grant_tokens=grant_tokens,
        )
        r["data_key"] = data_key
    except boto.exception.BotoServerError as e:
        r["error"] = __utils__["boto.get_error"](e)
    return r


def generate_data_key_without_plaintext(
    key_id,
    encryption_context=None,
    number_of_bytes=None,
    key_spec=None,
    grant_tokens=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Generate a secure data key without a plaintext copy of the key.

    CLI example::

        salt myminion boto_kms.generate_data_key_without_plaintext 'alias/mykey' number_of_bytes=1024 key_spec=AES_128
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        data_key = conn.generate_data_key_without_plaintext(
            key_id,
            encryption_context=encryption_context,
            number_of_bytes=number_of_bytes,
            key_spec=key_spec,
            grant_tokens=grant_tokens,
        )
        r["data_key"] = data_key
    except boto.exception.BotoServerError as e:
        r["error"] = __utils__["boto.get_error"](e)
    return r


def generate_random(
    number_of_bytes=None, region=None, key=None, keyid=None, profile=None
):
    """
    Generate a random string.

    CLI example::

        salt myminion boto_kms.generate_random number_of_bytes=1024
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        random = conn.generate_random(number_of_bytes)
        r["random"] = random["Plaintext"]
    except boto.exception.BotoServerError as e:
        r["error"] = __utils__["boto.get_error"](e)
    return r


def get_key_policy(
    key_id, policy_name, region=None, key=None, keyid=None, profile=None
):
    """
    Get the policy for the specified key.

    CLI example::

        salt myminion boto_kms.get_key_policy 'alias/mykey' mypolicy
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        key_policy = conn.get_key_policy(key_id, policy_name)
        r["key_policy"] = salt.serializers.json.deserialize(
            key_policy["Policy"], object_pairs_hook=odict.OrderedDict
        )
    except boto.exception.BotoServerError as e:
        r["error"] = __utils__["boto.get_error"](e)
    return r


def get_key_rotation_status(key_id, region=None, key=None, keyid=None, profile=None):
    """
    Get status of whether or not key rotation is enabled for a key.

    CLI example::

        salt myminion boto_kms.get_key_rotation_status 'alias/mykey'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        key_rotation_status = conn.get_key_rotation_status(key_id)
        r["result"] = key_rotation_status["KeyRotationEnabled"]
    except boto.exception.BotoServerError as e:
        r["error"] = __utils__["boto.get_error"](e)
    return r


def list_grants(
    key_id, limit=None, marker=None, region=None, key=None, keyid=None, profile=None
):
    """
    List grants for the specified key.

    CLI example::

        salt myminion boto_kms.list_grants 'alias/mykey'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if key_id.startswith("alias/"):
        key_id = _get_key_id(key_id)
    r = {}
    try:
        _grants = []
        next_marker = None
        while True:
            grants = conn.list_grants(key_id, limit=limit, marker=next_marker)
            for grant in grants["Grants"]:
                _grants.append(grant)
            if "NextMarker" in grants:
                next_marker = grants["NextMarker"]
            else:
                break
        r["grants"] = _grants
    except boto.exception.BotoServerError as e:
        r["error"] = __utils__["boto.get_error"](e)
    return r


def list_key_policies(
    key_id, limit=None, marker=None, region=None, key=None, keyid=None, profile=None
):
    """
    List key_policies for the specified key.

    CLI example::

        salt myminion boto_kms.list_key_policies 'alias/mykey'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if key_id.startswith("alias/"):
        key_id = _get_key_id(key_id)
    r = {}
    try:
        key_policies = conn.list_key_policies(key_id, limit=limit, marker=marker)
        # TODO: handle limit, marker and truncation automatically.
        r["key_policies"] = key_policies["PolicyNames"]
    except boto.exception.BotoServerError as e:
        r["error"] = __utils__["boto.get_error"](e)
    return r


def put_key_policy(
    key_id, policy_name, policy, region=None, key=None, keyid=None, profile=None
):
    """
    Attach a key policy to the specified key.

    CLI example::

        salt myminion boto_kms.put_key_policy 'alias/mykey' default '{"Statement":...}'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        conn.put_key_policy(
            key_id, policy_name, salt.serializers.json.serialize(policy)
        )
        r["result"] = True
    except boto.exception.BotoServerError as e:
        r["result"] = False
        r["error"] = __utils__["boto.get_error"](e)
    return r


def re_encrypt(
    ciphertext_blob,
    destination_key_id,
    source_encryption_context=None,
    destination_encryption_context=None,
    grant_tokens=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Reencrypt encrypted data with a new master key.

    CLI example::

        salt myminion boto_kms.re_encrypt 'encrypted_data' 'alias/mynewkey' default '{"Statement":...}'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        ciphertext = conn.re_encrypt(
            ciphertext_blob,
            destination_key_id,
            source_encryption_context,
            destination_encryption_context,
            grant_tokens,
        )
        r["ciphertext"] = ciphertext
    except boto.exception.BotoServerError as e:
        r["error"] = __utils__["boto.get_error"](e)
    return r


def revoke_grant(key_id, grant_id, region=None, key=None, keyid=None, profile=None):
    """
    Revoke a grant from a key.

    CLI example::

        salt myminion boto_kms.revoke_grant 'alias/mykey' 8u89hf-j09j...
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if key_id.startswith("alias/"):
        key_id = _get_key_id(key_id)
    r = {}
    try:
        conn.revoke_grant(key_id, grant_id)
        r["result"] = True
    except boto.exception.BotoServerError as e:
        r["result"] = False
        r["error"] = __utils__["boto.get_error"](e)
    return r


def update_key_description(
    key_id, description, region=None, key=None, keyid=None, profile=None
):
    """
    Update a key's description.

    CLI example::

        salt myminion boto_kms.update_key_description 'alias/mykey' 'My key'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    r = {}
    try:
        conn.update_key_description(key_id, description)
        r["result"] = True
    except boto.exception.BotoServerError as e:
        r["result"] = False
        r["error"] = __utils__["boto.get_error"](e)
    return r
