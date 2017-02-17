# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import pyrax_queues

pyrax_queues.__opts__ = {}
pyrax_queues.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PyraxQueuesTestCase(TestCase):
    '''
    Test cases for salt.states.pyrax_queues
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure the RackSpace queue exists.
        '''
        name = 'myqueue'
        provider = 'my-pyrax'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': ''}

        mock_dct = MagicMock(side_effect=[{provider: {'salt': True}},
                                          {provider: {'salt': False}},
                                          {provider: {'salt': False}}, False])
        with patch.dict(pyrax_queues.__salt__, {'cloud.action': mock_dct}):
            comt = ('{0} present.'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(pyrax_queues.present(name, provider), ret)

            with patch.dict(pyrax_queues.__opts__, {'test': True}):
                comt = ('Rackspace queue myqueue is set to be created.')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(pyrax_queues.present(name, provider), ret)

            with patch.dict(pyrax_queues.__opts__, {'test': False}):
                comt = ('Failed to create myqueue Rackspace queue.')
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(pyrax_queues.present(name, provider), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure the named Rackspace queue is deleted.
        '''
        name = 'myqueue'
        provider = 'my-pyrax'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': ''}

        mock_dct = MagicMock(side_effect=[{provider: {'salt': False}},
                                          {provider: {'salt': True}}])
        with patch.dict(pyrax_queues.__salt__, {'cloud.action': mock_dct}):
            comt = ('myqueue does not exist.')
            ret.update({'comment': comt})
            self.assertDictEqual(pyrax_queues.absent(name, provider), ret)

            with patch.dict(pyrax_queues.__opts__, {'test': True}):
                comt = ('Rackspace queue myqueue is set to be removed.')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(pyrax_queues.absent(name, provider), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PyraxQueuesTestCase, needs_daemon=False)
