# -*- coding: utf-8 -*-
"""
Manage CognitoIdentity Functions
================================

.. versionadded:: 2016.11.0

Create and destroy CognitoIdentity identity pools. Be aware that this interacts with
Amazon's services, and so may incur charges.

This module uses ``boto3``, which can be installed via package, or pip.

This module accepts explicit vpc credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    vpc.keyid: GKTADJGHEIQSXMKKRBJ08H
    vpc.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile,
either passed in as a dict, or as a string to pull from pillars or minion
config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. code-block:: yaml

    Ensure function exists:
        boto_cognitoidentity.pool_present:
            - PoolName: my_identity_pool
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

from salt.ext.six import string_types

# Import Salt Libs

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if boto is available.
    """
    return (
        "boto_cognitoidentity"
        if "boto_cognitoidentity.describe_identity_pools" in __salt__
        else False
    )


def _get_object(objname, objtype):
    """
    Helper function to retrieve objtype from pillars if objname
    is string_types, used for SupportedLoginProviders and
    OpenIdConnectProviderARNs.
    """
    ret = None
    if objname is None:
        return ret

    if isinstance(objname, string_types):
        if objname in __opts__:
            ret = __opts__[objname]
        master_opts = __pillar__.get("master", {})
        if objname in master_opts:
            ret = master_opts[objname]
        if objname in __pillar__:
            ret = __pillar__[objname]
    elif isinstance(objname, objtype):
        ret = objname

    if not isinstance(ret, objtype):
        ret = None

    return ret


def _role_present(
    ret, IdentityPoolId, AuthenticatedRole, UnauthenticatedRole, conn_params
):
    """
    Helper function to set the Roles to the identity pool
    """
    r = __salt__["boto_cognitoidentity.get_identity_pool_roles"](
        IdentityPoolName="", IdentityPoolId=IdentityPoolId, **conn_params
    )
    if r.get("error"):
        ret["result"] = False
        failure_comment = "Failed to get existing identity pool roles: " "{0}".format(
            r["error"].get("message", r["error"])
        )
        ret["comment"] = "{0}\n{1}".format(ret["comment"], failure_comment)
        return

    existing_identity_pool_role = r.get("identity_pool_roles")[0].get("Roles", {})
    r = __salt__["boto_cognitoidentity.set_identity_pool_roles"](
        IdentityPoolId=IdentityPoolId,
        AuthenticatedRole=AuthenticatedRole,
        UnauthenticatedRole=UnauthenticatedRole,
        **conn_params
    )
    if not r.get("set"):
        ret["result"] = False
        failure_comment = "Failed to set roles: " "{0}".format(
            r["error"].get("message", r["error"])
        )
        ret["comment"] = "{0}\n{1}".format(ret["comment"], failure_comment)
        return

    updated_identity_pool_role = r.get("roles")

    if existing_identity_pool_role != updated_identity_pool_role:
        if not ret["changes"]:
            ret["changes"]["old"] = dict()
            ret["changes"]["new"] = dict()
        ret["changes"]["old"]["Roles"] = existing_identity_pool_role
        ret["changes"]["new"]["Roles"] = r.get("roles")
        ret["comment"] = "{0}\n{1}".format(
            ret["comment"], "identity pool roles updated."
        )
    else:
        ret["comment"] = "{0}\n{1}".format(
            ret["comment"], "identity pool roles is already current."
        )

    return


