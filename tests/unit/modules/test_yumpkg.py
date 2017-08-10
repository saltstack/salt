# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt libs
import salt.modules.yumpkg as yumpkg
import salt.modules.pkg_resource as pkg_resource


@skipIf(NO_MOCK, NO_MOCK_REASON)
class YumTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.yumpkg
    '''
    def setup_loader_modules(self):
        return {yumpkg: {'rpm': None}}

    def test_list_pkgs(self):
        '''
        Test packages listing.

        :return:
        '''
        def _add_data(data, key, value):
            data.setdefault(key, []).append(value)

        rpm_out = [
            'python-urlgrabber_|-(none)_|-3.10_|-8.el7_|-noarch_|-(none)_|-1487838471',
            'alsa-lib_|-(none)_|-1.1.1_|-1.el7_|-x86_64_|-(none)_|-1487838475',
            'gnupg2_|-(none)_|-2.0.22_|-4.el7_|-x86_64_|-(none)_|-1487838477',
            'rpm-python_|-(none)_|-4.11.3_|-21.el7_|-x86_64_|-(none)_|-1487838477',
            'pygpgme_|-(none)_|-0.3_|-9.el7_|-x86_64_|-(none)_|-1487838478',
            'yum_|-(none)_|-3.4.3_|-150.el7.centos_|-noarch_|-(none)_|-1487838479',
            'lzo_|-(none)_|-2.06_|-8.el7_|-x86_64_|-(none)_|-1487838479',
            'qrencode-libs_|-(none)_|-3.4.1_|-3.el7_|-x86_64_|-(none)_|-1487838480',
            'ustr_|-(none)_|-1.0.4_|-16.el7_|-x86_64_|-(none)_|-1487838480',
            'shadow-utils_|-2_|-4.1.5.1_|-24.el7_|-x86_64_|-(none)_|-1487838481',
            'util-linux_|-(none)_|-2.23.2_|-33.el7_|-x86_64_|-(none)_|-1487838484',
            'openssh_|-(none)_|-6.6.1p1_|-33.el7_3_|-x86_64_|-(none)_|-1487838485',
            'virt-what_|-(none)_|-1.13_|-8.el7_|-x86_64_|-(none)_|-1487838486',
        ]
        with patch.dict(yumpkg.__grains__, {'osarch': 'x86_64'}), \
             patch.dict(yumpkg.__salt__, {'cmd.run': MagicMock(return_value=os.linesep.join(rpm_out))}), \
             patch.dict(yumpkg.__salt__, {'pkg_resource.add_pkg': _add_data}), \
             patch.dict(yumpkg.__salt__, {'pkg_resource.format_pkg_list': pkg_resource.format_pkg_list}), \
             patch.dict(yumpkg.__salt__, {'pkg_resource.stringify': MagicMock()}):
            pkgs = yumpkg.list_pkgs(versions_as_list=True)
            for pkg_name, pkg_version in {
                'python-urlgrabber': '3.10-8.el7',
                'alsa-lib': '1.1.1-1.el7',
                'gnupg2': '2.0.22-4.el7',
                'rpm-python': '4.11.3-21.el7',
                'pygpgme': '0.3-9.el7',
                'yum': '3.4.3-150.el7.centos',
                'lzo': '2.06-8.el7',
                'qrencode-libs': '3.4.1-3.el7',
                'ustr': '1.0.4-16.el7',
                'shadow-utils': '2:4.1.5.1-24.el7',
                'util-linux': '2.23.2-33.el7',
                'openssh': '6.6.1p1-33.el7_3',
                'virt-what': '1.13-8.el7'}.items():
                self.assertTrue(pkgs.get(pkg_name))
                self.assertEqual(pkgs[pkg_name], [pkg_version])

    def test_list_pkgs_with_attr(self):
        '''
        Test packages listing with the attr parameter

        :return:
        '''
        def _add_data(data, key, value):
            data.setdefault(key, []).append(value)

        rpm_out = [
            'python-urlgrabber_|-(none)_|-3.10_|-8.el7_|-noarch_|-(none)_|-1487838471',
            'alsa-lib_|-(none)_|-1.1.1_|-1.el7_|-x86_64_|-(none)_|-1487838475',
            'gnupg2_|-(none)_|-2.0.22_|-4.el7_|-x86_64_|-(none)_|-1487838477',
            'rpm-python_|-(none)_|-4.11.3_|-21.el7_|-x86_64_|-(none)_|-1487838477',
            'pygpgme_|-(none)_|-0.3_|-9.el7_|-x86_64_|-(none)_|-1487838478',
            'yum_|-(none)_|-3.4.3_|-150.el7.centos_|-noarch_|-(none)_|-1487838479',
            'lzo_|-(none)_|-2.06_|-8.el7_|-x86_64_|-(none)_|-1487838479',
            'qrencode-libs_|-(none)_|-3.4.1_|-3.el7_|-x86_64_|-(none)_|-1487838480',
            'ustr_|-(none)_|-1.0.4_|-16.el7_|-x86_64_|-(none)_|-1487838480',
            'shadow-utils_|-2_|-4.1.5.1_|-24.el7_|-x86_64_|-(none)_|-1487838481',
            'util-linux_|-(none)_|-2.23.2_|-33.el7_|-x86_64_|-(none)_|-1487838484',
            'openssh_|-(none)_|-6.6.1p1_|-33.el7_3_|-x86_64_|-(none)_|-1487838485',
            'virt-what_|-(none)_|-1.13_|-8.el7_|-x86_64_|-(none)_|-1487838486',
        ]
        with patch.dict(yumpkg.__grains__, {'osarch': 'x86_64'}), \
             patch.dict(yumpkg.__salt__, {'cmd.run': MagicMock(return_value=os.linesep.join(rpm_out))}), \
             patch.dict(yumpkg.__salt__, {'pkg_resource.add_pkg': _add_data}), \
             patch.dict(yumpkg.__salt__, {'pkg_resource.format_pkg_list': pkg_resource.format_pkg_list}), \
             patch.dict(yumpkg.__salt__, {'pkg_resource.stringify': MagicMock()}):
            pkgs = yumpkg.list_pkgs(attr=['arch', 'install_date_time_t'])
            for pkg_name, pkg_attr in {
                'python-urlgrabber': {
                    'version': '3.10-8.el7',
                    'arch': 'noarch',
                    'install_date_time_t': 1487838471,
                },
                'alsa-lib': {
                    'version': '1.1.1-1.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838475,
                },
                'gnupg2': {
                    'version': '2.0.22-4.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838477,
                },
                'rpm-python': {
                    'version': '4.11.3-21.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838477,
                },
                'pygpgme': {
                    'version': '0.3-9.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838478,
                },
                'yum': {
                    'version': '3.4.3-150.el7.centos',
                    'arch': 'noarch',
                    'install_date_time_t': 1487838479,
                },
                'lzo': {
                    'version': '2.06-8.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838479,
                },
                'qrencode-libs': {
                    'version': '3.4.1-3.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838480,
                },
                'ustr': {
                    'version': '1.0.4-16.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838480,
                },
                'shadow-utils': {
                    'version': '2:4.1.5.1-24.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838481,
                },
                'util-linux': {
                    'version': '2.23.2-33.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838484,
                },
                'openssh': {
                    'version': '6.6.1p1-33.el7_3',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838485,
                },
                'virt-what': {
                    'version': '1.13-8.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838486,
                }}.items():
                self.assertTrue(pkgs.get(pkg_name))
                self.assertEqual(pkgs[pkg_name], [pkg_attr])
