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
from salt.states import service

# Globals
service.__salt__ = {}
service.__opts__ = {}


def func(name):
    '''
        Mock func method
    '''
    return name


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ServiceTestCase(TestCase):
    '''
        Validate the service state
    '''
    def test_running(self):
        '''
            Test to verify that the service is running
        '''

        tmock = MagicMock(return_value=True)
        fmock = MagicMock(return_value=False)
        vmock = MagicMock(return_value="salt")

        # used enabled instead of enable
        with patch.object(service, '_enabled_used_error', vmock):
            self.assertEqual(service.running("salt", enabled=1), 'salt')

        # Service not available
        ret = {'comment': '',
               'changes': {},
               'name': 'salt',
               'result': True}
        with patch.object(service, '_available', fmock):
            self.assertDictEqual(service.running("salt"), ret)

        # Service available
        with patch.object(service, '_available', tmock):
            # Test = False
            with patch.dict(service.__opts__, {'test': False}):

                # Service running, no changes
                ret = {'changes': {},
                       'comment': 'The service salt is already running',
                       'name': 'salt',
                       'result': True}
                with patch.dict(service.__salt__,
                                {'service.enabled':
                                 MagicMock(side_effect=[True, True]),
                                 'service.status': tmock}):
                    self.assertDictEqual(service.running("salt"), ret)

                # service disabled and running, service enabled
                ret = {'changes': 'saltstack',
                       'comment': 'The service salt is already running, '
                                  'service enabled',
                       'name': 'salt',
                       'result': True}
                mock = MagicMock(return_value={'changes': 'saltstack'})
                with patch.dict(service.__salt__,
                                {'service.enabled':
                                 MagicMock(side_effect=[False, True]),
                                 'service.status': tmock}):
                    with patch.object(service, '_enable', mock):
                        self.assertDictEqual(service.running("salt", True), ret)

                # service was disabled and running, no change
                ret = {'changes': {},
                       'comment': 'The service salt is already running',
                       'name': 'salt',
                       'result': True}
                with patch.dict(service.__salt__,
                                {'service.enabled':
                                 MagicMock(side_effect=[False, False]),
                                 'service.status': tmock}):
                    with patch.object(service, '_disable', None):
                        self.assertDictEqual(
                            service.running("salt", False), ret)

                # Service not started, service disabled
                ret = {'changes': 'saltstack',
                       'comment': 'Started Service salt, service enabled',
                       'name': 'salt',
                       'result': True}
                with patch.dict(service.__salt__,
                                {'service.status':
                                     MagicMock(side_effect=[False, True]),
                                 'service.enabled':
                                     MagicMock(side_effect=[False, True]),
                                 'service.start':
                                     MagicMock(return_value="stack")}):
                    with patch.object(service, '_enable',
                            MagicMock(return_value={'changes': 'saltstack'})):
                        self.assertDictEqual(service.running("salt", True), ret)

                # Service enabled and stopped, fails to start
                ret = {'changes': {},
                       'comment': 'Service salt failed to start',
                       'name': 'salt',
                       'result': True}
                with patch.dict(service.__salt__,
                                {'service.status':
                                     MagicMock(side_effect=[False, False]),
                                 'service.enabled':
                                     MagicMock(side_effect=[True, True]),
                                 'service.start':
                                     MagicMock(return_value="stack")}):
                    with patch.object(service, '_enable',
                            MagicMock(return_value={'changes': 'saltstack'})):
                        self.assertDictEqual(service.running("salt", True), ret)

            # Test = True
            with patch.dict(service.__opts__, {'test': True}):

                # Service running, no changes (test)
                ret = {'changes': {},
                       'comment': 'Service salt is already started',
                       'name': 'salt',
                       'result': True}
                with patch.dict(service.__salt__,
                                {'service.enabled':
                                     MagicMock(side_effect=[True, True]),
                                 'service.status': tmock}):
                    self.assertDictEqual(service.running("salt"), ret)

                # Service not running, no changes (test)
                ret = {'changes': {},
                       'comment': 'Service salt is set to start',
                       'name': 'salt',
                       'result': None}
                with patch.dict(service.__salt__,
                                {'service.enabled':
                                     MagicMock(side_effect=[False, False]),
                                 'service.status': fmock}):
                    self.assertDictEqual(service.running("salt"), ret)

    def test_dead(self):
        '''
            Test to ensure that the named service is dead
        '''
        # Check if enabled was used
        mock = MagicMock(return_value="salt")
        with patch.object(service, '_enabled_used_error', mock):
            self.assertEqual(service.dead("salt", enabled=1), 'salt')

        # check if the service is available
        ret = {'changes': {}, 'comment': '', 'name': 'salt', 'result': True}
        tmock = MagicMock(return_value=True)
        fmock = MagicMock(return_value=False)
        mock = MagicMock(return_value={'changes': 'saltstack'})

        with patch.object(service, '_available', fmock):
            self.assertDictEqual(service.dead("salt"), ret)

        # service available
        with patch.object(service, '_available', tmock):

            # test = True
            with patch.dict(service.__opts__, {'test': True}):

                # service not running and disabled, will enable (test)
                ret = {'changes': {},
                       'comment': 'Service salt is already stopped and '
                                  'will be enabled',
                       'name': 'salt',
                       'result': None}
                with patch.dict(service.__salt__,
                                {'service.enabled':
                                     MagicMock(return_value=False),
                                 'service.status':
                                     MagicMock(return_value=False)}):
                    with patch.object(service, '_enable', mock):
                        self.assertDictEqual(service.dead("salt", True), ret)

                # service running and enabled
                ret = {'changes': {},
                       'comment': 'Service salt is set to be killed',
                       'name': 'salt',
                       'result': None}
                with patch.dict(service.__salt__,
                                {'service.enabled':
                                     MagicMock(return_value=True),
                                 'service.status':
                                     MagicMock(return_value=True)}):
                    self.assertDictEqual(service.dead("salt"), ret)

            # test = False
            with patch.dict(service.__opts__, {'test': False}):

                # Service stopped and disabled, no change
                ret = {'changes': 'saltstack',
                       'comment': 'The service salt is already dead',
                       'name': 'salt',
                       'result': True}
                with patch.dict(
                    service.__salt__,
                    {'service.enabled': MagicMock(return_value=False),
                     'service.stop': MagicMock(return_value=True),
                     'service.status': MagicMock(return_value=False)}):
                    with patch.object(service, '_enable', mock):
                        self.assertDictEqual(service.dead("salt", True), ret)

                # service enabled and running, service killed
                ret = {'changes': 'saltstack',
                       'comment': 'Killed Service salt',
                       'name': 'salt',
                       'result': True}
                with patch.dict(
                    service.__salt__,
                    {'service.enabled': MagicMock(side_effect=[True, True]),
                     'service.status': MagicMock(side_effect=[True, False]),
                     'service.stop': MagicMock(return_value="stack")}):
                    with patch.object(service, '_enable',
                            MagicMock(return_value={'changes': 'saltstack'})):
                        self.assertDictEqual(service.dead("salt", True), ret)

                # test an initd with a wrong status (True even if dead)
                ret = {'changes': {},
                       'comment': 'Service salt failed to die',
                       'name': 'salt',
                       'result': False}
                with patch.dict(
                    service.__salt__,
                    {'service.enabled': MagicMock(side_effect=[False, False]),
                     'service.status': MagicMock(side_effect=[True, True]),
                     'service.stop': MagicMock(return_value="stack")}):
                    with patch.object(service, '_disable',
                                      MagicMock(return_value={})):
                        self.assertDictEqual(service.dead("salt", False), ret)

    def test_enabled(self):
        '''
            Test to verify that the service is enabled
        '''
        ret = {'changes': 'saltstack', 'comment': '', 'name': 'salt',
               'result': True}
        mock = MagicMock(return_value={'changes': 'saltstack'})
        with patch.object(service, '_enable', mock):
            self.assertDictEqual(service.enabled("salt"), ret)

    def test_disabled(self):
        '''
            Test to verify that the service is disabled
        '''
        ret = {'changes': 'saltstack', 'comment': '', 'name': 'salt',
               'result': True}
        mock = MagicMock(return_value={'changes': 'saltstack'})
        with patch.object(service, '_disable', mock):
            self.assertDictEqual(service.disabled("salt"), ret)

    def test_mod_watch(self):
        '''
            Test to the service watcher, called to invoke the watch command.
        '''
        ret = [{'changes': {},
                'comment': 'Service is already stopped', 'name': 'salt',
                'result': True},
               {'changes': {},
                'comment': 'Unable to trigger watch for service.stack',
                'name': 'salt', 'result': False},
               {'changes': {},
                'comment': 'Service is set to be started', 'name': 'salt',
                'result': None},
               {'changes': {'salt': 'salt'},
                'comment': 'Service started', 'name': 'salt',
                'result': 'salt'}]

        mock = MagicMock(return_value=False)
        with patch.dict(service.__salt__, {'service.status': mock}):
            self.assertDictEqual(service.mod_watch("salt", "dead"), ret[0])

            with patch.dict(service.__salt__, {'service.start': func}):
                with patch.dict(service.__opts__, {'test': True}):
                    self.assertDictEqual(service.mod_watch("salt", "running"),
                                         ret[2])

                with patch.dict(service.__opts__, {'test': False}):
                    self.assertDictEqual(service.mod_watch("salt", "running"),
                                         ret[3])

        self.assertDictEqual(service.mod_watch("salt", "stack"), ret[1])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ServiceTestCase, needs_daemon=False)
