# -*- coding: utf-8 -*-
# Copyright 2017 Damon Atkins
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
r'''
Collect information about software installed on Windows OS
================

:maintainer: Salt Stack <https://github.com/saltstack>
:codeauthor: Damon Atkins <https://github.com/damon-atkins>
:maturity: new
:depends: pywin32, six
:platform: windows

Known Issue: install_date may not match Control Panel\Programs\Programs and Features
'''


# Note although this code will work with Python 2.7, win32api does not
# support Unicode. i.e non ASCII characters may be returned with unexpected
# results e.g. a '?' instead of the correct character
# Python 3.6 or newer is recommended.

# Import _future_ python libs first & before any other code
# pylint: disable=incompatible-py3-code
from __future__ import absolute_import
from __future__ import unicode_literals
__version__ = '0.1'
# Import Standard libs
import sys
import re
import platform
import locale
import logging
import os.path
import datetime
import time
import collections
from functools import cmp_to_key
# Import third party libs
try:
    from salt.ext import six
except ImportError:
    import six  # pylint: disable=blacklisted-external-import

try:
    import win32api
    import win32con
    import win32process
    import win32security
    import pywintypes
    import winerror

except ImportError:
    if __name__ == '__main__':
        raise ImportError('Please install pywin32/pypiwin32')
    else:
        raise


if __name__ == '__main__':
    LOG_CONSOLE = logging.StreamHandler()
    LOG_CONSOLE.setFormatter(logging.Formatter('[%(levelname)s]: %(message)s'))
    log = logging.getLogger(__name__)
    log.addHandler(LOG_CONSOLE)
    log.setLevel(logging.DEBUG)
else:
    log = logging.getLogger(__name__)


try:
    from salt.utils.odict import OrderedDict
except ImportError:
    from collections import OrderedDict

try:
    from salt.utils.versions import LooseVersion
except ImportError:
    from distutils.version import LooseVersion  # pylint: disable=blacklisted-module


# pylint: disable=too-many-instance-attributes

