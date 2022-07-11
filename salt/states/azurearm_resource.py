"""
Azure (ARM) Resource State Module

.. versionadded:: 2019.2.0

.. warning::

    This cloud provider will be removed from Salt in version 3007 in favor of
    the `saltext.azurerm Salt Extension
    <https://github.com/salt-extensions/saltext-azurerm>`_

:maintainer: <devops@eitr.tech>
:maturity: new
:depends:
    * `azure <https://pypi.python.org/pypi/azure>`_ >= 2.0.0
    * `azure-common <https://pypi.python.org/pypi/azure-common>`_ >= 1.1.8
    * `azure-mgmt <https://pypi.python.org/pypi/azure-mgmt>`_ >= 1.0.0
    * `azure-mgmt-compute <https://pypi.python.org/pypi/azure-mgmt-compute>`_ >= 1.0.0
    * `azure-mgmt-network <https://pypi.python.org/pypi/azure-mgmt-network>`_ >= 1.7.1
    * `azure-mgmt-resource <https://pypi.python.org/pypi/azure-mgmt-resource>`_ >= 1.1.0
    * `azure-mgmt-storage <https://pypi.python.org/pypi/azure-mgmt-storage>`_ >= 1.0.0
    * `azure-mgmt-web <https://pypi.python.org/pypi/azure-mgmt-web>`_ >= 0.32.0
    * `azure-storage <https://pypi.python.org/pypi/azure-storage>`_ >= 0.34.3
    * `msrestazure <https://pypi.python.org/pypi/msrestazure>`_ >= 0.4.21
:platform: linux

:configuration: This module requires Azure Resource Manager credentials to be passed as a dictionary of
    keyword arguments to the ``connection_auth`` parameter in order to work properly. Since the authentication
    parameters are sensitive, it's recommended to pass them to the states via pillar.

    Required provider parameters:

    if using username and password:
      * ``subscription_id``
      * ``username``
      * ``password``

    if using a service principal:
      * ``subscription_id``
      * ``tenant``
      * ``client_id``
      * ``secret``

    Optional provider parameters:

    **cloud_environment**: Used to point the cloud driver to different API endpoints, such as Azure GovCloud. Possible values:
      * ``AZURE_PUBLIC_CLOUD`` (default)
      * ``AZURE_CHINA_CLOUD``
      * ``AZURE_US_GOV_CLOUD``
      * ``AZURE_GERMAN_CLOUD``

    Example Pillar for Azure Resource Manager authentication:

    .. code-block:: yaml

        azurearm:
            user_pass_auth:
                subscription_id: 3287abc8-f98a-c678-3bde-326766fd3617
                username: fletch
                password: 123pass
            mysubscription:
                subscription_id: 3287abc8-f98a-c678-3bde-326766fd3617
                tenant: ABCDEFAB-1234-ABCD-1234-ABCDEFABCDEF
                client_id: ABCDEFAB-1234-ABCD-1234-ABCDEFABCDEF
                secret: XXXXXXXXXXXXXXXXXXXXXXXX
                cloud_environment: AZURE_PUBLIC_CLOUD

    Example states using Azure Resource Manager authentication:

    .. code-block:: jinja

        {% set profile = salt['pillar.get']('azurearm:mysubscription') %}
        Ensure resource group exists:
            azurearm_resource.resource_group_present:
                - name: my_rg
                - location: westus
                - tags:
                    how_awesome: very
                    contact_name: Elmer Fudd Gantry
                - connection_auth: {{ profile }}

        Ensure resource group is absent:
            azurearm_resource.resource_group_absent:
                - name: other_rg
                - connection_auth: {{ profile }}

"""


import json
import logging
from functools import wraps

import salt.utils.azurearm
import salt.utils.files

