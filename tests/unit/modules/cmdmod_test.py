# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Salt Libs
from salt.modules import cmdmod
from salt.log import LOG_LEVELS

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')


@skipIf(NO_MOCK, NO_MOCK_REASON)
class CMDMODTestCase(TestCase):
    '''
    Unit tests for the salt.modules.cmdmod module
    '''

    mock_loglevels = {'info': 'foo', 'all': 'bar', 'critical': 'bar',
                      'trace': 'bar', 'garbage': 'bar', 'error': 'bar',
                      'debug': 'bar', 'warning': 'bar', 'quiet': 'bar'}

    def test_render_cmd(self):
        '''
        Tests return when template=None
        '''
        self.assertEqual(cmdmod._render_cmd('foo', 'bar', None),
                         ('foo', 'bar'))

    def test_check_loglevel_bad_level(self):
        '''
        Tests return of providing an invalid loglevel option
        '''
        with patch.dict(LOG_LEVELS, self.mock_loglevels):
            self.assertEqual(cmdmod._check_loglevel(level='bad_loglevel'), 'foo')

    def test_check_loglevel_bad_level_not_str(self):
        '''
        Tests the return of providing an invalid loglevel option that is not a string
        '''
        with patch.dict(LOG_LEVELS, self.mock_loglevels):
            self.assertEqual(cmdmod._check_loglevel(level=1000), 'foo')

    def test_check_loglevel_quiet(self):
        '''
        Tests the return of providing a loglevel of 'quiet'
        '''
        with patch.dict(LOG_LEVELS, self.mock_loglevels):
            self.assertEqual(cmdmod._check_loglevel(level='quiet'), None)

    def test_check_loglevel_utils_quite(self):
        '''
        Tests the return of quiet=True
        '''
        with patch.dict(LOG_LEVELS, self.mock_loglevels):
            self.assertEqual(cmdmod._check_loglevel(quiet=True), None)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CMDMODTestCase, needs_daemon=False)
