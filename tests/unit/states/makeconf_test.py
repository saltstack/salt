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
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import makeconf

makeconf.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MakeconfTestCase(TestCase):
    '''
    Test cases for salt.states.makeconf
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to verify that the variable is in the ``make.conf``
        and has the provided settings.
        '''
        name = 'makeopts'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock_t = MagicMock(return_value=True)
        with patch.dict(makeconf.__salt__, {'makeconf.get_var': mock_t}):
            comt = ('Variable {0} is already present in make.conf'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(makeconf.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to verify that the variable is not in the ``make.conf``.
        '''
        name = 'makeopts'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(return_value=None)
        with patch.dict(makeconf.__salt__, {'makeconf.get_var': mock}):
            comt = ('Variable {0} is already absent from make.conf'
                    .format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(makeconf.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MakeconfTestCase, needs_daemon=False)
