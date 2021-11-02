"""
Manage accounts in Samba's passdb using pdbedit

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:platform:      posix

.. versionadded:: 2017.7.0
"""

import binascii
import hashlib
import logging
import re
import shlex

import salt.modules.cmdmod
import salt.utils.path

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "pdbedit"

# Function aliases
__func_alias__ = {
    "list_users": "list",
    "get_user": "get",
}


def __virtual__():
    """
    Provides pdbedit if available
    """
    # NOTE: check for pdbedit command
    if not salt.utils.path.which("pdbedit"):
        return (False, "pdbedit command is not available")

    # NOTE: check version is >= 4.5.x
    ver = salt.modules.cmdmod.run("pdbedit -V")
    ver_regex = re.compile(r"^Version\s(\d+)\.(\d+)\.(\d+).*$")
    ver_match = ver_regex.match(ver)
    if not ver_match:
        return (False, "pdbedit -V returned an unknown version format")

    if not (int(ver_match.group(1)) >= 4 and int(ver_match.group(2)) >= 5):
        return (False, "pdbedit is to old, 4.5.0 or newer is required")

    try:
        hashlib.new("md4", "".encode("utf-16le"))
    except ValueError:
        return (False, "Hash type md4 unsupported")
    return __virtualname__


def generate_nt_hash(password):
    """
    Generate a NT HASH

    CLI Example:

    .. code-block:: bash

        salt '*' pdbedit.generate_nt_hash my_passwd
    """
    return binascii.hexlify(
        hashlib.new("md4", password.encode("utf-16le")).digest()
    ).upper()


def list_users(verbose=True, hashes=False):
    """
    List user accounts

    verbose : boolean
        return all information
    hashes : boolean
        include NT HASH and LM HASH in verbose output

    CLI Example:

    .. code-block:: bash

        salt '*' pdbedit.list
    """
    users = {} if verbose else []

    if verbose:
        # parse detailed user data
        res = __salt__["cmd.run_all"](
            "pdbedit --list --verbose {hashes}".format(
                hashes="--smbpasswd-style" if hashes else ""
            ),
        )

        if res["retcode"] > 0:
            log.error(res["stderr"] if "stderr" in res else res["stdout"])
            return users

        user_data = {}
        for user in res["stdout"].splitlines():
            if user.startswith("-"):
                if "unix username" in user_data:
                    users[user_data["unix username"]] = user_data
                user_data = {}
            elif ":" in user:
                label = user[: user.index(":")].strip().lower()
                data = user[(user.index(":") + 1) :].strip()
                user_data[label] = data

        if user_data:
            users[user_data["unix username"]] = user_data
    else:
        # list users
        res = __salt__["cmd.run_all"]("pdbedit --list")

        if res["retcode"] > 0:
            return {"Error": res["stderr"] if "stderr" in res else res["stdout"]}

        for user in res["stdout"].splitlines():
            if ":" not in user:
                continue
            user_data = user.split(":")
            if len(user_data) >= 3:
                users.append(user_data[0])

    return users


def get_user(login, hashes=False):
    """
    Get user account details

    login : string
        login name
    hashes : boolean
        include NTHASH and LMHASH in verbose output

    CLI Example:

    .. code-block:: bash

        salt '*' pdbedit.get kaylee
    """
    users = list_users(verbose=True, hashes=hashes)
    return users[login] if login in users else {}


def delete(login):
    """
    Delete user account

    login : string
        login name

    CLI Example:

    .. code-block:: bash

        salt '*' pdbedit.delete wash
    """
    if login in list_users(False):
        res = __salt__["cmd.run_all"](
            "pdbedit --delete {login}".format(login=shlex.quote(login)),
        )

        if res["retcode"] > 0:
            return {login: res["stderr"] if "stderr" in res else res["stdout"]}

        return {login: "deleted"}

    return {login: "absent"}


def create(login, password, password_hashed=False, machine_account=False):
    """
    Create user account

    login : string
        login name
    password : string
        password
    password_hashed : boolean
        set if password is a nt hash instead of plain text
    machine_account : boolean
        set to create a machine trust account instead

    CLI Example:

    .. code-block:: bash

        salt '*' pdbedit.create zoe 9764951149F84E770889011E1DC4A927 nthash
        salt '*' pdbedit.create river  1sw4ll0w3d4bug
    """
    ret = "unchanged"

    # generate nt hash if needed
    if password_hashed:
        password_hash = password.upper()
        password = ""  # wipe password
    else:
        password_hash = generate_nt_hash(password)

    # create user
    if login not in list_users(False):
        # NOTE: --create requires a password, even if blank
        res = __salt__["cmd.run_all"](
            cmd="pdbedit --create --user {login} -t {machine}".format(
                login=shlex.quote(login),
                machine="--machine" if machine_account else "",
            ),
            stdin="{password}\n{password}\n".format(password=password),
        )

        if res["retcode"] > 0:
            return {login: res["stderr"] if "stderr" in res else res["stdout"]}

        ret = "created"

    # update password if needed
    user = get_user(login, True)
    if user["nt hash"] != password_hash:
        res = __salt__["cmd.run_all"](
            "pdbedit --modify --user {login} --set-nt-hash={nthash}".format(
                login=shlex.quote(login), nthash=shlex.quote(password_hash)
            ),
        )

        if res["retcode"] > 0:
            return {login: res["stderr"] if "stderr" in res else res["stdout"]}

        if ret != "created":
            ret = "updated"

    return {login: ret}


