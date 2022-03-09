"""
Management of Zabbix usermacros.
:codeauthor: Raymond Kuiper <qix@the-wired.net>

"""


def __virtual__():
    """
    Only make these states available if Zabbix module is available.
    """
    if "zabbix.usermacro_create" in __salt__:
        return True
    return (False, "zabbix module could not be loaded")


def present(name, value, hostid=None, **kwargs):
    """
    Creates a new usermacro.

    :param name: name of the usermacro
    :param value: value of the usermacro
    :param hostid: id's of the hosts to apply the usermacro on, if missing a global usermacro is assumed.

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        override host usermacro:
            zabbix_usermacro.present:
                - name: '{$SNMP_COMMUNITY}''
                - value: 'public'
                - hostid: 21

    """
    connection_args = {}
    if "_connection_user" in kwargs:
        connection_args["_connection_user"] = kwargs["_connection_user"]
    if "_connection_password" in kwargs:
        connection_args["_connection_password"] = kwargs["_connection_password"]
    if "_connection_url" in kwargs:
        connection_args["_connection_url"] = kwargs["_connection_url"]

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    # Comment and change messages
    if hostid:
        comment_usermacro_created = "Usermacro {} created on hostid {}.".format(
            name, hostid
        )
        comment_usermacro_updated = "Usermacro {} updated on hostid {}.".format(
            name, hostid
        )
        comment_usermacro_notcreated = (
            "Unable to create usermacro: {} on hostid {}. ".format(name, hostid)
        )
        comment_usermacro_exists = "Usermacro {} already exists on hostid {}.".format(
            name, hostid
        )
        changes_usermacro_created = {
            name: {
                "old": "Usermacro {} does not exist on hostid {}.".format(name, hostid),
                "new": "Usermacro {} created on hostid {}.".format(name, hostid),
            }
        }
    else:
        comment_usermacro_created = "Usermacro {} created.".format(name)
        comment_usermacro_updated = "Usermacro {} updated.".format(name)
        comment_usermacro_notcreated = "Unable to create usermacro: {}. ".format(name)
        comment_usermacro_exists = "Usermacro {} already exists.".format(name)
        changes_usermacro_created = {
            name: {
                "old": "Usermacro {} does not exist.".format(name),
                "new": "Usermacro {} created.".format(name),
            }
        }

    # Zabbix API expects script parameters as a string of arguments separated by newline characters
    if "exec_params" in kwargs:
        if isinstance(kwargs["exec_params"], list):
            kwargs["exec_params"] = "\n".join(kwargs["exec_params"]) + "\n"
        else:
            kwargs["exec_params"] = str(kwargs["exec_params"]) + "\n"
    if hostid:
        usermacro_exists = __salt__["zabbix.usermacro_get"](
            name, hostids=hostid, **connection_args
        )
    else:
        usermacro_exists = __salt__["zabbix.usermacro_get"](
            name, globalmacro=True, **connection_args
        )

    if usermacro_exists:
        usermacroobj = usermacro_exists[0]
        if hostid:
            usermacroid = int(usermacroobj["hostmacroid"])
        else:
            usermacroid = int(usermacroobj["globalmacroid"])
        update_value = False

        if str(value) != usermacroobj["value"]:
            update_value = True

    # Dry run, test=true mode
    if __opts__["test"]:
        if usermacro_exists:
            if update_value:
                ret["result"] = None
                ret["comment"] = comment_usermacro_updated
            else:
                ret["result"] = True
                ret["comment"] = comment_usermacro_exists
        else:
            ret["result"] = None
            ret["comment"] = comment_usermacro_created
        return ret

    error = []

    if usermacro_exists:
        if update_value:
            ret["result"] = True
            ret["comment"] = comment_usermacro_updated

            if hostid:
                updated_value = __salt__["zabbix.usermacro_update"](
                    usermacroid, value=value, **connection_args
                )
            else:
                updated_value = __salt__["zabbix.usermacro_updateglobal"](
                    usermacroid, value=value, **connection_args
                )
            if not isinstance(updated_value, int):
                if "error" in updated_value:
                    error.append(updated_value["error"])
                else:
                    ret["changes"]["value"] = value
        else:
            ret["result"] = True
            ret["comment"] = comment_usermacro_exists
    else:
        if hostid:
            usermacro_create = __salt__["zabbix.usermacro_create"](
                name, value, hostid, **connection_args
            )
        else:
            usermacro_create = __salt__["zabbix.usermacro_createglobal"](
                name, value, **connection_args
            )

        if "error" not in usermacro_create:
            ret["result"] = True
            ret["comment"] = comment_usermacro_created
            ret["changes"] = changes_usermacro_created
        else:
            ret["result"] = False
            ret["comment"] = comment_usermacro_notcreated + str(
                usermacro_create["error"]
            )

    # error detected
    if error:
        ret["changes"] = {}
        ret["result"] = False
        ret["comment"] = str(error)

    return ret


