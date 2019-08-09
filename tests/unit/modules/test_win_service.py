# -*- coding: utf-8 -*-
'''
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf, WAR_ROOM_SKIP
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.win_service as win_service

# Import 3rd Party Libs
try:
    WINAPI = True
    import win32serviceutil
    import pywintypes
except ImportError:
    WINAPI = False


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinServiceTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Test cases for salt.modules.win_service
    '''
    def setup_loader_modules(self):
        return {win_service: {}}

    def test_get_enabled(self):
        '''
            Test to return the enabled services
        '''
        mock = MagicMock(return_value=[{'ServiceName': 'spongebob'},
                                       {'ServiceName': 'squarepants'},
                                       {'ServiceName': 'patrick'}])
        with patch.object(win_service, '_get_services', mock):
            mock_info = MagicMock(side_effect=[{'StartType': 'Auto'},
                                               {'StartType': 'Manual'},
                                               {'StartType': 'Disabled'}])
            with patch.object(win_service, 'info', mock_info):
                self.assertListEqual(win_service.get_enabled(),
                                     ['spongebob'])

    def test_get_disabled(self):
        '''
            Test to return the disabled services
        '''
        mock = MagicMock(return_value=[{'ServiceName': 'spongebob'},
                                       {'ServiceName': 'squarepants'},
                                       {'ServiceName': 'patrick'}])
        with patch.object(win_service, '_get_services', mock):
            mock_info = MagicMock(side_effect=[{'StartType': 'Auto'},
                                               {'StartType': 'Manual'},
                                               {'StartType': 'Disabled'}])
            with patch.object(win_service, 'info', mock_info):
                self.assertListEqual(win_service.get_disabled(),
                                     ['patrick', 'squarepants'])

    def test_available(self):
        '''
            Test to Returns ``True`` if the specified service
            is available, otherwise returns ``False``
        '''
        mock = MagicMock(return_value=['c', 'a', 'b'])
        with patch.object(win_service, 'get_all', mock):
            self.assertTrue(win_service.available("a"))

    def test_missing(self):
        '''
            Test to the inverse of service.available
        '''
        mock = MagicMock(return_value=['c', 'a', 'b'])
        with patch.object(win_service, 'get_all', mock):
            self.assertTrue(win_service.missing("d"))

    def test_get_all(self):
        '''
            Test to return all installed services
        '''
        mock = MagicMock(return_value=[{'ServiceName': 'spongebob'},
                                       {'ServiceName': 'squarepants'},
                                       {'ServiceName': 'patrick'}])
        with patch.object(win_service, '_get_services', mock):
            self.assertListEqual(win_service.get_all(),
                                 ['patrick', 'spongebob', 'squarepants'])

    def test_get_service_name(self):
        '''
            Test to the Display Name is what is displayed
            in Windows when services.msc is executed.
        '''
        mock = MagicMock(return_value=[{'ServiceName': 'spongebob',
                                        'DisplayName': 'Sponge Bob'},
                                       {'ServiceName': 'squarepants',
                                        'DisplayName': 'Square Pants'},
                                       {'ServiceName': 'patrick',
                                        'DisplayName': 'Patrick the Starfish'}])
        with patch.object(win_service, '_get_services', mock):
            self.assertDictEqual(win_service.get_service_name(),
                                 {'Patrick the Starfish': 'patrick',
                                  'Sponge Bob': 'spongebob',
                                  'Square Pants': 'squarepants'})
            self.assertDictEqual(win_service.get_service_name('patrick'),
                                 {'Patrick the Starfish': 'patrick'})

    @skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
    @skipIf(not WINAPI, 'win32serviceutil not available')
    def test_start(self):
        '''
            Test to start the specified service
        '''
        mock_true = MagicMock(return_value=True)
        mock_false = MagicMock(return_value=False)
        mock_info = MagicMock(side_effect=[{'Status': 'Running'}])

        with patch.object(win32serviceutil, 'StartService', mock_true), \
                patch.object(win_service, 'disabled', mock_false), \
                patch.object(win_service, 'info', mock_info):
            self.assertTrue(win_service.start('spongebob'))

        mock_info = MagicMock(side_effect=[{'Status': 'Stopped', 'Status_WaitHint': 0},
                                           {'Status': 'Start Pending', 'Status_WaitHint': 0},
                                           {'Status': 'Running'}])

        with patch.object(win32serviceutil, 'StartService', mock_true), \
                patch.object(win_service, 'disabled', mock_false), \
                patch.object(win_service, 'info', mock_info), \
                patch.object(win_service, 'status', mock_true):
            self.assertTrue(win_service.start('spongebob'))

    @skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
    @skipIf(not WINAPI, 'pywintypes not available')
    def test_start_already_running(self):
        '''
        Test starting a service that is already running
        '''
        mock_false = MagicMock(return_value=False)
        mock_error = MagicMock(
            side_effect=pywintypes.error(1056,
                                         'StartService',
                                         'Service is running'))
        mock_info = MagicMock(side_effect=[{'Status': 'Running'}])
        with patch.object(win32serviceutil, 'StartService', mock_error), \
                 patch.object(win_service, 'disabled', mock_false), \
                 patch.object(win_service, '_status_wait', mock_info):
            self.assertTrue(win_service.start('spongebob'))

    @skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
    @skipIf(not WINAPI, 'win32serviceutil not available')
    def test_stop(self):
        '''
            Test to stop the specified service
        '''
        mock_true = MagicMock(return_value=True)
        mock_false = MagicMock(return_value=False)
        mock_info = MagicMock(side_effect=[{'Status': 'Stopped'}])

        with patch.object(win32serviceutil, 'StopService', mock_true), \
                patch.object(win_service, '_status_wait', mock_info):
            self.assertTrue(win_service.stop('spongebob'))

        mock_info = MagicMock(side_effect=[{'Status': 'Running', 'Status_WaitHint': 0},
                                           {'Status': 'Stop Pending', 'Status_WaitHint': 0},
                                           {'Status': 'Stopped'}])

        with patch.object(win32serviceutil, 'StopService', mock_true), \
                patch.object(win_service, 'info', mock_info), \
                patch.object(win_service, 'status', mock_false):
            self.assertTrue(win_service.stop('spongebob'))

    @skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
    @skipIf(not WINAPI, 'pywintypes not available')
    def test_stop_not_running(self):
        '''
        Test stopping a service that is already stopped
        '''
        mock_error = MagicMock(
            side_effect=pywintypes.error(1062,
                                         'StopService',
                                         'Service is not running'))
        mock_info = MagicMock(side_effect=[{'Status': 'Stopped'}])
        with patch.object(win32serviceutil, 'StopService', mock_error), \
                patch.object(win_service, '_status_wait', mock_info):
            self.assertTrue(win_service.stop('spongebob'))

    def test_restart(self):
        '''
            Test to restart the named service
        '''
        mock_true = MagicMock(return_value=True)
        with patch.object(win_service, 'create_win_salt_restart_task',
                          mock_true):
            with patch.object(win_service, 'execute_salt_restart_task',
                              mock_true):
                self.assertTrue(win_service.restart("salt-minion"))

        with patch.object(win_service, 'stop', mock_true):
            with patch.object(win_service, 'start', mock_true):
                self.assertTrue(win_service.restart("salt"))

    def test_createwin_saltrestart_task(self):
        '''
            Test to create a task in Windows task
            scheduler to enable restarting the salt-minion
        '''
        mock_true = MagicMock(return_value=True)
        with patch.dict(win_service.__salt__, {'task.create_task': mock_true}):
            self.assertTrue(win_service.create_win_salt_restart_task())

    def test_execute_salt_restart_task(self):
        '''
            Test to run the Windows Salt restart task
        '''
        mock_true = MagicMock(return_value=True)
        with patch.dict(win_service.__salt__, {'task.run': mock_true}):
            self.assertTrue(win_service.execute_salt_restart_task())

    @skipIf(not WINAPI, 'win32serviceutil not available')
    def test_status(self):
        '''
            Test to return the status for a service
        '''
        mock_info = MagicMock(side_effect=[{'Status': 'Running'},
                                           {'Status': 'Stop Pending'},
                                           {'Status': 'Stopped'}])

        with patch.object(win_service, 'info', mock_info):
            self.assertTrue(win_service.status('spongebob'))
            self.assertTrue(win_service.status('patrick'))
            self.assertFalse(win_service.status('squidward'))

    def test_getsid(self):
        '''
            Test to return the sid for this windows service
        '''
        mock_info = MagicMock(side_effect=[{'sid': 'S-1-5-80-1956725871...'},
                                           {'sid': None}])
        with patch.object(win_service, 'info', mock_info):
            self.assertEqual(win_service.getsid('spongebob'),
                             'S-1-5-80-1956725871...')
            self.assertEqual(win_service.getsid('plankton'), None)

    def test_enable(self):
        '''
            Test to enable the named service to start at boot
        '''
        mock_modify = MagicMock(return_value=True)
        mock_info = MagicMock(return_value={'StartType': 'Auto',
                                            'StartTypeDelayed': False})
        with patch.object(win_service, 'modify', mock_modify):
            with patch.object(win_service, 'info', mock_info):
                self.assertTrue(win_service.enable('spongebob'))

    def test_disable(self):
        '''
            Test to disable the named service to start at boot
        '''
        mock_modify = MagicMock(return_value=True)
        mock_info = MagicMock(return_value={'StartType': 'Disabled'})
        with patch.object(win_service, 'modify', mock_modify):
            with patch.object(win_service, 'info', mock_info):
                self.assertTrue(win_service.disable('spongebob'))

    def test_enabled(self):
        '''
            Test to check to see if the named
            service is enabled to start on boot
        '''
        mock = MagicMock(side_effect=[{'StartType': 'Auto'},
                                      {'StartType': 'Disabled'}])
        with patch.object(win_service, 'info', mock):
            self.assertTrue(win_service.enabled('spongebob'))
            self.assertFalse(win_service.enabled('squarepants'))

    def test_enabled_with_space_in_name(self):
        '''
            Test to check to see if the named
            service is enabled to start on boot
            when have space in service name
        '''
        mock = MagicMock(side_effect=[{'StartType': 'Auto'},
                                      {'StartType': 'Disabled'}])
        with patch.object(win_service, 'info', mock):
            self.assertTrue(win_service.enabled('spongebob test'))
            self.assertFalse(win_service.enabled('squarepants test'))

    def test_disabled(self):
        '''
            Test to check to see if the named
            service is disabled to start on boot
        '''
        mock = MagicMock(side_effect=[False, True])
        with patch.object(win_service, 'enabled', mock):
            self.assertTrue(win_service.disabled('spongebob'))
            self.assertFalse(win_service.disabled('squarepants'))

    def test_cmd_quote(self):
        '''
        Make sure the command gets quoted correctly
        '''
        # Should always return command wrapped in double quotes
        expected = r'"C:\Program Files\salt\test.exe"'

        # test no quotes
        bin_path = r'C:\Program Files\salt\test.exe'
        self.assertEqual(win_service._cmd_quote(bin_path), expected)

        # test single quotes
        bin_path = r"'C:\Program Files\salt\test.exe'"
        self.assertEqual(win_service._cmd_quote(bin_path), expected)

        # test double quoted single quotes
        bin_path = '"\'C:\\Program Files\\salt\\test.exe\'"'
        self.assertEqual(win_service._cmd_quote(bin_path), expected)

        # test single quoted, double quoted, single quotes
        bin_path = "\'\"\'C:\\Program Files\\salt\\test.exe\'\"\'"
        self.assertEqual(win_service._cmd_quote(bin_path), expected)

    def test_service_dependencies(self):
        def _all():
            return ['Spongebob', 'Sandy', 'Patrick', 'Garry', 'Rocko', 'Heffer', 'Beverly']

        def _info(name):
            data = {}
            data['Spongebob'] = {'Dependencies': ['GaRrY']}
            data['Sandy'] = {'Dependencies': ['Spongebob']}
            data['Patrick'] = {'Dependencies': ['Sandy', 'gARRY']}
            data['Garry'] = {'Dependencies': []}

            data['Rocko'] = {'Dependencies': []}
            data['Heffer'] = {'Dependencies': ['Rocko']}
            data['Beverly'] = {'Dependencies': []}
            return data[name]

        spongebob = win_service.ServiceDependencies('spongebob', _all, _info)
        self.assertListEqual(['Garry'], spongebob.dependencies(with_indirect=False))
        self.assertListEqual(['Garry'], spongebob.dependencies(with_indirect=True))
        self.assertListEqual(['Sandy'], spongebob.parents(with_indirect=False))
        self.assertListEqual(['Sandy', 'Patrick'], spongebob.parents(with_indirect=True))
        self.assertListEqual(['Garry', 'Spongebob', 'Sandy', 'Patrick'], spongebob.start_order(with_deps=True, with_parents=True))
        self.assertListEqual(['Patrick', 'Sandy', 'Spongebob', 'Garry'], spongebob.stop_order(with_deps=True, with_parents=True))

        sandy = win_service.ServiceDependencies('SANDY', _all, _info)
        self.assertListEqual(sandy.dependencies(with_indirect=False), ['Spongebob'])
        self.assertListEqual(sandy.dependencies(with_indirect=True), ['Garry', 'Spongebob'])
        self.assertListEqual(sandy.parents(with_indirect=False), ['Patrick'])
        self.assertListEqual(sandy.parents(with_indirect=True), ['Patrick'])
        self.assertListEqual(['Garry', 'Spongebob', 'Sandy', 'Patrick'], spongebob.start_order(with_deps=True, with_parents=True))
        self.assertListEqual(['Patrick', 'Sandy', 'Spongebob', 'Garry'], spongebob.stop_order(with_deps=True, with_parents=True))
        self.assertListEqual(['Spongebob'], spongebob.start_order(with_deps=False, with_parents=False))
        self.assertListEqual(['Spongebob'], spongebob.stop_order(with_deps=False, with_parents=False))

        patrick = win_service.ServiceDependencies('Patrick', _all, _info)
        self.assertListEqual(['Garry', 'Sandy'], patrick.dependencies(with_indirect=False))
        self.assertListEqual(['Garry', 'Spongebob', 'Sandy'], patrick.dependencies(with_indirect=True))
        self.assertListEqual([], patrick.parents(with_indirect=False))
        self.assertListEqual([], patrick.parents(with_indirect=True))
        self.assertListEqual(['Garry', 'Spongebob', 'Sandy', 'Patrick'], spongebob.start_order(with_deps=True, with_parents=True))
        self.assertListEqual(['Patrick', 'Sandy', 'Spongebob', 'Garry'], spongebob.stop_order(with_deps=True, with_parents=True))

        garry = win_service.ServiceDependencies('gARRy', _all, _info)
        self.assertListEqual([], garry.dependencies(with_indirect=False))
        self.assertListEqual([], garry.dependencies(with_indirect=True))
        self.assertListEqual(['Patrick', 'Spongebob'], garry.parents(with_indirect=False))
        self.assertListEqual(['Spongebob', 'Sandy', 'Patrick'], garry.parents(with_indirect=True))
        self.assertListEqual(['Garry', 'Spongebob', 'Sandy', 'Patrick'], spongebob.start_order(with_deps=True, with_parents=True))
        self.assertListEqual(['Patrick', 'Sandy', 'Spongebob', 'Garry'], spongebob.stop_order(with_deps=True, with_parents=True))

        rocko = win_service.ServiceDependencies('Rocko', _all, _info)
        self.assertListEqual([], rocko.dependencies(with_indirect=False))
        self.assertListEqual([], rocko.dependencies(with_indirect=True))
        self.assertListEqual(['Heffer'], rocko.parents(with_indirect=False))
        self.assertListEqual(['Heffer'], rocko.parents(with_indirect=True))

        heffer = win_service.ServiceDependencies('Heffer', _all, _info)
        self.assertListEqual(['Rocko'], heffer.dependencies(with_indirect=False))
        self.assertListEqual(['Rocko'], heffer.dependencies(with_indirect=True))
        self.assertListEqual([], heffer.parents(with_indirect=False))
        self.assertListEqual([], heffer.parents(with_indirect=True))

        beverly = win_service.ServiceDependencies('beverly', _all, _info)
        self.assertListEqual([], beverly.dependencies(with_indirect=False))
        self.assertListEqual([], beverly.dependencies(with_indirect=True))
        self.assertListEqual([], beverly.parents(with_indirect=False))
        self.assertListEqual([], beverly.parents(with_indirect=True))

        with self.assertRaises(ValueError):
            spunky = win_service.ServiceDependencies('Spunky', _all, _info)
            spunky.dependencies()
            spunky.parents()
