# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
from salt.ext.six import text_type as text

# Import Salt Libs
from salt.utils.sanitizers import clean

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import NO_MOCK, NO_MOCK_REASON
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SanitizersTestCase(TestCase):
    '''
    TestCase for sanitizers
    '''
    def test_sanitized_trim(self):
        '''
        Test sanitized input for trimming
        '''
        value = u' sample '
        response = clean.trim(value)
        assert response == 'sample'
        assert type(response) == text

    def test_sanitized_filename(self):
        '''
        Test sanitized input for filename
        '''
        value = '/absolute/path/to/the/file.txt'
        response = clean.filename(value)
        assert response == 'file.txt'

        value = '../relative/path/to/the/file.txt'
        response = clean.filename(value)
        assert response == 'file.txt'

    def test_sanitized_hostname(self):
        '''
        Test sanitized input for hostname (id)
        '''
        value = '   ../ ../some/dubious/hostname      '
        response = clean.hostname(value)
        assert response == 'somedubioushostname'

    test_sanitized_id = test_sanitized_hostname


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SanitizersTestCase, needs_daemon=False)
