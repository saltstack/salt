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
'''

# Import python libs
from ctypes import CDLL, POINTER, Structure, CFUNCTYPE, cast, pointer, sizeof
from ctypes import c_void_p, c_uint, c_char_p, c_char, c_int
from ctypes.util import find_library

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
        return "<PamMessage %i '%s'>" % (self.msg_style, self.msg)


class PamResponse(Structure):
    '''
    Wrapper class for pam_response structure
    '''
    _fields_ = [
            ('resp', c_char_p),
            ('resp_retcode', c_int),
            ]

    def __repr__(self):
        return "<PamResponse %i '%s'>" % (self.resp_retcode, self.resp)


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
except Exception:
    HAS_PAM = False
else:
    HAS_PAM = True


def __virtual__():
    '''
    Only load on Linux systems
    '''
    if HAS_PAM:
        return 'pam'
    else:
        return False


def authenticate(username, password, service='login'):
    '''
    Returns True if the given username and password authenticate for the
    given service.  Returns False otherwise

    ``username``: the username to authenticate

    ``password``: the password in plain text

    ``service``: the PAM service to authenticate against.
                 Defaults to 'login'
    '''
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
        return False

    retval = PAM_AUTHENTICATE(handle, 0)
    return retval == 0


def auth(username, password, **kwargs):
    '''
    Authenticate via pam
    '''
    return authenticate(username, password, kwargs.get('service', 'login'))
