# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import contextlib

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
        ret = [{'comment': '', 'changes': {}, 'name': 'salt', 'result': True},
               {'changes': {},
                'comment': 'The service salt is already running',
                'name': 'salt', 'result': True},
               {'changes': 'saltstack',
                'comment': 'The service salt is already running',
                'name': 'salt', 'result': True},
               {'changes': {},
                'comment': 'Service salt is set to start', 'name': 'salt',
                'result': None},
               {'changes': 'saltstack',
                'comment': 'Started Service salt', 'name': 'salt',
                'result': True},
               {'changes': {},
                'comment': 'The service salt is already running',
                'name': 'salt', 'result': True}]

        tmock = MagicMock(return_value=True)
        fmock = MagicMock(return_value=False)
        vmock = MagicMock(return_value="salt")
        with patch.object(service, '_enabled_used_error', vmock):
            self.assertEqual(service.running("salt", enabled=1), 'salt')

        with patch.object(service, '_available', fmock):
            self.assertDictEqual(service.running("salt"), ret[0])

        with patch.object(service, '_available', tmock):
            with contextlib.nested(
                patch.dict(service.__opts__, {'test': False}),
                patch.dict(
                    service.__salt__,
                    {'service.enabled': tmock, 'service.status': tmock}
                )
            ):
                self.assertDictEqual(service.running("salt"), ret[1])

                # service was enabled and running, no changes
                mock = MagicMock(return_value={'changes': 'saltstack'})
                with contextlib.nested(
                    patch.dict(service.__opts__, {'test': False}),
                    patch.dict(
                        service.__salt__,
                        {'service.enabled':
                         MagicMock(side_effect=[False, True]),
                         'service.status': tmock}
                    ),
                    patch.object(service, '_enable', mock)
                ):
                    self.assertDictEqual(service.running("salt", True), ret[2])

                with contextlib.nested(
                    patch.dict(service.__opts__, {'test': False}),
                    patch.dict(
                        service.__salt__,
                        {'service.enabled':
                         MagicMock(side_effect=[True, False]),
                         'service.status': tmock}
                    ),
                    patch.object(service, '_disable', mock)
                ):
                    self.assertDictEqual(service.running("salt", False),
                                         ret[2])

                with patch.dict(service.__opts__, {'test': True}):
                    self.assertDictEqual(service.running("salt"), ret[5])

                with contextlib.nested(
                    patch.dict(
                        service.__salt__,
                        {'service.status': fmock}
                    ),
                    patch.dict(service.__opts__, {'test': True})
                ):
                    self.assertDictEqual(service.running("salt"), ret[3])

                with contextlib.nested(
                    patch.dict(service.__opts__, {'test': False}),
                    patch.dict(
                        service.__salt__, {
                            'service.status':
                            MagicMock(side_effect=[False, True]),
                            'service.enabled':
                            MagicMock(side_effect=[False, True]),
                            'service.start':
                            MagicMock(return_value="stack")}),
                    patch.object(
                        service, '_enable',
                        MagicMock(return_value={'changes': 'saltstack'}))
                ):
                    self.assertDictEqual(service.running("salt", True), ret[4])

    def test_dead(self):
        '''
            Test to ensure that the named service is dead
        '''
        ret = [{'changes': {}, 'comment': '', 'name': 'salt', 'result': True},
               {'changes': 'saltstack',
                'comment': 'The service salt is already dead', 'name': 'salt',
                'result': True},
               {'changes': {},
                'comment': 'Service salt is set to be killed', 'name': 'salt',
                'result': None},
               {'changes': 'saltstack',
                'comment': 'Service salt was killed', 'name': 'salt',
                'result': True},
               {'changes': {},
                'comment': 'Service salt was killed', 'name': 'salt',
                'result': True},
               {'changes': 'saltstack',
                'comment': 'The service salt is already dead', 'name': 'salt',
                'result': True}]

        mock = MagicMock(return_value="salt")
        with patch.object(service, '_enabled_used_error', mock):
            self.assertEqual(service.dead("salt", enabled=1), 'salt')

        tmock = MagicMock(return_value=True)
        fmock = MagicMock(return_value=False)
        with patch.object(service, '_available', fmock):
            self.assertDictEqual(service.dead("salt"), ret[0])

        with patch.object(service, '_available', tmock):
            mock = MagicMock(return_value={'changes': 'saltstack'})
            with contextlib.nested(
                patch.dict(service.__opts__, {'test': True}),
                patch.dict(
                    service.__salt__,
                    {'service.enabled': MagicMock(return_value=False),
                     'service.stop': MagicMock(return_value=True),
                     'service.status': MagicMock(return_value=False)}),
                patch.object(service, '_enable', mock)
            ):
                self.assertDictEqual(service.dead("salt", True), ret[5])
            with contextlib.nested(
                patch.dict(service.__opts__, {'test': False}),
                patch.dict(
                    service.__salt__,
                    {'service.enabled': MagicMock(return_value=False),
                     'service.stop': MagicMock(return_value=True),
                     'service.status': MagicMock(return_value=False)}),
                patch.object(service, '_enable', mock)
            ):
                self.assertDictEqual(service.dead("salt", True), ret[1])

            with contextlib.nested(
                patch.dict(service.__opts__, {'test': True}),
                patch.dict(
                    service.__salt__,
                    {'service.enabled': MagicMock(return_value=True),
                     'service.status': MagicMock(return_value=True)}),
            ):
                self.assertDictEqual(service.dead("salt"), ret[2])

            with contextlib.nested(
                patch.dict(service.__opts__, {'test': False}),
                patch.dict(
                    service.__salt__,
                    {'service.enabled':
                     MagicMock(side_effect=[True, True, False]),
                     'service.status':
                     MagicMock(side_effect=[True, True, False]),
                     'service.stop': MagicMock(return_value="stack")}),
                patch.object(
                    service, '_enable',
                    MagicMock(return_value={'changes': 'saltstack'}))
            ):
                self.assertDictEqual(service.dead("salt", True), ret[3])

            # test an initd which a wrong status (True even if dead)
            with contextlib.nested(
                patch.dict(service.__opts__, {'test': False}),
                patch.dict(
                    service.__salt__,
                    {'service.enabled':
                     MagicMock(side_effect=[False, False, False]),
                     'service.status':
                     MagicMock(side_effect=[True, True, True]),
                     'service.stop': MagicMock(return_value="stack")}),
                patch.object(
                    service, '_disable',
                    MagicMock(return_value={}))
            ):
                self.assertDictEqual(service.dead("salt", False), ret[4])

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
