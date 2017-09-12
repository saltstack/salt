# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Ryan Lewis (ryansname@gmail.com)`

    tests.unit.modules.portage_flags
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import salt libs
import salt.modules.portage_config as portage_config


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PortageConfigTestCase(TestCase, LoaderModuleMockMixin):

    class DummyAtom(object):
        def __init__(self, atom):
            self.cp, self.repo = atom.split("::") if "::" in atom else (atom, None)

    def setup_loader_modules(self):
        self.portage = MagicMock()
        self.addCleanup(delattr, self, 'portage')
        return {portage_config: {'portage': self.portage}}

    def test_get_config_file_wildcards(self):
        pairs = [
            ('*/*::repo', '/etc/portage/package.mask/repo'),
            ('*/pkg::repo', '/etc/portage/package.mask/pkg'),
            ('cat/*', '/etc/portage/package.mask/cat'),
            ('cat/pkg', '/etc/portage/package.mask/cat/pkg'),
            ('cat/pkg::repo', '/etc/portage/package.mask/cat/pkg'),
        ]

        for (atom, expected) in pairs:
            dummy_atom = self.DummyAtom(atom)
            self.portage.dep.Atom = MagicMock(return_value=dummy_atom)
            with patch.object(portage_config, '_p_to_cp', MagicMock(return_value=dummy_atom.cp)):
                self.assertEqual(portage_config._get_config_file('mask', atom), expected)
