# The pam components have been modified to be salty and have been taken from
# the pam module under this licence:
# (c) 2007 Chris AtLee <chris@atlee.ca>
# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license.php
"""
Authenticate against PAM

Provides an authenticate function that will allow the caller to authenticate
a user against the Pluggable Authentication Modules (PAM) on the system.

Implemented using ctypes, so no compilation is necessary.

There is one extra configuration option for pam.  The `pam_service` that is
authenticated against.  This defaults to `login`

.. code-block:: yaml

    auth.pam.service: login

.. note:: Solaris-like (SmartOS, OmniOS, ...) systems may need ``auth.pam.service`` set to ``other``.

.. note:: PAM authentication will not work for the ``root`` user.

    The Python interface to PAM does not support authenticating as ``root``.

.. note:: This module executes itself in a subprocess in order to user the system python
    and pam libraries. We do this to avoid openssl version conflicts when
    running under a salt onedir build.

.. note:: Running ``salt-master`` as a non-root user (the 3006.x packaging
    default is the ``salt`` user) and using PAM eauth requires extra
    privileges so that PAM's ``unix_chkpwd`` helper can validate other
    users' passwords. ``unix_chkpwd`` refuses to authenticate users other
    than the caller unless the caller can read ``/etc/shadow``. The two
    standard remediations are:

    1. **Debian-derived distributions:** add the master's user to the
       ``shadow`` group (e.g. ``usermod -a -G shadow salt``) so the master
       process can read ``/etc/shadow`` indirectly via the setgid-shadow
       ``unix_chkpwd`` helper.
    2. **RPM-based distributions:** revert the master to run as ``root``
       (``user: root`` in ``/etc/salt/master``); ``/etc/shadow`` cannot be
       made readable to a non-root group safely there.

    When PAM auth fails and the master is running as a non-root user
    without ``/etc/shadow`` access, a CRITICAL log entry naming the cause
    and the two remediations is emitted (once per process). See
    https://github.com/saltstack/salt/issues/64275 for the full
    discussion.
"""

import logging
import os
import pathlib
import subprocess
import sys
from ctypes import (
    CDLL,
    CFUNCTYPE,
    POINTER,
    Structure,
    c_char,
    c_char_p,
    c_int,
    c_uint,
    c_void_p,
    cast,
    pointer,
    sizeof,
)
from ctypes.util import find_library

HAS_USER = True
try:
    import salt.utils.user
except ImportError:
    HAS_USER = False

log = logging.getLogger(__name__)

try:
    LIBC = CDLL(find_library("c"))

    CALLOC = LIBC.calloc
    CALLOC.restype = c_void_p
    CALLOC.argtypes = [c_uint, c_uint]

    STRDUP = LIBC.strdup
    STRDUP.argstypes = [c_char_p]
    STRDUP.restype = POINTER(c_char)  # NOT c_char_p !!!!
except Exception:  # pylint: disable=broad-except
    log.trace("Failed to load libc using ctypes", exc_info=True)
    HAS_LIBC = False
else:
    HAS_LIBC = True

# Various constants
PAM_PROMPT_ECHO_OFF = 1
PAM_PROMPT_ECHO_ON = 2
PAM_ERROR_MSG = 3
PAM_TEXT_INFO = 4


class PamHandle(Structure):
    """
    Wrapper class for pam_handle_t
    """

    _fields_ = [("handle", c_void_p)]

    def __init__(self):
        Structure.__init__(self)
        self.handle = 0


class PamMessage(Structure):
    """
    Wrapper class for pam_message structure
    """

    _fields_ = [
        ("msg_style", c_int),
        ("msg", c_char_p),
    ]

    def __repr__(self):
        return f"<PamMessage {self.msg_style} '{self.msg}'>"


class PamResponse(Structure):
    """
    Wrapper class for pam_response structure
    """

    _fields_ = [
        ("resp", c_char_p),
        ("resp_retcode", c_int),
    ]

    def __repr__(self):
        return f"<PamResponse {self.resp_retcode} '{self.resp}'>"


CONV_FUNC = CFUNCTYPE(
    c_int, c_int, POINTER(POINTER(PamMessage)), POINTER(POINTER(PamResponse)), c_void_p
)


