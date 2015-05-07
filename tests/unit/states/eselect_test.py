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
from salt.states import eselect

eselect.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class EselectTestCase(TestCase):
    '''
    Test cases for salt.states.eselect
    '''
    # 'set_' function tests: 1

    def test_set_(self):
        '''
        Test to verify that the given module is set to the given target
        '''
        name = 'myeselect'
        target = 'hardened/linux/amd64'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(return_value=target)
        with patch.dict(eselect.__salt__, {'eselect.get_current_target': mock}):
            comt = ('Target {0!r} is already set on {1!r} module.'
                    .format(target, name))
            ret.update({'comment': comt})
            self.assertDictEqual(eselect.set_(name, target), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(EselectTestCase, needs_daemon=False)