def modify(
    login,
    password=None,
    password_hashed=False,
    domain=None,
    profile=None,
    script=None,
    drive=None,
    homedir=None,
    fullname=None,
    account_desc=None,
    account_control=None,
    machine_sid=None,
    user_sid=None,
    reset_login_hours=False,
    reset_bad_password_count=False,
):
    """
    Modify user account

    login : string
        login name
    password : string
        password
    password_hashed : boolean
        set if password is a nt hash instead of plain text
    domain : string
        users domain
    profile : string
        profile path
    script : string
        logon script
    drive : string
        home drive
    homedir : string
        home directory
    fullname : string
        full name
    account_desc : string
        account description
    machine_sid : string
        specify the machines new primary group SID or rid
    user_sid : string
        specify the users new primary group SID or rid
    account_control : string
        specify user account control properties

        .. note::
            Only the following can be set:
            - N: No password required
            - D: Account disabled
            - H: Home directory required
            - L: Automatic Locking
            - X: Password does not expire
    reset_login_hours : boolean
        reset the users allowed logon hours
    reset_bad_password_count : boolean
        reset the stored bad login counter

    .. note::
        if user is absent and password is provided, the user will be created

    CLI Example:

    .. code-block:: bash

        salt '*' pdbedit.modify inara fullname='Inara Serra'
        salt '*' pdbedit.modify simon password=r1v3r
        salt '*' pdbedit.modify jane drive='V:' homedir='\\\\serenity\\jane\\profile'
        salt '*' pdbedit.modify mal account_control=NX
    """
    ret = "unchanged"

    # flag mapping
    flags = {
        "domain": "--domain=",
        "full name": "--fullname=",
        "account desc": "--account-desc=",
        "home directory": "--homedir=",
        "homedir drive": "--drive=",
        "profile path": "--profile=",
        "logon script": "--script=",
        "account flags": "--account-control=",
        "user sid": "-U ",
        "machine sid": "-M ",
    }

    # field mapping
    provided = {
        "domain": domain,
        "full name": fullname,
        "account desc": account_desc,
        "home directory": homedir,
        "homedir drive": drive,
        "profile path": profile,
        "logon script": script,
        "account flags": account_control,
        "user sid": user_sid,
        "machine sid": machine_sid,
    }

    # update password
    if password:
        ret = create(login, password, password_hashed)[login]
        if ret not in ["updated", "created", "unchanged"]:
            return {login: ret}
    elif login not in list_users(False):
        return {login: "absent"}

    # check for changes
    current = get_user(login, hashes=True)
    changes = {}
    for key, val in provided.items():
        if key in ["user sid", "machine sid"]:
            if (
                val is not None
                and key in current
                and not current[key].endswith(str(val))
            ):
                changes[key] = str(val)
        elif key in ["account flags"]:
            if val is not None:
                if val.startswith("["):
                    val = val[1:-1]
                new = []
                for f in val.upper():
                    if f not in ["N", "D", "H", "L", "X"]:
                        log.warning(
                            "pdbedit.modify - unknown %s flag for account_control, ignored",
                            f,
                        )
                    else:
                        new.append(f)
                changes[key] = "[{flags}]".format(flags="".join(new))
        else:
            if val is not None and key in current and current[key] != val:
                changes[key] = val

    # apply changes
    if len(changes) > 0 or reset_login_hours or reset_bad_password_count:
        cmds = []
        for change in changes:
            cmds.append(
                "{flag}{value}".format(
                    flag=flags[change],
                    value=shlex.quote(changes[change]),
                )
            )
        if reset_login_hours:
            cmds.append("--logon-hours-reset")
        if reset_bad_password_count:
            cmds.append("--bad-password-count-reset")

        res = __salt__["cmd.run_all"](
            "pdbedit --modify --user {login} {changes}".format(
                login=shlex.quote(login),
                changes=" ".join(cmds),
            ),
        )

        if res["retcode"] > 0:
            return {login: res["stderr"] if "stderr" in res else res["stdout"]}

        if ret != "created":
            ret = "updated"

    return {login: ret}


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
