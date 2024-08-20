"""
Manage the shadow file on Linux systems

.. important::
    If you feel that Salt should be using this module to manage passwords on a
    minion, and it is using a different module (or gives an error similar to
    *'shadow.info' is not available*), see :ref:`here
    <module-provider-override>`.
"""

import datetime
import functools
import logging
import os

import salt.utils.data
import salt.utils.files
from salt.exceptions import CommandExecutionError

try:
    import spwd
except ImportError:
    pass


try:
    import salt.utils.pycrypto

    HAS_CRYPT = True
except ImportError:
    HAS_CRYPT = False

__virtualname__ = "shadow"

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__ if __grains__.get("kernel", "") == "Linux" else False


def default_hash():
    """
    Returns the default hash used for unset passwords

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.default_hash
    """
    return "!"


def info(name, root=None):
    """
    Return information for the specified user

    name
        User to get the information for

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.info root
    """
    if root is not None:
        getspnam = functools.partial(_getspnam, root=root)
    else:
        getspnam = functools.partial(spwd.getspnam)

    try:
        data = getspnam(name)
        ret = {
            "name": data.sp_namp if hasattr(data, "sp_namp") else data.sp_nam,
            "passwd": data.sp_pwdp if hasattr(data, "sp_pwdp") else data.sp_pwd,
            "lstchg": data.sp_lstchg,
            "min": data.sp_min,
            "max": data.sp_max,
            "warn": data.sp_warn,
            "inact": data.sp_inact,
            "expire": data.sp_expire,
        }
    except (KeyError, FileNotFoundError):
        return {
            "name": "",
            "passwd": "",
            "lstchg": "",
            "min": "",
            "max": "",
            "warn": "",
            "inact": "",
            "expire": "",
        }
    return ret


def _set_attrib(name, key, value, param, root=None, validate=True):
    """
    Set a parameter in /etc/shadow
    """
    pre_info = info(name, root=root)

    # If the user is not present or the attribute is already present,
    # we return early
    if not pre_info["name"]:
        return False

    if value == pre_info[key]:
        return True

    cmd = ["chage"]

    if root is not None:
        cmd.extend(("-R", root))

    cmd.extend((param, value, name))

    ret = not __salt__["cmd.retcode"](cmd, python_shell=False)
    if validate:
        ret = info(name, root=root).get(key) == value
    return ret


def set_inactdays(name, inactdays, root=None):
    """
    Set the number of days of inactivity after a password has expired before
    the account is locked. See man chage.

    name
        User to modify

    inactdays
        Set password inactive after this number of days

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_inactdays username 7
    """
    return _set_attrib(name, "inact", inactdays, "-I", root=root)


def set_maxdays(name, maxdays, root=None):
    """
    Set the maximum number of days during which a password is valid.
    See man chage.

    name
        User to modify

    maxdays
        Maximum number of days during which a password is valid

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_maxdays username 90
    """
    return _set_attrib(name, "max", maxdays, "-M", root=root)


def set_mindays(name, mindays, root=None):
    """
    Set the minimum number of days between password changes. See man chage.

    name
        User to modify

    mindays
        Minimum number of days between password changes

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_mindays username 7
    """
    return _set_attrib(name, "min", mindays, "-m", root=root)


def gen_password(password, crypt_salt=None, algorithm="sha512"):
    """
    .. versionadded:: 2014.7.0

    Generate hashed password

    .. note::

        When called this function is called directly via remote-execution,
        the password argument may be displayed in the system's process list.
        This may be a security risk on certain systems.

    password
        Plaintext password to be hashed.

    crypt_salt
        Crpytographic salt. If not given, a random 8-character salt will be
        generated.

    algorithm
        The following hash algorithms are supported:

        * md5
        * blowfish (not in mainline glibc, only available in distros that add it)
        * sha256
        * sha512 (default)

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.gen_password 'I_am_password'
        salt '*' shadow.gen_password 'I_am_password' crypt_salt='I_am_salt' algorithm=sha256
    """
    if not HAS_CRYPT:
        raise CommandExecutionError(
            "gen_password is not available on this operating system "
            'because the "crypt" python module is not available.'
        )
    return salt.utils.pycrypto.gen_hash(crypt_salt, password, algorithm)


def del_password(name, root=None):
    """
    .. versionadded:: 2014.7.0

    Delete the password from name user

    name
        User to delete

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.del_password username
    """
    cmd = ["passwd"]
    if root is not None:
        cmd.extend(("-R", root))
    cmd.extend(("-d", name))

    __salt__["cmd.run"](cmd, python_shell=False, output_loglevel="quiet")
    uinfo = info(name, root=root)
    return not uinfo["passwd"] and uinfo["name"] == name


def lock_password(name, root=None):
    """
    .. versionadded:: 2016.11.0

    Lock the password from specified user

    name
        User to lock

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.lock_password username
    """
    pre_info = info(name, root=root)
    if not pre_info["name"]:
        return False

    if pre_info["passwd"].startswith("!"):
        return True

    cmd = ["passwd"]

    if root is not None:
        cmd.extend(("-R", root))

    cmd.extend(("-l", name))

    __salt__["cmd.run"](cmd, python_shell=False)
    return info(name, root=root)["passwd"].startswith("!")


