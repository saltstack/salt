# -*- coding: utf-8 -*-
'''
    :codauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch, call

ensure_in_syspath('../../')

from salt.modules import cron

STUB_USER = 'root'
STUB_PATH = '/tmp'

STUB_CRON_TIMESTAMP = {'minute': '1',
                  'hour': '2',
                  'daymonth': '3',
                  'month': '4',
                  'dayweek': '5'}

STUB_SIMPLE_RAW_CRON = '5 0 * * * /tmp/no_script.sh'
STUB_SIMPLE_CRON_DICT = {'pre': ['5 0 * * * /tmp/no_script.sh'], 'crons': [], 'env': [], 'special': []}

__grains__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PsTestCase(TestCase):
    def test__needs_change(self):
        self.assertTrue(cron._needs_change(True, False))

    def test__needs_change_random(self):
        '''
        Assert that if the new var is 'random' and old is '* that we return True
        '''
        self.assertTrue(cron._needs_change('*', 'random'))

    ## Still trying to figure this one out.
    # def test__render_tab(self):
    #     pass

    def test__get_cron_cmdstr_solaris(self):
        cron.__grains__ = __grains__
        with patch.dict(cron.__grains__, {'os_family': 'Solaris'}):
            self.assertEqual('su - root -c "crontab /tmp"',
                             cron._get_cron_cmdstr(STUB_USER, STUB_PATH))

    def test__get_cron_cmdstr(self):
        cron.__grains__ = __grains__
        with patch.dict(cron.__grains__, {'os_family': None}):
            self.assertEqual('crontab -u root /tmp',
                             cron._get_cron_cmdstr(STUB_USER, STUB_PATH))

    def test__date_time_match(self):
        '''
        Passes if a match is found on all elements. Note the conversions to strings here!
        :return:
        '''
        self.assertTrue(cron._date_time_match(STUB_CRON_TIMESTAMP,
                                    minute=STUB_CRON_TIMESTAMP['minute'],
                                    hour=STUB_CRON_TIMESTAMP['hour'],
                                    daymonth=STUB_CRON_TIMESTAMP['daymonth'],
                                    dayweek=STUB_CRON_TIMESTAMP['dayweek']
                                    ))

    @patch('salt.modules.cron.raw_cron', new=MagicMock(return_value=STUB_SIMPLE_RAW_CRON))
    def test_list_tab(self):
        self.assertDictEqual(STUB_SIMPLE_CRON_DICT, cron.list_tab('DUMMY_USER'))

    @patch('salt.modules.cron._write_cron_lines')
    @patch('salt.modules.cron.list_tab', new=MagicMock(return_value=STUB_SIMPLE_CRON_DICT))
    def test_set_special(self, write_cron_lines_mock):
        expected_write_call = call('DUMMY_USER',
                                   ['5 0 * * * /tmp/no_script.sh\n',
                                    '# Lines below here are managed by Salt, do not edit\n',
                                    '@hourly echo Hi!\n'])
        ret = cron.set_special('DUMMY_USER', '@hourly', 'echo Hi!')
        write_cron_lines_mock.assert_has_calls(expected_write_call)

    def test__get_cron_date_time(self):
        ret = cron._get_cron_date_time(minute=STUB_CRON_TIMESTAMP['minute'],
                                    hour=STUB_CRON_TIMESTAMP['hour'],
                                    daymonth=STUB_CRON_TIMESTAMP['daymonth'],
                                    dayweek=STUB_CRON_TIMESTAMP['dayweek'],
                                    month=STUB_CRON_TIMESTAMP['month'])
        self.assertDictEqual(ret, STUB_CRON_TIMESTAMP)

    ## FIXME: More sophisticated _get_cron_date_time checks should be added here.

    @patch('salt.modules.cron._write_cron_lines', new=MagicMock(return_value={'retcode': False}))
    @patch('salt.modules.cron.raw_cron', new=MagicMock(return_value=STUB_SIMPLE_RAW_CRON))
    def test_set_job(self):
        cron.__grains__ = __grains__
        with patch.dict(cron.__grains__, {'os': None}):
            cron.set_job('DUMMY_USER', 1, 2, 3, 4, 5,
                         '/bin/echo NOT A DROID',
                         'WERE YOU LOOKING FOR ME?')
            expected_call = call('DUMMY_USER',
                                 ['5 0 * * * /tmp/no_script.sh\n',
                                  '# Lines below here are managed by Salt, do not edit\n',
                                  '# WERE YOU LOOKING FOR ME?\n',
                                  '1 2 3 4 5 /bin/echo NOT A DROID\n'])
            cron._write_cron_lines.call_args.assert_called_with(expected_call)

    @patch('salt.modules.cron._write_cron_lines', new=MagicMock(return_value={'retcode': False}))
    @patch('salt.modules.cron.raw_cron', new=MagicMock(return_value=STUB_SIMPLE_RAW_CRON))
    def test_rm_job_is_absent(self):
        with patch.dict(cron.__grains__, {'os': None}):
            ret = cron.rm_job('DUMMY_USER', '/bin/echo NOT A DROID', 1, 2, 3, 4, 5)
            self.assertEqual('absent', ret)
