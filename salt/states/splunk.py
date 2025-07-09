"""
Splunk User State Module

.. versionadded:: 2016.3.0

This state is used to ensure presence of users in splunk.

.. code-block:: yaml

    ensure example test user 1:
        splunk.present:
            - name: 'Example TestUser1'
            - email: example@domain.com
"""


def __virtual__():
    """
    Only load if the splunk module is available in __salt__
    """
    if "splunk.list_users" in __salt__:
        return "splunk"
    return (False, "splunk module could not be loaded")


def present(email, profile="splunk", **kwargs):
    """
    Ensure a user is present

    .. code-block:: yaml

        ensure example test user 1:
            splunk.user_present:
                - realname: 'Example TestUser1'
                - name: 'exampleuser'
                - email: 'example@domain.com'
                - roles: ['user']

    The following parameters are required:

    email
        This is the email of the user in splunk
    """

    name = kwargs.get("name")

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    target = __salt__["splunk.get_user"](email, profile=profile, user_details=True)

    if not target:
        if __opts__["test"]:
            ret["comment"] = f"User {name} will be created"
            return ret

        # create the user
        result = __salt__["splunk.create_user"](email, profile=profile, **kwargs)
        if result:
            ret["changes"].setdefault("old", None)
            ret["changes"].setdefault("new", f"User {name} exists")
            ret["result"] = True
        else:
            ret["result"] = False
            ret["comment"] = f"Failed to create {name}"

        return ret
    else:
        ret["comment"] = f"User {name} set to be updated."
        if __opts__["test"]:
            ret["result"] = None
            return ret

        # found a user... updating
        result = __salt__["splunk.update_user"](email, profile, **kwargs)

        if isinstance(result, bool) and result:
            # no update
            ret["result"] = None
            ret["comment"] = "No changes"
        else:
            diff = {}
            for field in [
                "name",
                "realname",
                "roles",
                "defaultApp",
                "tz",
                "capabilities",
            ]:
                if field == "roles":
                    diff["roles"] = list(
                        set(target.get(field, [])).symmetric_difference(
                            set(result.get(field, []))
                        )
                    )
                elif target.get(field) != result.get(field):
                    diff[field] = result.get(field)

            newvalues = result
            ret["result"] = True
            ret["changes"]["diff"] = diff
            ret["changes"]["old"] = target
            ret["changes"]["new"] = newvalues

    return ret


def absent(email, profile="splunk", **kwargs):
    """
    Ensure a splunk user is absent

    .. code-block:: yaml

        ensure example test user 1:
            splunk.absent:
                - email: 'example@domain.com'
                - name: 'exampleuser'

    The following parameters are required:

    email
        This is the email of the user in splunk
    name
        This is the splunk username used to identify the user.

    """
    user_identity = kwargs.get("name")

    ret = {
        "name": user_identity,
        "changes": {},
        "result": None,
        "comment": f"User {user_identity} is absent.",
    }

    target = __salt__["splunk.get_user"](email, profile=profile)

    if not target:
        ret["comment"] = f"User {user_identity} does not exist"
        ret["result"] = True
        return ret

    if __opts__["test"]:
        ret["comment"] = f"User {user_identity} is all set to be deleted"
        ret["result"] = None
        return ret

    result = __salt__["splunk.delete_user"](email, profile=profile)

    if result:
        ret["comment"] = f"Deleted user {user_identity}"
        ret["changes"].setdefault("old", f"User {user_identity} exists")
        ret["changes"].setdefault("new", f"User {user_identity} deleted")
        ret["result"] = True

    else:
        ret["comment"] = f"Failed to delete {user_identity}"
        ret["result"] = False

    return ret
