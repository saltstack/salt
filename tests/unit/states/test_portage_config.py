# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
from salt.states import portage_config

portage_config.__salt__ = {}
portage_config.__opts__ = {'test': True}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PortageConfigTestCase(TestCase):
    '''
    Test cases for salt.states.portage_config
    '''
    # 'mod_init' function tests: 1

    def test_mod_init(self):
        '''
        Test to enforce a nice structure on the configuration files.
        '''
        name = 'salt'

        mock = MagicMock(side_effect=[True, Exception])
        with patch.dict(portage_config.__salt__,
                        {'portage_config.enforce_nice_config': mock}):
            self.assertTrue(portage_config.mod_init(name))

            self.assertFalse(portage_config.mod_init(name))

    # 'flags' function tests: 1

    @patch('traceback.format_exc', MagicMock(return_value='SALTSTACK'))
    def test_flags(self):
        '''
        Test to enforce the given flags on the given package or ``DEPEND`` atom.
        '''
        name = 'salt'

        ret = {'name': name,
               'result': False,
               'comment': 'SALTSTACK',
               'changes': {}}

        mock = MagicMock(side_effect=Exception('error'))
        with patch.dict(portage_config.__salt__,
                        {'portage_config.get_missing_flags': mock}):
            self.assertDictEqual(portage_config.flags(name, use='openssl'), ret)

            self.assertDictEqual(portage_config.flags(name,
                                                      accept_keywords=True),
                                 ret)

            self.assertDictEqual(portage_config.flags(name, env=True), ret)

            self.assertDictEqual(portage_config.flags(name, license=True), ret)

            self.assertDictEqual(portage_config.flags(name, properties=True),
                                 ret)

            self.assertDictEqual(portage_config.flags(name, mask=True), ret)

            self.assertDictEqual(portage_config.flags(name, unmask=True), ret)

            ret.update({'comment': '', 'result': True})
            self.assertDictEqual(portage_config.flags(name), ret)