class RegSoftwareInfo(object):
    '''
    Retrieve Registry data on a single installed software item or component.

    Attribute:
        None

    :codeauthor: Damon Atkins <https://github.com/damon-atkins>
    '''

    # Variables shared by all instances
    __guid_pattern = re.compile(r'^\{(\w{8})-(\w{4})-(\w{4})-(\w\w)(\w\w)-(\w\w)(\w\w)(\w\w)(\w\w)(\w\w)(\w\w)\}$')
    __squid_pattern = re.compile(r'^(\w{8})(\w{4})(\w{4})(\w\w)(\w\w)(\w\w)(\w\w)(\w\w)(\w\w)(\w\w)(\w\w)$')
    __version_pattern = re.compile(r'\d+\.\d+\.\d+[\w.-]*|\d+\.\d+[\w.-]*')
    __upgrade_codes = {}
    __upgrade_code_have_scan = {}

    __reg_types = {
        'str': (win32con.REG_EXPAND_SZ, win32con.REG_SZ),
        'list': (win32con.REG_MULTI_SZ),
        'int': (win32con.REG_DWORD, win32con.REG_DWORD_BIG_ENDIAN, win32con.REG_QWORD),
        'bytes': (win32con.REG_BINARY)
    }

    # Search 64bit, on 64bit platform, on 32bit its ignored
    if platform.architecture()[0] == '32bit':
        # Handle Python 32bit on 64&32 bit platform and Python 64bit
        if win32process.IsWow64Process():  # pylint: disable=no-member
            # 32bit python on a 64bit platform
            __use_32bit_lookup = {True: 0, False: win32con.KEY_WOW64_64KEY}
        else:
            # 32bit python on a 32bit platform
            __use_32bit_lookup = {True: 0, False: None}
    else:
        __use_32bit_lookup = {True: win32con.KEY_WOW64_32KEY, False: 0}

    def __init__(self, key_guid, sid=None, use_32bit=False):
        '''
        Initialise against a software item or component.

        All software has a unique "Identifer" within the registry. This can be free
        form text/numbers e.g. "MySoftware" or
        GUID e.g. "{0EAF0D8F-C9CF-4350-BD9A-07EC66929E04}"

        Args:
            key_guid (str): Identifer.
            sid (str): Security IDentifier of the User or None for Computer/Machine.
            use_32bit (bool):
                Regisrty location of the Identifer. ``True`` 32 bit registry only
                meaning fully on 64 bit OS.
        '''
        self.__reg_key_guid = key_guid  # also called IdentifyingNumber(wmic)
        self.__squid = ''
        self.__reg_products_path = ''
        self.__reg_upgradecode_path = ''
        self.__patch_list = None

        # If a valid GUID create the SQUID also.
        guid_match = self.__guid_pattern.match(key_guid)
        if guid_match is not None:
            for index in range(1, 12):
                # __guid_pattern breaks up the GUID
                self.__squid += guid_match.group(index)[::-1]

        if sid:
            # User data seems to be more spreadout within the registry.
            self.__reg_hive = 'HKEY_USERS'
            self.__reg_32bit = False  # Force to False
            self.__reg_32bit_access = 0  # HKEY_USERS does not have a 32bit and 64bit view
            self.__reg_uninstall_path = ('{0}\\Software\\Microsoft\\Windows\\'
                                         'CurrentVersion\\Uninstall\\{1}').format(sid, key_guid)
            if self.__squid:
                self.__reg_products_path = \
                    '{0}\\Software\\Classes\\Installer\\Products\\{1}'.format(sid, self.__squid)
                self.__reg_upgradecode_path = \
                    '{0}\\Software\\Microsoft\\Installer\\UpgradeCodes'.format(sid)
                self.__reg_patches_path = \
                    ('Software\\Microsoft\\Windows\\CurrentVersion\\Installer\\UserData\\'
                     '{0}\\Products\\{1}\\Patches').format(sid, self.__squid)
        else:
            self.__reg_hive = 'HKEY_LOCAL_MACHINE'
            self.__reg_32bit = use_32bit
            self.__reg_32bit_access = self.__use_32bit_lookup[use_32bit]
            self.__reg_uninstall_path = \
                'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{0}'.format(key_guid)
            if self.__squid:
                self.__reg_products_path = \
                    'Software\\Classes\\Installer\\Products\\{0}'.format(self.__squid)
                self.__reg_upgradecode_path = 'Software\\Classes\\Installer\\UpgradeCodes'
                self.__reg_patches_path = \
                    ('Software\\Microsoft\\Windows\\CurrentVersion\\Installer\\UserData\\'
                     'S-1-5-18\\Products\\{0}\\Patches').format(self.__squid)

        # OpenKey is expensive, open in advance and keep it open.
        # This must exist
        try:
            # pylint: disable=no-member
            self.__reg_uninstall_handle = \
                win32api.RegOpenKeyEx(getattr(win32con, self.__reg_hive),
                                      self.__reg_uninstall_path,
                                      0,
                                      win32con.KEY_READ | self.__reg_32bit_access)
        except pywintypes.error as exc:  # pylint: disable=no-member
            if exc.winerror == winerror.ERROR_FILE_NOT_FOUND:
                log.error(
                    ('Software/Component Not Found  key_guid: \'{0}\', sid: \'{1}\''
                     ', use_32bit: \'{2}\''.format(key_guid, sid, use_32bit))
                )
            raise  # This must exist or have no errors

        self.__reg_products_handle = None
        if self.__squid:
            try:
                # pylint: disable=no-member
                self.__reg_products_handle = \
                    win32api.RegOpenKeyEx(getattr(win32con, self.__reg_hive),
                                          self.__reg_products_path,
                                          0,
                                          win32con.KEY_READ | self.__reg_32bit_access)
            except pywintypes.error as exc:  # pylint: disable=no-member
                if exc.winerror == winerror.ERROR_FILE_NOT_FOUND:
                    log.debug(
                        ('Software/Component Not Found in Products section of registry '
                         'key_guid: \'{0}\', sid: \'{1}\', use_32bit: \'{2}\''
                         .format(key_guid, sid, use_32bit))
                    )
                    self.__squid = None  # mark it as not a SQUID
                else:
                    raise

        self.__mod_time1970 = 0
        # pylint: disable=no-member
        mod_win_time = win32api.RegQueryInfoKeyW(self.__reg_uninstall_handle).get('LastWriteTime', None)
        # pylint: enable=no-member
        if mod_win_time:
            # at some stage __int__() was removed from pywintypes.datetime to return secs since 1970
            if hasattr(mod_win_time, 'utctimetuple'):
                self.__mod_time1970 = time.mktime(mod_win_time.utctimetuple())
            elif hasattr(mod_win_time, '__int__'):
                self.__mod_time1970 = int(mod_win_time)

    def __squid_to_guid(self, squid):
        '''
        Squished GUID (SQUID) to GUID.

        A SQUID is a Squished/Compressed version of a GUID to use up less space
        in the registry.

        Args:
            squid (str): Squished GUID.

        Returns:
            str: the GUID if a valid SQUID provided.
        '''
        if not squid:
            return ''
        squid_match = self.__squid_pattern.match(squid)
        guid = ''
        if squid_match is not None:
            guid = '{' +\
                squid_match.group(1)[::-1]+'-' +\
                squid_match.group(2)[::-1]+'-' +\
                squid_match.group(3)[::-1]+'-' +\
                squid_match.group(4)[::-1]+squid_match.group(5)[::-1] + '-'
            for index in range(6, 12):
                guid += squid_match.group(index)[::-1]
            guid += '}'
        return guid

    @staticmethod
    def __one_equals_true(value):
        '''
        Test for ``1`` as a number or a string and return ``True`` if it is.

        Args:
            value: string or number or None.

        Returns:
            bool: ``True`` if 1 otherwise ``False``.
        '''
        if isinstance(value, six.integer_types) and value == 1:
            return True
        elif (isinstance(value, six.string_types) and
              re.match(r'\d+', value, flags=re.IGNORECASE + re.UNICODE) is not None and
              str(value) == 1):
            return True
        return False

    @staticmethod
    def __reg_query_value(handle, value_name):
        '''
        Calls RegQueryValueEx

        If PY2 ensure unicode string and expand REG_EXPAND_SZ before returning
        Remember to catch not found exceptions when calling.

        Args:
            handle (object): open registry handle.
            value_name (str): Name of the value you wished returned

        Returns:
            tuple: type, value
        '''
        # item_value, item_type = win32api.RegQueryValueEx(self.__reg_uninstall_handle, value_name)
        item_value, item_type = win32api.RegQueryValueEx(handle, value_name)  # pylint: disable=no-member
        if six.PY2 and isinstance(item_value, six.string_types) and not isinstance(item_value, six.text_type):
            try:
                item_value = six.text_type(item_value, encoding='mbcs')
            except UnicodeError:
                pass
        if item_type == win32con.REG_EXPAND_SZ:
            # expects Unicode input
            win32api.ExpandEnvironmentStrings(item_value)  # pylint: disable=no-member
            item_type = win32con.REG_SZ
        return item_value, item_type

    @property
    def install_time(self):
        '''
        Return the install time, or provide an estimate of install time.

        Installers or even self upgrading software must/should update the date
        held within InstallDate field when they change versions. Some installers
        do not set ``InstallDate`` at all so we use the last modified time on the
        registry key.

        Returns:
            int: Seconds since 1970 UTC.
        '''
        time1970 = self.__mod_time1970  # time of last resort
        try:
            # pylint: disable=no-member
            date_string, item_type = \
                win32api.RegQueryValueEx(self.__reg_uninstall_handle, 'InstallDate')
        except pywintypes.error as exc:  # pylint: disable=no-member
            if exc.winerror == winerror.ERROR_FILE_NOT_FOUND:
                return time1970  # i.e. use time of last resort
            else:
                raise

        if item_type == win32con.REG_SZ:
            try:
                date_object = datetime.datetime.strptime(date_string, "%Y%m%d")
                time1970 = time.mktime(date_object.timetuple())
            except ValueError:  # date format is not correct
                pass

        return time1970

    def get_install_value(self, value_name, wanted_type=None):
        '''
        For the uninstall section of the registry return the name value.

        Args:
            value_name (str): Registry value name.
            wanted_type (str):
                The type of value wanted if the type does not match
                None is return. wanted_type support values are
                ``str`` ``int`` ``list`` ``bytes``.

        Returns:
            value: Value requested or None if not found.
        '''
        try:
            item_value, item_type = self.__reg_query_value(self.__reg_uninstall_handle, value_name)
        except pywintypes.error as exc:  # pylint: disable=no-member
            if exc.winerror == winerror.ERROR_FILE_NOT_FOUND:
                # Not Found
                return None
            raise

        if wanted_type and item_type not in self.__reg_types[wanted_type]:
            item_value = None

        return item_value

    def is_install_true(self, key):
        '''
        For the uninstall section check if name value is ``1``.

        Args:
            value_name (str): Registry value name.

        Returns:
            bool: ``True`` if ``1`` otherwise ``False``.
        '''
        return self.__one_equals_true(self.get_install_value(key))

    def get_product_value(self, value_name, wanted_type=None):
        '''
        For the product section of the registry return the name value.

        Args:
            value_name (str): Registry value name.
            wanted_type (str):
                The type of value wanted if the type does not match
                None is return. wanted_type support values are
                ``str`` ``int`` ``list`` ``bytes``.

        Returns:
            value: Value requested or ``None`` if not found.
        '''
        if not self.__reg_products_handle:
            return None
        subkey, search_value_name = os.path.split(value_name)
        try:
            if subkey:

                handle = win32api.RegOpenKeyEx(  # pylint: disable=no-member
                            self.__reg_products_handle,
                            subkey,
                            0,
                            win32con.KEY_READ | self.__reg_32bit_access)
                item_value, item_type = self.__reg_query_value(handle, search_value_name)
                win32api.RegCloseKey(handle)  # pylint: disable=no-member
            else:
                item_value, item_type = \
                    win32api.RegQueryValueEx(self.__reg_products_handle, value_name)  # pylint: disable=no-member
        except pywintypes.error as exc:  # pylint: disable=no-member
            if exc.winerror == winerror.ERROR_FILE_NOT_FOUND:
                # Not Found
                return None
            raise

        if wanted_type and item_type not in self.__reg_types[wanted_type]:
            item_value = None
        return item_value

    @property
    def upgrade_code(self):
        '''
        For installers which follow the Microsoft Installer standard, returns
        the ``Upgrade code``.

        Returns:
            value (str): ``Upgrade code`` GUID for installed software.
        '''
        if not self.__squid:
            # Must have a valid squid for an upgrade code to exist
            return ''

        # GUID/SQUID are unique, so it does not matter if they are 32bit or
        # 64bit or user install so all items are cached into a single dict
        have_scan_key = '{0}\\{1}\\{2}'.format(self.__reg_hive, self.__reg_upgradecode_path, self.__reg_32bit)
        if not self.__upgrade_codes or self.__reg_key_guid not in self.__upgrade_codes:
            # Read in the upgrade codes in this section of the registry.
            try:
                uc_handle = win32api.RegOpenKeyEx(getattr(win32con, self.__reg_hive),  # pylint: disable=no-member
                                                  self.__reg_upgradecode_path,
                                                  0,
                                                  win32con.KEY_READ | self.__reg_32bit_access)
            except pywintypes.error as exc:  # pylint: disable=no-member
                if exc.winerror == winerror.ERROR_FILE_NOT_FOUND:
                    # Not Found
                    log.warning('Not Found {0}\\{1} 32bit {2}'.format(self.__reg_hive,
                                                                      self.__reg_upgradecode_path,
                                                                      self.__reg_32bit))
                    return ''
                raise
            squid_upgrade_code_all, _, _, suc_pytime = zip(*win32api.RegEnumKeyEx(uc_handle))  # pylint: disable=no-member

            # Check if we have already scanned these upgrade codes before, and also
            # check if they have been updated in the registry since last time we scanned.
            if (have_scan_key in self.__upgrade_code_have_scan and
                    self.__upgrade_code_have_scan[have_scan_key] == (squid_upgrade_code_all, suc_pytime)):
                log.debug('Scan skipped for upgrade codes, no changes (%s)', have_scan_key)
                return ''  # we have scanned this before and no new changes.

            # Go into each squid upgrade code and find all the related product codes.
            log.debug('Scan for upgrade codes (%s) for product codes', have_scan_key)
            for upgrade_code_squid in squid_upgrade_code_all:
                upgrade_code_guid = self.__squid_to_guid(upgrade_code_squid)
                pc_handle = win32api.RegOpenKeyEx(uc_handle,  # pylint: disable=no-member
                                                  upgrade_code_squid,
                                                  0,
                                                  win32con.KEY_READ | self.__reg_32bit_access)
                _, pc_val_count, _ = win32api.RegQueryInfoKey(pc_handle)  # pylint: disable=no-member
                for item_index in range(pc_val_count):
                    product_code_guid = \
                        self.__squid_to_guid(win32api.RegEnumValue(pc_handle, item_index)[0])  # pylint: disable=no-member
                    if product_code_guid:
                        self.__upgrade_codes[product_code_guid] = upgrade_code_guid
                win32api.RegCloseKey(pc_handle)  # pylint: disable=no-member

            win32api.RegCloseKey(uc_handle)  # pylint: disable=no-member
            self.__upgrade_code_have_scan[have_scan_key] = (squid_upgrade_code_all, suc_pytime)

        return self.__upgrade_codes.get(self.__reg_key_guid, '')

    @property
    def list_patches(self):
        '''
        For installers which follow the Microsoft Installer standard, returns
        a list of patches applied.

        Returns:
            value (list): Long name of the patch.
        '''
        if not self.__squid:
            # Must have a valid squid for an upgrade code to exist
            return []

        if self.__patch_list is None:
            # Read in the upgrade codes in this section of the reg.
            try:
                pat_all_handle = win32api.RegOpenKeyEx(getattr(win32con, self.__reg_hive),  # pylint: disable=no-member
                                                       self.__reg_patches_path,
                                                       0,
                                                       win32con.KEY_READ | self.__reg_32bit_access)
            except pywintypes.error as exc:  # pylint: disable=no-member
                if exc.winerror == winerror.ERROR_FILE_NOT_FOUND:
                    # Not Found
                    log.warning('Not Found {0}\\{1} 32bit {2}'.format(self.__reg_hive,
                                                                      self.__reg_patches_path,
                                                                      self.__reg_32bit))
                    return []
                raise

            pc_sub_key_cnt, _, _ = win32api.RegQueryInfoKey(pat_all_handle)  # pylint: disable=no-member
            if not pc_sub_key_cnt:
                return []
            squid_patch_all, _, _, _ = zip(*win32api.RegEnumKeyEx(pat_all_handle))  # pylint: disable=no-member

            ret = []
            # Scan the patches for the DisplayName of active patches.
            for patch_squid in squid_patch_all:
                try:
                    patch_squid_handle = win32api.RegOpenKeyEx(  # pylint: disable=no-member
                            pat_all_handle,
                            patch_squid,
                            0,
                            win32con.KEY_READ | self.__reg_32bit_access)
                    patch_display_name, patch_display_name_type = \
                        self.__reg_query_value(patch_squid_handle, 'DisplayName')
                    patch_state, patch_state_type = self.__reg_query_value(patch_squid_handle, 'State')
                    if (patch_state_type != win32con.REG_DWORD or
                            not isinstance(patch_state_type, six.integer_types) or
                            patch_state != 1 or   # 1 is Active, 2 is Superseded/Obsolute
                            patch_display_name_type != win32con.REG_SZ):
                        continue
                    win32api.RegCloseKey(patch_squid_handle)  # pylint: disable=no-member
                    ret.append(patch_display_name)
                except pywintypes.error as exc:  # pylint: disable=no-member
                    if exc.winerror == winerror.ERROR_FILE_NOT_FOUND:
                        log.debug('skipped patch, not found {}'.format(patch_squid))
                        continue
                    raise

        return ret

    @property
    def registry_path_text(self):
        '''
        Returns the uninstall path this object is associated with.

        Returns:
            str: <hive>\\<uninstall registry entry>
        '''
        return '{0}\\{1}'.format(self.__reg_hive, self.__reg_uninstall_path)

    @property
    def registry_path(self):
        '''
        Returns the uninstall path this object is associated with.

        Returns:
            tuple: hive, uninstall registry entry path.
        '''
        return (self.__reg_hive, self.__reg_uninstall_path)

    @property
    def guid(self):
        '''
        Return GUID or Key.

        Returns:
            str: GUID or Key
        '''
        return self.__reg_key_guid

    @property
    def squid(self):
        '''
        Return SQUID of the GUID if a valid GUID.

        Returns:
            str: GUID
        '''
        return self.__squid

    @property
    def package_code(self):
        '''
        Return package code of the software.

        Returns:
            str: GUID
        '''
        return self.__squid_to_guid(self.get_product_value('PackageCode'))

    @property
    def version_binary(self):
        '''
        Return version number which is stored in binary format.

        Returns:
            str: <major 0-255>.<minior 0-255>.<build 0-65535> or None if not found
        '''
        # Under MSI 'Version' is a 'REG_DWORD' which then sets other registry
        # values like DisplayVersion to x.x.x to the same value.
        # However not everyone plays by the rules, so we need to check first.
        # version_binary_data will be None if the reg value does not exist.
        # Some installs set 'Version' to REG_SZ (string) which is not
        # the MSI standard
        try:
            item_value, item_type = self.__reg_query_value(self.__reg_uninstall_handle, 'version')
        except pywintypes.error as exc:  # pylint: disable=no-member
            if exc.winerror == winerror.ERROR_FILE_NOT_FOUND:
                # Not Found
                return '', ''

        version_binary_text = ''
        version_src = ''
        if item_value:
            if item_type == win32con.REG_DWORD:
                if isinstance(item_value, six.integer_types):
                    version_binary_raw = item_value
                if version_binary_raw:
                    # Major.Minor.Build
                    version_binary_text = '{0}.{1}.{2}'.format(
                        version_binary_raw >> 24 & 0xff,
                        version_binary_raw >> 16 & 0xff,
                        version_binary_raw & 0xffff)
                    version_src = 'binary-version'

            elif (item_type == win32con.REG_SZ and
                    isinstance(item_value, six.string_types) and
                    self.__version_pattern.match(item_value) is not None):
                # Hey, version should be a int/REG_DWORD, an installer has set
                # it to a string
                version_binary_text = item_value.strip(' ')
                version_src = 'binary-version (string)'

        return (version_binary_text, version_src)


