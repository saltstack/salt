# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import json

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
import salt.states.grafana as grafana
from salt.exceptions import SaltInvocationError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GrafanaTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.grafana
    '''
    def setup_loader_modules(self):
        return {grafana: {}}

    # 'dashboard_present' function tests: 1

    def test_dashboard_present(self):
        '''
        Test to ensure the grafana dashboard exists and is managed.
        '''
        name = 'myservice'
        rows = ['systemhealth', 'requests', 'title']
        row = [{'panels': [{'id': 'a'}], 'title': 'systemhealth'}]

        ret = {'name': name,
               'result': None,
               'changes': {},
               'comment': ''}

        comt1 = ("Dashboard myservice is set to be updated. The following rows "
                 "set to be updated: ['systemhealth']")
        self.assertRaises(SaltInvocationError, grafana.dashboard_present, name,
                          profile=False)

        self.assertRaises(SaltInvocationError, grafana.dashboard_present, name,
                          True, True)

        mock = MagicMock(side_effect=[{'hosts': True, 'index': False},
                                      {'hosts': True, 'index': True},
                                      {'hosts': True, 'index': True},
                                      {'hosts': True, 'index': True},
                                      {'hosts': True, 'index': True},
                                      {'hosts': True, 'index': True},
                                      {'hosts': True, 'index': True}])
        mock_f = MagicMock(side_effect=[False, False, True, True, True, True])
        mock_t = MagicMock(return_value='')
        mock_i = MagicMock(return_value=False)
        source = {'dashboard': '["rows", {"rows":["baz", null, 1.0, 2]}]'}
        mock_dict = MagicMock(return_value={'_source': source})
        with patch.dict(grafana.__salt__, {'config.option': mock,
                                           'elasticsearch.exists': mock_f,
                                           'pillar.get': mock_t,
                                           'elasticsearch.get': mock_dict,
                                           'elasticsearch.index': mock_i}):
            self.assertRaises(SaltInvocationError, grafana.dashboard_present,
                              name)

            with patch.dict(grafana.__opts__, {'test': True}):
                self.assertRaises(SaltInvocationError, grafana.dashboard_present,
                                  name)

                comt = ('Dashboard {0} is set to be created.'.format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(grafana.dashboard_present(name, True), ret)

                mock = MagicMock(return_value={'rows':
                                               [{'panels': 'b',
                                                 'title': 'systemhealth'}]})
                with patch.object(json, 'loads', mock):
                    ret.update({'comment': comt1, 'result': None})
                    self.assertDictEqual(grafana.dashboard_present(name, True,
                                                                   rows=row),
                                         ret)

            with patch.object(json, 'loads',
                              MagicMock(return_value={'rows': {}})):
                self.assertRaises(SaltInvocationError,
                                  grafana.dashboard_present, name,
                                  rows_from_pillar=rows)

                comt = ('Dashboard myservice is up to date')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(grafana.dashboard_present(name, True), ret)

            mock = MagicMock(return_value={'rows': [{'panels': 'b',
                                                     'title': 'systemhealth'}]})
            with patch.dict(grafana.__opts__, {'test': False}):
                with patch.object(json, 'loads', mock):
                    comt = ('Failed to update dashboard myservice.')
                    ret.update({'comment': comt, 'result': False})
                    self.assertDictEqual(grafana.dashboard_present(name, True,
                                                                   rows=row),
                                         ret)

    # 'dashboard_absent' function tests: 1

    def test_dashboard_absent(self):
        '''
        Test to ensure the named grafana dashboard is deleted.
        '''
        name = 'myservice'

        ret = {'name': name,
               'result': None,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[{'hosts': True, 'index': False},
                                      {'hosts': True, 'index': True},
                                      {'hosts': True, 'index': True}])
        mock_f = MagicMock(side_effect=[True, False])
        with patch.dict(grafana.__salt__, {'config.option': mock,
                                           'elasticsearch.exists': mock_f}):
            self.assertRaises(SaltInvocationError, grafana.dashboard_absent,
                              name)

            with patch.dict(grafana.__opts__, {'test': True}):
                comt = ('Dashboard myservice is set to be removed.')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(grafana.dashboard_absent(name), ret)

            comt = ('Dashboard myservice does not exist.')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(grafana.dashboard_absent(name), ret)
