# -*- coding: utf-8 -*-
'''
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch,
)

# Import Salt Libs
import salt.utils.path
import salt.modules.at as at


class AtTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for the salt.modules.at module
    '''

    def setup_loader_modules(self):
        return {at: {}}

    atq_output = {'jobs': [{'date': '2014-12-11', 'job': 101, 'queue': 'A',
                            'tag': '', 'time': '19:48:47', 'user': 'B'}]}

    @classmethod
    def tearDownClass(cls):
        del cls.atq_output

    def test_atq_not_available(self):
        '''
        Tests the at.atq not available for any type of os_family.
        '''
        with patch('salt.modules.at._cmd', MagicMock(return_value=None)):
            with patch.dict(at.__grains__, {'os_family': 'RedHat'}):
                self.assertEqual(at.atq(), '\'at.atq\' is not available.')

            with patch.dict(at.__grains__, {'os_family': ''}):
                self.assertEqual(at.atq(), '\'at.atq\' is not available.')

    def test_atq_no_jobs_available(self):
        '''
        Tests the no jobs available for any type of os_family.
        '''
        with patch('salt.modules.at._cmd', MagicMock(return_value='')):
            with patch.dict(at.__grains__, {'os_family': 'RedHat'}):
                self.assertDictEqual(at.atq(), {'jobs': []})

            with patch.dict(at.__grains__, {'os_family': ''}):
                self.assertDictEqual(at.atq(), {'jobs': []})

    def test_atq_list(self):
        '''
        Tests the list all queued and running jobs.
        '''
        with patch('salt.modules.at._cmd') as salt_modules_at__cmd_mock:
            salt_modules_at__cmd_mock.return_value = '101\tThu Dec 11 \
            19:48:47 2014 A B'
            with patch.dict(at.__grains__, {'os_family': '', 'os': ''}):
                self.assertDictEqual(at.atq(), {'jobs': [{'date': '2014-12-11',
                                                          'job': 101,
                                                          'queue': 'A',
                                                          'tag': '',
                                                          'time': '19:48:00',
                                                          'user': 'B'}]})

            salt_modules_at__cmd_mock.return_value = '101\t2014-12-11 \
            19:48:47 A B'
            with patch.dict(at.__grains__, {'os_family': 'RedHat', 'os': ''}):
                self.assertDictEqual(at.atq(), {'jobs': [{'date': '2014-12-11',
                                                          'job': 101,
                                                          'queue': 'A',
                                                          'tag': '',
                                                          'time': '19:48:47',
                                                          'user': 'B'}]})

            salt_modules_at__cmd_mock.return_value = 'SALT: Dec 11, \
            2014 19:48 A 101 B'
            with patch.dict(at.__grains__, {'os_family': '', 'os': 'OpenBSD'}):
                self.assertDictEqual(at.atq(), {'jobs': [{'date': '2014-12-11',
                                                          'job': '101',
                                                          'queue': 'B',
                                                          'tag': '',
                                                          'time': '19:48:00',
                                                          'user': 'A'}]})

    def test_atrm(self):
        """
        Tests for remove jobs from the queue.
        """
        with patch('salt.modules.at.atq', MagicMock(return_value=self.atq_output)):
            with patch.object(salt.utils.path, 'which', return_value=None):
                self.assertEqual(at.atrm(), "'at.atrm' is not available.")

            with patch.object(salt.utils.path, 'which', return_value=True):
                self.assertDictEqual(at.atrm(), {'jobs': {'removed': [],
                                                          'tag': None}})

            with patch.object(at, '_cmd', return_value=True):
                with patch.object(salt.utils.path, 'which', return_value=True):
                    self.assertDictEqual(at.atrm('all'),
                                         {'jobs': {'removed': ['101'],
                                                   'tag': None}})

            with patch.object(at, '_cmd', return_value=True):
                with patch.object(salt.utils.path, 'which', return_value=True):
                    self.assertDictEqual(at.atrm(101),
                                         {'jobs': {'removed': ['101'],
                                                   'tag': None}})

            with patch.object(at, '_cmd', return_value=None):
                self.assertEqual(at.atrm(101), '\'at.atrm\' is not available.')

    def test_jobcheck(self):
        """
        Tests for check the job from queue.
        """
        with patch('salt.modules.at.atq', MagicMock(return_value=self.atq_output)):
            self.assertDictEqual(at.jobcheck(),
                                 {'error': 'You have given a condition'})

            self.assertDictEqual(at.jobcheck(runas='foo'),
                                 {'note': 'No match jobs or time format error',
                                  'jobs': []})

            self.assertDictEqual(at.jobcheck(runas='B', tag='', hour=19, minute=48,
                                             day=11, month=12, Year=2014),
                                 {'jobs': [{'date': '2014-12-11',
                                            'job': 101,
                                            'queue': 'A',
                                            'tag': '',
                                            'time': '19:48:47',
                                            'user': 'B'}]})

    def test_at(self):
        """
        Tests for add a job to the queue.
        """
        with patch('salt.modules.at.atq', MagicMock(return_value=self.atq_output)):
            self.assertDictEqual(at.at(), {'jobs': []})

            with patch.object(salt.utils.path, 'which', return_value=None):
                self.assertEqual(at.at('12:05am', '/sbin/reboot', tag='reboot'),
                                 "'at.at' is not available.")

            with patch.object(salt.utils.path, 'which', return_value=True):
                with patch.dict(at.__grains__, {'os_family': 'RedHat'}):
                    mock = MagicMock(return_value=None)
                    with patch.dict(at.__salt__, {'cmd.run': mock}):
                        self.assertEqual(at.at('12:05am', '/sbin/reboot',
                                               tag='reboot'),
                                         "'at.at' is not available.")

                    mock = MagicMock(return_value='Garbled time')
                    with patch.dict(at.__salt__, {'cmd.run': mock}):
                        self.assertDictEqual(at.at('12:05am', '/sbin/reboot',
                                                   tag='reboot'),
                                             {'jobs': [],
                                              'error': 'invalid timespec'})

                    mock = MagicMock(return_value='warning: commands\nA B')
                    with patch.dict(at.__salt__, {'cmd.run': mock}):
                        with patch.dict(at.__grains__, {'os': 'OpenBSD'}):
                            self.assertDictEqual(at.at('12:05am', '/sbin/reboot',
                                                       tag='reboot'),
                                                 {'jobs': [{'date': '2014-12-11',
                                                            'job': 101,
                                                            'queue': 'A',
                                                            'tag': '',
                                                            'time': '19:48:47',
                                                            'user': 'B'}]})

                with patch.dict(at.__grains__, {'os_family': ''}):
                    mock = MagicMock(return_value=None)
                    with patch.dict(at.__salt__, {'cmd.run': mock}):
                        self.assertEqual(at.at('12:05am', '/sbin/reboot',
                                               tag='reboot'),
                                         "'at.at' is not available.")

    def test_atc(self):
        """
            Tests for atc
        """
        with patch.object(at, '_cmd', return_value=None):
            self.assertEqual(at.atc(101), '\'at.atc\' is not available.')

        with patch.object(at, '_cmd', return_value=''):
            self.assertDictEqual(at.atc(101),
                                 {'error': 'invalid job id \'101\''})

        with patch.object(at, '_cmd',
                          return_value='101\tThu Dec 11 19:48:47 2014 A B'):
            self.assertEqual(at.atc(101), '101\tThu Dec 11 19:48:47 2014 A B')