def unlock_password(name, root=None):
    """
    .. versionadded:: 2016.11.0

    Unlock the password from name user

    name
        User to unlock

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.unlock_password username
    """
    pre_info = info(name, root=root)
    if not pre_info["name"]:
        return False

    if not pre_info["passwd"].startswith("!"):
        return True

    cmd = ["passwd"]

    if root is not None:
        cmd.extend(("-R", root))

    cmd.extend(("-u", name))

    __salt__["cmd.run"](cmd, python_shell=False)
    return not info(name, root=root)["passwd"].startswith("!")


def set_password(name, password, use_usermod=False, root=None):
    """
    Set the password for a named user. The password must be a properly defined
    hash. A password hash can be generated with :py:func:`gen_password`.

    name
        User to set the password

    password
        Password already hashed

    use_usermod
        Use usermod command to better compatibility

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_password root '$1$UYCIxa628.9qXjpQCjM4a..'
    """
    if __salt__["cmd.retcode"](["id", name], ignore_retcode=True) != 0:
        log.warning("user %s does not exist, cannot set password", name)
        return False

    if not salt.utils.data.is_true(use_usermod):
        # Edit the shadow file directly
        # ALT Linux uses tcb to store password hashes. More information found
        # in manpage (http://docs.altlinux.org/manpages/tcb.5.html)
        if __grains__["os"] == "ALT":
            s_file = f"/etc/tcb/{name}/shadow"
        else:
            s_file = "/etc/shadow"
        if root:
            s_file = os.path.join(root, os.path.relpath(s_file, os.path.sep))

        ret = {}
        if not os.path.isfile(s_file):
            return ret
        lines = []
        user_found = False
        lstchg = str((datetime.datetime.today() - datetime.datetime(1970, 1, 1)).days)
        with salt.utils.files.fopen(s_file, "r") as fp_:
            for line in fp_:
                # Fix malformed entry by first ignoring extra fields, then
                # adding missing fields.
                comps = line.strip().split(":")[:9]
                if comps[0] == name:
                    num_missing = 9 - len(comps)
                    if num_missing:
                        comps.extend([""] * num_missing)
                    user_found = True
                    comps[1] = password
                    comps[2] = lstchg
                    line = ":".join(comps) + "\n"
                lines.append(line)
        if not user_found:
            log.warning("shadow entry not present for user %s, adding", name)
            with salt.utils.files.fopen(s_file, "a+") as fp_:
                fp_.write(
                    "{name}:{password}:{lstchg}::::::\n".format(
                        name=name, password=password, lstchg=lstchg
                    )
                )
        else:
            with salt.utils.files.fopen(s_file, "w+") as fp_:
                fp_.writelines(lines)
        uinfo = info(name, root=root)
        return uinfo["passwd"] == password
    else:
        # Use usermod -p (less secure, but more feature-complete)
        cmd = ["usermod"]
        if root is not None:
            cmd.extend(("-R", root))
        cmd.extend(("-p", password, name))

        __salt__["cmd.run"](cmd, python_shell=False, output_loglevel="quiet")
        uinfo = info(name, root=root)
        return uinfo["passwd"] == password


def set_warndays(name, warndays, root=None):
    """
    Set the number of days of warning before a password change is required.
    See man chage.

    name
        User to modify

    warndays
        Number of days of warning before a password change is required

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_warndays username 7
    """
    return _set_attrib(name, "warn", warndays, "-W", root=root)


def set_date(name, date, root=None):
    """
    Sets the value for the date the password was last changed to days since the
    epoch (January 1, 1970). See man chage.

    name
        User to modify

    date
        Date the password was last changed

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_date username 0
    """
    return _set_attrib(name, "lstchg", date, "-d", root=root, validate=False)


def set_expire(name, expire, root=None):
    """
    .. versionchanged:: 2014.7.0

    Sets the value for the date the account expires as days since the epoch
    (January 1, 1970). Using a value of -1 will clear expiration. See man
    chage.

    name
        User to modify

    date
        Date the account expires

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_expire username -1
    """
    return _set_attrib(name, "expire", expire, "-E", root=root, validate=False)


def list_users(root=None):
    """
    .. versionadded:: 2018.3.0

    Return a list of all shadow users

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.list_users
    """
    if root is not None:
        getspall = functools.partial(_getspall, root=root)
    else:
        getspall = functools.partial(spwd.getspall)

    return sorted(
        user.sp_namp if hasattr(user, "sp_namp") else user.sp_nam for user in getspall()
    )


def _getspnam(name, root=None):
    """
    Alternative implementation for getspnam, that use only /etc/shadow
    """
    root = "/" if not root else root
    passwd = os.path.join(root, "etc/shadow")
    with salt.utils.files.fopen(passwd) as fp_:
        for line in fp_:
            comps = line.strip().split(":")
            if comps[0] == name:
                # Generate a getspnam compatible output
                for i in range(2, 9):
                    comps[i] = int(comps[i]) if comps[i] else -1
                return spwd.struct_spwd(comps)
    raise KeyError


def _getspall(root=None):
    """
    Alternative implementation for getspnam, that use only /etc/shadow
    """
    root = "/" if not root else root
    passwd = os.path.join(root, "etc/shadow")
    with salt.utils.files.fopen(passwd) as fp_:
        for line in fp_:
            comps = line.strip().split(":")
            # Generate a getspall compatible output
            for i in range(2, 9):
                comps[i] = int(comps[i]) if comps[i] else -1
            yield spwd.struct_spwd(comps)
