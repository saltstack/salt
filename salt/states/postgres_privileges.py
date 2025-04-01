"""
Management of PostgreSQL Privileges
===================================

The postgres_privileges module is used to manage Postgres privileges.
Privileges can be set as either absent or present.

Privileges can be set on the following database object types:

* database
* schema
* tablespace
* table
* sequence
* language
* group

Setting the grant option is supported as well.

.. versionadded:: 2016.3.0

.. code-block:: yaml

    baruwa:
      postgres_privileges.present:
        - object_name: awl
        - object_type: table
        - privileges:
          - SELECT
          - INSERT
          - DELETE
        - grant_option: False
        - prepend: public
        - maintenance_db: testdb

.. code-block:: yaml

    andrew:
      postgres_privileges.present:
        - object_name: admins
        - object_type: group
        - grant_option: False
        - maintenance_db: testdb

.. code-block:: yaml

    baruwa:
      postgres_privileges.absent:
        - object_name: awl
        - object_type: table
        - privileges:
          - SELECT
          - INSERT
          - DELETE
        - prepend: public
        - maintenance_db: testdb

.. code-block:: yaml

    andrew:
      postgres_privileges.absent:
        - object_name: admins
        - object_type: group
        - maintenance_db: testdb
"""


def __virtual__():
    """
    Only load if the postgres module is present
    """
    if "postgres.privileges_grant" not in __salt__:
        return (
            False,
            "Unable to load postgres module.  Make sure `postgres.bins_dir` is set.",
        )
    return True


def present(
    name,
    object_name,
    object_type,
    privileges=None,
    grant_option=None,
    prepend="public",
    maintenance_db=None,
    user=None,
    db_password=None,
    db_host=None,
    db_port=None,
    db_user=None,
):
    """
    Grant the requested privilege(s) on the specified object to a role

    name
        Name of the role to which privileges should be granted

    object_name
       Name of the object on which the grant is to be performed.
       'ALL' may be used for objects of type 'table' or 'sequence'.

    object_type
       The object type, which can be one of the following:

       - table
       - sequence
       - schema
       - tablespace
       - language
       - database
       - group
       - function

       View permissions should specify `object_type: table`.

    privileges
       List of privileges to grant, from the list below:

       - INSERT
       - CREATE
       - TRUNCATE
       - CONNECT
       - TRIGGER
       - SELECT
       - USAGE
       - TEMPORARY
       - UPDATE
       - EXECUTE
       - REFERENCES
       - DELETE
       - ALL

       :note: privileges should not be set when granting group membership

    grant_option
        If grant_option is set to True, the recipient of the privilege can
        in turn grant it to others

    prepend
        Table and Sequence object types live under a schema so this should be
        provided if the object is not under the default `public` schema

    maintenance_db
        The name of the database in which the language is to be installed

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
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "The requested privilege(s) are already set",
    }

    privileges = ",".join(privileges) if privileges else None

    kwargs = {
        "privileges": privileges,
        "grant_option": grant_option,
        "prepend": prepend,
        "maintenance_db": maintenance_db,
        "runas": user,
        "host": db_host,
        "user": db_user,
        "port": db_port,
        "password": db_password,
    }

    if not __salt__["postgres.has_privileges"](
        name, object_name, object_type, **kwargs
    ):
        _privs = object_name if object_type == "group" else privileges

        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "The privilege(s): {} are set to be granted to {}".format(
                _privs, name
            )
            return ret

        if __salt__["postgres.privileges_grant"](
            name, object_name, object_type, **kwargs
        ):
            ret["comment"] = "The privilege(s): {} have been granted to {}".format(
                _privs, name
            )
            ret["changes"][name] = "Present"
        else:
            ret["comment"] = "Failed to grant privilege(s): {} to {}".format(
                _privs, name
            )
            ret["result"] = False

    return ret


def absent(
    name,
    object_name,
    object_type,
    privileges=None,
    prepend="public",
    maintenance_db=None,
    user=None,
    db_password=None,
    db_host=None,
    db_port=None,
    db_user=None,
):
    """
    Revoke the requested privilege(s) on the specificed object(s)

    name
        Name of the role whose privileges should be revoked

    object_name
       Name of the object on which the revoke is to be performed

    object_type
       The object type, which can be one of the following:

       - table
       - sequence
       - schema
       - tablespace
       - language
       - database
       - group
       - function

       View permissions should specify `object_type: table`.

    privileges
       Comma separated list of privileges to revoke, from the list below:

       - INSERT
       - CREATE
       - TRUNCATE
       - CONNECT
       - TRIGGER
       - SELECT
       - USAGE
       - TEMPORARY
       - UPDATE
       - EXECUTE
       - REFERENCES
       - DELETE
       - ALL

       :note: privileges should not be set when revoking group membership

    prepend
        Table and Sequence object types live under a schema so this should be
        provided if the object is not under the default `public` schema

    maintenance_db
        The name of the database in which the language is to be installed

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
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "The requested privilege(s) are not set so cannot be revoked",
    }

    privileges = ",".join(privileges) if privileges else None

    kwargs = {
        "privileges": privileges,
        "prepend": prepend,
        "maintenance_db": maintenance_db,
        "runas": user,
        "host": db_host,
        "user": db_user,
        "port": db_port,
        "password": db_password,
    }

    if __salt__["postgres.has_privileges"](name, object_name, object_type, **kwargs):
        _privs = object_name if object_type == "group" else privileges

        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = (
                "The privilege(s): {} are set to be revoked from {}".format(
                    _privs, name
                )
            )
            return ret

        if __salt__["postgres.privileges_revoke"](
            name, object_name, object_type, **kwargs
        ):
            ret["comment"] = "The privilege(s): {} have been revoked from {}".format(
                _privs, name
            )
            ret["changes"][name] = "Absent"
        else:
            ret["comment"] = "Failed to revoke privilege(s): {} from {}".format(
                _privs, name
            )
            ret["result"] = False

    return ret
