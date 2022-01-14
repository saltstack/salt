"""
Management of user accounts.
============================

The user module is used to create and manage user settings, users can be set
as either absent or present

.. code-block:: yaml

    fred:
      user.present:
        - fullname: Fred Jones
        - shell: /bin/zsh
        - home: /home/fred
        - uid: 4000
        - gid: 4000
        - groups:
          - wheel
          - storage
          - games

    testuser:
      user.absent
"""

import logging
import os

import salt.utils.data
import salt.utils.dateutils
import salt.utils.platform
import salt.utils.user
import salt.utils.versions
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def _group_changes(cur, wanted, remove=False):
    """
    Determine if the groups need to be changed
    """
    old = set(cur)
    new = set(wanted)
    if (remove and old != new) or (not remove and not new.issubset(old)):
        return True
    return False


def _changes(
    name,
    uid=None,
    gid=None,
    groups=None,
    optional_groups=None,
    remove_groups=True,
    home=None,
    createhome=True,
    password=None,
    enforce_password=True,
    empty_password=False,
    shell=None,
    fullname="",
    roomnumber="",
    workphone="",
    homephone="",
    other="",
    loginclass=None,
    date=None,
    mindays=0,
    maxdays=999999,
    inactdays=0,
    warndays=7,
    expire=None,
    win_homedrive=None,
    win_profile=None,
    win_logonscript=None,
    win_description=None,
    allow_uid_change=False,
    allow_gid_change=False,
):
    """
    Return a dict of the changes required for a user if the user is present,
    otherwise return False.

    Updated in 2015.8.0 to include support for windows homedrive, profile,
    logonscript, and description fields.

    Updated in 2014.7.0 to include support for shadow attributes, all
    attributes supported as integers only.
    """

    if "shadow.info" in __salt__:
        lshad = __salt__["shadow.info"](name)

    lusr = __salt__["user.info"](name)
    if not lusr:
        return False

    change = {}
    if groups is None:
        groups = lusr["groups"]
    wanted_groups = sorted(set((groups or []) + (optional_groups or [])))
    if uid and lusr["uid"] != uid:
        change["uid"] = uid
    if gid is not None and lusr["gid"] not in (gid, __salt__["file.group_to_gid"](gid)):
        change["gid"] = gid
    default_grp = __salt__["file.gid_to_group"](gid if gid is not None else lusr["gid"])
    old_default_grp = __salt__["file.gid_to_group"](lusr["gid"])
    # Remove the default group from the list for comparison purposes.
    if default_grp in lusr["groups"]:
        lusr["groups"].remove(default_grp)
    # If the group is being changed, make sure that the old primary group is
    # also removed from the list. Otherwise, if a user's gid is being changed
    # and their old primary group is reassigned as an additional group, Salt
    # will not properly detect the need for the change.
    if old_default_grp != default_grp and old_default_grp in lusr["groups"]:
        lusr["groups"].remove(old_default_grp)
    # If there's a group by the same name as the user, remove it from the list
    # for comparison purposes.
    if name in lusr["groups"] and name not in wanted_groups:
        lusr["groups"].remove(name)
    # Remove default group from wanted_groups, as this requirement is
    # already met
    if default_grp in wanted_groups:
        wanted_groups.remove(default_grp)
    if _group_changes(lusr["groups"], wanted_groups, remove_groups):
        change["groups"] = wanted_groups
    if home and lusr["home"] != home:
        change["home"] = home
    if createhome:
        newhome = home if home else lusr["home"]
        if newhome is not None and not os.path.isdir(newhome):
            change["homeDoesNotExist"] = newhome
    if shell and lusr["shell"] != shell:
        change["shell"] = shell
    if "shadow.info" in __salt__ and "shadow.default_hash" in __salt__:
        if password and not empty_password:
            default_hash = __salt__["shadow.default_hash"]()
            if (
                lshad["passwd"] == default_hash
                or lshad["passwd"] != default_hash
                and enforce_password
            ):
                if lshad["passwd"] != password:
                    change["passwd"] = password
        if empty_password and lshad["passwd"] != "":
            change["empty_password"] = True
        if date is not None and lshad["lstchg"] != date:
            change["date"] = date
        if mindays is not None and lshad["min"] != mindays:
            change["mindays"] = mindays
        if maxdays is not None and lshad["max"] != maxdays:
            change["maxdays"] = maxdays
        if inactdays is not None and lshad["inact"] != inactdays:
            change["inactdays"] = inactdays
        if warndays is not None and lshad["warn"] != warndays:
            change["warndays"] = warndays
        if expire and lshad["expire"] != expire:
            change["expire"] = expire
    elif "shadow.info" in __salt__ and salt.utils.platform.is_windows():
        if (
            expire
            and expire != -1
            and salt.utils.dateutils.strftime(lshad["expire"])
            != salt.utils.dateutils.strftime(expire)
        ):
            change["expire"] = expire

    # GECOS fields
    fullname = salt.utils.data.decode(fullname)
    lusr["fullname"] = salt.utils.data.decode(lusr["fullname"])
    if fullname is not None and lusr["fullname"] != fullname:
        change["fullname"] = fullname
    if win_homedrive and lusr["homedrive"] != win_homedrive:
        change["win_homedrive"] = win_homedrive
    if win_profile and lusr["profile"] != win_profile:
        change["win_profile"] = win_profile
    if win_logonscript and lusr["logonscript"] != win_logonscript:
        change["win_logonscript"] = win_logonscript
    if win_description and lusr["description"] != win_description:
        change["win_description"] = win_description

    # MacOS doesn't have full GECOS support, so check for the "ch" functions
    # and ignore these parameters if these functions do not exist.
    if "user.chroomnumber" in __salt__ and roomnumber is not None:
        roomnumber = salt.utils.data.decode(roomnumber)
        lusr["roomnumber"] = salt.utils.data.decode(lusr["roomnumber"])
        if lusr["roomnumber"] != roomnumber:
            change["roomnumber"] = roomnumber
    if "user.chworkphone" in __salt__ and workphone is not None:
        workphone = salt.utils.data.decode(workphone)
        lusr["workphone"] = salt.utils.data.decode(lusr["workphone"])
        if lusr["workphone"] != workphone:
            change["workphone"] = workphone
    if "user.chhomephone" in __salt__ and homephone is not None:
        homephone = salt.utils.data.decode(homephone)
        lusr["homephone"] = salt.utils.data.decode(lusr["homephone"])
        if lusr["homephone"] != homephone:
            change["homephone"] = homephone
    if "user.chother" in __salt__ and other is not None:
        other = salt.utils.data.decode(other)
        lusr["other"] = salt.utils.data.decode(lusr["other"])
        if lusr["other"] != other:
            change["other"] = other
    # OpenBSD/FreeBSD login class
    if __grains__["kernel"] in ("OpenBSD", "FreeBSD"):
        if loginclass:
            if __salt__["user.get_loginclass"](name) != loginclass:
                change["loginclass"] = loginclass

    errors = []
    if not allow_uid_change and "uid" in change:
        errors.append(
            "Changing uid ({} -> {}) not permitted, set allow_uid_change to "
            "True to force this change. Note that this will not change file "
            "ownership.".format(lusr["uid"], uid)
        )
    if not allow_gid_change and "gid" in change:
        errors.append(
            "Changing gid ({} -> {}) not permitted, set allow_gid_change to "
            "True to force this change. Note that this will not change file "
            "ownership.".format(lusr["gid"], gid)
        )
    if errors:
        raise CommandExecutionError(
            "Encountered error checking for needed changes", info=errors
        )

    return change


