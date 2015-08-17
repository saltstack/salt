# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

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
                            'cluster rahulha@salt'})
                self.assertDictEqual(rabbitmq_cluster.joined('salt', 'salt',
                                                             'rahulha'), ret)

            with patch.dict(rabbitmq_cluster.__opts__, {"test": False}):
                mock = MagicMock(return_value={'Error': 'ERR'})
                with patch.dict(rabbitmq_cluster.__salt__,
                                {"rabbitmq.join_cluster": mock}):
                    ret.update({'result': False,
                                'comment': 'ERR'})
                    self.assertDictEqual(rabbitmq_cluster.joined('salt',
                                                                 'salt',
                                                                 'rahulha'),
                                         ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RabbitmqClusterTestCase, needs_daemon=False)
