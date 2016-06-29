# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Ryan Lewis (ryansname@gmail.com)`

    tests.unit.modules.portage_flags
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.mock import NO_MOCK, NO_MOCK_REASON

# Import salt libs
from salt.modules import portage_config


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PortageConfigTestCase(TestCase):
    def test_get_config_file_wildcards(self):
        pairs = [
            ('*/*::repo', '/etc/portage/package.mask/repo'),
            ('*/pkg::repo', '/etc/portage/package.mask/pkg'),
            ('cat/*', '/etc/portage/package.mask/cat'),
            ('cat/pkg', '/etc/portage/package.mask/cat/pkg'),
            ('cat/pkg::repo', '/etc/portage/package.mask/cat/pkg'),
        ]

        for (atom, expected) in pairs:
            self.assertEqual(portage_config._get_config_file('mask', atom), expected)
