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
        self.messages = list()

    def info(self, data):
        '''
        Collects the data from the logger of info type.

        :param data:
        :return:
        '''
        self.messages.append({'message': data, 'type': 'info'})

    def warning(self, data):
        '''
        Collects the data from the logger of warning type.

        :param data:
        :return:
        '''
        self.messages.append({'message': data, 'type': 'warning'})

    def has_message(self, msg, log_type=None):
        '''
        Check if log has message.

        :param data:
        :return:
        '''
        for data in self.messages:
            if (data['type'] == log_type or not log_type) and data['message'].find(msg) > -1:
                return True

        return False


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
            with patch('salt.cli.daemons.log', _logger):
                for alg in ['md5', 'sha1']:
                    _create_master().start()
                    self.assertTrue(_logger.messages)
                    self.assertTrue(_logger.has_message('Do not use {alg}'.format(alg=alg),
                                                        log_type='warning'))

                _logger.reset()

                for alg in ['sha224', 'sha256', 'sha384', 'sha512']:
                    _create_master().start()
                    self.assertTrue(_logger.messages)
                    self.assertFalse(_logger.has_message('Do not use '))

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
            with patch('salt.cli.daemons.log', _logger):
                for alg in ['md5', 'sha1']:
                    _create_minion().start()
                    self.assertTrue(_logger.messages)
                    self.assertTrue(_logger.has_message('Do not use {alg}'.format(alg=alg),
                                                        log_type='warning'))

                _logger.reset()

                for alg in ['sha224', 'sha256', 'sha384', 'sha512']:
                    _create_minion().start()
                    self.assertTrue(_logger.messages)
                    self.assertFalse(_logger.has_message('Do not use '))

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
            with patch('salt.cli.daemons.log', _logger):
                for alg in ['md5', 'sha1']:
                    _create_proxy_minion().start()
                    self.assertTrue(_logger.messages)
                    self.assertTrue(_logger.has_message('Do not use {alg}'.format(alg=alg),
                                                        log_type='warning'))

                _logger.reset()

                for alg in ['sha224', 'sha256', 'sha384', 'sha512']:
                    _create_proxy_minion().start()
                    self.assertTrue(_logger.messages)
                    self.assertFalse(_logger.has_message('Do not use '))

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
            with patch('salt.cli.daemons.log', _logger):
                for alg in ['md5', 'sha1']:
                    _create_syndic().start()
                    self.assertTrue(_logger.messages)
                    self.assertTrue(_logger.has_message('Do not use {alg}'.format(alg=alg),
                                                        log_type='warning'))

                _logger.reset()

                for alg in ['sha224', 'sha256', 'sha384', 'sha512']:
                    _create_syndic().start()
                    self.assertTrue(_logger.messages)
                    self.assertFalse(_logger.has_message('Do not use '))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DaemonsStarterTestCase, needs_daemon=False)