__virtualname__ = "azurearm_resource"

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only make this state available if the azurearm_resource module is available.
    """
    if "azurearm_resource.resource_group_check_existence" in __salt__:
        return __virtualname__
    return (False, "azurearm_resource module could not be loaded")


def _deprecation_message(function):
    """
    Decorator wrapper to warn about azurearm deprecation
    """

    @wraps(function)
    def wrapped(*args, **kwargs):
        salt.utils.versions.warn_until(
            "Chlorine",
            "The 'azurearm' functionality in Salt has been deprecated and its "
            "functionality will be removed in version 3007 in favor of the "
            "saltext.azurerm Salt Extension. "
            "(https://github.com/salt-extensions/saltext-azurerm)",
            category=FutureWarning,
        )
        ret = function(*args, **salt.utils.args.clean_kwargs(**kwargs))
        return ret

    return wrapped


@_deprecation_message
def resource_group_present(
    name, location, managed_by=None, tags=None, connection_auth=None, **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Ensure a resource group exists.

    :param name:
        Name of the resource group.

    :param location:
        The Azure location in which to create the resource group. This value cannot be updated once
        the resource group is created.

    :param managed_by:
        The ID of the resource that manages this resource group. This value cannot be updated once
        the resource group is created.

    :param tags:
        A dictionary of strings can be passed as tag metadata to the resource group object.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure resource group exists:
            azurearm_resource.resource_group_present:
                - name: group1
                - location: eastus
                - tags:
                    contact_name: Elmer Fudd Gantry
                - connection_auth: {{ profile }}

    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    if not isinstance(connection_auth, dict):
        ret[
            "comment"
        ] = "Connection information must be specified via connection_auth dictionary!"
        return ret

    group = {}

    present = __salt__["azurearm_resource.resource_group_check_existence"](
        name, **connection_auth
    )

    if present:
        group = __salt__["azurearm_resource.resource_group_get"](
            name, **connection_auth
        )
        ret["changes"] = __utils__["dictdiffer.deep_diff"](
            group.get("tags", {}), tags or {}
        )

        if not ret["changes"]:
            ret["result"] = True
            ret["comment"] = "Resource group {} is already present.".format(name)
            return ret

        if __opts__["test"]:
            ret["comment"] = "Resource group {} tags would be updated.".format(name)
            ret["result"] = None
            ret["changes"] = {"old": group.get("tags", {}), "new": tags}
            return ret

    elif __opts__["test"]:
        ret["comment"] = "Resource group {} would be created.".format(name)
        ret["result"] = None
        ret["changes"] = {
            "old": {},
            "new": {
                "name": name,
                "location": location,
                "managed_by": managed_by,
                "tags": tags,
            },
        }
        return ret

    group_kwargs = kwargs.copy()
    group_kwargs.update(connection_auth)

    group = __salt__["azurearm_resource.resource_group_create_or_update"](
        name, location, managed_by=managed_by, tags=tags, **group_kwargs
    )
    present = __salt__["azurearm_resource.resource_group_check_existence"](
        name, **connection_auth
    )

    if present:
        ret["result"] = True
        ret["comment"] = "Resource group {} has been created.".format(name)
        ret["changes"] = {"old": {}, "new": group}
        return ret

    ret["comment"] = "Failed to create resource group {}! ({})".format(
        name, group.get("error")
    )
    return ret


@_deprecation_message
def resource_group_absent(name, connection_auth=None):
    """
    .. versionadded:: 2019.2.0

    Ensure a resource group does not exist in the current subscription.

    :param name:
        Name of the resource group.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    if not isinstance(connection_auth, dict):
        ret[
            "comment"
        ] = "Connection information must be specified via connection_auth dictionary!"
        return ret

    group = {}

    present = __salt__["azurearm_resource.resource_group_check_existence"](
        name, **connection_auth
    )

    if not present:
        ret["result"] = True
        ret["comment"] = "Resource group {} is already absent.".format(name)
        return ret

    elif __opts__["test"]:
        group = __salt__["azurearm_resource.resource_group_get"](
            name, **connection_auth
        )

        ret["comment"] = "Resource group {} would be deleted.".format(name)
        ret["result"] = None
        ret["changes"] = {
            "old": group,
            "new": {},
        }
        return ret

    group = __salt__["azurearm_resource.resource_group_get"](name, **connection_auth)
    deleted = __salt__["azurearm_resource.resource_group_delete"](
        name, **connection_auth
    )

    if deleted:
        present = False
    else:
        present = __salt__["azurearm_resource.resource_group_check_existence"](
            name, **connection_auth
        )

    if not present:
        ret["result"] = True
        ret["comment"] = "Resource group {} has been deleted.".format(name)
        ret["changes"] = {"old": group, "new": {}}
        return ret

    ret["comment"] = "Failed to delete resource group {}!".format(name)
    return ret


