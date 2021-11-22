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
            ret["comment"] = "User {} will be created".format(name)
            return ret

        # create the user
        result = __salt__["splunk.create_user"](email, profile=profile, **kwargs)
        if result:
            ret["changes"].setdefault("old", None)
            ret["changes"].setdefault("new", "User {} exists".format(name))
            ret["result"] = True
        else:
            ret["result"] = False
            ret["comment"] = "Failed to create {}".format(name)

        return ret
    else:
        ret["comment"] = "User {} set to be updated.".format(name)
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
        "comment": "User {} is absent.".format(user_identity),
    }

    target = __salt__["splunk.get_user"](email, profile=profile)

    if not target:
        ret["comment"] = "User {} does not exist".format(user_identity)
        ret["result"] = True
        return ret

    if __opts__["test"]:
        ret["comment"] = "User {} is all set to be deleted".format(user_identity)
        ret["result"] = None
        return ret

    result = __salt__["splunk.delete_user"](email, profile=profile)

    if result:
        ret["comment"] = "Deleted user {}".format(user_identity)
        ret["changes"].setdefault("old", "User {} exists".format(user_identity))
        ret["changes"].setdefault("new", "User {} deleted".format(user_identity))
        ret["result"] = True

    else:
        ret["comment"] = "Failed to delete {}".format(user_identity)
        ret["result"] = False

    return ret
