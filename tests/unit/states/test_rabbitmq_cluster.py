# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.states import rabbitmq_cluster

# Globals
rabbitmq_cluster.__salt__ = {}
rabbitmq_cluster.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RabbitmqClusterTestCase(TestCase):
    '''
        Validate the rabbitmq_cluster state
    '''
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
