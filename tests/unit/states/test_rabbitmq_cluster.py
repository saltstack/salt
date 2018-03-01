# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.states.rabbitmq_cluster as rabbitmq_cluster


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RabbitmqClusterTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Validate the rabbitmq_cluster state
    '''
    def setup_loader_modules(self):
        return {rabbitmq_cluster: {}}

    def test_joined(self):
        '''
        Test to ensure the current node joined
        to a cluster with node user@host
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}

        mock = MagicMock(side_effect=[['rahulha@salt'], [''], ['']])
        with patch.dict(rabbitmq_cluster.__salt__,
                        {"rabbitmq.cluster_status": mock}):
            ret.update({'comment': 'Already in cluster'})
            self.assertDictEqual(rabbitmq_cluster.joined('salt', 'salt',
                                                         'rahulha'), ret)

            with patch.dict(rabbitmq_cluster.__opts__, {"test": True}):
                ret.update({'result': None,
                            'comment': 'Node is set to join '
                            'cluster rahulha@salt',
                            'changes': {'new': 'rahulha@salt', 'old': ''}})
                self.assertDictEqual(rabbitmq_cluster.joined('salt', 'salt',
                                                             'rahulha'), ret)

            with patch.dict(rabbitmq_cluster.__opts__, {"test": False}):
                mock = MagicMock(return_value={'Error': 'ERR'})
                with patch.dict(rabbitmq_cluster.__salt__,
                                {"rabbitmq.join_cluster": mock}):
                    ret.update({'result': False,
                                'comment': 'ERR',
                                'changes': {}})
                    self.assertDictEqual(rabbitmq_cluster.joined('salt',
                                                                 'salt',
                                                                 'rahulha'),
                                         ret)