def present(
    name,
    uid=None,
    gid=None,
    usergroup=None,
    groups=None,
    optional_groups=None,
    remove_groups=True,
    home=None,
    createhome=True,
    password=None,
    hash_password=False,
    enforce_password=True,
    empty_password=False,
    shell=None,
    unique=True,
    system=False,
    fullname=None,
    roomnumber=None,
    workphone=None,
    homephone=None,
    other=None,
    loginclass=None,
    date=None,
    mindays=None,
    maxdays=None,
    inactdays=None,
    warndays=None,
    expire=None,
    win_homedrive=None,
    win_profile=None,
    win_logonscript=None,
    win_description=None,
    nologinit=False,
    allow_uid_change=False,
    allow_gid_change=False,
):
    """
    Ensure that the named user is present with the specified properties

    name
        The name of the user to manage

    uid
        The user id to assign. If not specified, and the user does not exist,
        then the next available uid will be assigned.

    gid
        The id of the default group to assign to the user. Either a group name
        or gid can be used. If not specified, and the user does not exist, then
        the next available gid will be assigned.

    allow_uid_change : False
        Set to ``True`` to allow the state to update the uid.

        .. versionadded:: 2018.3.1

    allow_gid_change : False
        Set to ``True`` to allow the state to update the gid.

        .. versionadded:: 2018.3.1

    usergroup
        If True, a group with the same name as the user will be created. If
        False, a group with the same name as the user will not be created. The
        default is distribution-specific. See the USERGROUPS_ENAB section of
        the login.defs(5) man page.

        .. note::
            Only supported on GNU/Linux distributions

        .. versionadded:: 3001

    groups
        A list of groups to assign the user to, pass a list object. If a group
        specified here does not exist on the minion, the state will fail.
        If set to the empty list, the user will be removed from all groups
        except the default group. If unset, salt will assume current groups
        are still wanted, and will make no changes to them.

    optional_groups
        A list of groups to assign the user to, pass a list object. If a group
        specified here does not exist on the minion, the state will silently
        ignore it.

    NOTE: If the same group is specified in both "groups" and
    "optional_groups", then it will be assumed to be required and not optional.

    remove_groups
        Remove groups that the user is a member of that weren't specified in
        the state, Default is ``True``.

    home
        The custom login directory of user. Uses default value of underlying
        system if not set. Notice that this directory does not have to exist.
        This also the location of the home directory to create if createhome is
        set to True.

    createhome : True
        If set to ``False``, the home directory will not be created if it
        doesn't already exist.

        .. warning::
            Not supported on Windows or Mac OS.

            Additionally, parent directories will *not* be created. The parent
            directory for ``home`` must already exist.

    nologinit : False
        If set to ``True``, it will not add the user to lastlog and faillog
        databases.

        .. note::
            Not supported on Windows.

    password
        A password hash to set for the user. This field is only supported on
        Linux, FreeBSD, NetBSD, OpenBSD, and Solaris. If the ``empty_password``
        argument is set to ``True`` then ``password`` is ignored.
        For Windows this is the plain text password.
        For Linux, the hash can be generated with ``mkpasswd -m sha-256``.

    .. versionchanged:: 0.16.0
       BSD support added.

    hash_password
        Set to True to hash the clear text password. Default is ``False``.


    enforce_password
        Set to False to keep the password from being changed if it has already
        been set and the password hash differs from what is specified in the
        "password" field. This option will be ignored if "password" is not
        specified, Default is ``True``.

    empty_password
        Set to True to enable password-less login for user, Default is ``False``.

    shell
        The login shell, defaults to the system default shell

    unique
        Require a unique UID, Default is ``True``.

    system
        Choose UID in the range of FIRST_SYSTEM_UID and LAST_SYSTEM_UID, Default is
        ``False``.

    loginclass
        The login class, defaults to empty
        (BSD only)

    User comment field (GECOS) support (currently Linux, BSD, and MacOS
    only):

    The below values should be specified as strings to avoid ambiguities when
    the values are loaded. (Especially the phone and room number fields which
    are likely to contain numeric data)

    fullname
        The user's full name

    roomnumber
        The user's room number (not supported in MacOS)

    workphone
        The user's work phone number (not supported in MacOS)

    homephone
        The user's home phone number (not supported in MacOS)

    other
        The user's other attribute (not supported in MacOS)
        If GECOS field contains more than 4 commas, this field will have the rest of 'em

    .. versionchanged:: 2014.7.0
       Shadow attribute support added.

    Shadow attributes support (currently Linux only):

    The below values should be specified as integers.

    date
        Date of last change of password, represented in days since epoch
        (January 1, 1970).

    mindays
        The minimum number of days between password changes.

    maxdays
        The maximum number of days between password changes.

    inactdays
        The number of days after a password expires before an account is
        locked.

    warndays
        Number of days prior to maxdays to warn users.

    expire
        Date that account expires, represented in days since epoch (January 1,
        1970).

    The below parameters apply to windows only:

    win_homedrive (Windows Only)
        The drive letter to use for the home directory. If not specified the
        home directory will be a unc path. Otherwise the home directory will be
        mapped to the specified drive. Must be a letter followed by a colon.
        Because of the colon, the value must be surrounded by single quotes. ie:
        - win_homedrive: 'U:

        .. versionchanged:: 2015.8.0

    win_profile (Windows Only)
        The custom profile directory of the user. Uses default value of
        underlying system if not set.

        .. versionchanged:: 2015.8.0

    win_logonscript (Windows Only)
        The full path to the logon script to run when the user logs in.

        .. versionchanged:: 2015.8.0

    win_description (Windows Only)
        A brief description of the purpose of the users account.

        .. versionchanged:: 2015.8.0
    """
    # First check if a password is set. If password is set, check if
    # hash_password is True, then hash it.
    if password and hash_password:
        log.debug("Hashing a clear text password")
        # in case a password is already set, it will contain a Salt
        # which should be re-used to generate the new hash, other-
        # wise the Salt will be generated randomly, causing the
        # hash to change each time and thereby making the
        # user.present state non-idempotent.
        algorithms = {
            "1": "md5",
            "2a": "blowfish",
            "5": "sha256",
            "6": "sha512",
        }
        try:
            _, algo, shadow_salt, shadow_hash = __salt__["shadow.info"](name)[
                "passwd"
            ].split("$", 4)
            if algo == "1":
                log.warning("Using MD5 for hashing passwords is considered insecure!")
            log.debug(
                "Re-using existing shadow salt for hashing password using %s",
                algorithms.get(algo),
            )
            password = __salt__["shadow.gen_password"](
                password, crypt_salt=shadow_salt, algorithm=algorithms.get(algo)
            )
        except ValueError:
            log.info(
                "No existing shadow salt found, defaulting to a randomly generated"
                " new one"
            )
            password = __salt__["shadow.gen_password"](password)

    if fullname is not None:
        fullname = salt.utils.data.decode(fullname)
    if roomnumber is not None:
        roomnumber = salt.utils.data.decode(roomnumber)
    if workphone is not None:
        workphone = salt.utils.data.decode(workphone)
    if homephone is not None:
        homephone = salt.utils.data.decode(homephone)
    if other is not None:
        other = salt.utils.data.decode(other)

    # createhome not supported on Windows
    if __grains__["kernel"] == "Windows":
        createhome = False

    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "User {} is present and up to date".format(name),
    }

    # the comma is used to separate field in GECOS, thus resulting into
    # salt adding the end of fullname each time this function is called
    for gecos_field in [fullname, roomnumber, workphone]:
        if isinstance(gecos_field, str) and "," in gecos_field:
            ret["comment"] = "Unsupported char ',' in {}".format(gecos_field)
            ret["result"] = False
            return ret

    if groups:
        missing_groups = [x for x in groups if not __salt__["group.info"](x)]
        if missing_groups:
            ret["comment"] = "The following group(s) are not present: {}".format(
                ",".join(missing_groups)
            )
            ret["result"] = False
            return ret

    if optional_groups:
        present_optgroups = [x for x in optional_groups if __salt__["group.info"](x)]
        for missing_optgroup in [
            x for x in optional_groups if x not in present_optgroups
        ]:
            log.debug(
                'Optional group "%s" for user "%s" is not present',
                missing_optgroup,
                name,
            )
    else:
        present_optgroups = None

    # Log a warning for all groups specified in both "groups" and
    # "optional_groups" lists.
    if groups and optional_groups:
        for isected in set(groups).intersection(optional_groups):
            log.warning(
                'Group "%s" specified in both groups and optional_groups for user %s',
                isected,
                name,
            )

    # If usergroup was specified, we'll also be creating a new
    # group. We should report this change without setting the gid
    # variable.
    if usergroup and __salt__["file.group_to_gid"](name) != "":
        changes_gid = name
    else:
        changes_gid = gid

    try:
        changes = _changes(
            name,
            uid,
            changes_gid,
            groups,
            present_optgroups,
            remove_groups,
            home,
            createhome,
            password,
            enforce_password,
            empty_password,
            shell,
            fullname,
            roomnumber,
            workphone,
            homephone,
            other,
            loginclass,
            date,
            mindays,
            maxdays,
            inactdays,
            warndays,
            expire,
            win_homedrive,
            win_profile,
            win_logonscript,
            win_description,
            allow_uid_change,
            allow_gid_change,
        )
    except CommandExecutionError as exc:
        ret["result"] = False
        ret["comment"] = exc.strerror
        return ret

    if changes:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "The following user attributes are set to be changed:\n"
            for key, val in changes.items():
                if key == "passwd":
                    val = "XXX-REDACTED-XXX"
                elif key == "group" and not remove_groups:
                    key = "ensure groups"
                ret["comment"] += "{}: {}\n".format(key, val)
            return ret
        # The user is present
        if "shadow.info" in __salt__:
            lshad = __salt__["shadow.info"](name)
        if __grains__["kernel"] in ("OpenBSD", "FreeBSD"):
            lcpre = __salt__["user.get_loginclass"](name)
        pre = __salt__["user.info"](name)

        # Make changes

        if "passwd" in changes:
            del changes["passwd"]
            if not empty_password:
                __salt__["shadow.set_password"](name, password)
            else:
                log.warning("No password will be set when empty_password=True")

        if changes.pop("empty_password", False) is True:
            __salt__["shadow.del_password"](name)

        if "date" in changes:
            del changes["date"]
            __salt__["shadow.set_date"](name, date)

        def _change_homedir(name, val):
            if __grains__["kernel"] in ("Darwin", "Windows"):
                __salt__["user.chhome"](name, val)
            else:
                __salt__["user.chhome"](name, val, persist=False)

        _homedir_changed = False
        if "home" in changes:
            val = changes.pop("home")
            if "homeDoesNotExist" not in changes:
                _change_homedir(name, val)
                _homedir_changed = True

        if "homeDoesNotExist" in changes:
            val = changes.pop("homeDoesNotExist")
            if not _homedir_changed:
                _change_homedir(name, val)
            if not os.path.isdir(val):
                __salt__["file.mkdir"](val, pre["uid"], pre["gid"], 0o755)

        if "mindays" in changes:
            del changes["mindays"]
            __salt__["shadow.set_mindays"](name, mindays)

        if "maxdays" in changes:
            del changes["maxdays"]
            __salt__["shadow.set_maxdays"](name, maxdays)

        if "inactdays" in changes:
            del changes["inactdays"]
            __salt__["shadow.set_inactdays"](name, inactdays)

        if "warndays" in changes:
            del changes["warndays"]
            __salt__["shadow.set_warndays"](name, warndays)

        if "expire" in changes:
            del changes["expire"]
            __salt__["shadow.set_expire"](name, expire)

        if "win_homedrive" in changes:
            __salt__["user.update"](name=name, homedrive=changes.pop("win_homedrive"))

        if "win_profile" in changes:
            __salt__["user.update"](name=name, profile=changes.pop("win_profile"))

        if "win_logonscript" in changes:
            __salt__["user.update"](
                name=name, logonscript=changes.pop("win_logonscript")
            )

        if "win_description" in changes:
            __salt__["user.update"](
                name=name, description=changes.pop("win_description")
            )

        # Do the changes that have "ch" functions for them, but skip changing
        # groups for now. Changing groups before changing the chgid could cause
        # unpredictable results, including failure to set the proper groups.
        # NOTE: list(changes) required here to avoid modifying dictionary
        # during iteration.
        for key in [
            x
            for x in list(changes)
            if x != "groups" and "user.ch{}".format(x) in __salt__
        ]:
            __salt__["user.ch{}".format(key)](name, changes.pop(key))

        # Do group changes last
        if "groups" in changes:
            __salt__["user.chgroups"](name, changes.pop("groups"), not remove_groups)

        if changes:
            ret.get("warnings", []).append(
                "Unhandled changes: {}".format(", ".join(changes))
            )

        post = __salt__["user.info"](name)
        spost = {}
        if "shadow.info" in __salt__ and lshad["passwd"] != password:
            spost = __salt__["shadow.info"](name)
        if __grains__["kernel"] in ("OpenBSD", "FreeBSD"):
            lcpost = __salt__["user.get_loginclass"](name)
        # See if anything changed
        for key in post:
            if post[key] != pre[key]:
                ret["changes"][key] = post[key]
        if "shadow.info" in __salt__:
            for key in spost:
                if lshad[key] != spost[key]:
                    if key == "passwd":
                        ret["changes"][key] = "XXX-REDACTED-XXX"
                    else:
                        ret["changes"][key] = spost[key]
        if __grains__["kernel"] in ("OpenBSD", "FreeBSD") and lcpost != lcpre:
            ret["changes"]["loginclass"] = lcpost
        if ret["changes"]:
            ret["comment"] = "Updated user {}".format(name)
        changes = _changes(
            name,
            uid,
            gid,
            groups,
            present_optgroups,
            remove_groups,
            home,
            createhome,
            password,
            enforce_password,
            empty_password,
            shell,
            fullname,
            roomnumber,
            workphone,
            homephone,
            other,
            loginclass,
            date,
            mindays,
            maxdays,
            inactdays,
            warndays,
            expire,
            win_homedrive,
            win_profile,
            win_logonscript,
            win_description,
            allow_uid_change=True,
            allow_gid_change=True,
        )
        # allow_uid_change and allow_gid_change passed as True to avoid race
        # conditions where a uid/gid is modified outside of Salt. If an
        # unauthorized change was requested, it would have been caught the
        # first time we ran _changes().

        if changes:
            ret["comment"] = "These values could not be changed: {}".format(changes)
            ret["result"] = False
        return ret

    if changes is False:
        # The user is not present, make it!
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "User {} set to be added".format(name)
            return ret
        if groups and present_optgroups:
            groups.extend(present_optgroups)
        elif present_optgroups:
            groups = present_optgroups[:]

        # Setup params specific to Linux and Windows to be passed to the
        # add.user function
        if not salt.utils.platform.is_windows():
            params = {
                "name": name,
                "uid": uid,
                "gid": gid,
                "groups": groups,
                "home": home,
                "shell": shell,
                "unique": unique,
                "system": system,
                "fullname": fullname,
                "roomnumber": roomnumber,
                "workphone": workphone,
                "homephone": homephone,
                "other": other,
                "createhome": createhome,
                "nologinit": nologinit,
                "loginclass": loginclass,
                "usergroup": usergroup,
            }
        else:
            params = {
                "name": name,
                "password": password,
                "fullname": fullname,
                "description": win_description,
                "groups": groups,
                "home": home,
                "homedrive": win_homedrive,
                "profile": win_profile,
                "logonscript": win_logonscript,
            }
        result = __salt__["user.add"](**params)
        if result is True:
            ret["comment"] = "New user {} created".format(name)
            ret["changes"] = __salt__["user.info"](name)
            if not createhome:
                # pwd incorrectly reports presence of home
                ret["changes"]["home"] = ""
            if (
                "shadow.info" in __salt__
                and not salt.utils.platform.is_windows()
                and not salt.utils.platform.is_darwin()
            ):
                if password and not empty_password:
                    __salt__["shadow.set_password"](name, password)
                    spost = __salt__["shadow.info"](name)
                    if spost["passwd"] != password:
                        ret[
                            "comment"
                        ] = "User {} created but failed to set password to {}".format(
                            name, "XXX-REDACTED-XXX"
                        )
                        ret["result"] = False
                    ret["changes"]["password"] = "XXX-REDACTED-XXX"
                if empty_password and not password:
                    __salt__["shadow.del_password"](name)
                    spost = __salt__["shadow.info"](name)
                    if spost["passwd"] != "":
                        ret[
                            "comment"
                        ] = "User {} created but failed to empty password".format(name)
                        ret["result"] = False
                    ret["changes"]["password"] = ""
                if date is not None:
                    __salt__["shadow.set_date"](name, date)
                    spost = __salt__["shadow.info"](name)
                    if spost["lstchg"] != date:
                        ret["comment"] = (
                            "User {} created but failed to set"
                            " last change date to"
                            " {}".format(name, date)
                        )
                        ret["result"] = False
                    ret["changes"]["date"] = date
                if mindays:
                    __salt__["shadow.set_mindays"](name, mindays)
                    spost = __salt__["shadow.info"](name)
                    if spost["min"] != mindays:
                        ret["comment"] = (
                            "User {} created but failed to set"
                            " minimum days to"
                            " {}".format(name, mindays)
                        )
                        ret["result"] = False
                    ret["changes"]["mindays"] = mindays
                if maxdays:
                    __salt__["shadow.set_maxdays"](name, maxdays)
                    spost = __salt__["shadow.info"](name)
                    if spost["max"] != maxdays:
                        ret["comment"] = (
                            "User {} created but failed to set"
                            " maximum days to"
                            " {}".format(name, maxdays)
                        )
                        ret["result"] = False
                    ret["changes"]["maxdays"] = maxdays
                if inactdays:
                    __salt__["shadow.set_inactdays"](name, inactdays)
                    spost = __salt__["shadow.info"](name)
                    if spost["inact"] != inactdays:
                        ret["comment"] = (
                            "User {} created but failed to set"
                            " inactive days to"
                            " {}".format(name, inactdays)
                        )
                        ret["result"] = False
                    ret["changes"]["inactdays"] = inactdays
                if warndays:
                    __salt__["shadow.set_warndays"](name, warndays)
                    spost = __salt__["shadow.info"](name)
                    if spost["warn"] != warndays:
                        ret[
                            "comment"
                        ] = "User {} created but failed to set warn days to {}".format(
                            name, warndays
                        )
                        ret["result"] = False
                    ret["changes"]["warndays"] = warndays
                if expire:
                    __salt__["shadow.set_expire"](name, expire)
                    spost = __salt__["shadow.info"](name)
                    if spost["expire"] != expire:
                        ret["comment"] = (
                            "User {} created but failed to set"
                            " expire days to"
                            " {}".format(name, expire)
                        )
                        ret["result"] = False
                    ret["changes"]["expire"] = expire
            elif salt.utils.platform.is_windows():
                if password and not empty_password:
                    if not __salt__["user.setpassword"](name, password):
                        ret[
                            "comment"
                        ] = "User {} created but failed to set password to {}".format(
                            name, "XXX-REDACTED-XXX"
                        )
                        ret["result"] = False
                    ret["changes"]["passwd"] = "XXX-REDACTED-XXX"
                if expire:
                    __salt__["shadow.set_expire"](name, expire)
                    spost = __salt__["shadow.info"](name)
                    if salt.utils.dateutils.strftime(
                        spost["expire"]
                    ) != salt.utils.dateutils.strftime(expire):
                        ret["comment"] = (
                            "User {} created but failed to set"
                            " expire days to"
                            " {}".format(name, expire)
                        )
                        ret["result"] = False
                    ret["changes"]["expiration_date"] = spost["expire"]
            elif salt.utils.platform.is_darwin() and password and not empty_password:
                if not __salt__["shadow.set_password"](name, password):
                    ret[
                        "comment"
                    ] = "User {} created but failed to set password to {}".format(
                        name, "XXX-REDACTED-XXX"
                    )
                    ret["result"] = False
                ret["changes"]["passwd"] = "XXX-REDACTED-XXX"
        else:
            # if we failed to create a user, result is either false or
            # str in the case of windows so handle both cases here
            if isinstance(result, str):
                ret["comment"] = result
            else:
                ret["comment"] = "Failed to create new user {}".format(name)
            ret["result"] = False
    return ret


def absent(name, purge=False, force=False):
    """
    Ensure that the named user is absent

    name
        The name of the user to remove

    purge
        Set purge to True to delete all of the user's files as well as the user,
        Default is ``False``.

    force
        If the user is logged in, the absent state will fail. Set the force
        option to True to remove the user even if they are logged in. Not
        supported in FreeBSD and Solaris, Default is ``False``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    lusr = __salt__["user.info"](name)
    if lusr:
        # The user is present, make it not present
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "User {} set for removal".format(name)
            return ret
        beforegroups = set(salt.utils.user.get_group_list(name))
        ret["result"] = __salt__["user.delete"](name, purge, force)
        aftergroups = {g for g in beforegroups if __salt__["group.info"](g)}
        if ret["result"]:
            ret["changes"] = {}
            for g in beforegroups - aftergroups:
                ret["changes"]["{} group".format(g)] = "removed"
            ret["changes"][name] = "removed"
            ret["comment"] = "Removed user {}".format(name)
        else:
            ret["result"] = False
            ret["comment"] = "Failed to remove user {}".format(name)
        return ret

    ret["comment"] = "User {} is not present".format(name)

    return ret
