# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import publish
import salt.crypt
import salt.transport
from salt.exceptions import SaltReqTimeoutError

# Globals
publish.__opts__ = {}


class SAuth(object):
    '''
    Mock SAuth class
    '''
    def __init__(self, __opts__):
        self.tok = None

    def gen_token(self, tok):
        '''
        Mock gen_token method
        '''
        self.tok = tok
        return 'salt_tok'


class Channel(object):
    '''
    Mock Channel class
    '''
    flag = None

    def __init__(self):
        self.tok = None
        self.load = None

    def factory(self, tok):
        '''
        Mock factory method
        '''
        self.tok = tok
        return Channel()

    def send(self, load):
        '''
        Mock send method
        '''
        self.load = load
        if self.flag == 1:
            raise SaltReqTimeoutError
        return True

salt.transport.Channel = Channel()


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.crypt.SAuth', return_value=SAuth(publish.__opts__))
class PublishTestCase(TestCase):
    '''
    Test cases for salt.modules.publish
    '''
    # 'publish' function tests: 1

    def test_publish(self, mock):
        '''
        Test if it publish a command from the minion out to other minions.
        '''
        self.assertDictEqual(publish.publish('os:Fedora', 'publish.salt'), {})

    # 'full_data' function tests: 1

    def test_full_data(self, mock):
        '''
        Test if it return the full data about the publication
        '''
        self.assertDictEqual(publish.publish('*', 'publish.salt'), {})

    # 'runner' function tests: 1

    def test_runner(self, mock):
        '''
        Test if it execute a runner on the master and return the data
        from the runner function
        '''
        ret = ('No access to master. If using salt-call with --local,'
               ' please remove.')
        self.assertEqual(publish.runner('manage.down'), ret)

        mock = MagicMock(return_value=True)
        mock_id = MagicMock(return_value='salt_id')
        with patch.dict(publish.__opts__, {'master_uri': mock,
                                           'id': mock_id}):
            Channel.flag = 0
            self.assertTrue(publish.runner('manage.down'))

            Channel.flag = 1
            self.assertEqual(publish.runner('manage.down'),
                             "'manage.down' runner publish timed out")


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PublishTestCase, needs_daemon=False)