class PamConv(Structure):
    """
    Wrapper class for pam_conv structure
    """

    _fields_ = [("conv", CONV_FUNC), ("appdata_ptr", c_void_p)]


try:
    LIBPAM = CDLL(find_library("pam"))
    PAM_START = LIBPAM.pam_start
    PAM_START.restype = c_int
    PAM_START.argtypes = [c_char_p, c_char_p, POINTER(PamConv), POINTER(PamHandle)]

    PAM_AUTHENTICATE = LIBPAM.pam_authenticate
    PAM_AUTHENTICATE.restype = c_int
    PAM_AUTHENTICATE.argtypes = [PamHandle, c_int]

    PAM_ACCT_MGMT = LIBPAM.pam_acct_mgmt
    PAM_ACCT_MGMT.restype = c_int
    PAM_ACCT_MGMT.argtypes = [PamHandle, c_int]

    PAM_END = LIBPAM.pam_end
    PAM_END.restype = c_int
    PAM_END.argtypes = [PamHandle, c_int]
except Exception:  # pylint: disable=broad-except
    log.trace("Failed to load pam using ctypes", exc_info=True)
    HAS_PAM = False
else:
    HAS_PAM = True


def __virtual__():
    """
    Only load on Linux systems
    """
    return HAS_LIBC and HAS_PAM


def _authenticate(username, password, service, encoding="utf-8"):
    """
    Returns True if the given username and password authenticate for the
    given service.  Returns False otherwise

    ``username``: the username to authenticate

    ``password``: the password in plain text
    """
    if isinstance(username, str):
        username = username.encode(encoding)
    if isinstance(password, str):
        password = password.encode(encoding)
    if isinstance(service, str):
        service = service.encode(encoding)

    @CONV_FUNC
    def my_conv(n_messages, messages, p_response, app_data):
        """
        Conversation function that answers PAM prompts:

        * ``PAM_PROMPT_ECHO_OFF`` (hidden input) is answered with the
          supplied password.
        * ``PAM_PROMPT_ECHO_ON`` (visible input) is answered with the
          supplied username. Some PAM modules issue such a prompt — for
          example to re-prompt for the user — and previously the conv
          left that response slot NULL, which caused ``pam_authenticate``
          to fail with no diagnostic.
        * ``PAM_ERROR_MSG`` and ``PAM_TEXT_INFO`` are informational and
          require no response; their CALLOC-zeroed slots are left alone.
        """
        # Create an array of n_messages response objects
        addr = CALLOC(n_messages, sizeof(PamResponse))
        p_response[0] = cast(addr, POINTER(PamResponse))
        for i in range(n_messages):
            style = messages[i].contents.msg_style
            if style == PAM_PROMPT_ECHO_OFF:
                resp_copy = STRDUP(password)
            elif style == PAM_PROMPT_ECHO_ON:
                resp_copy = STRDUP(username)
            else:
                continue
            p_response.contents[i].resp = cast(resp_copy, c_char_p)
            p_response.contents[i].resp_retcode = 0
        return 0

    handle = PamHandle()
    conv = PamConv(my_conv, 0)
    retval = PAM_START(service, username, pointer(conv), pointer(handle))

    if retval != 0:
        # TODO: This is not an authentication error, something
        # has gone wrong starting up PAM
        PAM_END(handle, retval)
        return False

    retval = PAM_AUTHENTICATE(handle, 0)
    if retval == 0:
        retval = PAM_ACCT_MGMT(handle, 0)
    PAM_END(handle, 0)
    return retval == 0


# Memo so the one-shot /etc/shadow-inaccessibility diagnostic only fires
# once per master process. Module-level so it survives across calls to
# ``authenticate()`` for the lifetime of the interpreter.
_SHADOW_DIAGNOSTIC_LOGGED = False

# Standard path to the shadow password database on Linux. Centralised so
# tests (and any non-standard distro layouts) can override.
_SHADOW_PATH = "/etc/shadow"


