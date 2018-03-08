# -*- coding: utf-8 -*-
'''
Get Version information from Windows
'''
# http://stackoverflow.com/questions/32300004/python-ctypes-getting-0-with-getversionex-function
from __future__ import absolute_import, print_function, unicode_literals

# Import Third Party Libs
import ctypes
try:
    from ctypes.wintypes import BYTE, WORD, DWORD, WCHAR
    HAS_WIN32 = True
except (ImportError, ValueError):
    HAS_WIN32 = False

if HAS_WIN32:
    kernel32 = ctypes.WinDLL(str('kernel32'),  # future lint: disable=blacklisted-function
                             use_last_error=True)


# Although utils are often directly imported, it is also possible to use the
# loader.
def __virtual__():
    '''
    Only load if Win32 Libraries are installed
    '''
    if not HAS_WIN32:
        return False, 'This utility requires pywin32'

    return 'win_osinfo'


def os_version_info_ex():
    '''
    Helper function to return the results of the GetVersionExW Windows API call.
    It is a ctypes Structure that contains Windows OS Version information.

    Returns:
        class: An instance of a class containing version info
    '''
    if not HAS_WIN32:
        return

    class OSVersionInfo(ctypes.Structure):
        _fields_ = (('dwOSVersionInfoSize', DWORD),
                    ('dwMajorVersion', DWORD),
                    ('dwMinorVersion', DWORD),
                    ('dwBuildNumber', DWORD),
                    ('dwPlatformId', DWORD),
                    ('szCSDVersion', WCHAR * 128))

        def __init__(self, *args, **kwds):
            super(OSVersionInfo, self).__init__(*args, **kwds)
            self.dwOSVersionInfoSize = ctypes.sizeof(self)
            kernel32.GetVersionExW(ctypes.byref(self))

    class OSVersionInfoEx(OSVersionInfo):
        _fields_ = (('wServicePackMajor', WORD),
                    ('wServicePackMinor', WORD),
                    ('wSuiteMask', WORD),
                    ('wProductType', BYTE),
                    ('wReserved', BYTE))

    return OSVersionInfoEx()


def get_os_version_info():
    info = os_version_info_ex()
    ret = {'MajorVersion': info.dwMajorVersion,
           'MinorVersion': info.dwMinorVersion,
           'BuildNumber': info.dwBuildNumber,
           'PlatformID': info.dwPlatformId,
           'ServicePackMajor': info.wServicePackMajor,
           'ServicePackMinor': info.wServicePackMinor,
           'SuiteMask': info.wSuiteMask,
           'ProductType': info.wProductType}

    return ret
