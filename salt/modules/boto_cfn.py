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


import logging

import salt.utils.versions
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

# pylint: disable=import-error
try:
    # pylint: disable=unused-import
    import boto3

    logging.getLogger("boto3").setLevel(logging.CRITICAL)
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def __virtual__():
    """
    Only load if boto libraries exist.
    """
    return salt.utils.versions.check_boto_reqs(check_boto=False)


def __init__(opts):
    if HAS_BOTO3:
        __utils__["boto3.assign_funcs"](__name__, "cfn", module="cloudformation")


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
        exists = conn.describe_stacks(StackName=name)
        log.debug("Stack %s exists.", name)
        return True
    except conn.exceptions.ClientError as e:
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
        resp = conn.describe_stacks(StackName=name)
        if resp["Stacks"]:
            stack = resp["Stacks"][0]
            log.debug("Found VPC: %s", stack["StackId"])
            return {"stack": stack}
    except conn.exceptions.ClientError as e:
        log.warning("Could not describe stack %s.\n%s", name, e)
        return None


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
    if all((template_body, template_url)):
        raise SaltInvocationError(
            "Only one of the following may be specified: template_body, template_url"
        )

    if all((stack_policy_body, stack_policy_url)):
        raise SaltInvocationError(
            "Only one of the following may be specified: stack_policy_body, stack_policy_url"
        )

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        kwargs = {"StackName": name}
        if template_body is not None:
            kwargs.update({"TemplateBody": template_body})
        if template_url is not None:
            kwargs.update({"TemplateURL": template_url})
        if parameters is not None:
            kwargs.update({"Parameters": parameters})
        if notification_arns is not None:
            kwargs.update({"NotificationARNs": notification_arns})
        if disable_rollback is not None:
            kwargs.update({"DisableRollback": disable_rollback})
        if timeout_in_minutes is not None:
            kwargs.update({"TimeoutInMinutes": timeout_in_minutes})
        if capabilities is not None:
            kwargs.update({"Capabilities": capabilities})
        if tags is not None:
            kwargs.update({"Tags": tags})
            kwargs.update({"StackPolicyBody": stack_policy_body})
        if stack_policy_url is not None:
            kwargs.update({"StackPolicyURL": stack_policy_url})
        return conn.create_stack(**kwargs)
    except conn.exceptions.ClientError as e:
        msg = "Failed to create stack {}.\n{}".format(name, e)
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
        kwargs = {"StackName": name}
        if template_body is not None:
            kwargs.update({"TemplateBody": template_body})
        if template_url is not None:
            kwargs.update({"TemplateURL": template_url})
        if parameters is not None:
            kwargs.update({"Parameters": parameters})
        if notification_arns is not None:
            kwargs.update({"NotificationARNs": notification_arns})
        if disable_rollback is not None:
            kwargs.update({"DisableRollback": disable_rollback})
        if timeout_in_minutes is not None:
            kwargs.update({"TimeoutInMinutes": timeout_in_minutes})
        if capabilities is not None:
            kwargs.update({"Capabilities": capabilities})
        if tags is not None:
            kwargs.update({"Tags": tags})
        if use_previous_template is not None:
            kwargs.update({"UsePreviousTemplate": use_previous_template})
        if stack_policy_during_update_body is not None:
            kwargs.update(
                {"StackPolicyDuringUpdateBody": stack_policy_during_update_body}
            )
        if stack_policy_during_update_url is not None:
            kwargs.update(
                {"StackPolicyDuringUpdateURL": stack_policy_during_update_url}
            )
        if stack_policy_body is not None:
            kwargs.update({"StackPolicyBody": stack_policy_body})
        if stack_policy_url is not None:
            kwargs.update({"StackPolicyURL": stack_policy_url})
        update = conn.update_stack(**kwargs)
        log.debug("Updated result is : %s.", update)
        return update
    except conn.exceptions.ClientError as e:
        msg = "Failed to update stack {}.".format(name)
        log.debug(e)
        log.error(msg)
        return str(e)


def delete(name, region=None, key=None, keyid=None, profile=None):
    """
    Delete a CFN stack.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cfn.delete mystack region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        return conn.delete_stack(StackName=name)
    except conn.exceptions.ClientError as e:
        msg = "Failed to create stack {}.".format(name)
        log.error(msg)
        log.debug(e)
        return str(e)


def get_template(name, region=None, key=None, keyid=None, profile=None):
    """
    Check to see if attributes are set on a CFN stack.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cfn.get_template mystack
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        template = conn.get_template(StackName=name)
        log.info("Retrieved template for stack %s", name)
        return template
    except conn.exceptions.ClientError as e:
        log.debug(e)
        msg = "Template {} does not exist".format(name)
        log.error(msg)
        return str(e)


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
        return conn.validate_template(
            TemplateBody=template_body, TemplateURL=template_url
        )
    except conn.exceptions.ClientError as e:
        log.debug(e)
        msg = "Error while trying to validate template {}.".format(template_body)
        log.error(msg)
        return str(e)
