"""
Management of Zabbix users.

:codeauthor: Jiri Kotlin <jiri.kotlin@ultimum.io>


"""

import logging
from copy import deepcopy

import salt.utils.json
from salt.exceptions import SaltException
from salt.utils.versions import Version

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only make these states available if Zabbix module is available.
    """
    if "zabbix.user_create" in __salt__:
        return True
    return (False, "zabbix module could not be loaded")


def admin_password_present(name, password=None, **kwargs):
    """
    Initial change of Zabbix Admin password to password taken from one of the sources (only the most prioritized one):
        1. 'password' parameter
        2. '_connection_password' parameter
        3. pillar 'zabbix.password' setting

    1) Tries to log in as Admin with password found in state password parameter or _connection_password
       or pillar or default zabbix password in this precise order, if any of them is present.
    2) If one of above passwords matches, it tries to change the password to the most prioritized one.
    3) If not able to connect with any password then it fails.

    :param name: Just a name of state
    :param password: Optional - desired password for Admin to be set
    :param _connection_user: Optional - Ignored in this state (always assumed 'Admin')
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        # password taken from pillar or _connection_password
        zabbix-admin-password:
            zabbix_user.admin_password_present

        # directly set password
        zabbix-admin-password:
            zabbix_user.admin_password_present:
                - password: SECRET_PASS
    """
    login_error_messages = [
        "Login name or password is incorrect",
        "Incorrect user name or password",
    ]
    dry_run = __opts__["test"]
    default_zabbix_user = "Admin"
    default_zabbix_password = "zabbix"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    passwords = []
    connection_args = {}
    connection_args["_connection_user"] = default_zabbix_user
    if "_connection_url" in kwargs:
        connection_args["_connection_url"] = kwargs["_connection_url"]

    config_password = __salt__["config.option"]("zabbix.password", None)
    if config_password:
        passwords.append(config_password)
    if "_connection_password" in kwargs:
        passwords.append(kwargs["_connection_password"])
    if password:
        passwords.append(password)

    # get unique list in preserved order and reverse it
    seen = set()
    unique_passwords = [str(x) for x in passwords if x not in seen and not seen.add(x)]
    unique_passwords.reverse()

    if not unique_passwords:
        ret["comment"] = (
            "Could not find any Zabbix Admin password setting! See documentation."
        )
        return ret
    else:
        desired_password = unique_passwords[0]

    unique_passwords.append(default_zabbix_password)

    for pwd in unique_passwords:
        connection_args["_connection_password"] = pwd
        try:
            user_get = __salt__["zabbix.user_get"](
                default_zabbix_user, **connection_args
            )
        except SaltException as err:
            if all([x not in str(err) for x in login_error_messages]):
                raise
            user_get = False
        if user_get:
            if pwd == desired_password:
                ret["result"] = True
                ret["comment"] = "Admin password is correct."
                return ret
            else:
                break

    if user_get:
        if not dry_run:
            user_update = __salt__["zabbix.user_update"](
                user_get[0]["userid"], passwd=desired_password, **connection_args
            )
            if user_update:
                ret["result"] = True
                ret["changes"]["passwd"] = "changed to '" + str(desired_password) + "'"
        else:
            ret["result"] = None
            ret["comment"] = (
                "Password for user "
                + str(default_zabbix_user)
                + " updated to '"
                + str(desired_password)
                + "'"
            )

    return ret


def present(alias, passwd, usrgrps, medias=None, password_reset=False, **kwargs):
    """
    Ensures that the user exists, eventually creates new user.
    NOTE: use argument firstname instead of name to not mess values with name from salt sls.

    .. versionadded:: 2016.3.0

    :param alias: user alias
    :param passwd: user's password
    :param usrgrps: user groups to add the user to
    :param medias: Optional - user's medias to create
    :param password_reset: whether or not to reset password at update
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)
    :param firstname: string with firstname of the user, use 'firstname' instead of 'name' parameter to not mess \
    with value supplied from Salt sls file.

    .. code-block:: yaml

        make_user:
            zabbix_user.present:
                - alias: George
                - passwd: donottellanyonE@456x
                - password_reset: True
                - usrgrps:
                    - 13
                    - 7
                - medias:
                    - me@example.com:
                        - mediatype: mail
                        - period: '1-7,00:00-24:00'
                        - severity: NIWAHD
                    - make_jabber:
                        - active: true
                        - mediatype: jabber
                        - period: '1-5,08:00-19:00'
                        - sendto: jabbera@example.com
                    - text_me_morning_disabled:
                        - active: false
                        - mediatype: sms
                        - period: '1-5,09:30-10:00'
                        - severity: D
                        - sendto: '+42032132588568'

    """
    if medias is None:
        medias = []
    usrgrps = [int(x) for x in usrgrps]
    connection_args = {}
    if "_connection_user" in kwargs:
        connection_args["_connection_user"] = kwargs["_connection_user"]
    if "_connection_password" in kwargs:
        connection_args["_connection_password"] = kwargs["_connection_password"]
    if "_connection_url" in kwargs:
        connection_args["_connection_url"] = kwargs["_connection_url"]

    ret = {"name": alias, "changes": {}, "result": False, "comment": ""}

    # Comment and change messages
    comment_user_created = f"User {alias} created."
    comment_user_updated = f"User {alias} updated."
    comment_user_notcreated = f"Unable to create user: {alias}. "
    comment_user_exists = f"User {alias} already exists."
    changes_user_created = {
        alias: {
            "old": f"User {alias} does not exist.",
            "new": f"User {alias} created.",
        }
    }

    def _media_format(medias_data):
        """
        Formats medias from SLS file into valid JSON usable for zabbix API.
        Completes JSON with default values.

        :param medias_data: list of media data from SLS file

        """
        if not medias_data:
            return list()
        medias_json = salt.utils.json.loads(salt.utils.json.dumps(medias_data))
        medias_attr = ("active", "mediatype", "period", "severity", "sendto")
        media_type = {"mail": 1, "jabber": 2, "sms": 3}
        media_severities = ("D", "H", "A", "W", "I", "N")

        medias_dict = dict()
        for media in medias_json:
            for med in media:
                medias_dict[med] = dict()
                for medattr in media[med]:
                    for key, value in medattr.items():
                        if key in medias_attr:
                            medias_dict[med][key] = value

        medias_list = list()
        for key, value in medias_dict.items():
            # Load media values or default values
            active = "0" if str(value.get("active", "true")).lower() == "true" else "1"
            mediatype_sls = str(value.get("mediatype", "mail")).lower()
            mediatypeid = str(media_type.get(mediatype_sls, 1))
            period = value.get("period", "1-7,00:00-24:00")
            sendto = value.get("sendto", key)

            severity_sls = value.get("severity", "HD")
            severity_bin = ""
            for sev in media_severities:
                if sev in severity_sls:
                    severity_bin += "1"
                else:
                    severity_bin += "0"
            severity = str(int(severity_bin, 2))

            medias_list.append(
                {
                    "active": active,
                    "mediatypeid": mediatypeid,
                    "period": period,
                    "sendto": sendto,
                    "severity": severity,
                }
            )
        return medias_list

    user_exists = __salt__["zabbix.user_exists"](alias, **connection_args)
    zabbix_version = __salt__["zabbix.apiinfo_version"](**connection_args)

    if user_exists:
        user = __salt__["zabbix.user_get"](alias, **connection_args)[0]
        userid = user["userid"]

        update_usrgrps = False
        update_medias = False

        usergroups = deepcopy(user.get("usrgrps", []))
        cur_usrgrps = list()

        for usergroup in usergroups:
            cur_usrgrps.append(int(usergroup["usrgrpid"]))

        if set(cur_usrgrps) != set(usrgrps):
            update_usrgrps = True

        user_medias = user.get("medias", [])
        medias_formated = _media_format(medias)
        log.debug(user_medias)
        log.debug(medias_formated)

        if user_medias:
            user_medias_copy = deepcopy(user_medias)
            for user_med in user_medias_copy:
                user_med.pop("userid")
                user_med.pop("mediaid")
            media_diff = [x for x in medias_formated if x not in user_medias_copy] + [
                y for y in user_medias_copy if y not in medias_formated
            ]
            if media_diff:
                update_medias = True
        elif not user_medias and medias:
            update_medias = True

    # Dry run, test=true mode
    if __opts__["test"]:
        if user_exists:
            if update_usrgrps or password_reset or update_medias:
                ret["result"] = None
                ret["comment"] = comment_user_updated
            else:
                ret["result"] = True
                ret["comment"] = comment_user_exists
        else:
            ret["result"] = None
            ret["comment"] = comment_user_created

    error = []

    if user_exists:
        ret["result"] = True
        if update_usrgrps or password_reset or update_medias:
            ret["comment"] = comment_user_updated

            if Version(zabbix_version) > Version("3.4"):
                updates = deepcopy(connection_args)
                if update_usrgrps:
                    updates["usrgrps"] = usrgrps
                if password_reset:
                    updates["passwd"] = passwd
                if update_medias:
                    updates["medias"] = medias_formated
                result = __salt__["zabbix.user_update"](userid, **updates)

                new_user = __salt__["zabbix.user_get"](alias, **connection_args)[0]

                if "error" in result:
                    error.append(result["error"])
                else:
                    if update_usrgrps:
                        ret["changes"]["usrgrps"] = str(new_user["usrgrps"])
                    if update_medias:
                        ret["changes"]["medias"] = str(medias_formated)
                    if password_reset:
                        ret["changes"]["passwd"] = "updated"

                cur_usrgrps = list()
                for usergroup in new_user["usrgrps"]:
                    cur_usrgrps.append(int(usergroup["usrgrpid"]))

                usrgrp_diff = list(set(usrgrps) - set(cur_usrgrps))

                if usrgrp_diff and update_usrgrps:
                    error.append(f"Unable to update group(s): {usrgrp_diff}")

            else:
                if update_usrgrps:
                    __salt__["zabbix.user_update"](
                        userid, usrgrps=usrgrps, **connection_args
                    )
                    updated_groups = __salt__["zabbix.usergroup_get"](
                        userids=userid, **connection_args
                    )

                    cur_usrgrps = list()
                    for usergroup in updated_groups:
                        cur_usrgrps.append(int(usergroup["usrgrpid"]))

                    usrgrp_diff = list(set(usrgrps) - set(cur_usrgrps))

                    if usrgrp_diff:
                        error.append(f"Unable to update group(s): {usrgrp_diff}")

                    ret["changes"]["usrgrps"] = str(updated_groups)

                if password_reset:
                    updated_password = __salt__["zabbix.user_update"](
                        userid, passwd=passwd, **connection_args
                    )
                    if "error" in updated_password:
                        error.append(updated_groups["error"])
                    else:
                        ret["changes"]["passwd"] = "updated"

                if update_medias:
                    for user_med in user_medias:
                        deletedmed = __salt__["zabbix.user_deletemedia"](
                            user_med["mediaid"], **connection_args
                        )
                        if "error" in deletedmed:
                            error.append(deletedmed["error"])

                    for media in medias_formated:
                        updatemed = __salt__["zabbix.user_addmedia"](
                            userids=userid,
                            active=media["active"],
                            mediatypeid=media["mediatypeid"],
                            period=media["period"],
                            sendto=media["sendto"],
                            severity=media["severity"],
                            **connection_args,
                        )

                        if "error" in updatemed:
                            error.append(updatemed["error"])

                    ret["changes"]["medias"] = str(medias_formated)

        else:
            ret["comment"] = comment_user_exists
    else:
        user_create = __salt__["zabbix.user_create"](alias, passwd, usrgrps, **kwargs)

        if "error" not in user_create:
            ret["result"] = True
            ret["comment"] = comment_user_created
            ret["changes"] = changes_user_created
        else:
            ret["result"] = False
            ret["comment"] = comment_user_notcreated + str(user_create["error"])

    # error detected
    if error:
        ret["changes"] = {}
        ret["result"] = False
        ret["comment"] = str(error)

    return ret


def absent(name, **kwargs):
    """
    Ensures that the user does not exist, eventually delete user.

    .. versionadded:: 2016.3.0

    :param name: user alias
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        George:
            zabbix_user.absent

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
    comment_user_deleted = f"USer {name} deleted."
    comment_user_notdeleted = f"Unable to delete user: {name}. "
    comment_user_notexists = f"User {name} does not exist."
    changes_user_deleted = {
        name: {
            "old": f"User {name} exists.",
            "new": f"User {name} deleted.",
        }
    }

    user_get = __salt__["zabbix.user_get"](name, **connection_args)

    # Dry run, test=true mode
    if __opts__["test"]:
        if not user_get:
            ret["result"] = True
            ret["comment"] = comment_user_notexists
        else:
            ret["result"] = None
            ret["comment"] = comment_user_deleted
            ret["changes"] = changes_user_deleted

    if not user_get:
        ret["result"] = True
        ret["comment"] = comment_user_notexists
    else:
        try:
            userid = user_get[0]["userid"]
            user_delete = __salt__["zabbix.user_delete"](userid, **connection_args)
        except KeyError:
            user_delete = False

        if user_delete and "error" not in user_delete:
            ret["result"] = True
            ret["comment"] = comment_user_deleted
            ret["changes"] = changes_user_deleted
        else:
            ret["result"] = False
            ret["comment"] = comment_user_notdeleted + str(user_delete["error"])

    return ret
