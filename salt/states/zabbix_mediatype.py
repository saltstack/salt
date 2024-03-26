"""
Management of Zabbix mediatypes.

:codeauthor: Raymond Kuiper <qix@the-wired.net>

"""


def __virtual__():
    """
    Only make these states available if Zabbix module is available.
    """
    if "zabbix.mediatype_create" in __salt__:
        return True
    return (False, "zabbix module could not be loaded")


def present(name, mediatype, **kwargs):
    """
    Creates new mediatype.
    NOTE: This function accepts all standard mediatype properties: keyword argument names differ depending on your
    zabbix version, see:
    https://www.zabbix.com/documentation/3.0/manual/api/reference/host/object#host_inventory

    :param name: name of the mediatype
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        make_new_mediatype:
            zabbix_mediatype.present:
                - name: 'Email'
                - mediatype: 0
                - smtp_server: smtp.example.com
                - smtp_hello: zabbix.example.com
                - smtp_email: zabbix@example.com

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
    comment_mediatype_created = f"Mediatype {name} created."
    comment_mediatype_updated = f"Mediatype {name} updated."
    comment_mediatype_notcreated = f"Unable to create mediatype: {name}. "
    comment_mediatype_exists = f"Mediatype {name} already exists."
    changes_mediatype_created = {
        name: {
            "old": f"Mediatype {name} does not exist.",
            "new": f"Mediatype {name} created.",
        }
    }

    # Zabbix API expects script parameters as a string of arguments separated by newline characters
    if "exec_params" in kwargs:
        if isinstance(kwargs["exec_params"], list):
            kwargs["exec_params"] = "\n".join(kwargs["exec_params"]) + "\n"
        else:
            kwargs["exec_params"] = str(kwargs["exec_params"]) + "\n"

    mediatype_exists = __salt__["zabbix.mediatype_get"](name, **connection_args)

    if mediatype_exists:
        mediatypeobj = mediatype_exists[0]
        mediatypeid = int(mediatypeobj["mediatypeid"])
        update_email = False
        update_email_port = False
        update_email_security = False
        update_email_verify_peer = False
        update_email_verify_host = False
        update_email_auth = False
        update_script = False
        update_script_params = False
        update_sms = False
        update_jabber = False
        update_eztext = False
        update_status = False

        if (
            int(mediatype) == 0
            and "smtp_server" in kwargs
            and "smtp_helo" in kwargs
            and "smtp_email" in kwargs
        ):
            if (
                int(mediatype) != int(mediatypeobj["type"])
                or kwargs["smtp_server"] != mediatypeobj["smtp_server"]
                or kwargs["smtp_email"] != mediatypeobj["smtp_email"]
                or kwargs["smtp_helo"] != mediatypeobj["smtp_helo"]
            ):
                update_email = True

        if int(mediatype) == 0 and "smtp_port" in kwargs:
            if int(kwargs["smtp_port"]) != int(mediatypeobj["smtp_port"]):
                update_email_port = True

        if int(mediatype) == 0 and "smtp_security" in kwargs:
            if int(kwargs["smtp_security"]) != int(mediatypeobj["smtp_security"]):
                update_email_security = True

        if int(mediatype) == 0 and "smtp_verify_peer" in kwargs:
            if int(kwargs["smtp_verify_peer"]) != int(mediatypeobj["smtp_verify_peer"]):
                update_email_verify_peer = True

        if int(mediatype) == 0 and "smtp_verify_host" in kwargs:
            if int(kwargs["smtp_verify_host"]) != int(mediatypeobj["smtp_verify_host"]):
                update_email_verify_host = True

        if (
            int(mediatype) == 0
            and "smtp_authentication" in kwargs
            and "username" in kwargs
            and "passwd" in kwargs
        ):
            if (
                int(kwargs["smtp_authentication"])
                != int(mediatypeobj["smtp_authentication"])
                or kwargs["username"] != mediatypeobj["username"]
                or kwargs["passwd"] != mediatypeobj["passwd"]
            ):
                update_email_auth = True

        if int(mediatype) == 1 and "exec_path" in kwargs:
            if (
                int(mediatype) != int(mediatypeobj["type"])
                or kwargs["exec_path"] != mediatypeobj["exec_path"]
            ):
                update_script = True

        if int(mediatype) == 1 and "exec_params" in kwargs:
            if kwargs["exec_params"] != mediatypeobj["exec_params"]:
                update_script_params = True

        if int(mediatype) == 2 and "gsm_modem" in kwargs:
            if (
                int(mediatype) != int(mediatypeobj["type"])
                or kwargs["gsm_modem"] != mediatypeobj["gsm_modem"]
            ):
                update_sms = True

        if int(mediatype) == 3 and "username" in kwargs and "passwd" in kwargs:
            if (
                int(mediatype) != int(mediatypeobj["type"])
                or kwargs["username"] != mediatypeobj["username"]
                or kwargs["passwd"] != mediatypeobj["passwd"]
            ):
                update_jabber = True

        if (
            int(mediatype) == 100
            and "username" in kwargs
            and "passwd" in kwargs
            and "exec_path" in kwargs
        ):
            if (
                int(mediatype) != int(mediatypeobj["type"])
                or kwargs["username"] != mediatypeobj["username"]
                or kwargs["passwd"] != mediatypeobj["passwd"]
                or kwargs["exec_path"] != mediatypeobj["exec_path"]
            ):
                update_eztext = True

        if "status" in kwargs:
            if int(kwargs["status"]) != int(mediatypeobj["status"]):
                update_status = True

    # Dry run, test=true mode
    if __opts__["test"]:
        if mediatype_exists:
            if update_status:
                ret["result"] = None
                ret["comment"] = comment_mediatype_updated
            else:
                ret["result"] = True
                ret["comment"] = comment_mediatype_exists
        else:
            ret["result"] = None
            ret["comment"] = comment_mediatype_created
        return ret

    error = []

    if mediatype_exists:
        if (
            update_email
            or update_email_port
            or update_email_security
            or update_email_verify_peer
            or update_email_verify_host
            or update_email_auth
            or update_script
            or update_script_params
            or update_sms
            or update_jabber
            or update_eztext
            or update_status
        ):
            ret["result"] = True
            ret["comment"] = comment_mediatype_updated

            if update_email:
                updated_email = __salt__["zabbix.mediatype_update"](
                    mediatypeid,
                    type=mediatype,
                    smtp_server=kwargs["smtp_server"],
                    smtp_helo=kwargs["smtp_helo"],
                    smtp_email=kwargs["smtp_email"],
                    **connection_args,
                )
                if "error" in updated_email:
                    error.append(updated_email["error"])
                else:
                    ret["changes"]["smtp_server"] = kwargs["smtp_server"]
                    ret["changes"]["smtp_helo"] = kwargs["smtp_helo"]
                    ret["changes"]["smtp_email"] = kwargs["smtp_email"]

            if update_email_port:
                updated_email_port = __salt__["zabbix.mediatype_update"](
                    mediatypeid, smtp_port=kwargs["smtp_port"], **connection_args
                )
                if "error" in updated_email_port:
                    error.append(updated_email_port["error"])
                else:
                    ret["changes"]["smtp_port"] = kwargs["smtp_port"]

            if update_email_security:
                updated_email_security = __salt__["zabbix.mediatype_update"](
                    mediatypeid,
                    smtp_security=kwargs["smtp_security"],
                    **connection_args,
                )
                if "error" in updated_email_security:
                    error.append(updated_email_security["error"])
                else:
                    ret["changes"]["smtp_security"] = kwargs["smtp_security"]

            if update_email_verify_peer:
                updated_email_verify_peer = __salt__["zabbix.mediatype_update"](
                    mediatypeid,
                    smtp_verify_peer=kwargs["smtp_verify_peer"],
                    **connection_args,
                )
                if "error" in updated_email_verify_peer:
                    error.append(updated_email_verify_peer["error"])
                else:
                    ret["changes"]["smtp_verify_peer"] = kwargs["smtp_verify_peer"]

            if update_email_verify_host:
                updated_email_verify_host = __salt__["zabbix.mediatype_update"](
                    mediatypeid,
                    smtp_verify_host=kwargs["smtp_verify_host"],
                    **connection_args,
                )
                if "error" in updated_email_verify_host:
                    error.append(updated_email_verify_host["error"])
                else:
                    ret["changes"]["smtp_verify_host"] = kwargs["smtp_verify_host"]

            if update_email_auth:
                updated_email_auth = __salt__["zabbix.mediatype_update"](
                    mediatypeid,
                    username=kwargs["username"],
                    passwd=kwargs["passwd"],
                    smtp_authentication=kwargs["smtp_authentication"],
                    **connection_args,
                )
                if "error" in updated_email_auth:
                    error.append(updated_email_auth["error"])
                else:
                    ret["changes"]["smtp_authentication"] = kwargs[
                        "smtp_authentication"
                    ]
                    ret["changes"]["username"] = kwargs["username"]

            if update_script:
                updated_script = __salt__["zabbix.mediatype_update"](
                    mediatypeid,
                    type=mediatype,
                    exec_path=kwargs["exec_path"],
                    **connection_args,
                )
                if "error" in updated_script:
                    error.append(updated_script["error"])
                else:
                    ret["changes"]["exec_path"] = kwargs["exec_path"]

            if update_script_params:
                updated_script_params = __salt__["zabbix.mediatype_update"](
                    mediatypeid, exec_params=kwargs["exec_params"], **connection_args
                )
                if "error" in updated_script_params:
                    error.append(updated_script["error"])
                else:
                    ret["changes"]["exec_params"] = kwargs["exec_params"]

            if update_sms:
                updated_sms = __salt__["zabbix.mediatype_update"](
                    mediatypeid,
                    type=mediatype,
                    gsm_modem=kwargs["gsm_modem"],
                    **connection_args,
                )
                if "error" in updated_sms:
                    error.append(updated_sms["error"])
                else:
                    ret["changes"]["gsm_modem"] = kwargs["gsm_modem"]

            if update_jabber:
                updated_jabber = __salt__["zabbix.mediatype_update"](
                    mediatypeid,
                    type=mediatype,
                    username=kwargs["username"],
                    passwd=kwargs["passwd"],
                    **connection_args,
                )
                if "error" in updated_jabber:
                    error.append(updated_jabber["error"])
                else:
                    ret["changes"]["username"] = kwargs["username"]

            if update_eztext:
                updated_eztext = __salt__["zabbix.mediatype_update"](
                    mediatypeid,
                    type=mediatype,
                    username=kwargs["username"],
                    passwd=kwargs["passwd"],
                    exec_path=kwargs["exec_path"],
                    **connection_args,
                )
                if "error" in updated_eztext:
                    error.append(updated_eztext["error"])
                else:
                    ret["changes"]["username"] = kwargs["username"]
                    ret["changes"]["exec_path"] = kwargs["exec_path"]

            if update_status:
                updated_status = __salt__["zabbix.mediatype_update"](
                    mediatypeid, status=kwargs["status"], **connection_args
                )
                if "error" in updated_status:
                    error.append(updated_status["error"])
                else:
                    ret["changes"]["status"] = kwargs["status"]

        else:
            ret["result"] = True
            ret["comment"] = comment_mediatype_exists
    else:
        mediatype_create = __salt__["zabbix.mediatype_create"](
            name, mediatype, **kwargs
        )

        if "error" not in mediatype_create:
            ret["result"] = True
            ret["comment"] = comment_mediatype_created
            ret["changes"] = changes_mediatype_created
        else:
            ret["result"] = False
            ret["comment"] = comment_mediatype_notcreated + str(
                mediatype_create["error"]
            )

    # error detected
    if error:
        ret["changes"] = {}
        ret["result"] = False
        ret["comment"] = str(error)

    return ret


def absent(name, **kwargs):
    """
    Ensures that the mediatype does not exist, eventually deletes the mediatype.

    :param name: name of the mediatype
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        delete_mediatype:
            zabbix_mediatype.absent:
                - name: 'Email'
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
    comment_mediatype_deleted = f"Mediatype {name} deleted."
    comment_mediatype_notdeleted = f"Unable to delete mediatype: {name}. "
    comment_mediatype_notexists = f"Mediatype {name} does not exist."
    changes_mediatype_deleted = {
        name: {
            "old": f"Mediatype {name} exists.",
            "new": f"Mediatype {name} deleted.",
        }
    }

    mediatype_exists = __salt__["zabbix.mediatype_get"](name, **connection_args)

    # Dry run, test=true mode
    if __opts__["test"]:
        if not mediatype_exists:
            ret["result"] = True
            ret["comment"] = comment_mediatype_notexists
        else:
            ret["result"] = None
            ret["comment"] = comment_mediatype_deleted
        return ret

    if not mediatype_exists:
        ret["result"] = True
        ret["comment"] = comment_mediatype_notexists
    else:
        try:
            mediatypeid = mediatype_exists[0]["mediatypeid"]
            mediatype_delete = __salt__["zabbix.mediatype_delete"](
                mediatypeid, **connection_args
            )
        except KeyError:
            mediatype_delete = False

        if mediatype_delete and "error" not in mediatype_delete:
            ret["result"] = True
            ret["comment"] = comment_mediatype_deleted
            ret["changes"] = changes_mediatype_deleted
        else:
            ret["result"] = False
            ret["comment"] = comment_mediatype_notdeleted + str(
                mediatype_delete["error"]
            )

    return ret
