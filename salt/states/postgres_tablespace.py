# -*- coding: utf-8 -*-
"""
Management of PostgreSQL tablespace
===================================

A module used to create and manage PostgreSQL tablespaces.

.. code-block:: yaml

    ssd-tablespace:
      postgres_tablespace.present:
        - name: indexes
        - directory: /mnt/ssd-data

.. versionadded:: 2015.8.0

"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
import salt.utils.dictupdate as dictupdate

# Import 3rd-party libs
from salt.ext.six import iteritems


def __virtual__():
    """
    Only load if the postgres module is present and is new enough (has ts funcs)
    """
    if "postgres.tablespace_exists" not in __salt__:
        return (
            False,
            "Unable to load postgres module.  Make sure `postgres.bins_dir` is set.",
        )
    return True


def present(
    name,
    directory,
    options=None,
    owner=None,
    user=None,
    maintenance_db=None,
    db_password=None,
    db_host=None,
    db_port=None,
    db_user=None,
):
    """
    Ensure that the named tablespace is present with the specified properties.
    For more information about all of these options run ``man 7
    create_tablespace``.

    name
        The name of the tablespace to create/manage.

    directory
        The directory where the tablespace will be located, must already exist

    options
        A dictionary of options to specify for the tablespace.
        Currently, the only tablespace options supported are ``seq_page_cost``
        and ``random_page_cost``. Default values are shown in the example below:

        .. code-block:: yaml

            my_space:
              postgres_tablespace.present:
                - directory: /srv/my_tablespace
                - options:
                    seq_page_cost: 1.0
                    random_page_cost: 4.0

    owner
        The database user that will be the owner of the tablespace.
        Defaults to the user executing the command (i.e. the `user` option)

    user
        System user all operations should be performed on behalf of

    maintenance_db
        Database to act on

    db_user
        Database username if different from config or default

    db_password
        User password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "Tablespace {0} is already present".format(name),
    }
    dbargs = {
        "maintenance_db": maintenance_db,
        "runas": user,
        "host": db_host,
        "user": db_user,
        "port": db_port,
        "password": db_password,
    }
    tblspaces = __salt__["postgres.tablespace_list"](**dbargs)
    if name not in tblspaces:
        # not there, create it
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "Tablespace {0} is set to be created".format(name)
            return ret
        if __salt__["postgres.tablespace_create"](
            name, directory, options, owner, **dbargs
        ):
            ret["comment"] = "The tablespace {0} has been created".format(name)
            ret["changes"][name] = "Present"
            return ret

    # already exists, make sure it's got the right config
    if tblspaces[name]["Location"] != directory and not __opts__["test"]:
        ret[
            "comment"
        ] = """Tablespace {0} is not at the right location. This is
            unfixable without dropping and recreating the tablespace.""".format(
            name
        )
        ret["result"] = False
        return ret

    if owner and not tblspaces[name]["Owner"] == owner:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "Tablespace {0} owner to be altered".format(name)
        if (
            __salt__["postgres.tablespace_alter"](name, new_owner=owner)
            and not __opts__["test"]
        ):
            ret["comment"] = "Tablespace {0} owner changed".format(name)
            ret["changes"][name] = {"owner": owner}
            ret["result"] = True

    if options:
        # options comes from postgres as a sort of json(ish) string, but it
        # can't really be parsed out, but it's in a fairly consistent format
        # that we should be able to string check:
        # {seq_page_cost=1.1,random_page_cost=3.9}
        # TODO remove options that exist if possible
        for k, v in iteritems(options):
            # if 'seq_page_cost=1.1' not in '{seq_page_cost=1.1,...}'
            if "{0}={1}".format(k, v) not in tblspaces[name]["Opts"]:
                if __opts__["test"]:
                    ret["result"] = None
                    ret[
                        "comment"
                    ] = """Tablespace {0} options to be
                        altered""".format(
                        name
                    )
                    break  # we know it's going to be altered, no reason to cont
                if __salt__["postgres.tablespace_alter"](name, set_option={k: v}):
                    ret["comment"] = "Tablespace {0} opts changed".format(name)
                    dictupdate.update(ret["changes"], {name: {"options": {k: v}}})
                    ret["result"] = True

    return ret


def absent(
    name,
    user=None,
    maintenance_db=None,
    db_user=None,
    db_password=None,
    db_host=None,
    db_port=None,
):
    """
    Ensure that the named tablespace is absent.

    name
        The name of the tablespace to remove

    user
        System user all operations should be performed on behalf of

    maintenance_db
        Database to act on

    db_user
        Database username if different from config or defaul

    db_password
        User password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default
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
    # check if tablespace exists and remove it
    if __salt__["postgres.tablespace_exists"](name, **db_args):
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "Tablespace {0} is set to be removed".format(name)
            return ret
        if __salt__["postgres.tablespace_remove"](name, **db_args):
            ret["comment"] = "Tablespace {0} has been removed".format(name)
            ret["changes"][name] = "Absent"
            return ret

    # fallback
    ret["comment"] = "Tablespace {0} is not present, so it cannot " "be removed".format(
        name
    )
    return ret
