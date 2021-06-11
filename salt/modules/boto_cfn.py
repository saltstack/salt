# -*- coding: utf-8 -*-
"""
Connection module for Amazon Cloud Formation

.. versionadded:: 2015.5.0

:configuration: This module accepts explicit AWS credentials but can also utilize
    IAM roles assigned to the instance through Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        cfn.keyid: GKTADJGHEIQSXMKKRBJ08H
        cfn.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        cfn.region: us-east-1

:depends: boto
"""
# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

import salt.utils.versions

# Import Salt libs
from salt.ext import six

log = logging.getLogger(__name__)

# Import third party libs
# pylint: disable=import-error
try:
    # pylint: disable=unused-import
    import boto
    import boto.cloudformation

    # pylint: enable=unused-import
    from boto.exception import BotoServerError

    logging.getLogger("boto").setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


def __virtual__():
    """
    Only load if boto libraries exist.
    """
    return salt.utils.versions.check_boto_reqs(check_boto3=False)


def __init__(opts):
    if HAS_BOTO:
        __utils__["boto.assign_funcs"](
            __name__, "cfn", module="cloudformation", pack=__salt__
        )


def exists(name, region=None, key=None, keyid=None, profile=None):
    """
    Check to see if a stack exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cfn.exists mystack region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        # Returns an object if stack exists else an exception
        exists = conn.describe_stacks(name)
        log.debug("Stack %s exists.", name)
        return True
    except BotoServerError as e:
        log.debug("boto_cfn.exists raised an exception", exc_info=True)
        return False


def describe(name, region=None, key=None, keyid=None, profile=None):
    """
    Describe a stack.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cfn.describe mystack region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        # Returns an object if stack exists else an exception
        r = conn.describe_stacks(name)
        if r:
            stack = r[0]
            log.debug("Found VPC: %s", stack.stack_id)
            keys = (
                "stack_id",
                "description",
                "stack_status",
                "stack_status_reason",
                "tags",
            )

            ret = dict([(k, getattr(stack, k)) for k in keys if hasattr(stack, k)])
            o = getattr(stack, "outputs")
            p = getattr(stack, "parameters")
            outputs = {}
            parameters = {}
            for i in o:
                outputs[i.key] = i.value
            ret["outputs"] = outputs
            for j in p:
                parameters[j.key] = j.value
            ret["parameters"] = parameters

            return {"stack": ret}

        log.debug("Stack %s exists.", name)
        return True
    except BotoServerError as e:
        log.warning("Could not describe stack %s.\n%s", name, e)
        return False


def create(
    name,
    template_body=None,
    template_url=None,
    parameters=None,
    notification_arns=None,
    disable_rollback=None,
    timeout_in_minutes=None,
    capabilities=None,
    tags=None,
    on_failure=None,
    stack_policy_body=None,
    stack_policy_url=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Create a CFN stack.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cfn.create mystack template_url='https://s3.amazonaws.com/bucket/template.cft' \
        region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        return conn.create_stack(
            name,
            template_body,
            template_url,
            parameters,
            notification_arns,
            disable_rollback,
            timeout_in_minutes,
            capabilities,
            tags,
            on_failure,
            stack_policy_body,
            stack_policy_url,
        )
    except BotoServerError as e:
        msg = "Failed to create stack {0}.\n{1}".format(name, e)
        log.error(msg)
        log.debug(e)
        return False


def update_stack(
    name,
    template_body=None,
    template_url=None,
    parameters=None,
    notification_arns=None,
    disable_rollback=False,
    timeout_in_minutes=None,
    capabilities=None,
    tags=None,
    use_previous_template=None,
    stack_policy_during_update_body=None,
    stack_policy_during_update_url=None,
    stack_policy_body=None,
    stack_policy_url=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Update a CFN stack.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cfn.update_stack mystack template_url='https://s3.amazonaws.com/bucket/template.cft' \
        region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        update = conn.update_stack(
            name,
            template_body,
            template_url,
            parameters,
            notification_arns,
            disable_rollback,
            timeout_in_minutes,
            capabilities,
            tags,
            use_previous_template,
            stack_policy_during_update_body,
            stack_policy_during_update_url,
            stack_policy_body,
            stack_policy_url,
        )
        log.debug("Updated result is : %s.", update)
        return update
    except BotoServerError as e:
        msg = "Failed to update stack {0}.".format(name)
        log.debug(e)
        log.error(msg)
        return six.text_type(e)


def delete(name, region=None, key=None, keyid=None, profile=None):
    """
    Delete a CFN stack.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cfn.delete mystack region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        return conn.delete_stack(name)
    except BotoServerError as e:
        msg = "Failed to create stack {0}.".format(name)
        log.error(msg)
        log.debug(e)
        return six.text_type(e)


def get_template(name, region=None, key=None, keyid=None, profile=None):
    """
    Check to see if attributes are set on a CFN stack.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cfn.get_template mystack
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        template = conn.get_template(name)
        log.info("Retrieved template for stack %s", name)
        return template
    except BotoServerError as e:
        log.debug(e)
        msg = "Template {0} does not exist".format(name)
        log.error(msg)
        return six.text_type(e)


def validate_template(
    template_body=None,
    template_url=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Validate cloudformation template

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cfn.validate_template mystack-template
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        # Returns an object if json is validated and an exception if its not
        return conn.validate_template(template_body, template_url)
    except BotoServerError as e:
        log.debug(e)
        msg = "Error while trying to validate template {0}.".format(template_body)
        log.error(msg)
        return six.text_type(e)
