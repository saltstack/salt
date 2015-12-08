# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import match
import salt.ext.six.moves.builtins as __builtin__  # pylint: disable=import-error,no-name-in-module

# Globals
match.__grains__ = {}
match.__salt__ = {}
match.__opts__ = {}
match.__pillar__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MatchTestCase(TestCase):
    '''
    Test cases for salt.modules.match
    '''
    @patch('salt.minion.Matcher')
    def test_compound(self, mock_matcher):
        '''
        Test for Return True if the minion ID matches the given compound target
        '''
        with patch.dict(match.__grains__, {'id': 101}):

            mock_matcher.side_effect = MagicMock()
            with patch.object(mock_matcher, 'compound_match', MagicMock()):
                self.assertTrue(match.compound('tgt'))

            mock_matcher.side_effect = MagicMock(return_value='B')
            self.assertFalse(match.compound('tgt'))

    @patch('salt.minion.Matcher')
    def test_ipcidr(self, mock_matcher):
        '''
        Test for Return True if the minion matches the given ipcidr target
        '''
        with patch.dict(match.__grains__, {'id': 101}):

            mock_matcher.side_effect = MagicMock()
            with patch.object(mock_matcher, 'ipcidr_match', MagicMock()):
                self.assertTrue(match.ipcidr('tgt'))

            mock_matcher.side_effect = MagicMock(return_value='B')
            self.assertFalse(match.ipcidr('tgt'))

    @patch('salt.minion.Matcher')
    def test_pillar(self, mock_matcher):
        '''
        Test for Return True if the minion matches the given pillar target.
        '''
        with patch.dict(match.__grains__, {'id': 101}):

            mock_matcher.side_effect = MagicMock()
            with patch.object(mock_matcher, 'pillar_match', MagicMock()):
                self.assertTrue(match.pillar('tgt'))

            mock_matcher.side_effect = MagicMock(return_value='B')
            self.assertFalse(match.pillar('tgt'))

    @patch('salt.minion.Matcher')
    def test_data(self, mock_matcher):
        '''
        Test for Return True if the minion matches the given data target
        '''
        with patch.dict(match.__grains__, {'id': 101}):

            mock_matcher.side_effect = MagicMock()
            with patch.object(mock_matcher, 'data_match', MagicMock()):
                self.assertTrue(match.data('tgt'))

            mock_matcher.side_effect = MagicMock(return_value='B')
            self.assertFalse(match.data('tgt'))

    @patch('salt.minion.Matcher')
    def test_grain_pcre(self, mock_matcher):
        '''
        Test for Return True if the minion matches the given grain_pcre target
        '''
        with patch.dict(match.__grains__, {'id': 101}):

            mock_matcher.side_effect = MagicMock()
            with patch.object(mock_matcher, 'grain_pcre_match', MagicMock()):
                self.assertTrue(match.grain_pcre('tgt'))

            mock_matcher.side_effect = MagicMock(return_value='B')
            self.assertFalse(match.grain_pcre('tgt'))

    @patch('salt.minion.Matcher')
    def test_grain(self, mock_matcher):
        '''
        Test for Return True if the minion matches the given grain target
        '''
        with patch.dict(match.__grains__, {'id': 101}):

            mock_matcher.side_effect = MagicMock()
            with patch.object(mock_matcher, 'grain_match', MagicMock()):
                self.assertTrue(match.grain('tgt'))

            mock_matcher.side_effect = MagicMock(return_value='B')
            self.assertFalse(match.grain('tgt'))

    @patch('salt.minion.Matcher')
    def test_list_(self, mock_matcher):
        '''
        Test for Return True if the minion ID matches the given list target
        '''
        with patch.dict(match.__grains__, {'id': 101}):

            mock_matcher.side_effect = MagicMock()
            with patch.object(mock_matcher, 'list_match', MagicMock()):
                self.assertTrue(match.list_('tgt'))

            mock_matcher.side_effect = MagicMock(return_value='B')
            self.assertFalse(match.list_('tgt'))

    @patch('salt.minion.Matcher')
    def test_pcre(self, mock_matcher):
        '''
        Test for Return True if the minion ID matches the given pcre target
        '''
        mock_matcher.side_effect = MagicMock()
        with patch.dict(match.__grains__, {'id': 101}):
            with patch.object(mock_matcher, 'pcre_match', MagicMock()):
                self.assertTrue(match.pcre('tgt'))

        mock_matcher.side_effect = MagicMock(return_value='B')
        with patch.dict(match.__grains__, {'id': 101}):
            self.assertFalse(match.pcre('tgt'))

    @patch('salt.minion.Matcher')
    def test_glob(self, mock_matcher):
        '''
        Test for Return True if the minion ID matches the given glob target
        '''
        with patch.dict(match.__grains__, {'id': 101}):

            mock_matcher.side_effect = MagicMock()
            with patch.object(mock_matcher, 'glob_match', MagicMock()):
                self.assertTrue(match.glob('tgt'))

            mock_matcher.side_effect = MagicMock(return_value='B')
            self.assertFalse(match.glob('tgt'))

    def test_filter_by(self):
        '''
        Test for Return the first match in a dictionary of target patterns
        '''
        with patch.object(__builtin__, 'dict', MagicMock()):

            self.assertEqual(match.filter_by({'key': 'value'},
                                             minion_id=101), 'value')

            self.assertEqual(match.filter_by({'key': 'value'}), 'value')

            self.assertEqual(match.filter_by({}), None)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MatchTestCase, needs_daemon=False)
