# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
from salt.states import supervisord

supervisord.__salt__ = {}
supervisord.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SupervisordTestCase(TestCase):
    '''
    Test cases for salt.states.supervisord
    '''
    # 'running' function tests: 1

    def test_running(self):
        '''
        Test to ensure the named service is running.
        '''
        name = 'wsgi_server'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': ''}

        comt = ('Supervisord module not activated.'
                ' Do you need to install supervisord?')
        ret.update({'comment': comt, 'result': False})
        self.assertDictEqual(supervisord.running(name), ret)

        mock = MagicMock(return_value={name: {'state': 'running'}})
        with patch.dict(supervisord.__salt__, {'supervisord.status': mock}):
            with patch.dict(supervisord.__opts__, {'test': True}):
                comt = ('Service wsgi_server is already running')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(supervisord.running(name), ret)

            with patch.dict(supervisord.__opts__, {'test': False}):
                comt = ('Not starting already running service: wsgi_server')
                ret.update({'comment': comt})
                self.assertDictEqual(supervisord.running(name), ret)

    # 'dead' function tests: 1

    def test_dead(self):
        '''
        Test to ensure the named service is dead (not running).
        '''
        name = 'wsgi_server'

        ret = {'name': name,
               'changes': {},
               'result': None,
               'comment': ''}

        with patch.dict(supervisord.__opts__, {'test': True}):
            comt = ('Service {0} is set to be stopped'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(supervisord.dead(name), ret)

    # 'mod_watch' function tests: 1

    def test_mod_watch(self):
        '''
        Test to always restart on watch.
        '''
        name = 'wsgi_server'

        ret = {'name': name,
               'changes': {},
               'result': None,
               'comment': ''}

        comt = ('Supervisord module not activated.'
                ' Do you need to install supervisord?')
        ret.update({'comment': comt, 'result': False})
        self.assertDictEqual(supervisord.mod_watch(name), ret)
