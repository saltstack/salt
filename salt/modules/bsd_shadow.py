"""
Manage the password database on BSD systems

.. important::
    If you feel that Salt should be using this module to manage passwords on a
    minion, and it is using a different module (or gives an error similar to
    *'shadow.info' is not available*), see :ref:`here
    <module-provider-override>`.
"""


import salt.utils.files
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError, SaltInvocationError

try:
    import pwd
except ImportError:
    pass

try:
    import salt.utils.pycrypto

    HAS_CRYPT = True
except ImportError:
    HAS_CRYPT = False

# Define the module's virtual name
__virtualname__ = "shadow"


def __virtual__():
    if "BSD" in __grains__.get("os", ""):
        return __virtualname__
    return (
        False,
        "The bsd_shadow execution module cannot be loaded: "
        "only available on BSD family systems.",
    )


def default_hash():
    """
    Returns the default hash used for unset passwords

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.default_hash
    """
    return "*" if __grains__["os"].lower() == "freebsd" else "*************"


def gen_password(password, crypt_salt=None, algorithm="sha512"):
    """
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


def info(name):
    """
    Return information for the specified user

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.info someuser
    """
    try:
        data = pwd.getpwnam(name)
        ret = {"name": data.pw_name, "passwd": data.pw_passwd}
    except KeyError:
        return {"name": "", "passwd": ""}

    if not isinstance(name, str):
        name = str(name)
    if ":" in name:
        raise SaltInvocationError("Invalid username '{}'".format(name))

    if __salt__["cmd.has_exec"]("pw"):
        change, expire = __salt__["cmd.run_stdout"](
            ["pw", "user", "show", name], python_shell=False
        ).split(":")[5:7]
    elif __grains__["kernel"] in ("NetBSD", "OpenBSD"):
        try:
            with salt.utils.files.fopen("/etc/master.passwd", "r") as fp_:
                for line in fp_:
                    line = salt.utils.stringutils.to_unicode(line)
                    if line.startswith("{}:".format(name)):
                        key = line.split(":")
                        change, expire = key[5:7]
                        ret["passwd"] = str(key[1])
                        break
        except OSError:
            change = expire = None
    else:
        change = expire = None

    try:
        ret["change"] = int(change)
    except ValueError:
        pass

    try:
        ret["expire"] = int(expire)
    except ValueError:
        pass

    return ret


def set_change(name, change):
    """
    Sets the time at which the password expires (in seconds since the UNIX
    epoch). See ``man 8 usermod`` on NetBSD and OpenBSD or ``man 8 pw`` on
    FreeBSD.

    A value of ``0`` sets the password to never expire.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_change username 1419980400
    """
    pre_info = info(name)
    if change == pre_info["change"]:
        return True
    if __grains__["kernel"] == "FreeBSD":
        cmd = ["pw", "user", "mod", name, "-f", change]
    else:
        cmd = ["usermod", "-f", change, name]
    __salt__["cmd.run"](cmd, python_shell=False)
    post_info = info(name)
    if post_info["change"] != pre_info["change"]:
        return post_info["change"] == change


def set_expire(name, expire):
    """
    Sets the time at which the account expires (in seconds since the UNIX
    epoch). See ``man 8 usermod`` on NetBSD and OpenBSD or ``man 8 pw`` on
    FreeBSD.

    A value of ``0`` sets the account to never expire.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_expire username 1419980400
    """
    pre_info = info(name)
    if expire == pre_info["expire"]:
        return True
    if __grains__["kernel"] == "FreeBSD":
        cmd = ["pw", "user", "mod", name, "-e", expire]
    else:
        cmd = ["usermod", "-e", expire, name]
    __salt__["cmd.run"](cmd, python_shell=False)
    post_info = info(name)
    if post_info["expire"] != pre_info["expire"]:
        return post_info["expire"] == expire


def del_password(name):
    """
    .. versionadded:: 2015.8.2

    Delete the password from name user

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.del_password username
    """
    cmd = "pw user mod {} -w none".format(name)
    __salt__["cmd.run"](cmd, python_shell=False, output_loglevel="quiet")
    uinfo = info(name)
    return not uinfo["passwd"]


def set_password(name, password):
    """
    Set the password for a named user. The password must be a properly defined
    hash. A password hash can be generated with :py:func:`gen_password`.

    It is important to make sure that a supported cipher is used.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_password someuser '$1$UYCIxa628.9qXjpQCjM4a..'
    """
    if __grains__.get("os", "") == "FreeBSD":
        cmd = ["pw", "user", "mod", name, "-H", "0"]
        stdin = password
    else:
        cmd = ["usermod", "-p", password, name]
        stdin = None
    __salt__["cmd.run"](cmd, stdin=stdin, output_loglevel="quiet", python_shell=False)
    return info(name)["passwd"] == password
