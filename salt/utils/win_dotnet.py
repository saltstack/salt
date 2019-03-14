# -*- coding: utf-8 -*-
'''
Dot NET functions
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.platform
import salt.utils.win_reg as win_reg

__virtualname__ = 'dotnet'


# Although utils are often directly imported, it is also possible to use the
# loader.
def __virtual__():
    '''
    Only load if Win32 Libraries are installed
    '''
    if not salt.utils.platform.is_windows():
        return False, 'This utility only works on Windows'

    return __virtualname__


def versions():
    hive = 'HKLM'
    key = 'SOFTWARE\\Microsoft\\NET Framework Setup\\NDP'
    ver_keys = win_reg.list_keys(hive=hive, key=key)

    def dotnet_45_plus_versions(release):
        if release >= 461808:
            return '4.7.2'
        if release >= 461308:
            return '4.7.1'
        if release >= 460798:
            return '4.7'
        if release >= 394802:
            return '4.6.2'
        if release >= 394254:
            return '4.6.1'
        if release >= 393295:
            return '4.6'
        if release >= 379893:
            return '4.5.2'
        if release >= 378675:
            return '4.5.1'
        if release >= 378389:
            return '4..5'

    return_dict = {'versions': [],
                   'details': {}}
    for ver_key in ver_keys:

        if ver_key.startswith('v'):
            if win_reg.value_exists(hive=hive,
                                    key='\\'.join([key, ver_key]),
                                    vname='Version'):
                # https://docs.microsoft.com/en-us/dotnet/framework/migration-guide/how-to-determine-which-versions-are-installed#find-net-framework-versions-1-4-with-codep
                install = win_reg.read_value(
                    hive=hive,
                    key='\\'.join([key, ver_key]),
                    vname='Install')['vdata']
                if not install:
                    continue
                version = win_reg.read_value(
                    hive=hive,
                    key='\\'.join([key, ver_key]),
                    vname='Version')['vdata']
                sp = win_reg.read_value(
                    hive=hive,
                    key='\\'.join([key, ver_key]),
                    vname='SP')['vdata']
            elif win_reg.value_exists(
                    hive=hive,
                    key='\\'.join([key, ver_key, 'Full']),
                    vname='Release'):
                # https://docs.microsoft.com/en-us/dotnet/framework/migration-guide/how-to-determine-which-versions-are-installed#find-net-framework-versions-45-and-later-with-code
                version = dotnet_45_plus_versions(
                    win_reg.read_value(
                        hive=hive,
                        key='\\'.join([key, ver_key, 'Full']),
                        vname='Release')['vdata'])
                sp = 'N/A'
            else:
                continue

            service_pack = ' SP{0}'.format(sp) if not sp == 'N/A' else ''
            return_dict['versions'].append(version)
            return_dict['details'][ver_key] = {
                'version': version,
                'service_pack': sp,
                'full': '{0}{1}'.format(version, service_pack)}

    return return_dict


def versions_list():
    return sorted(versions()['versions'])


def versions_details():
    return versions()['details']
