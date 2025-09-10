"""
Management of PostgreSQL databases
==================================

The postgres_database module is used to create and manage Postgres databases.
Databases can be set as either absent or present

.. code-block:: yaml

    frank:
      postgres_database.present
"""


def __virtual__():
    """
    Only load if the postgres module is present
    """
    if "postgres.user_exists" not in __salt__:
        return (
            False,
            "Unable to load postgres module.  Make sure `postgres.bins_dir` is set.",
        )
    return True


def present(
    name,
    tablespace=None,
    encoding=None,
    lc_collate=None,
    lc_ctype=None,
    owner=None,
    owner_recurse=False,
    template=None,
    user=None,
    maintenance_db=None,
    db_password=None,
    db_host=None,
    db_port=None,
    db_user=None,
):
    """
    Ensure that the named database is present with the specified properties.
    For more information about all of these options see man createdb(1)

    name
        The name of the database to manage

    tablespace
        Default tablespace for the database

    encoding
        The character encoding scheme to be used in this database. The encoding
        has to be defined in the following format (without hyphen).

        .. code-block:: yaml

          - encoding: UTF8

    lc_collate
        The LC_COLLATE setting to be used in this database

    lc_ctype
        The LC_CTYPE setting to be used in this database

    owner
        The username of the database owner

    owner_recurse
        Recurse owner change to all relations in the database

    template
        The template database from which to build this database

    user
        System user all operations should be performed on behalf of

    db_user
        database username if different from config or default

    db_password
        user password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default

        .. versionadded:: 0.17.0
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"Database {name} is already present",
    }

    db_args = {
        "maintenance_db": maintenance_db,
        "runas": user,
        "host": db_host,
        "user": db_user,
        "port": db_port,
        "password": db_password,
    }
    dbs = __salt__["postgres.db_list"](**db_args)
    db_params = dbs.get(name, {})

    if name in dbs and all(
        (
            db_params.get("Tablespace") == tablespace if tablespace else True,
            (
                db_params.get("Encoding").lower() == encoding.lower()
                if encoding
                else True
            ),
            db_params.get("Collate") == lc_collate if lc_collate else True,
            db_params.get("Ctype") == lc_ctype if lc_ctype else True,
            db_params.get("Owner") == owner if owner else True,
        )
    ):
        return ret
    elif name in dbs and any(
        (
            (
                db_params.get("Encoding").lower() != encoding.lower()
                if encoding
                else False
            ),
            db_params.get("Collate") != lc_collate if lc_collate else False,
            db_params.get("Ctype") != lc_ctype if lc_ctype else False,
        )
    ):
        ret["comment"] = (
            "Database {} has wrong parameters which couldn't be changed on fly.".format(
                name
            )
        )
        ret["result"] = False
        return ret

    # The database is not present, make it!
    if __opts__["test"]:
        ret["result"] = None
        if name not in dbs:
            ret["comment"] = f"Database {name} is set to be created"
        else:
            ret["comment"] = (
                f"Database {name} exists, but parameters need to be changed"
            )
        return ret
    if name not in dbs and __salt__["postgres.db_create"](
        name,
        tablespace=tablespace,
        encoding=encoding,
        lc_collate=lc_collate,
        lc_ctype=lc_ctype,
        owner=owner,
        template=template,
        **db_args,
    ):
        ret["comment"] = f"The database {name} has been created"
        ret["changes"][name] = "Present"
    elif name in dbs and __salt__["postgres.db_alter"](
        name, tablespace=tablespace, owner=owner, owner_recurse=owner_recurse, **db_args
    ):
        ret["comment"] = f"Parameters for database {name} have been changed"
        ret["changes"][name] = "Parameters changed"
    elif name in dbs:
        ret["comment"] = f"Failed to change parameters for database {name}"
        ret["result"] = False
    else:
        ret["comment"] = f"Failed to create database {name}"
        ret["result"] = False

    return ret


def absent(
    name,
    user=None,
    maintenance_db=None,
    db_password=None,
    db_host=None,
    db_port=None,
    db_user=None,
):
    """
    Ensure that the named database is absent

    name
        The name of the database to remove

    db_user
        database username if different from config or default

    db_password
        user password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default

    user
        System user all operations should be performed on behalf of

        .. versionadded:: 0.17.0
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    db_args = {
        "maintenance_db": maintenance_db,
        "runas": user,
        "host": db_host,
        "user": db_user,
        "port": db_port,
        "password": db_password,
    }
    # check if db exists and remove it
    if __salt__["postgres.db_exists"](name, **db_args):
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Database {name} is set to be removed"
            return ret
        if __salt__["postgres.db_remove"](name, **db_args):
            ret["comment"] = f"Database {name} has been removed"
            ret["changes"][name] = "Absent"
            return ret

    # fallback
    ret["comment"] = f"Database {name} is not present, so it cannot be removed"
    return ret