class WinSoftware(object):
    '''
    Point in time snapshot of the software and components installed on
    a system.

    Attributes:
        None

    :codeauthor: Damon Atkins <https://github.com/damon-atkins>
    '''
    __sid_pattern = re.compile(r'^S-\d-\d-\d+$|^S-\d-\d-\d+-\d+-\d+-\d+-\d+$')
    __whitespace_pattern = re.compile(r'^\s*$', flags=re.UNICODE)
    # items we copy out of the uninstall section of the registry without further processing
    __uninstall_search_list = [
      ('url', 'str', ['URLInfoAbout', 'HelpLink', 'MoreInfoUrl', 'UrlUpdateInfo']),
      ('size', 'int', ['Size', 'EstimatedSize']),
      ('win_comments', 'str', ['Comments']),
      ('win_release_type', 'str', ['ReleaseType']),
      ('win_product_id', 'str', ['ProductID']),
      ('win_product_codes', 'str', ['ProductCodes']),
      ('win_package_refs', 'str', ['PackageRefs']),
      ('win_install_location', 'str', ['InstallLocation']),
      ('win_install_src_dir', 'str', ['InstallSource']),
      ('win_parent_pkg_uid', 'str', ['ParentKeyName']),
      ('win_parent_name', 'str', ['ParentDisplayName'])
      ]
    # items we copy out of the products section of the registry without further processing
    __products_search_list = [
      ('win_advertise_flags', 'int', ['AdvertiseFlags']),
      ('win_redeployment_flags', 'int', ['DeploymentFlags']),
      ('win_instance_type', 'int', ['InstanceType']),
      ('win_package_name', 'str', ['SourceList\\PackageName'])
      ]

    def __init__(self, version_only=False, user_pkgs=False, pkg_obj=None):
        '''
        Point in time snapshot of the software and components installed on
        a system.

        Args:
            version_only (bool): Provide list of versions installed instead of detail.
            user_pkgs (bool): Include software/components installed with user space.
            pkg_obj (object):
                If None (default) return default package naming standard and use
                default version capture methods (``DisplayVersion`` then
                ``Version``, otherwise ``0.0.0.0``)
        '''
        self.__pkg_obj = pkg_obj  # must be set before calling get_software_details
        self.__version_only = version_only
        self.__reg_software = {}
        self.__get_software_details(user_pkgs=user_pkgs)
        self.__pkg_cnt = len(self.__reg_software)
        self.__iter_list = None

    @property
    def data(self):
        '''
        Returns the raw data

        Returns:
            dict: contents of the dict are dependant on the parameters passed
                when the class was initiated.
        '''
        return self.__reg_software

    @property
    def version_only(self):
        '''
        Returns True if class initiated with ``version_only=True``

        Returns:
            bool: The value of ``version_only``
        '''
        return self.__version_only

    def __len__(self):
        '''
        Returns total number of software/components installed.

        Returns:
            int: total number of software/components installed.
        '''
        return self.__pkg_cnt

    def __getitem__(self, pkg_id):
        '''
        Returns information on a package.

        Args:
            pkg_id (str): Package Id of the software/component

        Returns:
            dict or list: List if ``version_only`` is ``True`` otherwise dict
        '''
        if pkg_id in self.__reg_software:
            return self.__reg_software[pkg_id]
        else:
            raise KeyError(pkg_id)

    def __iter__(self):
        '''
        Standard interation class initialisation over package information.
        '''
        if self.__iter_list is not None:
            raise RuntimeError('Can only perform one iter at a time')
        self.__iter_list = collections.deque(sorted(self.__reg_software.keys()))
        return self

    def __next__(self):
        '''
        Returns next Package Id.

        Returns:
            str: Package Id
        '''
        try:
            return self.__iter_list.popleft()
        except IndexError:
            self.__iter_list = None
            raise StopIteration

    def next(self):
        '''
        Returns next Package Id.

        Returns:
            str: Package Id
        '''
        return self.__next__()

    def get(self, pkg_id, default_value=None):
        '''
        Returns information on a package.

        Args:
            pkg_id (str): Package Id of the software/component.
            default_value: Value to return when the Package Id is not found.

        Returns:
            dict or list: List if ``version_only`` is ``True`` otherwise dict
        '''
        return self.__reg_software.get(pkg_id, default_value)

    @staticmethod
    def __oldest_to_latest_version(ver1, ver2):
        '''
        Used for sorting version numbers oldest to latest
        '''
        return 1 if LooseVersion(ver1) > LooseVersion(ver2) else -1

    @staticmethod
    def __latest_to_oldest_version(ver1, ver2):
        '''
        Used for sorting version numbers, latest to oldest
        '''
        return 1 if LooseVersion(ver1) < LooseVersion(ver2) else -1

    def pkg_version_list(self, pkg_id):
        '''
        Returns information on a package.

        Args:
            pkg_id (str): Package Id of the software/component.

        Returns:
            list: List of version numbers installed.
        '''
        pkg_data = self.__reg_software.get(pkg_id, None)
        if not pkg_data:
            return []

        if isinstance(pkg_data, list):
            # raw data is 'pkgid': [sorted version list]
            return pkg_data  # already sorted oldest to newest

        # Must be a dict or OrderDict, and contain full details
        installed_versions = list(pkg_data.get('version').keys())
        return sorted(installed_versions, key=cmp_to_key(self.__oldest_to_latest_version))

    def pkg_version_latest(self, pkg_id):
        '''
        Returns a package latest version installed out of all the versions
        currently installed.

        Args:
            pkg_id (str): Package Id of the software/component.

        Returns:
            str: Latest/Newest version number installed.
        '''
        return self.pkg_version_list(pkg_id)[-1]

    def pkg_version_oldest(self, pkg_id):
        '''
        Returns a package oldest version installed out of all the versions
        currently installed.

        Args:
            pkg_id (str): Package Id of the software/component.

        Returns:
            str: Oldest version number installed.
        '''
        return self.pkg_version_list(pkg_id)[0]

    @staticmethod
    def __sid_to_username(sid):
        '''
        Provided with a valid Windows Security Identifier (SID) and returns a Username

        Args:
            sid (str): Security Identifier (SID).

        Returns:
            str: Username in the format of username@realm or username@computer.
        '''
        if sid is None or sid == '':
            return ''
        try:
            sid_bin = win32security.GetBinarySid(sid)  # pylint: disable=no-member
        except pywintypes.error as exc:  # pylint: disable=no-member
            raise ValueError(
                    'pkg: Software owned by {0} is not valid: [{1}] {2}'.format(sid, exc.winerror, exc.strerror)
                )
        try:
            name, domain, _account_type = win32security.LookupAccountSid(None, sid_bin)  # pylint: disable=no-member
            user_name = '{0}\\{1}'.format(domain, name)
        except pywintypes.error as exc:  # pylint: disable=no-member
            # if user does not exist...
            # winerror.ERROR_NONE_MAPPED = No mapping between account names and
            # security IDs was carried out.
            if exc.winerror == winerror.ERROR_NONE_MAPPED:  # 1332
                # As the sid is from the registry it should be valid
                # even if it cannot be lookedup, so the sid is returned
                return sid
            else:
                raise ValueError(
                          'Failed looking up sid \'{0}\' username: [{1}] {2}'.format(sid, exc.winerror, exc.strerror)
                        )
        try:
            user_principal = win32security.TranslateName(  # pylint: disable=no-member
                            user_name,
                            win32api.NameSamCompatible,  # pylint: disable=no-member
                            win32api.NameUserPrincipal)  # pylint: disable=no-member
        except pywintypes.error as exc:  # pylint: disable=no-member
            # winerror.ERROR_NO_SUCH_DOMAIN The specified domain either does not exist
            # or could not be contacted, computer may not be part of a domain also
            # winerror.ERROR_INVALID_DOMAINNAME The format of the specified domain name is
            # invalid. e.g. S-1-5-19 which is a local account
            # winerror.ERROR_NONE_MAPPED No mapping between account names and security IDs was done.
            if exc.winerror in (winerror.ERROR_NO_SUCH_DOMAIN,
                                winerror.ERROR_INVALID_DOMAINNAME,
                                winerror.ERROR_NONE_MAPPED):
                return '{0}@{1}'.format(name.lower(), domain.lower())
            else:
                raise
        return user_principal

    def __software_to_pkg_id(self, publisher, name, is_component, is_32bit):
        '''
        Determine the Package ID of a software/component using the
        software/component ``publisher``, ``name``, whether its a software or a
        component, and if its 32bit or 64bit archiecture.

        Args:
            publisher (str): Publisher of the software/component.
            name (str): Name of the software.
            is_component (bool): True if package is a component.
            is_32bit (bool): True if the software/component is 32bit architecture.

        Returns:
            str: Package Id
        '''
        if publisher:
            # remove , and lowercase as , are used as list separators
            pub_lc = publisher.replace(',', '').lower()

        else:
            # remove , and lowercase
            pub_lc = 'NoValue'  # Capitals/Special Value

        if name:
            name_lc = name.replace(',', '').lower()
            # remove ,   OR we do the URL Encode on chars we do not want e.g. \\ and ,
        else:
            name_lc = 'NoValue'  # Capitals/Special Value

        if is_component:
            soft_type = 'comp'
        else:
            soft_type = 'soft'

        if is_32bit:
            soft_type += '32'  # Tag only the 32bit only

        default_pkg_id = pub_lc+'\\\\'+name_lc+'\\\\'+soft_type

        # Check to see if class was initialise with pkg_obj with a method called
        # to_pkg_id, and if so use it for the naming standard instead of the default
        if self.__pkg_obj and hasattr(self.__pkg_obj, 'to_pkg_id'):
            pkg_id = self.__pkg_obj.to_pkg_id(publisher, name, is_component, is_32bit)
            if pkg_id:
                return pkg_id

        return default_pkg_id

    def __version_capture_slp(self, pkg_id, version_binary, version_display, display_name):
        '''
        This returns the version and where the version string came from, based on instructions
        under ``version_capture``, if ``version_capture`` is missing, it defaults to
        value of display-version.

        Args:
            pkg_id (str): Publisher of the software/component.
            version_binary (str): Name of the software.
            version_display (str): True if package is a component.
            display_name (str): True if the software/component is 32bit architecture.

        Returns:
            str: Package Id
        '''
        if self.__pkg_obj and hasattr(self.__pkg_obj, 'version_capture'):
            version_str, src, version_user_str = \
                self.__pkg_obj.version_capture(pkg_id, version_binary, version_display, display_name)
            if src != 'use-default' and version_str and src:
                return version_str, src, version_user_str
            elif src != 'use-default':
                raise ValueError(
                    'version capture within object \'{0}\' failed '
                    'for pkg id: \'{1}\' it returned \'{2}\' \'{3}\' '
                    '\'{4}\''.format(str(self.__pkg_obj), pkg_id, version_str, src, version_user_str)
                    )

        # If self.__pkg_obj.version_capture() not defined defaults to using
        # version_display and if not valid then use version_binary, and as a last
        # result provide the version 0.0.0.0.0 to indicate version string was not determined.
        if version_display and re.match(r'\d+', version_display, flags=re.IGNORECASE + re.UNICODE) is not None:
            version_str = version_display
            src = 'display-version'
        elif version_binary and re.match(r'\d+', version_binary, flags=re.IGNORECASE + re.UNICODE) is not None:
            version_str = version_binary
            src = 'version-binary'
        else:
            src = 'none'
            version_str = '0.0.0.0.0'
        # return version str, src of the version, "user" interpretation of the version
        # which by default is version_str
        return version_str, src, version_str

    def __collect_software_info(self, sid, key_software, use_32bit):
        '''
        Update data with the next software found
        '''

        reg_soft_info = RegSoftwareInfo(key_software, sid, use_32bit)

        # Check if the registry entry is a valid.
        # a) Cannot manage software without at least a display name
        display_name = reg_soft_info.get_install_value('DisplayName', wanted_type='str')
        if display_name is None or self.__whitespace_pattern.match(display_name):
            return

        # b) make sure its not an 'Hotfix', 'Update Rollup', 'Security Update', 'ServicePack'
        # General this is software which pre dates Windows 10
        default_value = reg_soft_info.get_install_value('', wanted_type='str')
        release_type = reg_soft_info.get_install_value('ReleaseType', wanted_type='str')

        if (re.match(r'^{.*\}\.KB\d{6,}$', key_software, flags=re.IGNORECASE + re.UNICODE) is not None or
                (default_value and default_value.startswith(('KB', 'kb', 'Kb'))) or
                (release_type and release_type in ('Hotfix', 'Update Rollup', 'Security Update', 'ServicePack'))):
            log.debug('skipping hotfix/update/service pack {0}'.format(key_software))
            return

        # if NoRemove exists we would expect their to be no UninstallString
        uninstall_no_remove = reg_soft_info.is_install_true('NoRemove')
        uninstall_string = reg_soft_info.get_install_value('UninstallString')
        uninstall_quiet_string = reg_soft_info.get_install_value('QuietUninstallString')
        uninstall_modify_path = reg_soft_info.get_install_value('ModifyPath')
        windows_installer = reg_soft_info.is_install_true('WindowsInstaller')
        system_component = reg_soft_info.is_install_true('SystemComponent')
        publisher = reg_soft_info.get_install_value('Publisher', wanted_type='str')

        # UninstallString is optional if the installer is "windows installer"/MSI
        # However for it to appear in Control-Panel -> Program and Features -> Uninstall or change a program
        # the UninstallString needs to be set or ModifyPath set
        if (uninstall_string is None and
                uninstall_quiet_string is None and
                uninstall_modify_path is None and
                (not windows_installer)):
            return

        # Question: If uninstall string is not set and windows_installer should we set it
        # Question: if uninstall_quiet is not set .......

        if sid:
            username = self.__sid_to_username(sid)
        else:
            username = None

        # We now have a valid software install or a system component
        pkg_id = self.__software_to_pkg_id(publisher, display_name, system_component, use_32bit)
        version_binary, version_src = reg_soft_info.version_binary
        version_display = reg_soft_info.get_install_value('DisplayVersion', wanted_type='str')
        # version_capture is what the slp defines, the result overrides. Question: maybe it should error if it fails?
        (version_text, version_src, user_version) = \
            self.__version_capture_slp(pkg_id, version_binary, version_display, display_name)
        if not user_version:
            user_version = version_text

        # log.trace('%s\\%s ver:%s src:%s', username or 'SYSTEM', pkg_id, version_text, version_src)

        if username:
            dict_key = '{};{}'.format(username, pkg_id)  # Use ; as its not a valid hostnmae char
        else:
            dict_key = pkg_id

        # Guessing the architecture http://helpnet.flexerasoftware.com/isxhelp21/helplibrary/IHelp64BitSupport.htm
        # A 32 bit installed.exe can install a 64 bit app, but for it to write to 64bit reg it will
        # need to use WOW. So the following is a bit of a guess

        if self.__version_only:
            # package name and package version list, are the only info being return
            if dict_key in self.__reg_software:
                if version_text not in self.__reg_software[dict_key]:
                    # Not expecting the list to be big, simple search and insert
                    insert_point = 0
                    for ver_item in self.__reg_software[dict_key]:
                        if LooseVersion(version_text) <= LooseVersion(ver_item):
                            break
                        insert_point += 1
                    self.__reg_software[dict_key].insert(insert_point, version_text)
                else:
                    # This code is here as it can happen, especially if the
                    # package id provided by pkg_obj is simple.
                    log.debug((
                               'Found extra entries for \'{0}\' with same version \'{1}\' '
                               'skipping entry \'{2}\''.format(dict_key, version_text, key_software)
                               ))
            else:
                self.__reg_software[dict_key] = [version_text]

            return

        if dict_key in self.__reg_software:
            data = self.__reg_software[dict_key]
        else:
            data = self.__reg_software[dict_key] = OrderedDict()

        if sid:
            # HKEY_USERS has no 32bit and 64bit view like HKEY_LOCAL_MACHINE
            data.update({'arch': 'unknown'})
        else:
            arch_str = 'x86' if use_32bit else 'x64'
            if 'arch' in data:
                if data['arch'] != arch_str:
                    data['arch'] = 'many'
            else:
                data.update({'arch': arch_str})

        if publisher:
            if 'vendor' in data:
                if data['vendor'].lower() != publisher.lower():
                    data['vendor'] = 'many'
            else:
                data['vendor'] = publisher

        if 'win_system_component' in data:
            if data['win_system_component'] != system_component:
                data['win_system_component'] = None
        else:
            data['win_system_component'] = system_component

        data.update({'win_version_src': version_src})

        data.setdefault('version', {})
        if version_text in data['version']:
            if 'win_install_count' in data['version'][version_text]:
                data['version'][version_text]['win_install_count'] += 1
            else:
                # This is only defined when we have the same item already
                data['version'][version_text]['win_install_count'] = 2
        else:
            data['version'][version_text] = OrderedDict()

        version_data = data['version'][version_text]
        version_data.update({'win_display_name': display_name})
        if uninstall_string:
            version_data.update({'win_uninstall_cmd': uninstall_string})
        if uninstall_quiet_string:
            version_data.update({'win_uninstall_quiet_cmd': uninstall_quiet_string})
        if uninstall_no_remove:
            version_data.update({'win_uninstall_no_remove': uninstall_no_remove})

        version_data.update({'win_product_code': key_software})
        if version_display:
            version_data.update({'win_version_display': version_display})
        if version_binary:
            version_data.update({'win_version_binary': version_binary})
        if user_version:
            version_data.update({'win_version_user': user_version})

        # Determine Installer Product
        #   'NSIS:Language'
        #   'Inno Setup: Setup Version'
        if (windows_installer or
                (uninstall_string and
                    re.search(r'MsiExec.exe\s|MsiExec\s', uninstall_string, flags=re.IGNORECASE + re.UNICODE))):
            version_data.update({'win_installer_type': 'winmsi'})
        elif (re.match(r'InstallShield_', key_software, re.IGNORECASE) is not None or
                (uninstall_string and (
                 re.search(r'InstallShield', uninstall_string, flags=re.IGNORECASE + re.UNICODE) is not None or
                 re.search(r'isuninst\.exe.*\.isu', uninstall_string, flags=re.IGNORECASE + re.UNICODE) is not None)
                 )
              ):
            version_data.update({'win_installer_type': 'installshield'})
        elif (key_software.endswith('_is1') and
              reg_soft_info.get_install_value('Inno Setup: Setup Version', wanted_type='str')):
            version_data.update({'win_installer_type': 'inno'})
        elif (uninstall_string and
              re.search(r'.*\\uninstall.exe|.*\\uninst.exe', uninstall_string, flags=re.IGNORECASE + re.UNICODE)):
            version_data.update({'win_installer_type': 'nsis'})
        else:
            version_data.update({'win_installer_type': 'unknown'})

        # Update dict with information retrieved so far for detail results to be return
        # Do not add fields which are blank.
        language_number = reg_soft_info.get_install_value('Language')
        if isinstance(language_number, six.integer_types) and language_number in locale.windows_locale:
            version_data.update({'win_language': locale.windows_locale[language_number]})

        package_code = reg_soft_info.package_code
        if package_code:
            version_data.update({'win_package_code': package_code})

        upgrade_code = reg_soft_info.upgrade_code
        if upgrade_code:
            version_data.update({'win_upgrade_code': upgrade_code})

        is_minor_upgrade = reg_soft_info.is_install_true('IsMinorUpgrade')
        if is_minor_upgrade:
            version_data.update({'win_is_minor_upgrade': is_minor_upgrade})

        install_time = reg_soft_info.install_time
        if install_time:
            version_data.update({'install_date': datetime.datetime.fromtimestamp(install_time).isoformat()})
            version_data.update({'install_date_time_t': int(install_time)})

        for infokey, infotype, regfield_list in self.__uninstall_search_list:
            for regfield in regfield_list:
                strvalue = reg_soft_info.get_install_value(regfield, wanted_type=infotype)
                if strvalue:
                    version_data.update({infokey: strvalue})
                    break

        for infokey, infotype, regfield_list in self.__products_search_list:
            for regfield in regfield_list:
                data = reg_soft_info.get_product_value(regfield, wanted_type=infotype)
                if data is not None:
                    version_data.update({infokey: data})
                    break
        patch_list = reg_soft_info.list_patches
        if patch_list:
            version_data.update({'win_patches': patch_list})

    def __get_software_details(self, user_pkgs):
        '''
        This searches the uninstall keys in the registry to find
        a match in the sub keys, it will return a dict with the
        display name as the key and the version as the value
        .. sectionauthor:: Damon Atkins <https://github.com/damon-atkins>
        .. versionadded:: Carbon
        '''

        # FUNCTION MAIN CODE #
        # Search 64bit, on 64bit platform, on 32bit its ignored.
        if platform.architecture()[0] == '32bit':
            # Handle Python 32bit on 64&32 bit platform and Python 64bit
            if win32process.IsWow64Process():  # pylint: disable=no-member
                # 32bit python on a 64bit platform
                use_32bit_lookup = {True: 0, False: win32con.KEY_WOW64_64KEY}
                arch_list = [True, False]
            else:
                # 32bit python on a 32bit platform
                use_32bit_lookup = {True: 0, False: None}
                arch_list = [True]

        else:
            # Python is 64bit therefore most be on 64bit System.
            use_32bit_lookup = {True: win32con.KEY_WOW64_32KEY, False: 0}
            arch_list = [True, False]

        # Process software installed for the machine i.e. all users.
        for arch_flag in arch_list:
            key_search = 'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall'
            log.debug('SYSTEM processing 32bit:{0}'.format(arch_flag))
            handle = win32api.RegOpenKeyEx(  # pylint: disable=no-member
                        win32con.HKEY_LOCAL_MACHINE,
                        key_search,
                        0,
                        win32con.KEY_READ | use_32bit_lookup[arch_flag])
            reg_key_all, _, _, _ = zip(*win32api.RegEnumKeyEx(handle))  # pylint: disable=no-member
            win32api.RegCloseKey(handle)  # pylint: disable=no-member
            for reg_key in reg_key_all:
                self.__collect_software_info(None, reg_key, arch_flag)

        if not user_pkgs:
            return

        # Process software installed under all USERs, this adds significate processing time.
        # There is not 32/64 bit registry redirection under user tree.
        log.debug('Processing user software... please wait')
        handle_sid = win32api.RegOpenKeyEx(  # pylint: disable=no-member
                        win32con.HKEY_USERS,
                        '',
                        0,
                        win32con.KEY_READ)
        sid_all = []
        for index in range(win32api.RegQueryInfoKey(handle_sid)[0]):  # pylint: disable=no-member
            sid_all.append(win32api.RegEnumKey(handle_sid, index))  # pylint: disable=no-member

        for sid in sid_all:
            if self.__sid_pattern.match(sid) is not None:  # S-1-5-18 needs to be ignored?
                user_uninstall_path = '{0}\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall'.format(sid)
                try:
                    handle = win32api.RegOpenKeyEx(  # pylint: disable=no-member
                                handle_sid,
                                user_uninstall_path,
                                0,
                                win32con.KEY_READ)
                except pywintypes.error as exc:  # pylint: disable=no-member
                    if exc.winerror == winerror.ERROR_FILE_NOT_FOUND:
                        # Not Found Uninstall under SID
                        log.debug('Not Found {}'.format(user_uninstall_path))
                        continue
                    else:
                        raise
                try:
                    reg_key_all, _, _, _ = zip(*win32api.RegEnumKeyEx(handle))  # pylint: disable=no-member
                except ValueError:
                    log.debug(('No Entries Found {}').format(user_uninstall_path))
                    reg_key_all = []
                win32api.RegCloseKey(handle)  # pylint: disable=no-member
                for reg_key in reg_key_all:
                    self.__collect_software_info(sid, reg_key, False)
        win32api.RegCloseKey(handle_sid)  # pylint: disable=no-member
        return


def __main():
    '''This module can also be run directly for testing
        Args:
            detail|list : Provide ``detail`` or version ``list``.
            system|system+user: System installed and System and User installs.
    '''
    if len(sys.argv) < 3:
        sys.stderr.write('usage: {0} <detail|list> <system|system+user>\n'.format(sys.argv[0]))
        sys.exit(64)
    user_pkgs = False
    version_only = False
    if str(sys.argv[1]) == 'list':
        version_only = True
    if str(sys.argv[2]) == 'system+user':
        user_pkgs = True
    import json
    import timeit

    def run():
        '''
        Main run code, when this module is run directly
        '''
        pkg_list = WinSoftware(user_pkgs=user_pkgs, version_only=version_only)
        print(json.dumps(pkg_list.data, sort_keys=True, indent=4))  # pylint: disable=superfluous-parens
        print('Total: {}'.format(len(pkg_list)))  # pylint: disable=superfluous-parens

    print('Time Taken: {}'.format(timeit.timeit(run, number=1)))  # pylint: disable=superfluous-parens


if __name__ == '__main__':
    __main()
