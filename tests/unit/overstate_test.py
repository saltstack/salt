# -*- coding: utf-8 -*-
'''
    :codauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch, mock_open, call
ensure_in_syspath('../')

# Import salt libs
import salt.overstate

opts = {'file_roots': {},
        'conf_file': ''}

overstate_sls = {
    'mysql': {
        'match': 'db*',
        'sls': {
            'mysql.server', 'drbd'
        }
    },
    'webservers': {
        'match': 'web*',
        'require': ['mysql']
    },
    'all': {
        'match': '*',
        'require': {
            'mysql', 'webservers'
        }
    }

}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class OverstateTestCase(TestCase):
    @patch('salt.client.LocalClient.cmd')
    def test__stage_list(self, local_client_mock):
        overstate = salt.overstate.OverState(opts)
        overstate._stage_list(['test1', 'test2'])
        local_client_mock.assert_called_with('test1 or test2', 'test.ping', expr_form='compound')

    # @skipIf(True, "Do not run this test! It exposes a memory leak inside pyyaml: https://bitbucket.org/xi/pyyaml/issue/24")
    # def test__names(self):
    #     y = 'a'
    #     mopen = mock_open(read_data=y)
    #     with patch('salt.utils.fopen', mopen, create=True):
    #         overstate = salt.overstate.OverState(opts, overstate='a')

    def test__names(self):
        overstate = salt.overstate.OverState(opts)
        overstate.over = overstate._OverState__sort_stages(overstate_sls)
        self.assertEqual({'webservers', 'all', 'mysql'}, overstate._names())

    def test_get_stage(self):
        overstate = salt.overstate.OverState(opts)
        overstate.over = overstate._OverState__sort_stages(overstate_sls)
        ret = overstate.get_stage('mysql')
        self.assertDictEqual({'mysql': {'match': 'db*', 'sls': {'drbd', 'mysql.server'}}}, ret)

    @patch('salt.overstate.OverState.call_stage')
    def test_stages(self, call_stage_mock):
        '''
        This is a very basic test and needs expansion, since call_stage is mocked!
        '''
        overstate = salt.overstate.OverState(opts)
        overstate.over = overstate._OverState__sort_stages(overstate_sls)
        overstate.stages()
        expected_calls = [call('all', {'require': {'webservers', 'mysql'}, 'match': '*'}),
                          call('mysql', {'match': 'db*', 'sls': {'drbd', 'mysql.server'}}),
                          call('webservers', {'require': ['mysql'], 'match': 'web*'})]
        call_stage_mock.assert_has_calls(expected_calls, any_order=False)

    def test_verify_stage(self):
        overstate = salt.overstate.OverState(opts)
        test_stage = {'require': {'webservers', 'mysql'}, 'match': '*'}
        ret = overstate.verify_stage(test_stage)
        self.assertDictEqual(test_stage, test_stage)

    def test_verify_fail(self):
        overstate = salt.overstate.OverState(opts)
        test_stage = {'require': {'webservers', 'mysql'}}
        ret = overstate.verify_stage(test_stage)
        self.assertIn('No "match" argument in stage.', ret)

    @patch('salt.utils.check_state_result')
    def test__check_results_for_failed_prereq(self, check_state_result_mock):
        check_state_result_mock.return_value = True
        overstate = salt.overstate.OverState(opts)
        overstate.over_run = {'mysql':
                                  {'minion1':
                                       {
                                           'ret': {
                                               'result': True,
                                               'comment': 'Victory is ours!',
                                               'name': 'mysql',
                                               'changes': {},
                                               '__run_num__': 0,

                                           },
                                           'fun': MagicMock(name='Mock of minion1 mysql func'),
                                           'retcode': 0,
                                           'success': False

                                       }
                                  }
        }
        ret = overstate._check_results('mysql', 'all', {}, {'all': {}})
        self.assertDictEqual({'all': {'req_|-fail_|-fail_|-None': {'fun': 'req.fail',
                                       'ret': {'__run_num__': 0,
                                               'changes': {},
                                               'comment': 'Requisite mysql failed for stage on minion minion1',
                                               'name': 'Requisite Failure',
                                               'result': False},
                                       'retcode': 254,
                                       'success': False}}},
 {'all': {'req_|-fail_|-fail_|-None': {'fun': 'req.fail',
                                       'ret': {'__run_num__': 0,
                                               'changes': {},
                                               'comment': 'Requisite mysql failed for stage on minion minion1',
                                               'name': 'Requisite Failure',
                                               'result': False},
                                       'retcode': 254,
                                       'success': False}}},
                                        ret)

        



    # @patch('salt.overstate.OverState.call_stage')
    # def test_call_stage(self, call_stage_mock):
    #     overstate = salt.overstate.OverState(opts)
    #     overstate.over = overstate._OverState__sort_stages(overstate_sls)
    #     overstate.call_stage('all', {'require': {'webservers', 'mysql'}, 'match': '*'})
    #     overstate.call_stage('mysql', {'match': 'db*', 'sls': {'drbd', 'mysql.server'}})
    #     overstate.call_stage({'require': ['mysql'], 'match': 'web*'})
