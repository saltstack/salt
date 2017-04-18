# -*- coding: utf-8 -*-
# The pam components have been modified to be salty and have been taken from
# the pam module under this licence:
# (c) 2007 Chris AtLee <chris@atlee.ca>
# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license.php
'''
Authenticate against PAM

Provides an authenticate function that will allow the caller to authenticate
a user against the Pluggable Authentication Modules (PAM) on the system.

Implemented using ctypes, so no compilation is necessary.

There is one extra configuration option for pam.  The `pam_service` that is
authenticated against.  This defaults to `login`

.. code-block:: yaml

    auth.pam.service: login

.. note:: PAM authentication will not work for the ``root`` user.

    The Python interface to PAM does not support authenticating as ``root``.

.. note:: Using PAM groups with SSSD groups on python2.

    To use sssd with the PAM eauth module and groups the `pysss` module is
    needed.  On RedHat/CentOS this is `python-sss`.

    This should not be needed with python >= 3.3, because the `os` modules has the
    `getgrouplist` function.

'''

# Import Python Libs
from __future__ import absolute_import
from ctypes import CDLL, POINTER, Structure, CFUNCTYPE, cast, pointer, sizeof
from ctypes import c_void_p, c_uint, c_char_p, c_char, c_int
from ctypes.util import find_library

# Import Salt libs
from salt.utils import get_group_list
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

LIBPAM = CDLL(find_library('pam'))
LIBC = CDLL(find_library('c'))

CALLOC = LIBC.calloc
CALLOC.restype = c_void_p
CALLOC.argtypes = [c_uint, c_uint]

STRDUP = LIBC.strdup
STRDUP.argstypes = [c_char_p]
STRDUP.restype = POINTER(c_char)  # NOT c_char_p !!!!

# Various constants
PAM_PROMPT_ECHO_OFF = 1
PAM_PROMPT_ECHO_ON = 2
PAM_ERROR_MSG = 3
PAM_TEXT_INFO = 4


class PamHandle(Structure):
    '''
    Wrapper class for pam_handle_t
    '''
    _fields_ = [
            ('handle', c_void_p)
            ]

    def __init__(self):
        Structure.__init__(self)
        self.handle = 0


class PamMessage(Structure):
    '''
    Wrapper class for pam_message structure
    '''
    _fields_ = [
            ("msg_style", c_int),
            ("msg", c_char_p),
            ]

    def __repr__(self):
        return '<PamMessage {0} \'{1}\'>'.format(self.msg_style, self.msg)


class PamResponse(Structure):
    '''
    Wrapper class for pam_response structure
    '''
    _fields_ = [
            ('resp', c_char_p),
            ('resp_retcode', c_int),
            ]

    def __repr__(self):
        return '<PamResponse {0} \'{1}\'>'.format(self.resp_retcode, self.resp)


CONV_FUNC = CFUNCTYPE(c_int,
        c_int, POINTER(POINTER(PamMessage)),
               POINTER(POINTER(PamResponse)), c_void_p)


class PamConv(Structure):
    '''
    Wrapper class for pam_conv structure
    '''
    _fields_ = [
            ('conv', CONV_FUNC),
            ('appdata_ptr', c_void_p)
            ]


try:
    PAM_START = LIBPAM.pam_start
    PAM_START.restype = c_int
    PAM_START.argtypes = [c_char_p, c_char_p, POINTER(PamConv),
            POINTER(PamHandle)]

    PAM_AUTHENTICATE = LIBPAM.pam_authenticate
    PAM_AUTHENTICATE.restype = c_int
    PAM_AUTHENTICATE.argtypes = [PamHandle, c_int]

    PAM_ACCT_MGMT = LIBPAM.pam_acct_mgmt
    PAM_ACCT_MGMT.restype = c_int
    PAM_ACCT_MGMT.argtypes = [PamHandle, c_int]

    PAM_END = LIBPAM.pam_end
    PAM_END.restype = c_int
    PAM_END.argtypes = [PamHandle, c_int]
except Exception:
    HAS_PAM = False
else:
    HAS_PAM = True


def __virtual__():
    '''
    Only load on Linux systems
    '''
    return HAS_PAM


def authenticate(username, password):
    '''
    Returns True if the given username and password authenticate for the
    given service.  Returns False otherwise

    ``username``: the username to authenticate

    ``password``: the password in plain text
    '''
    service = __opts__.get('auth.pam.service', 'login')

    @CONV_FUNC
    def my_conv(n_messages, messages, p_response, app_data):
        '''
        Simple conversation function that responds to any
        prompt where the echo is off with the supplied password
        '''
        # Create an array of n_messages response objects
        addr = CALLOC(n_messages, sizeof(PamResponse))
        p_response[0] = cast(addr, POINTER(PamResponse))
        for i in range(n_messages):
            if messages[i].contents.msg_style == PAM_PROMPT_ECHO_OFF:
                pw_copy = STRDUP(str(password))
                p_response.contents[i].resp = cast(pw_copy, c_char_p)
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
        PAM_ACCT_MGMT(handle, 0)
    PAM_END(handle, 0)
    return retval == 0


def auth(username, password, **kwargs):
    '''
    Authenticate via pam
    '''
    return authenticate(username, password)


def groups(username, *args, **kwargs):
    '''
    Retrieve groups for a given user for this auth provider

    Uses system groups
    '''
    return get_group_list(username)
