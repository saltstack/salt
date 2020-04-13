# -*- coding: utf-8 -*-
"""
Connection module for Amazon SSM

:configuration: This module uses IAM roles assigned to the instance through
    Instance Profiles. Dynamic credentials are then automatically obtained
    from AWS API and no further configuration is necessary. More Information
    available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

:depends: boto3
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

import salt.utils.json as json

# Import Salt libs
import salt.utils.versions

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if boto libraries exist.
    """
    has_boto_reqs = salt.utils.versions.check_boto_reqs()
    if has_boto_reqs is True:
        __utils__["boto3.assign_funcs"](__name__, "ssm")
    return has_boto_reqs


def get_parameter(
    name,
    withdecryption=False,
    resp_json=False,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Retrives a parameter from SSM Parameter Store

    .. versionadded:: 3000

    .. code-block:: text

        salt-call boto_ssm.get_parameter test-param withdescription=True
    """
    conn = __utils__["boto3.get_connection"](
        "ssm", region=region, key=key, keyid=keyid, profile=profile
    )
    try:
        resp = conn.get_parameter(Name=name, WithDecryption=withdecryption)
    except conn.exceptions.ParameterNotFound:
        log.warning("get_parameter: Unable to locate name: %s", name)
        return False

    if resp_json:
        return json.loads(resp["Parameter"]["Value"])
    else:
        return resp["Parameter"]["Value"]


def put_parameter(
    Name,
    Value,
    Description=None,
    Type="String",
    KeyId=None,
    Overwrite=False,
    AllowedPattern=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Sets a parameter in the SSM parameter store

    .. versionadded:: 3000

    .. code-block:: text

        salt-call boto_ssm.put_parameter test-param test_value Type=SecureString KeyId=alias/aws/ssm Description='test encrypted key'
    """
    conn = __utils__["boto3.get_connection"](
        "ssm", region=region, key=key, keyid=keyid, profile=profile
    )
    if Type not in ("String", "StringList", "SecureString"):
        raise AssertionError("Type needs to be String|StringList|SecureString")
    if Type == "SecureString" and not KeyId:
        raise AssertionError("Require KeyId with SecureString")

    boto_args = {}
    if Description:
        boto_args["Description"] = Description
    if KeyId:
        boto_args["KeyId"] = KeyId
    if AllowedPattern:
        boto_args["AllowedPattern"] = AllowedPattern

    try:
        resp = conn.put_parameter(
            Name=Name, Value=Value, Type=Type, Overwrite=Overwrite, **boto_args
        )
    except conn.exceptions.ParameterAlreadyExists:
        log.warning(
            "The parameter already exists."
            " To overwrite this value, set the Overwrite option in the request to True"
        )
        return False
    return resp["Version"]


def delete_parameter(Name, region=None, key=None, keyid=None, profile=None):
    """
    Removes a parameter from the SSM parameter store

    .. versionadded:: 3000

    .. code-block:: text
        salt-call boto_ssm.delete_parameter test-param
    """
    conn = __utils__["boto3.get_connection"](
        "ssm", region=region, key=key, keyid=keyid, profile=profile
    )
    try:
        resp = conn.delete_parameter(Name=Name)
    except conn.exceptions.ParameterNotFound:
        log.warning("delete_parameter: Unable to locate name: %s", Name)
        return False
    if resp["ResponseMetadata"]["HTTPStatusCode"] == 200:
        return True
    else:
        return False
