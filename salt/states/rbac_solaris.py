"""
Management of Solaris RBAC

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       rbac_solaris,solaris_user
:platform:      solaris,illumos

.. versionadded:: 2016.11.0

.. code-block:: yaml

    sjorge:
      rbac.managed:
        - roles:
            - netcfg
        - profiles:
            - System Power
        - authorizations:
            - solaris.audit.*
"""

import logging

log = logging.getLogger(__name__)

# Define the state's virtual name
__virtualname__ = "rbac"


def __virtual__():
    """
    Provides rbac on Solaris like platforms
    """
    if (
        "rbac.profile_list" in __salt__
        and "user.list_users" in __salt__
        and __grains__["kernel"] == "SunOS"
    ):
        return True
    else:
        return (
            False,
            "{} state module can only be loaded on Solaris".format(__virtualname__),
        )


def managed(name, roles=None, profiles=None, authorizations=None):
    """
    Manage RBAC properties for user

    name : string
        username
    roles : list
        list of roles for user
    profiles : list
        list of profiles for user
    authorizations : list
        list of authorizations for user

    .. warning::
        All existing roles, profiles and authorizations will be replaced!
        An empty list will remove everything.

        Set the property to `None` to not manage it.

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    ## check properties
    if name not in __salt__["user.list_users"]():
        ret["result"] = False
        ret["comment"] = "User {} does not exist!".format(name)
        return ret
    if roles and not isinstance(roles, (list)):
        ret["result"] = False
        ret["comment"] = "Property roles is not None or list!"
        return ret
    if profiles and not isinstance(profiles, (list)):
        ret["result"] = False
        ret["comment"] = "Property profiles is not None or list!"
        return ret
    if authorizations and not isinstance(authorizations, (list)):
        ret["result"] = False
        ret["comment"] = "Property authorizations is not None or list!"
        return ret
    log.debug(
        "rbac.managed - roles=%s, profiles=%s, authorizations=%s",
        roles,
        profiles,
        authorizations,
    )

    ## update roles
    if isinstance(roles, (list)):
        # compute changed
        roles_current = __salt__["rbac.role_get"](name)
        roles_add = [r for r in roles if r not in roles_current]
        roles_rm = [r for r in roles_current if r not in roles]

        # execute and verify changes
        if roles_add:
            res_roles_add = __salt__["rbac.role_add"](name, ",".join(roles_add).strip())
            roles_current = __salt__["rbac.role_get"](name)
            for role in roles_add:
                if "roles" not in ret["changes"]:
                    ret["changes"]["roles"] = {}
                ret["changes"]["roles"][role] = (
                    "Added" if role in roles_current else "Failed"
                )
                if ret["changes"]["roles"][role] == "Failed":
                    ret["result"] = False

        if roles_rm:
            res_roles_rm = __salt__["rbac.role_rm"](name, ",".join(roles_rm).strip())

            roles_current = __salt__["rbac.role_get"](name)
            for role in roles_rm:
                if "roles" not in ret["changes"]:
                    ret["changes"]["roles"] = {}
                ret["changes"]["roles"][role] = (
                    "Removed" if role not in roles_current else "Failed"
                )
                if ret["changes"]["roles"][role] == "Failed":
                    ret["result"] = False

    ## update profiles
    if isinstance(profiles, (list)):
        # compute changed
        profiles_current = __salt__["rbac.profile_get"](name)
        profiles_add = [r for r in profiles if r not in profiles_current]
        profiles_rm = [r for r in profiles_current if r not in profiles]

        # execute and verify changes
        if profiles_add:
            res_profiles_add = __salt__["rbac.profile_add"](
                name, ",".join(profiles_add).strip()
            )
            profiles_current = __salt__["rbac.profile_get"](name)
            for profile in profiles_add:
                if "profiles" not in ret["changes"]:
                    ret["changes"]["profiles"] = {}
                ret["changes"]["profiles"][profile] = (
                    "Added" if profile in profiles_current else "Failed"
                )
                if ret["changes"]["profiles"][profile] == "Failed":
                    ret["result"] = False

        if profiles_rm:
            res_profiles_rm = __salt__["rbac.profile_rm"](
                name, ",".join(profiles_rm).strip()
            )

            profiles_current = __salt__["rbac.profile_get"](name)
            for profile in profiles_rm:
                if "profiles" not in ret["changes"]:
                    ret["changes"]["profiles"] = {}
                ret["changes"]["profiles"][profile] = (
                    "Removed" if profile not in profiles_current else "Failed"
                )
                if ret["changes"]["profiles"][profile] == "Failed":
                    ret["result"] = False

    ## update auths
    if isinstance(authorizations, (list)):
        # compute changed
        auths_current = __salt__["rbac.auth_get"](name, False)
        auths_add = [r for r in authorizations if r not in auths_current]
        auths_rm = [r for r in auths_current if r not in authorizations]

        # execute and verify changes
        if auths_add:
            res_auths_add = __salt__["rbac.auth_add"](name, ",".join(auths_add).strip())
            auths_current = __salt__["rbac.auth_get"](name)
            for auth in auths_add:
                if "authorizations" not in ret["changes"]:
                    ret["changes"]["authorizations"] = {}
                ret["changes"]["authorizations"][auth] = (
                    "Added" if auth in auths_current else "Failed"
                )
                if ret["changes"]["authorizations"][auth] == "Failed":
                    ret["result"] = False

        if auths_rm:
            res_auths_rm = __salt__["rbac.auth_rm"](name, ",".join(auths_rm).strip())

            auths_current = __salt__["rbac.auth_get"](name)
            for auth in auths_rm:
                if "authorizations" not in ret["changes"]:
                    ret["changes"]["authorizations"] = {}
                ret["changes"]["authorizations"][auth] = (
                    "Removed" if auth not in auths_current else "Failed"
                )
                if ret["changes"]["authorizations"][auth] == "Failed":
                    ret["result"] = False

    return ret
