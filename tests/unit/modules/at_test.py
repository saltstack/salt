# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import at

# Globals
at.__grains__ = {}


class AtTestCase(TestCase):
    '''
    TestCase for the salt.modules.at module
    '''

    @patch('salt.modules.at._cmd', MagicMock(return_value=None))
    def test_atq_not_available(self):
        '''
        Tests the at.atq not available for any type of os_family.
        '''
        with patch.dict(at.__grains__, {'os_family': 'RedHat'}):
            self.assertEqual(at.atq(), '\'at.atq\' is not available.')

        with patch.dict(at.__grains__, {'os_family': ''}):
            self.assertEqual(at.atq(), '\'at.atq\' is not available.')

    @patch('salt.modules.at._cmd', MagicMock(return_value=''))
    def test_atq_no_jobs_available(self):
        '''
        Tests the no jobs available for any type of os_family.
        '''
        with patch.dict(at.__grains__, {'os_family': 'RedHat'}):
            self.assertDictEqual(at.atq(), {'jobs': []})

        with patch.dict(at.__grains__, {'os_family': ''}):
            self.assertDictEqual(at.atq(), {'jobs': []})

    @patch('salt.modules.at._cmd')
    def test_atq_list(self,salt_modules_at__cmd_mock):
        '''
        Tests the list all queued and running jobs.
        '''
        salt_modules_at__cmd_mock.return_value='101\tThu Dec 11 19:48:47 2014 A B'
        with patch.dict(at.__grains__, {'os_family': '', 'os': ''}):
            self.assertDictEqual(at.atq(), {'jobs': [{'date': '2014-12-11',
                                                      'job': 101,
                                                      'queue': 'A',
                                                      'tag': '',
                                                      'time': '19:48:00',
                                                      'user': 'B'}]
                                            })

        salt_modules_at__cmd_mock.return_value='101\t2014-12-11 19:48:47 A B'
        with patch.dict(at.__grains__, {'os_family': 'RedHat', 'os': ''}):
            self.assertDictEqual(at.atq(), {'jobs': [{'date': '2014-12-11',
                                                      'job': 101,
                                                      'queue': 'A',
                                                      'tag': '',
                                                      'time': '19:48:47',
                                                      'user': 'B'}]
                                            })

        salt_modules_at__cmd_mock.return_value='SALT: Dec 11, 2014 19:48 A 101 B'
        with patch.dict(at.__grains__, {'os_family': '', 'os': 'OpenBSD'}):
            self.assertDictEqual(at.atq(), {'jobs': [{'date': '2014-12-11',
                                                      'job': '101',
                                                      'queue': 'B',
                                                      'tag': '',
                                                      'time': '19:48:00',
                                                      'user': 'A'}]
                                            })


if __name__ == '__main__':
    from integration import run_tests
    run_tests(AtTestCase, needs_daemon=False)
