# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''

# Import python libs
from __future__ import absolute_import
import multiprocessing

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, MagicMock, NO_MOCK, NO_MOCK_REASON
from tests.support.mixins import SaltClientTestCaseMixin

# Import Salt libs
import salt.cli.daemons as daemons


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
class DaemonsStarterTestCase(TestCase, SaltClientTestCaseMixin):
    '''
    Unit test for the daemons starter classes.
    '''

    def _multiproc_exec_test(self, exec_test):
        m_parent, m_child = multiprocessing.Pipe()
        p_ = multiprocessing.Process(target=exec_test, args=(m_child,))
        p_.start()
        self.assertTrue(m_parent.recv())
        p_.join()

    def test_master_daemon_hash_type_verified(self):
        '''
        Verify if Master is verifying hash_type config option.

        :return:
        '''
        def exec_test(child_pipe):
            def _create_master():
                '''
                Create master instance
                :return:
                '''
                obj = daemons.Master()
                obj.config = {'user': 'dummy', 'hash_type': alg}
                for attr in ['start_log_info', 'prepare', 'shutdown', 'master']:
                    setattr(obj, attr, MagicMock())

                return obj

            _logger = LoggerMock()
            ret = True
            with patch('salt.cli.daemons.check_user', MagicMock(return_value=True)):
                with patch('salt.cli.daemons.log', _logger):
                    for alg in ['md5', 'sha1']:
                        _create_master().start()
                        ret = ret and _logger.messages \
                                and _logger.has_message('Do not use {alg}'.format(alg=alg),
                                                        log_type='warning')

                    _logger.reset()

                    for alg in ['sha224', 'sha256', 'sha384', 'sha512']:
                        _create_master().start()
                        ret = ret and _logger.messages \
                              and not _logger.has_message('Do not use ')
                    child_pipe.send(ret)
                    child_pipe.close()
        self._multiproc_exec_test(exec_test)

    def test_minion_daemon_hash_type_verified(self):
        '''
        Verify if Minion is verifying hash_type config option.

        :return:
        '''

        def exec_test(child_pipe):
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

            ret = True
            _logger = LoggerMock()
            with patch('salt.cli.daemons.check_user', MagicMock(return_value=True)):
                with patch('salt.cli.daemons.log', _logger):
                    for alg in ['md5', 'sha1']:
                        _create_minion().start()
                        ret = ret and _logger.messages \
                                and _logger.has_message('Do not use {alg}'.format(alg=alg),
                                                        log_type='warning')
                    _logger.reset()

                    for alg in ['sha224', 'sha256', 'sha384', 'sha512']:
                        _create_minion().start()
                        ret = ret and _logger.messages \
                                and not _logger.has_message('Do not use ')

                child_pipe.send(ret)
                child_pipe.close()

        self._multiproc_exec_test(exec_test)

    def test_proxy_minion_daemon_hash_type_verified(self):
        '''
        Verify if ProxyMinion is verifying hash_type config option.

        :return:
        '''

        def exec_test(child_pipe):
            def _create_proxy_minion():
                '''
                Create proxy minion instance
                :return:
                '''
                obj = daemons.ProxyMinion()
                obj.config = {'user': 'dummy', 'hash_type': alg}
                for attr in ['minion', 'start_log_info', 'prepare', 'shutdown', 'tune_in']:
                    setattr(obj, attr, MagicMock())

                obj.minion.restart = False
                return obj

            ret = True
            _logger = LoggerMock()
            with patch('salt.cli.daemons.check_user', MagicMock(return_value=True)):
                with patch('salt.cli.daemons.log', _logger):
                    for alg in ['md5', 'sha1']:
                        _create_proxy_minion().start()
                        ret = ret and _logger.messages \
                                and _logger.has_message('Do not use {alg}'.format(alg=alg),
                                                        log_type='warning')

                    _logger.reset()

                    for alg in ['sha224', 'sha256', 'sha384', 'sha512']:
                        _create_proxy_minion().start()
                        ret = ret and _logger.messages \
                                and not _logger.has_message('Do not use ')
            child_pipe.send(ret)
            child_pipe.close()

        self._multiproc_exec_test(exec_test)

    def test_syndic_daemon_hash_type_verified(self):
        '''
        Verify if Syndic is verifying hash_type config option.

        :return:
        '''

        def exec_test(child_pipe):
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

            ret = True
            _logger = LoggerMock()
            with patch('salt.cli.daemons.check_user', MagicMock(return_value=True)):
                with patch('salt.cli.daemons.log', _logger):
                    for alg in ['md5', 'sha1']:
                        _create_syndic().start()
                        ret = ret and _logger.messages \
                                and _logger.has_message('Do not use {alg}'.format(alg=alg),
                                                        log_type='warning')

                    _logger.reset()

                    for alg in ['sha224', 'sha256', 'sha384', 'sha512']:
                        _create_syndic().start()
                        ret = ret and _logger.messages \
                                and not _logger.has_message('Do not use ')

            child_pipe.send(ret)
            child_pipe.close()

        self._multiproc_exec_test(exec_test)