def absent(name, hostid=None, **kwargs):
    """
    Ensures that the mediatype does not exist, eventually deletes the mediatype.

    :param name: name of the usermacro
    :param hostid: id's of the hosts to apply the usermacro on, if missing a global usermacro is assumed.

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        delete_usermacro:
            zabbix_usermacro.absent:
                - name: '{$SNMP_COMMUNITY}'

    """
    connection_args = {}
    if "_connection_user" in kwargs:
        connection_args["_connection_user"] = kwargs["_connection_user"]
    if "_connection_password" in kwargs:
        connection_args["_connection_password"] = kwargs["_connection_password"]
    if "_connection_url" in kwargs:
        connection_args["_connection_url"] = kwargs["_connection_url"]

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    # Comment and change messages
    if hostid:
        comment_usermacro_deleted = "Usermacro {} deleted from hostid {}.".format(
            name, hostid
        )
        comment_usermacro_notdeleted = (
            "Unable to delete usermacro: {} from hostid {}.".format(name, hostid)
        )
        comment_usermacro_notexists = (
            "Usermacro {} does not exist on hostid {}.".format(name, hostid)
        )
        changes_usermacro_deleted = {
            name: {
                "old": "Usermacro {} exists on hostid {}.".format(name, hostid),
                "new": "Usermacro {} deleted from {}.".format(name, hostid),
            }
        }
    else:
        comment_usermacro_deleted = "Usermacro {} deleted.".format(name)
        comment_usermacro_notdeleted = "Unable to delete usermacro: {}.".format(name)
        comment_usermacro_notexists = "Usermacro {} does not exist.".format(name)
        changes_usermacro_deleted = {
            name: {
                "old": "Usermacro {} exists.".format(name),
                "new": "Usermacro {} deleted.".format(name),
            }
        }
    if hostid:
        usermacro_exists = __salt__["zabbix.usermacro_get"](
            name, hostids=hostid, **connection_args
        )
    else:
        usermacro_exists = __salt__["zabbix.usermacro_get"](
            name, globalmacro=True, **connection_args
        )

    # Dry run, test=true mode
    if __opts__["test"]:
        if not usermacro_exists:
            ret["result"] = True
            ret["comment"] = comment_usermacro_notexists
        else:
            ret["result"] = None
            ret["comment"] = comment_usermacro_deleted
        return ret

    if not usermacro_exists:
        ret["result"] = True
        ret["comment"] = comment_usermacro_notexists
    else:
        try:
            if hostid:
                usermacroid = usermacro_exists[0]["hostmacroid"]
                usermacro_delete = __salt__["zabbix.usermacro_delete"](
                    usermacroid, **connection_args
                )
            else:
                usermacroid = usermacro_exists[0]["globalmacroid"]
                usermacro_delete = __salt__["zabbix.usermacro_deleteglobal"](
                    usermacroid, **connection_args
                )
        except KeyError:
            usermacro_delete = False

        if usermacro_delete and "error" not in usermacro_delete:
            ret["result"] = True
            ret["comment"] = comment_usermacro_deleted
            ret["changes"] = changes_usermacro_deleted
        else:
            ret["result"] = False
            ret["comment"] = comment_usermacro_notdeleted + str(
                usermacro_delete["error"]
            )

    return ret