def _can_validate_other_users():
    """
    Return ``(True, "")`` if the current process has the privileges PAM
    needs to validate a *different* user's password via ``unix_chkpwd``;
    return ``(False, <reason>)`` otherwise.

    On Linux PAM's ``pam_unix`` module shells out to the setgid-shadow
    helper ``unix_chkpwd`` for password verification. ``unix_chkpwd``
    refuses to authenticate users other than the caller unless the
    caller can read ``/etc/shadow`` — either because the caller's
    effective uid is 0, or because the caller is in the ``shadow``
    group (Debian-style). See linux-pam upstream discussion at
    https://github.com/linux-pam/linux-pam/issues/112 for the full
    rationale.

    This helper is used to produce an actionable diagnostic when
    ``authenticate()`` fails on a master running as a non-root user
    without ``shadow``-group access — the failure mode behind issue
    #64275, which previously logged only a bare "Pam auth failed" with
    empty stdout/stderr.
    """
    try:
        if os.geteuid() == 0:
            return True, ""
    except AttributeError:
        # No ``geteuid`` on this platform (e.g. Windows). PAM auth
        # itself won't load there, but be defensive.
        return True, ""
    if os.access(_SHADOW_PATH, os.R_OK):
        return True, ""
    return (
        False,
        (
            "process running as uid {uid} cannot read {shadow}, so PAM's "
            "unix_chkpwd helper will refuse to authenticate users other "
            "than the caller"
        ).format(uid=os.geteuid(), shadow=_SHADOW_PATH),
    )


def _log_shadow_diagnostic_once(username):
    """
    Emit, at most once per process, a CRITICAL log entry that explains
    why PAM auth is failing on a non-root master and how to fix it.

    Issue #64275: when the master runs as the ``salt`` user (the 3006.x
    packaging default) PAM auth fails silently because the helper
    subprocess inherits that uid and ``unix_chkpwd`` can't read
    ``/etc/shadow``. Three years of users hit this without a
    diagnostic; this function makes the failure self-explanatory.
    """
    global _SHADOW_DIAGNOSTIC_LOGGED
    if _SHADOW_DIAGNOSTIC_LOGGED:
        return
    ok, reason = _can_validate_other_users()
    if ok:
        return
    _SHADOW_DIAGNOSTIC_LOGGED = True
    log.critical(
        "PAM authentication for %r failed and %s. Either run the "
        "salt-master as the 'root' user, or add the master's user to "
        "the 'shadow' group so it can read %s (the latter works on "
        "Debian-derived distributions; on RPM-based distributions "
        "the master must run as root for PAM eauth to work). See "
        "https://github.com/saltstack/salt/issues/64275 for context.",
        username,
        reason,
        _SHADOW_PATH,
    )


def authenticate(username, password):
    """
    Returns True if the given username and password authenticate for the
    given service.  Returns False otherwise

    ``username``: the username to authenticate

    ``password``: the password in plain text
    """
    env = os.environ.copy()
    env["SALT_PAM_USERNAME"] = username
    env["SALT_PAM_PASSWORD"] = password
    env["SALT_PAM_SERVICE"] = __opts__.get("auth.pam.service", "login")
    env["SALT_PAM_ENCODING"] = __salt_system_encoding__
    pyexe = pathlib.Path(__opts__.get("auth.pam.python", "/usr/bin/python3")).resolve()
    pyfile = pathlib.Path(__file__).resolve()
    if not pyexe.exists():
        log.error("Error 'auth.pam.python' config value does not exist: %s", pyexe)
        return False
    ret = subprocess.run(
        [str(pyexe), str(pyfile)],
        env=env,
        capture_output=True,
        check=False,
    )
    if ret.returncode == 0:
        return True
    log.error("Pam auth failed for %s: %s %s", username, ret.stdout, ret.stderr)
    # Issue #64275: when the master runs as a non-root user without
    # /etc/shadow read access, every PAM auth for users other than the
    # master's own uid fails with no useful diagnostic. Emit a one-shot
    # CRITICAL log naming the cause and remediation.
    _log_shadow_diagnostic_once(username)
    return False


def auth(username, password, **kwargs):
    """
    Authenticate via pam
    """
    return authenticate(username, password)


def groups(username, *args, **kwargs):
    """
    Retrieve groups for a given user for this auth provider

    Uses system groups
    """
    return salt.utils.user.get_group_list(username)


if __name__ == "__main__":
    if _authenticate(
        os.environ["SALT_PAM_USERNAME"],
        os.environ["SALT_PAM_PASSWORD"],
        os.environ["SALT_PAM_SERVICE"],
        os.environ["SALT_PAM_ENCODING"],
    ):
        sys.exit(0)
    sys.exit(1)
