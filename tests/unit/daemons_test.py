# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import patch, MagicMock, NO_MOCK, NO_MOCK_REASON

ensure_in_syspath('../')

# Import Salt libs
import integration
from salt.cli import daemons


class LoggerMock(object):
    '''
    Logger data collector
    '''

    def __init__(self):
        '''
        init
        :return:
        '''
        self.reset()

    def reset(self):
        '''
        Reset values

        :return:
        '''
        self.last_message = self.last_type = None

    def info(self, data):
        '''
        Collects the data from the logger of info type.

        :param data:
        :return:
        '''
        self.last_message = data
        self.last_type = 'info'

    def warning(self, data):
        '''
        Collects the data from the logger of warning type.

        :param data:
        :return:
        '''
        self.last_message = data
        self.last_type = 'warning'


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DaemonsStarterTestCase(TestCase, integration.SaltClientTestCaseMixIn):
    '''
    Unit test for the daemons starter classes.
    '''

    def test_master_daemon_hash_type_verified(self):
        '''
        Verify if Master is verifying hash_type config option.

        :return:
        '''
        def _create_master():
            '''
            Create master instance
            :return:
            '''
            master = daemons.Master()
            master.config = {'user': 'dummy', 'hash_type': alg}
            for attr in ['master', 'start_log_info', 'prepare']:
                setattr(master, attr, MagicMock())

            return master

        _logger = LoggerMock()
        with patch('salt.cli.daemons.check_user', MagicMock(return_value=True)):
            with patch('salt.cli.daemons.logger', _logger):
                for alg in ['md5', 'sha1']:
                    _create_master().start()
                    self.assertEqual(_logger.last_type, 'warning')
                    self.assertTrue(_logger.last_message)
                    self.assertTrue(_logger.last_message.find('Do not use {alg}'.format(alg=alg)) > -1)

                _logger.reset()

                for alg in ['sha224', 'sha256', 'sha384', 'sha512']:
                    _create_master().start()
                    self.assertEqual(_logger.last_type, None)
                    self.assertFalse(_logger.last_message)

    def test_minion_daemon_hash_type_verified(self):
        '''
        Verify if Minion is verifying hash_type config option.

        :return:
        '''

        def _create_minion():
            '''
            Create minion instance
            :return:
            '''
            obj = daemons.Minion()
            obj.config = {'user': 'dummy', 'hash_type': alg}
            for attr in ['start_log_info', 'prepare', 'shutdown']:
                setattr(obj, attr, MagicMock())
            setattr(obj, 'minion', MagicMock(restart=False))

            return obj

        _logger = LoggerMock()
        with patch('salt.cli.daemons.check_user', MagicMock(return_value=True)):
            with patch('salt.cli.daemons.logger', _logger):
                for alg in ['md5', 'sha1']:
                    _create_minion().start()
                    self.assertEqual(_logger.last_type, 'warning')
                    self.assertTrue(_logger.last_message)
                    self.assertTrue(_logger.last_message.find('Do not use {alg}'.format(alg=alg)) > -1)

                _logger.reset()

                for alg in ['sha224', 'sha256', 'sha384', 'sha512']:
                    _create_minion().start()
                    self.assertEqual(_logger.last_type, None)
                    self.assertFalse(_logger.last_message)

    def test_proxy_minion_daemon_hash_type_verified(self):
        '''
        Verify if ProxyMinion is verifying hash_type config option.

        :return:
        '''

        def _create_proxy_minion():
            '''
            Create proxy minion instance
            :return:
            '''
            obj = daemons.ProxyMinion()
            obj.config = {'user': 'dummy', 'hash_type': alg}
            for attr in ['minion', 'start_log_info', 'prepare', 'shutdown']:
                setattr(obj, attr, MagicMock())

            return obj

        _logger = LoggerMock()
        with patch('salt.cli.daemons.check_user', MagicMock(return_value=True)):
            with patch('salt.cli.daemons.logger', _logger):
                for alg in ['md5', 'sha1']:
                    _create_proxy_minion().start()
                    self.assertEqual(_logger.last_type, 'warning')
                    self.assertTrue(_logger.last_message)
                    self.assertTrue(_logger.last_message.find('Do not use {alg}'.format(alg=alg)) > -1)

                _logger.reset()

                for alg in ['sha224', 'sha256', 'sha384', 'sha512']:
                    _create_proxy_minion().start()
                    self.assertEqual(_logger.last_type, None)
                    self.assertFalse(_logger.last_message)

    def test_syndic_daemon_hash_type_verified(self):
        '''
        Verify if Syndic is verifying hash_type config option.

        :return:
        '''

        def _create_syndic():
            '''
            Create syndic instance
            :return:
            '''
            obj = daemons.Syndic()
            obj.config = {'user': 'dummy', 'hash_type': alg}
            for attr in ['syndic', 'start_log_info', 'prepare', 'shutdown']:
                setattr(obj, attr, MagicMock())

            return obj

        _logger = LoggerMock()
        with patch('salt.cli.daemons.check_user', MagicMock(return_value=True)):
            with patch('salt.cli.daemons.logger', _logger):
                for alg in ['md5', 'sha1']:
                    _create_syndic().start()
                    self.assertEqual(_logger.last_type, 'warning')
                    self.assertTrue(_logger.last_message)
                    self.assertTrue(_logger.last_message.find('Do not use {alg}'.format(alg=alg)) > -1)

                _logger.reset()

                for alg in ['sha224', 'sha256', 'sha384', 'sha512']:
                    _create_syndic().start()
                    self.assertEqual(_logger.last_type, None)
                    self.assertFalse(_logger.last_message)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(DaemonsStarterTestCase, needs_daemon=False)
