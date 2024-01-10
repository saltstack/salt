"""
Management of MongoDB Users
===========================

:depends:   - pymongo Python module
"""

# Define the module's virtual name
__virtualname__ = "mongodb_user"


def __virtual__():
    if "mongodb.user_exists" in __salt__:
        return __virtualname__
    return (False, "mongodb module could not be loaded")


def present(
    name,
    passwd,
    database="admin",
    user=None,
    password=None,
    host=None,
    port=None,
    authdb=None,
    roles=None,
    ssl=False,
    verify_ssl=True,
):
    """
    Ensure that the user is present with the specified properties

    name
        The name of the user to manage

    passwd
        The password of the user to manage

    user
        MongoDB user with sufficient privilege to create the user

    password
        Password for the admin user specified with the ``user`` parameter

    host
        The hostname/IP address of the MongoDB server

    port
        The port on which MongoDB is listening

    database
        The database in which to create the user

        .. note::
            If the database doesn't exist, it will be created.

    authdb
        The database in which to authenticate

    roles
        The roles assigned to user specified with the ``name`` parameter

    ssl
        Whether or not to use SSL to connect to mongodb. Default False.

        .. versionadded:: 3005.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3005.0

    Example:

    .. code-block:: yaml

        mongouser-myapp:
          mongodb_user.present:
          - name: myapp
          - passwd: password-of-myapp
          - database: admin
          # Connect as admin:sekrit
          - user: admin
          - password: sekrit
          - roles:
              - readWrite
              - userAdmin
              - dbOwner

    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "User {} is already present".format(name),
    }

    # setup default empty roles if not provided to preserve previous API interface
    if roles is None:
        roles = []

    # Check for valid port
    try:
        port = int(port or __salt__["config.option"]("mongodb.port"))
    except TypeError:
        ret["result"] = False
        ret["comment"] = "Port ({!r}) is not an integer.".format(port)
        return ret

    # check if user exists
    users = __salt__["mongodb.user_find"](
        name,
        user,
        password,
        host,
        port,
        database,
        authdb,
        ssl=ssl,
        verify_ssl=verify_ssl,
    )
    if len(users) > 0:
        # check for errors returned in users e.g.
        #    users= (False, 'Failed to connect to MongoDB database localhost:27017')
        #    users= (False, 'not authorized on admin to execute command { usersInfo: "root" }')
        if not users[0]:
            ret["result"] = False
            ret["comment"] = "Mongo Err: {}".format(users[1])
            return ret

        # check each user occurrence
        for usr in users:
            # prepare empty list for current roles
            current_roles = []
            # iterate over user roles and append each to current_roles list
            for role in usr["roles"]:
                # check correct database to be sure to fill current_roles only for desired db
                if role["db"] == database:
                    current_roles.append(role["role"])

            # fill changes if the roles and current roles differ
            if not set(current_roles) == set(roles):
                ret["changes"].update(
                    {
                        name: {
                            "database": database,
                            "roles": {"old": current_roles, "new": roles},
                        }
                    }
                )

            __salt__["mongodb.user_create"](
                name,
                passwd,
                user,
                password,
                host,
                port,
                database=database,
                authdb=authdb,
                roles=roles,
                ssl=ssl,
                verify_ssl=verify_ssl,
            )
        return ret

    # if the check does not return a boolean, return an error
    # this may be the case if there is a database connection error
    if not isinstance(users, list):
        ret["comment"] = users
        ret["result"] = False
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "User {} is not present and needs to be created".format(name)
        return ret
    # The user is not present, make it!
    if __salt__["mongodb.user_create"](
        name,
        passwd,
        user,
        password,
        host,
        port,
        database=database,
        authdb=authdb,
        roles=roles,
        ssl=ssl,
        verify_ssl=verify_ssl,
    ):
        ret["comment"] = "User {} has been created".format(name)
        ret["changes"][name] = "Present"
    else:
        ret["comment"] = "Failed to create database {}".format(name)
        ret["result"] = False

    return ret


def absent(
    name,
    user=None,
    password=None,
    host=None,
    port=None,
    database="admin",
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    Ensure that the named user is absent

    name
        The name of the user to remove

    user
        MongoDB user with sufficient privilege to create the user

    password
        Password for the admin user specified by the ``user`` parameter

    host
        The hostname/IP address of the MongoDB server

    port
        The port on which MongoDB is listening

    database
        The database from which to remove the user specified by the ``name``
        parameter

    authdb
        The database in which to authenticate

    ssl
        Whether or not to use SSL to connect to mongodb. Default False.

        .. versionadded:: 3005.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3005.0
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    # check if user exists and remove it
    user_exists = __salt__["mongodb.user_exists"](
        name,
        user,
        password,
        host,
        port,
        database=database,
        authdb=authdb,
        ssl=ssl,
        verify_ssl=verify_ssl,
    )
    if user_exists is True:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "User {} is present and needs to be removed".format(name)
            return ret
        if __salt__["mongodb.user_remove"](
            name,
            user,
            password,
            host,
            port,
            database=database,
            authdb=authdb,
            ssl=ssl,
            verify_ssl=verify_ssl,
        ):
            ret["comment"] = "User {} has been removed".format(name)
            ret["changes"][name] = "Absent"
            return ret

    # if the check does not return a boolean, return an error
    # this may be the case if there is a database connection error
    if not isinstance(user_exists, bool):
        ret["comment"] = user_exists
        ret["result"] = False
        return ret

    # fallback
    ret["comment"] = "User {} is not present".format(name)
    return ret
