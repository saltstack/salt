"""
Connection module for Amazon Cloud Formation

.. versionadded:: 2015.8.0

:depends: boto
:configuration: This module accepts explicit AWS credentials but can also utilize
    IAM roles assigned to the instance through Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at
    http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    .. code-block:: yaml

        stack-present:
          boto_cfn.present:
            - name: mystack
            - template_body: salt://base/mytemplate.json
            - disable_rollback: true
            - region: eu-west-1
            - keyid: 'AKIAJHTMIQ2ASDFLASDF'
            - key: 'fdkjsafkljsASSADFalkfjasdf'

    .. code-block:: yaml

        stack-absent:
          boto_cfn.absent:
            - name: mystack
"""

import logging
import xml.etree.ElementTree as ET

import salt.utils.compat
import salt.utils.json

log = logging.getLogger(__name__)

__virtualname__ = "boto_cfn"


def __virtual__():
    """
    Only load if elementtree xml library and boto are available.
    """
    if "boto_cfn.exists" in __salt__:
        return True
    else:
        return (
            False,
            "Cannot load {} state: boto_cfn module unavailable".format(__virtualname__),
        )


def present(
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
    use_previous_template=None,
    stack_policy_during_update_body=None,
    stack_policy_during_update_url=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Ensure cloud formation stack is present.

    name (string) - Name of the stack.

    template_body (string) – Structure containing the template body. Can also be loaded from a file by using salt://.

    template_url (string) – Location of file containing the template body. The URL must point to a template located in
    an S3 bucket in the same region as the stack.

    parameters (list) – A list of key/value tuples that specify input parameters for the stack. A 3-tuple (key, value,
    bool) may be used to specify the UsePreviousValue option.

    notification_arns (list) – The Simple Notification Service (SNS) topic ARNs to publish stack related events.
    You can find your SNS topic ARNs using the `SNS_console`_ or your Command Line Interface (CLI).

    disable_rollback (bool) – Indicates whether or not to rollback on failure.

    timeout_in_minutes (integer) – The amount of time that can pass before the stack status becomes CREATE_FAILED; if
    DisableRollback is not set or is set to False, the stack will be rolled back.

    capabilities (list) – The list of capabilities you want to allow in the stack. Currently, the only valid capability
    is ‘CAPABILITY_IAM’.

    tags (dict) – A set of user-defined Tags to associate with this stack, represented by key/value pairs. Tags defined
    for the stack are propagated to EC2 resources that are created as part of the stack. A maximum number of 10 tags can
    be specified.

    on_failure (string) – Determines what action will be taken if stack creation fails. This must be one of:
    DO_NOTHING, ROLLBACK, or DELETE. You can specify either OnFailure or DisableRollback, but not both.

    stack_policy_body (string) – Structure containing the stack policy body. Can also be loaded from a file by using
    salt://.

    stack_policy_url (string) – Location of a file containing the stack policy. The URL must point to a policy
    (max size: 16KB) located in an S3 bucket in the same region as the stack.If you pass StackPolicyBody and
    StackPolicyURL, only StackPolicyBody is used.

    use_previous_template (boolean) – Used only when templates are not the same. Set to True to use the previous
    template instead of uploading a new one via TemplateBody or TemplateURL.

    stack_policy_during_update_body (string) – Used only when templates are not the same. Structure containing the
    temporary overriding stack policy body. If you pass StackPolicyDuringUpdateBody and StackPolicyDuringUpdateURL,
    only StackPolicyDuringUpdateBody is used. Can also be loaded from a file by using salt://.

    stack_policy_during_update_url (string) – Used only when templates are not the same. Location of a file containing
    the temporary overriding stack policy. The URL must point to a policy (max size: 16KB) located in an S3 bucket in
    the same region as the stack. If you pass StackPolicyDuringUpdateBody and StackPolicyDuringUpdateURL, only
    StackPolicyDuringUpdateBody is used.

    region (string) - Region to connect to.

    key (string) - Secret key to be used.

    keyid (string) - Access key to be used.

    profile (dict) - A dict with region, key and keyid, or a pillar key (string) that contains a dict with region, key
    and keyid.

    .. _`SNS_console`: https://console.aws.amazon.com/sns

    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    template_body = _get_template(template_body, name)
    stack_policy_body = _get_template(stack_policy_body, name)
    stack_policy_during_update_body = _get_template(
        stack_policy_during_update_body, name
    )

    for i in [template_body, stack_policy_body, stack_policy_during_update_body]:
        if isinstance(i, dict):
            return i

    _valid = _validate(template_body, template_url, region, key, keyid, profile)
    log.debug("Validate is : %s.", _valid)
    if _valid is not True:
        code, message = _valid
        ret["result"] = False
        ret["comment"] = "Template could not be validated.\n{} \n{}".format(
            code, message
        )
        return ret
    log.debug("Template %s is valid.", name)
    if __salt__["boto_cfn.exists"](name, region, key, keyid, profile):
        template = __salt__["boto_cfn.get_template"](name, region, key, keyid, profile)
        template = template["GetTemplateResponse"]["GetTemplateResult"][
            "TemplateBody"
        ].encode("ascii", "ignore")
        template = salt.utils.json.loads(template)
        _template_body = salt.utils.json.loads(template_body)
        compare = salt.utils.compat.cmp(template, _template_body)
        if compare != 0:
            log.debug("Templates are not the same. Compare value is %s", compare)
            # At this point we should be able to run update safely since we already validated the template
            if __opts__["test"]:
                ret["comment"] = "Stack {} is set to be updated.".format(name)
                ret["result"] = None
                return ret
            updated = __salt__["boto_cfn.update_stack"](
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
                region,
                key,
                keyid,
                profile,
            )
            if isinstance(updated, str):
                code, message = _get_error(updated)
                log.debug("Update error is %s and message is %s", code, message)
                ret["result"] = False
                ret["comment"] = "Stack {} could not be updated.\n{} \n{}.".format(
                    name, code, message
                )
                return ret
            ret["comment"] = "Cloud formation template {} has been updated.".format(
                name
            )
            ret["changes"]["new"] = updated
            return ret
        ret["comment"] = "Stack {} exists.".format(name)
        ret["changes"] = {}
        return ret
    if __opts__["test"]:
        ret["comment"] = "Stack {} is set to be created.".format(name)
        ret["result"] = None
        return ret
    created = __salt__["boto_cfn.create"](
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
        region,
        key,
        keyid,
        profile,
    )
    if created:
        ret["comment"] = "Stack {} was created.".format(name)
        ret["changes"]["new"] = created
        return ret
    ret["result"] = False
    return ret


def absent(name, region=None, key=None, keyid=None, profile=None):
    """
    Ensure cloud formation stack is absent.

    name (string) – The name of the stack to delete.

    region (string) - Region to connect to.

    key (string) - Secret key to be used.

    keyid (string) - Access key to be used.

    profile (dict) - A dict with region, key and keyid, or a pillar key (string) that contains a dict with region, key
    and keyid.
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    if not __salt__["boto_cfn.exists"](name, region, key, keyid, profile):
        ret["comment"] = "Stack {} does not exist.".format(name)
        ret["changes"] = {}
        return ret
    if __opts__["test"]:
        ret["comment"] = "Stack {} is set to be deleted.".format(name)
        ret["result"] = None
        return ret
    deleted = __salt__["boto_cfn.delete"](name, region, key, keyid, profile)
    if isinstance(deleted, str):
        code, message = _get_error(deleted)
        ret["comment"] = "Stack {} could not be deleted.\n{}\n{}".format(
            name, code, message
        )
        ret["result"] = False
        ret["changes"] = {}
        return ret
    if deleted:
        ret["comment"] = "Stack {} was deleted.".format(name)
        ret["changes"]["deleted"] = name
        return ret


def _get_template(template, name):
    # Checks if template is a file in salt defined by salt://.
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    if template is not None and "salt://" in template:
        try:
            return __salt__["cp.get_file_str"](template)
        except OSError as e:
            log.debug(e)
            ret["comment"] = "File {} not found.".format(template)
            ret["result"] = False
            return ret
    return template


def _validate(
    template_body=None,
    template_url=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    # Validates template. returns true if template syntax is correct.
    validate = __salt__["boto_cfn.validate_template"](
        template_body, template_url, region, key, keyid, profile
    )
    log.debug("Validate result is %s.", validate)
    if isinstance(validate, str):
        code, message = _get_error(validate)
        log.debug("Validate error is %s and message is %s.", code, message)
        return code, message
    return True


def _get_error(error):
    # Converts boto exception to string that can be used to output error.
    error = "\n".join(error.split("\n")[1:])
    error = ET.fromstring(error)
    code = error[0][1].text
    message = error[0][2].text
    return code, message
