# -*- coding: utf-8 -*-
"""
    :codeauthor: Bo Maryniuk <bo@suse.de>
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import multiprocessing

# Import Salt libs
import salt.cli.daemons as daemons
from tests.support.mixins import SaltClientTestCaseMixin
from tests.support.mock import MagicMock, patch

# Import Salt Testing libs
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class LoggerMock(object):
    """
    Logger data collector
    """

    def __init__(self):
        """
        init
        :return:
        """
        self.reset()

    def reset(self):
        """
        Reset values

        :return:
        """
        self.messages = []

    def info(self, message, *args, **kwargs):
        """
        Collects the data from the logger of info type.

        :param data:
        :return:
        """
        self.messages.append(
            {"message": message, "args": args, "kwargs": kwargs, "type": "info"}
        )

    def warning(self, message, *args, **kwargs):
        """
        Collects the data from the logger of warning type.

        :param data:
        :return:
        """
        self.messages.append(
            {"message": message, "args": args, "kwargs": kwargs, "type": "warning"}
        )

    def has_message(self, msg, log_type=None):
        """
        Check if log has message.

        :param data:
        :return:
        """
        for data in self.messages:
            log_str = (
                data["message"] % data["args"]
            )  # pylint: disable=incompatible-py3-code
            if (data["type"] == log_type or not log_type) and log_str.find(msg) > -1:
                return True

        return False


def _master_exec_test(child_pipe):
    def _create_master():
        """
        Create master instance
        :return:
        """
        obj = daemons.Master()
        obj.config = {"user": "dummy", "hash_type": alg}
        for attr in ["start_log_info", "prepare", "shutdown", "master"]:
            setattr(obj, attr, MagicMock())

        return obj

    _logger = LoggerMock()
    ret = True
    try:
        with patch("salt.cli.daemons.check_user", MagicMock(return_value=True)):
            with patch("salt.cli.daemons.log", _logger):
                for alg in ["md5", "sha1"]:
                    _create_master().start()
                    ret = ret and _logger.has_message(
                        "Do not use {alg}".format(alg=alg), log_type="warning"
                    )

                _logger.reset()

                for alg in ["sha224", "sha256", "sha384", "sha512"]:
                    _create_master().start()
                    ret = (
                        ret
                        and _logger.messages
                        and not _logger.has_message("Do not use ")
                    )
    except Exception:  # pylint: disable=broad-except
        log.exception("Exception raised in master daemon unit test")
        ret = False
    child_pipe.send(ret)
    child_pipe.close()


def _minion_exec_test(child_pipe):
    def _create_minion():
        """
        Create minion instance
        :return:
        """
        obj = daemons.Minion()
        obj.config = {"user": "dummy", "hash_type": alg}
        for attr in ["start_log_info", "prepare", "shutdown"]:
            setattr(obj, attr, MagicMock())
        setattr(obj, "minion", MagicMock(restart=False))

        return obj

    ret = True
    try:
        _logger = LoggerMock()
        with patch("salt.cli.daemons.check_user", MagicMock(return_value=True)):
            with patch("salt.cli.daemons.log", _logger):
                for alg in ["md5", "sha1"]:
                    _create_minion().start()
                    ret = ret and _logger.has_message(
                        "Do not use {alg}".format(alg=alg), log_type="warning"
                    )
                _logger.reset()

                for alg in ["sha224", "sha256", "sha384", "sha512"]:
                    _create_minion().start()
                    ret = (
                        ret
                        and _logger.messages
                        and not _logger.has_message("Do not use ")
                    )
    except Exception:  # pylint: disable=broad-except
        log.exception("Exception raised in minion daemon unit test")
        ret = False
    child_pipe.send(ret)
    child_pipe.close()


def _proxy_exec_test(child_pipe):
    def _create_proxy_minion():
        """
        Create proxy minion instance
        :return:
        """
        obj = daemons.ProxyMinion()
        obj.config = {"user": "dummy", "hash_type": alg}
        for attr in ["minion", "start_log_info", "prepare", "shutdown", "tune_in"]:
            setattr(obj, attr, MagicMock())

        obj.minion.restart = False
        return obj

    ret = True
    try:
        _logger = LoggerMock()
        with patch("salt.cli.daemons.check_user", MagicMock(return_value=True)):
            with patch("salt.cli.daemons.log", _logger):
                for alg in ["md5", "sha1"]:
                    _create_proxy_minion().start()
                    ret = ret and _logger.has_message(
                        "Do not use {alg}".format(alg=alg), log_type="warning"
                    )

                _logger.reset()

                for alg in ["sha224", "sha256", "sha384", "sha512"]:
                    _create_proxy_minion().start()
                    ret = (
                        ret
                        and _logger.messages
                        and not _logger.has_message("Do not use ")
                    )
    except Exception:  # pylint: disable=broad-except
        log.exception("Exception raised in proxy daemon unit test")
        ret = False
    child_pipe.send(ret)
    child_pipe.close()


def _syndic_exec_test(child_pipe):
    def _create_syndic():
        """
        Create syndic instance
        :return:
        """
        obj = daemons.Syndic()
        obj.config = {"user": "dummy", "hash_type": alg}
        for attr in ["syndic", "start_log_info", "prepare", "shutdown"]:
            setattr(obj, attr, MagicMock())

        return obj

    ret = True
    try:
        _logger = LoggerMock()
        with patch("salt.cli.daemons.check_user", MagicMock(return_value=True)):
            with patch("salt.cli.daemons.log", _logger):
                for alg in ["md5", "sha1"]:
                    _create_syndic().start()
                    ret = ret and _logger.has_message(
                        "Do not use {alg}".format(alg=alg), log_type="warning"
                    )

                _logger.reset()

                for alg in ["sha224", "sha256", "sha384", "sha512"]:
                    _create_syndic().start()
                    ret = (
                        ret
                        and _logger.messages
                        and not _logger.has_message("Do not use ")
                    )
    except Exception:  # pylint: disable=broad-except
        log.exception("Exception raised in syndic daemon unit test")
        ret = False
    child_pipe.send(ret)
    child_pipe.close()


class DaemonsStarterTestCase(TestCase, SaltClientTestCaseMixin):
    """
    Unit test for the daemons starter classes.
    """

    def _multiproc_exec_test(self, exec_test):
        m_parent, m_child = multiprocessing.Pipe()
        p_ = multiprocessing.Process(target=exec_test, args=(m_child,))
        p_.start()
        self.assertTrue(m_parent.recv())
        p_.join()

    def test_master_daemon_hash_type_verified(self):
        """
        Verify if Master is verifying hash_type config option.

        :return:
        """
        self._multiproc_exec_test(_master_exec_test)

    def test_minion_daemon_hash_type_verified(self):
        """
        Verify if Minion is verifying hash_type config option.

        :return:
        """
        self._multiproc_exec_test(_minion_exec_test)

    def test_proxy_minion_daemon_hash_type_verified(self):
        """
        Verify if ProxyMinion is verifying hash_type config option.

        :return:
        """
        self._multiproc_exec_test(_proxy_exec_test)

    def test_syndic_daemon_hash_type_verified(self):
        """
        Verify if Syndic is verifying hash_type config option.

        :return:
        """
        self._multiproc_exec_test(_syndic_exec_test)
