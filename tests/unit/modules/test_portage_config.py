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
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock
ensure_in_syspath('../../')

# Import salt libs
from salt.modules import portage_config


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PortageConfigTestCase(TestCase):
    class DummyAtom(object):
        def __init__(self, atom):
            self.cp, self.repo = atom.split("::") if "::" in atom else (atom, None)

    def test_get_config_file_wildcards(self):
        pairs = [
            ('*/*::repo', '/etc/portage/package.mask/repo'),
            ('*/pkg::repo', '/etc/portage/package.mask/pkg'),
            ('cat/*', '/etc/portage/package.mask/cat'),
            ('cat/pkg', '/etc/portage/package.mask/cat/pkg'),
            ('cat/pkg::repo', '/etc/portage/package.mask/cat/pkg'),
        ]

        portage_config.portage = MagicMock()
        for (atom, expected) in pairs:
            dummy_atom = self.DummyAtom(atom)
            portage_config.portage.dep.Atom = MagicMock(return_value=dummy_atom)
            portage_config._p_to_cp = MagicMock(return_value=dummy_atom.cp)
            self.assertEqual(portage_config._get_config_file('mask', atom), expected)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(PortageConfigTestCase, needs_daemon=False)
