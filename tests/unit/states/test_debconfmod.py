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
import salt.states.debconfmod as debconfmod

debconfmod.__salt__ = {}
debconfmod.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DebconfmodTestCase(TestCase):
    '''
    Test cases for salt.states.debconfmod
    '''
    # 'set_file' function tests: 1

    def test_set_file(self):
        '''
        Test to set debconf selections from a file or a template
        '''
        name = 'nullmailer'
        source = 'salt://pathto/pkg.selections'

        ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}

        comt = ('Context must be formed as a dict')
        ret.update({'comment': comt})
        self.assertDictEqual(debconfmod.set_file(name, source, context='salt'),
                             ret)

        comt = ('Defaults must be formed as a dict')
        ret.update({'comment': comt})
        self.assertDictEqual(debconfmod.set_file(name, source, defaults='salt'),
                             ret)

        with patch.dict(debconfmod.__opts__, {'test': True}):
            comt = ('Debconf selections would have been set.')
            ret.update({'comment': comt, 'result': None})
            self.assertDictEqual(debconfmod.set_file(name, source), ret)

            with patch.dict(debconfmod.__opts__, {'test': False}):
                mock = MagicMock(return_value=True)
                with patch.dict(debconfmod.__salt__,
                                {'debconf.set_file': mock}):
                    comt = ('Debconf selections were set.')
                    ret.update({'comment': comt, 'result': True})
                    self.assertDictEqual(debconfmod.set_file(name, source),
                                         ret)

    # 'set' function tests: 1

    def test_set(self):
        '''
        Test to set debconf selections
        '''
        name = 'nullmailer'
        data = {'shared/mailname': {'type': 'string',
                                    'value': 'server.domain.tld'},
                'nullmailer/relayhost': {'type': 'string',
                                         'value': 'mail.domain.tld'}}

        ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

        changes = {'nullmailer/relayhost': 'New value: mail.domain.tld',
                   'shared/mailname': 'New value: server.domain.tld'}

        mock = MagicMock(return_value=None)
        with patch.dict(debconfmod.__salt__, {'debconf.show': mock}):
            with patch.dict(debconfmod.__opts__, {'test': True}):
                ret.update({'changes': changes})
                self.assertDictEqual(debconfmod.set(name, data), ret)
