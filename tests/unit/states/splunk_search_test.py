# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import splunk_search

splunk_search.__salt__ = {}
splunk_search.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SplunkSearchTestCase(TestCase):
    '''
    Test cases for salt.states.splunk_search
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure a search is present.
        '''
        name = 'API Error Search'

        ret = {'name': name,
               'changes': {},
               'result': None,
               'comment': ''}

        mock = MagicMock(side_effect=[True, False, False, True])
        with patch.dict(splunk_search.__salt__, {'splunk_search.get': mock,
                                                 'splunk_search.create': mock}):
            with patch.dict(splunk_search.__opts__, {'test': True}):
                comt = ("Would update {0}".format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(splunk_search.present(name), ret)

                comt = ("Would create {0}".format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(splunk_search.present(name), ret)

            with patch.dict(splunk_search.__opts__, {'test': False}):
                ret.update({'comment': '', 'result': True,
                            'changes': {'new': {}, 'old': False}})
                self.assertDictEqual(splunk_search.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure a search is absent.
        '''
        name = 'API Error Search'

        ret = {'name': name,
               'result': None,
               'comment': ''}

        mock = MagicMock(side_effect=[True, False])
        with patch.dict(splunk_search.__salt__, {'splunk_search.get': mock}):
            with patch.dict(splunk_search.__opts__, {'test': True}):
                comt = ("Would delete {0}".format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(splunk_search.absent(name), ret)

            comt = ('{0} is absent.'.format(name))
            ret.update({'comment': comt, 'result': True,
                        'changes': {}})
            self.assertDictEqual(splunk_search.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SplunkSearchTestCase, needs_daemon=False)
