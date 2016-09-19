# -*- coding: utf-8 -*-
'''
Get Versioning information from Windows
'''
# http://stackoverflow.com/questions/32300004/python-ctypes-getting-0-with-getversionex-function
from __future__ import absolute_import

import ctypes
from ctypes.wintypes import BYTE, WORD, DWORD, WCHAR

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)


class OSVERSIONINFO(ctypes.Structure):
    _fields_ = (('dwOSVersionInfoSize', DWORD),
                ('dwMajorVersion', DWORD),
                ('dwMinorVersion', DWORD),
                ('dwBuildNumber', DWORD),
                ('dwPlatformId', DWORD),
                ('szCSDVersion', WCHAR * 128))

    def __init__(self, *args, **kwds):
        super(OSVERSIONINFO, self).__init__(*args, **kwds)
        self.dwOSVersionInfoSize = ctypes.sizeof(self)
        kernel32.GetVersionExW(ctypes.byref(self))


class OSVERSIONINFOEX(OSVERSIONINFO):
    _fields_ = (('wServicePackMajor', WORD),
                ('wServicePackMinor', WORD),
                ('wSuiteMask', WORD),
                ('wProductType', BYTE),
                ('wReserved', BYTE))


def errcheck_bool(result, func, args):
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    return args

kernel32.GetVersionExW.errcheck = errcheck_bool
kernel32.GetVersionExW.argtypes = (ctypes.POINTER(OSVERSIONINFO),)


def get_os_version_info():
    info = OSVERSIONINFOEX()
    ret = {'MajorVersion': info.dwMajorVersion,
           'MinorVersion': info.dwMinorVersion,
           'BuildNumber': info.dwBuildNumber,
           'PlatformID': info.dwPlatformId,
           'ServicePackMajor': info.wServicePackMajor,
           'ServicePackMinor': info.wServicePackMinor,
           'SuiteMask': info.wSuiteMask,
           'ProductType': info.wProductType}

    return ret