def pool_present(
    name,
    IdentityPoolName,
    AuthenticatedRole,
    AllowUnauthenticatedIdentities=False,
    UnauthenticatedRole=None,
    SupportedLoginProviders=None,
    DeveloperProviderName=None,
    OpenIdConnectProviderARNs=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Ensure Cognito Identity Pool exists.

    name
        The name of the state definition

    IdentityPoolName
        Name of the Cognito Identity Pool

    AuthenticatedRole
        An IAM role name or ARN that will be associated with temporary AWS
        credentials for an authenticated cognito identity.

    AllowUnauthenticatedIdentities
        Whether to allow anonymous user identities

    UnauthenticatedRole
        An IAM role name or ARN that will be associated with anonymous
        user identities

    SupportedLoginProviders
        A dictionary or pillar that contains key:value pairs mapping provider
        names to provider app IDs.

    DeveloperProviderName
        A string which is the domain by which Cognito will refer to your users.
        This name acts as a placeholder that allows your backend and the Cognito
        service to communicate about the developer provider.  Once you have set a
        developer provider name, you cannot change it.  Please take care in setting
        this parameter.

    OpenIdConnectProviderARNs
        A list or pillar name that contains a list of OpenID Connect provider ARNs.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    """
    ret = {"name": IdentityPoolName, "result": True, "comment": "", "changes": {}}

    conn_params = dict(region=region, key=key, keyid=keyid, profile=profile)

    r = __salt__["boto_cognitoidentity.describe_identity_pools"](
        IdentityPoolName=IdentityPoolName, **conn_params
    )

    if r.get("error"):
        ret["result"] = False
        ret["comment"] = "Failed to describe identity pools {0}".format(
            r["error"]["message"]
        )
        return ret

    identity_pools = r.get("identity_pools")
    if identity_pools and len(identity_pools) > 1:
        ret["result"] = False
        ret["comment"] = (
            "More than one identity pool for the given name matched "
            "Cannot execute pool_present function.\n"
            "Matched Identity Pools:\n{0}".format(identity_pools)
        )
        return ret
    existing_identity_pool = None if identity_pools is None else identity_pools[0]
    IdentityPoolId = (
        None
        if existing_identity_pool is None
        else existing_identity_pool.get("IdentityPoolId")
    )

    if __opts__["test"]:
        if identity_pools is None:
            ret["comment"] = "A new identity pool named {0} will be " "created.".format(
                IdentityPoolName
            )
        else:
            ret["comment"] = (
                "An existing identity pool named {0} with id "
                "{1}will be updated.".format(IdentityPoolName, IdentityPoolId)
            )
        ret["result"] = None
        return ret

    SupportedLoginProviders = _get_object(SupportedLoginProviders, dict)
    OpenIdConnectProviderARNs = _get_object(OpenIdConnectProviderARNs, list)

    request_params = dict(
        IdentityPoolName=IdentityPoolName,
        AllowUnauthenticatedIdentities=AllowUnauthenticatedIdentities,
        SupportedLoginProviders=SupportedLoginProviders,
        DeveloperProviderName=DeveloperProviderName,
        OpenIdConnectProviderARNs=OpenIdConnectProviderARNs,
    )
    request_params.update(conn_params)

    updated_identity_pool = None
    if IdentityPoolId is None:
        r = __salt__["boto_cognitoidentity.create_identity_pool"](**request_params)

        if r.get("created"):
            updated_identity_pool = r.get("identity_pool")
            IdentityPoolId = updated_identity_pool.get("IdentityPoolId")
            ret["comment"] = (
                "A new identity pool with name {0}, id {1} "
                "is created.".format(IdentityPoolName, IdentityPoolId)
            )
        else:
            ret["result"] = False
            ret["comment"] = "Failed to add a new identity pool: " "{0}".format(
                r["error"].get("message", r["error"])
            )
            return ret
    else:  # Update an existing pool
        request_params["IdentityPoolId"] = IdentityPoolId
        # we will never change the IdentityPoolName from the state module
        request_params.pop("IdentityPoolName", None)
        r = __salt__["boto_cognitoidentity.update_identity_pool"](**request_params)

        if r.get("updated"):
            updated_identity_pool = r.get("identity_pool")
            ret["comment"] = (
                "Existing identity pool with name {0}, id {1} "
                "is updated.".format(IdentityPoolName, IdentityPoolId)
            )
        else:
            ret["result"] = False
            ret["comment"] = (
                "Failed to update an existing identity pool {0} {1}: "
                "{2}".format(
                    IdentityPoolName,
                    IdentityPoolId,
                    r["error"].get("message", r["error"]),
                )
            )
            return ret

    if existing_identity_pool != updated_identity_pool:
        ret["changes"]["old"] = dict()
        ret["changes"]["new"] = dict()
        change_key = "Identity Pool Name {0}".format(IdentityPoolName)
        ret["changes"]["old"][change_key] = existing_identity_pool
        ret["changes"]["new"][change_key] = updated_identity_pool
    else:
        ret["comment"] = "Identity Pool state is current, no changes."

    # Now update the Auth/Unauth Roles
    _role_present(
        ret, IdentityPoolId, AuthenticatedRole, UnauthenticatedRole, conn_params
    )

    return ret


def pool_absent(
    name,
    IdentityPoolName,
    RemoveAllMatched=False,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Ensure cognito identity pool with passed properties is absent.

    name
        The name of the state definition.

    IdentityPoolName
        Name of the Cognito Identity Pool.  Please note that this may
        match multiple pools with the same given name, in which case,
        all will be removed.

    RemoveAllMatched
        If True, all identity pools with the matching IdentityPoolName
        will be removed.  If False and there are more than one identity pool
        with the matching IdentityPoolName, no action will be taken.  If False
        and there is only one identity pool with the matching IdentityPoolName,
        the identity pool will be removed.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    """

    ret = {"name": IdentityPoolName, "result": True, "comment": "", "changes": {}}

    conn_params = dict(region=region, key=key, keyid=keyid, profile=profile)

    r = __salt__["boto_cognitoidentity.describe_identity_pools"](
        IdentityPoolName=IdentityPoolName, **conn_params
    )

    if r.get("error"):
        ret["result"] = False
        ret["comment"] = "Failed to describe identity pools {0}".format(
            r["error"]["message"]
        )
        return ret

    identity_pools = r.get("identity_pools")

    if identity_pools is None:
        ret["result"] = True
        ret["comment"] = "No matching identity pool for the given name {0}".format(
            IdentityPoolName
        )
        return ret

    if not RemoveAllMatched and len(identity_pools) > 1:
        ret["result"] = False
        ret["comment"] = (
            "More than one identity pool for the given name matched "
            "and RemoveAllMatched flag is False.\n"
            "Matched Identity Pools:\n{0}".format(identity_pools)
        )
        return ret

    if __opts__["test"]:
        ret["comment"] = (
            "The following matched identity pools will be "
            "deleted.\n{0}".format(identity_pools)
        )
        ret["result"] = None
        return ret

    for identity_pool in identity_pools:
        IdentityPoolId = identity_pool.get("IdentityPoolId")
        r = __salt__["boto_cognitoidentity.delete_identity_pools"](
            IdentityPoolName="", IdentityPoolId=IdentityPoolId, **conn_params
        )
        if r.get("error"):
            ret["result"] = False
            failure_comment = "Failed to delete identity pool {0}: " "{1}".format(
                IdentityPoolId, r["error"].get("message", r["error"])
            )
            ret["comment"] = "{0}\n{1}".format(ret["comment"], failure_comment)
            return ret

        if r.get("deleted"):
            if not ret["changes"]:
                ret["changes"]["old"] = dict()
                ret["changes"]["new"] = dict()
            change_key = "Identity Pool Id {0}".format(IdentityPoolId)
            ret["changes"]["old"][change_key] = IdentityPoolName
            ret["changes"]["new"][change_key] = None
            ret["comment"] = "{0}\n{1}".format(
                ret["comment"], "{0} deleted".format(change_key)
            )
        else:
            ret["result"] = False
            failure_comment = "Identity Pool Id {0} not deleted, returned count 0".format(
                IdentityPoolId
            )
            ret["comment"] = "{0}\n{1}".format(ret["comment"], failure_comment)
            return ret

    return ret