@_deprecation_message
def policy_definition_present(
    name,
    policy_rule=None,
    policy_type=None,
    mode=None,
    display_name=None,
    description=None,
    metadata=None,
    parameters=None,
    policy_rule_json=None,
    policy_rule_file=None,
    template="jinja",
    source_hash=None,
    source_hash_name=None,
    skip_verify=False,
    connection_auth=None,
    **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Ensure a security policy definition exists.

    :param name:
        Name of the policy definition.

    :param policy_rule:
        A YAML dictionary defining the policy rule. See `Azure Policy Definition documentation
        <https://docs.microsoft.com/en-us/azure/azure-policy/policy-definition#policy-rule>`_ for details on the
        structure. One of ``policy_rule``, ``policy_rule_json``, or ``policy_rule_file`` is required, in that order of
        precedence for use if multiple parameters are used.

    :param policy_rule_json:
        A text field defining the entirety of a policy definition in JSON. See `Azure Policy Definition documentation
        <https://docs.microsoft.com/en-us/azure/azure-policy/policy-definition#policy-rule>`_ for details on the
        structure. One of ``policy_rule``, ``policy_rule_json``, or ``policy_rule_file`` is required, in that order of
        precedence for use if multiple parameters are used. Note that the `name` field in the JSON will override the
        ``name`` parameter in the state.

    :param policy_rule_file:
        The source of a JSON file defining the entirety of a policy definition. See `Azure Policy Definition
        documentation <https://docs.microsoft.com/en-us/azure/azure-policy/policy-definition#policy-rule>`_ for
        details on the structure. One of ``policy_rule``, ``policy_rule_json``, or ``policy_rule_file`` is required,
        in that order of precedence for use if multiple parameters are used. Note that the `name` field in the JSON
        will override the ``name`` parameter in the state.

    :param skip_verify:
        Used for the ``policy_rule_file`` parameter. If ``True``, hash verification of remote file sources
        (``http://``, ``https://``, ``ftp://``) will be skipped, and the ``source_hash`` argument will be ignored.

    :param source_hash:
        This can be a source hash string or the URI of a file that contains source hash strings.

    :param source_hash_name:
        When ``source_hash`` refers to a hash file, Salt will try to find the correct hash by matching the
        filename/URI associated with that hash.

    :param policy_type:
        The type of policy definition. Possible values are NotSpecified, BuiltIn, and Custom. Only used with the
        ``policy_rule`` parameter.

    :param mode:
        The policy definition mode. Possible values are NotSpecified, Indexed, and All. Only used with the
        ``policy_rule`` parameter.

    :param display_name:
        The display name of the policy definition. Only used with the ``policy_rule`` parameter.

    :param description:
        The policy definition description. Only used with the ``policy_rule`` parameter.

    :param metadata:
        The policy definition metadata defined as a dictionary. Only used with the ``policy_rule`` parameter.

    :param parameters:
        Required dictionary if a parameter is used in the policy rule. Only used with the ``policy_rule`` parameter.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure policy definition exists:
            azurearm_resource.policy_definition_present:
                - name: testpolicy
                - display_name: Test Policy
                - description: Test policy for testing policies.
                - policy_rule:
                    if:
                      allOf:
                        - equals: Microsoft.Compute/virtualMachines/write
                          source: action
                        - field: location
                          in:
                            - eastus
                            - eastus2
                            - centralus
                    then:
                      effect: deny
                - connection_auth: {{ profile }}

    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    if not isinstance(connection_auth, dict):
        ret[
            "comment"
        ] = "Connection information must be specified via connection_auth dictionary!"
        return ret

    if not policy_rule and not policy_rule_json and not policy_rule_file:
        ret["comment"] = (
            'One of "policy_rule", "policy_rule_json", or "policy_rule_file" is'
            " required!"
        )
        return ret

    if (
        sum(x is not None for x in [policy_rule, policy_rule_json, policy_rule_file])
        > 1
    ):
        ret["comment"] = (
            'Only one of "policy_rule", "policy_rule_json", or "policy_rule_file" is'
            " allowed!"
        )
        return ret

    if (policy_rule_json or policy_rule_file) and (
        policy_type or mode or display_name or description or metadata or parameters
    ):
        ret["comment"] = (
            'Policy definitions cannot be passed when "policy_rule_json" or'
            ' "policy_rule_file" is defined!'
        )
        return ret

    temp_rule = {}
    if policy_rule_json:
        try:
            temp_rule = json.loads(policy_rule_json)
        except Exception as exc:  # pylint: disable=broad-except
            ret["comment"] = "Unable to load policy rule json! ({})".format(exc)
            return ret
    elif policy_rule_file:
        try:
            # pylint: disable=unused-variable
            sfn, source_sum, comment_ = __salt__["file.get_managed"](
                None,
                template,
                policy_rule_file,
                source_hash,
                source_hash_name,
                None,
                None,
                None,
                __env__,
                None,
                None,
                skip_verify=skip_verify,
                **kwargs
            )
        except Exception as exc:  # pylint: disable=broad-except
            ret["comment"] = 'Unable to locate policy rule file "{}"! ({})'.format(
                policy_rule_file, exc
            )
            return ret

        if not sfn:
            ret["comment"] = 'Unable to locate policy rule file "{}"!)'.format(
                policy_rule_file
            )
            return ret

        try:
            with salt.utils.files.fopen(sfn, "r") as prf:
                temp_rule = json.load(prf)
        except Exception as exc:  # pylint: disable=broad-except
            ret["comment"] = 'Unable to load policy rule file "{}"! ({})'.format(
                policy_rule_file, exc
            )
            return ret

        if sfn:
            salt.utils.files.remove(sfn)

    policy_name = name
    if policy_rule_json or policy_rule_file:
        if temp_rule.get("name"):
            policy_name = temp_rule.get("name")
        policy_rule = temp_rule.get("properties", {}).get("policyRule")
        policy_type = temp_rule.get("properties", {}).get("policyType")
        mode = temp_rule.get("properties", {}).get("mode")
        display_name = temp_rule.get("properties", {}).get("displayName")
        description = temp_rule.get("properties", {}).get("description")
        metadata = temp_rule.get("properties", {}).get("metadata")
        parameters = temp_rule.get("properties", {}).get("parameters")

    policy = __salt__["azurearm_resource.policy_definition_get"](
        name, azurearm_log_level="info", **connection_auth
    )

    if "error" not in policy:
        if policy_type and policy_type.lower() != policy.get("policy_type", "").lower():
            ret["changes"]["policy_type"] = {
                "old": policy.get("policy_type"),
                "new": policy_type,
            }

        if (mode or "").lower() != policy.get("mode", "").lower():
            ret["changes"]["mode"] = {"old": policy.get("mode"), "new": mode}

        if (display_name or "").lower() != policy.get("display_name", "").lower():
            ret["changes"]["display_name"] = {
                "old": policy.get("display_name"),
                "new": display_name,
            }

        if (description or "").lower() != policy.get("description", "").lower():
            ret["changes"]["description"] = {
                "old": policy.get("description"),
                "new": description,
            }

        rule_changes = __utils__["dictdiffer.deep_diff"](
            policy.get("policy_rule", {}), policy_rule or {}
        )
        if rule_changes:
            ret["changes"]["policy_rule"] = rule_changes

        meta_changes = __utils__["dictdiffer.deep_diff"](
            policy.get("metadata", {}), metadata or {}
        )
        if meta_changes:
            ret["changes"]["metadata"] = meta_changes

        param_changes = __utils__["dictdiffer.deep_diff"](
            policy.get("parameters", {}), parameters or {}
        )
        if param_changes:
            ret["changes"]["parameters"] = param_changes

        if not ret["changes"]:
            ret["result"] = True
            ret["comment"] = "Policy definition {} is already present.".format(name)
            return ret

        if __opts__["test"]:
            ret["comment"] = "Policy definition {} would be updated.".format(name)
            ret["result"] = None
            return ret

    else:
        ret["changes"] = {
            "old": {},
            "new": {
                "name": policy_name,
                "policy_type": policy_type,
                "mode": mode,
                "display_name": display_name,
                "description": description,
                "metadata": metadata,
                "parameters": parameters,
                "policy_rule": policy_rule,
            },
        }

    if __opts__["test"]:
        ret["comment"] = "Policy definition {} would be created.".format(name)
        ret["result"] = None
        return ret

    # Convert OrderedDict to dict
    if isinstance(metadata, dict):
        metadata = json.loads(json.dumps(metadata))
    if isinstance(parameters, dict):
        parameters = json.loads(json.dumps(parameters))

    policy_kwargs = kwargs.copy()
    policy_kwargs.update(connection_auth)

    policy = __salt__["azurearm_resource.policy_definition_create_or_update"](
        name=policy_name,
        policy_rule=policy_rule,
        policy_type=policy_type,
        mode=mode,
        display_name=display_name,
        description=description,
        metadata=metadata,
        parameters=parameters,
        **policy_kwargs
    )

    if "error" not in policy:
        ret["result"] = True
        ret["comment"] = "Policy definition {} has been created.".format(name)
        return ret

    ret["comment"] = "Failed to create policy definition {}! ({})".format(
        name, policy.get("error")
    )
    return ret


@_deprecation_message
def policy_definition_absent(name, connection_auth=None):
    """
    .. versionadded:: 2019.2.0

    Ensure a policy definition does not exist in the current subscription.

    :param name:
        Name of the policy definition.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    if not isinstance(connection_auth, dict):
        ret[
            "comment"
        ] = "Connection information must be specified via connection_auth dictionary!"
        return ret

    policy = __salt__["azurearm_resource.policy_definition_get"](
        name, azurearm_log_level="info", **connection_auth
    )

    if "error" in policy:
        ret["result"] = True
        ret["comment"] = "Policy definition {} is already absent.".format(name)
        return ret

    elif __opts__["test"]:
        ret["comment"] = "Policy definition {} would be deleted.".format(name)
        ret["result"] = None
        ret["changes"] = {
            "old": policy,
            "new": {},
        }
        return ret

    deleted = __salt__["azurearm_resource.policy_definition_delete"](
        name, **connection_auth
    )

    if deleted:
        ret["result"] = True
        ret["comment"] = "Policy definition {} has been deleted.".format(name)
        ret["changes"] = {"old": policy, "new": {}}
        return ret

    ret["comment"] = "Failed to delete policy definition {}!".format(name)
    return ret


@_deprecation_message
def policy_assignment_present(
    name,
    scope,
    definition_name,
    display_name=None,
    description=None,
    assignment_type=None,
    parameters=None,
    connection_auth=None,
    **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Ensure a security policy assignment exists.

    :param name:
        Name of the policy assignment.

    :param scope:
        The scope of the policy assignment.

    :param definition_name:
        The name of the policy definition to assign.

    :param display_name:
        The display name of the policy assignment.

    :param description:
        The policy assignment description.

    :param assignment_type:
        The type of policy assignment.

    :param parameters:
        Required dictionary if a parameter is used in the policy rule.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure policy assignment exists:
            azurearm_resource.policy_assignment_present:
                - name: testassign
                - scope: /subscriptions/bc75htn-a0fhsi-349b-56gh-4fghti-f84852
                - definition_name: testpolicy
                - display_name: Test Assignment
                - description: Test assignment for testing assignments.
                - connection_auth: {{ profile }}

    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    if not isinstance(connection_auth, dict):
        ret[
            "comment"
        ] = "Connection information must be specified via connection_auth dictionary!"
        return ret

    policy = __salt__["azurearm_resource.policy_assignment_get"](
        name, scope, azurearm_log_level="info", **connection_auth
    )

    if "error" not in policy:
        if (
            assignment_type
            and assignment_type.lower() != policy.get("type", "").lower()
        ):
            ret["changes"]["type"] = {"old": policy.get("type"), "new": assignment_type}

        if scope.lower() != policy["scope"].lower():
            ret["changes"]["scope"] = {"old": policy["scope"], "new": scope}

        pa_name = policy["policy_definition_id"].split("/")[-1]
        if definition_name.lower() != pa_name.lower():
            ret["changes"]["definition_name"] = {"old": pa_name, "new": definition_name}

        if (display_name or "").lower() != policy.get("display_name", "").lower():
            ret["changes"]["display_name"] = {
                "old": policy.get("display_name"),
                "new": display_name,
            }

        if (description or "").lower() != policy.get("description", "").lower():
            ret["changes"]["description"] = {
                "old": policy.get("description"),
                "new": description,
            }

        param_changes = __utils__["dictdiffer.deep_diff"](
            policy.get("parameters", {}), parameters or {}
        )
        if param_changes:
            ret["changes"]["parameters"] = param_changes

        if not ret["changes"]:
            ret["result"] = True
            ret["comment"] = "Policy assignment {} is already present.".format(name)
            return ret

        if __opts__["test"]:
            ret["comment"] = "Policy assignment {} would be updated.".format(name)
            ret["result"] = None
            return ret

    else:
        ret["changes"] = {
            "old": {},
            "new": {
                "name": name,
                "scope": scope,
                "definition_name": definition_name,
                "type": assignment_type,
                "display_name": display_name,
                "description": description,
                "parameters": parameters,
            },
        }

    if __opts__["test"]:
        ret["comment"] = "Policy assignment {} would be created.".format(name)
        ret["result"] = None
        return ret

    if isinstance(parameters, dict):
        parameters = json.loads(json.dumps(parameters))

    policy_kwargs = kwargs.copy()
    policy_kwargs.update(connection_auth)
    policy = __salt__["azurearm_resource.policy_assignment_create"](
        name=name,
        scope=scope,
        definition_name=definition_name,
        type=assignment_type,
        display_name=display_name,
        description=description,
        parameters=parameters,
        **policy_kwargs
    )

    if "error" not in policy:
        ret["result"] = True
        ret["comment"] = "Policy assignment {} has been created.".format(name)
        return ret

    ret["comment"] = "Failed to create policy assignment {}! ({})".format(
        name, policy.get("error")
    )
    return ret


@_deprecation_message
def policy_assignment_absent(name, scope, connection_auth=None):
    """
    .. versionadded:: 2019.2.0

    Ensure a policy assignment does not exist in the provided scope.

    :param name:
        Name of the policy assignment.

    :param scope:
        The scope of the policy assignment.

    connection_auth
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    if not isinstance(connection_auth, dict):
        ret[
            "comment"
        ] = "Connection information must be specified via connection_auth dictionary!"
        return ret

    policy = __salt__["azurearm_resource.policy_assignment_get"](
        name, scope, azurearm_log_level="info", **connection_auth
    )

    if "error" in policy:
        ret["result"] = True
        ret["comment"] = "Policy assignment {} is already absent.".format(name)
        return ret

    elif __opts__["test"]:
        ret["comment"] = "Policy assignment {} would be deleted.".format(name)
        ret["result"] = None
        ret["changes"] = {
            "old": policy,
            "new": {},
        }
        return ret

    deleted = __salt__["azurearm_resource.policy_assignment_delete"](
        name, scope, **connection_auth
    )

    if deleted:
        ret["result"] = True
        ret["comment"] = "Policy assignment {} has been deleted.".format(name)
        ret["changes"] = {"old": policy, "new": {}}
        return ret

    ret["comment"] = "Failed to delete policy assignment {}!".format(name)
    return ret
