"""
Unit test for the daemons starter classes.
"""

import logging
import multiprocessing

import salt.cli.daemons
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


class LoggerMock:
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
            log_str = data["message"] % data["args"]
            if (data["type"] == log_type or not log_type) and log_str.find(msg) > -1:
                return True

        return False


def _master_exec_test(child_pipe):
    def _create_master():
        """
        Create master instance
        :return:
        """
        obj = salt.cli.daemons.Master()
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
                        f"Do not use {alg}", log_type="warning"
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
        obj = salt.cli.daemons.Minion()
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
                        f"Do not use {alg}", log_type="warning"
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
        obj = salt.cli.daemons.ProxyMinion()
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
                        f"Do not use {alg}", log_type="warning"
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
        obj = salt.cli.daemons.Syndic()
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
                        f"Do not use {alg}", log_type="warning"
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


def _multiproc_exec_test(exec_test):
    m_parent, m_child = multiprocessing.Pipe()
    p_ = multiprocessing.Process(target=exec_test, args=(m_child,))
    p_.start()
    assert m_parent.recv() is True
    p_.join()


def test_master_daemon_hash_type_verified():
    """
    Verify if Master is verifying hash_type config option.
    """
    _multiproc_exec_test(_master_exec_test)


def test_minion_daemon_hash_type_verified():
    """
    Verify if Minion is verifying hash_type config option.
    """
    _multiproc_exec_test(_minion_exec_test)


def test_proxy_minion_daemon_hash_type_verified():
    """
    Verify if ProxyMinion is verifying hash_type config option.
    """
    _multiproc_exec_test(_proxy_exec_test)


def test_syndic_daemon_hash_type_verified():
    """
    Verify if Syndic is verifying hash_type config option.
    """
    _multiproc_exec_test(_syndic_exec_test)


def test_master_skip_prepare(tmp_path):
    root_dir = tmp_path / "root"
    pki_dir = tmp_path / "pki"
    sock_dir = tmp_path / "socket"
    cache_dir = tmp_path / "cache"
    token_dir = tmp_path / "token"
    syndic_dir = tmp_path / "syndic"
    sqlite_dir = tmp_path / "sqlite_queue_dir"

    assert not pki_dir.exists()
    assert not sock_dir.exists()
    assert not cache_dir.exists()
    assert not token_dir.exists()
    assert not syndic_dir.exists()
    assert not sqlite_dir.exists()

    master = salt.cli.daemons.Master()
    master.config = {
        "verify_env": True,
        "pki_dir": str(pki_dir),
        "cachedir": str(cache_dir),
        "sock_dir": str(sock_dir),
        "token_dir": str(token_dir),
        "syndic_dir": str(syndic_dir),
        "sqlite_queue_dir": str(sqlite_dir),
        "cluster_id": None,
        "user": "root",
        "permissive_pki_access": False,
        "root_dir": str(root_dir),
    }

    assert not pki_dir.exists()
    assert not sock_dir.exists()
    assert not cache_dir.exists()
    assert not token_dir.exists()
    assert not syndic_dir.exists()
    assert not sqlite_dir.exists()


def test_master_prepare(tmp_path):
    root_dir = tmp_path / "root"
    pki_dir = tmp_path / "pki"
    sock_dir = tmp_path / "socket"
    cache_dir = tmp_path / "cache"
    token_dir = tmp_path / "token"
    syndic_dir = tmp_path / "syndic"
    sqlite_dir = tmp_path / "sqlite_queue_dir"

    assert not pki_dir.exists()
    assert not sock_dir.exists()
    assert not cache_dir.exists()
    assert not token_dir.exists()
    assert not syndic_dir.exists()
    assert not sqlite_dir.exists()

    master = salt.cli.daemons.Master()
    master.config = {
        "verify_env": True,
        "pki_dir": str(pki_dir),
        "cachedir": str(cache_dir),
        "sock_dir": str(sock_dir),
        "token_dir": str(token_dir),
        "syndic_dir": str(syndic_dir),
        "sqlite_queue_dir": str(sqlite_dir),
        "cluster_id": None,
        "user": "root",
        "permissive_pki_access": False,
        "root_dir": str(root_dir),
    }

    master.verify_environment()

    assert pki_dir.exists()
    assert (pki_dir / "minions").exists()
    assert (pki_dir / "minions_pre").exists()
    assert (pki_dir / "minions_denied").exists()
    assert (pki_dir / "minions_autosign").exists()
    assert (pki_dir / "minions_rejected").exists()
    assert sock_dir.exists()
    assert cache_dir.exists()
    assert (cache_dir / "jobs").exists()
    assert (cache_dir / "proc").exists()
    assert token_dir.exists()
    assert syndic_dir.exists()
    assert sqlite_dir.exists()


def test_master_prepare_cluster(tmp_path):
    root_dir = tmp_path / "root"
    pki_dir = tmp_path / "pki"
    sock_dir = tmp_path / "socket"
    cache_dir = tmp_path / "cache"
    token_dir = tmp_path / "token"
    syndic_dir = tmp_path / "syndic"
    sqlite_dir = tmp_path / "sqlite_queue_dir"
    cluster_dir = tmp_path / "cluster"

    assert not pki_dir.exists()
    assert not sock_dir.exists()
    assert not cache_dir.exists()
    assert not token_dir.exists()
    assert not syndic_dir.exists()
    assert not sqlite_dir.exists()
    assert not cluster_dir.exists()

    master = salt.cli.daemons.Master()
    master.config = {
        "verify_env": True,
        "cluster_id": "cluster-test",
        "cluster_pki_dir": str(cluster_dir),
        "pki_dir": str(pki_dir),
        "cachedir": str(cache_dir),
        "sock_dir": str(sock_dir),
        "token_dir": str(token_dir),
        "syndic_dir": str(syndic_dir),
        "sqlite_queue_dir": str(sqlite_dir),
        "user": "root",
        "permissive_pki_access": False,
        "root_dir": str(root_dir),
    }

    master.verify_environment()

    assert pki_dir.exists()
    assert (pki_dir / "minions").exists()
    assert (pki_dir / "minions_pre").exists()
    assert (pki_dir / "minions_denied").exists()
    assert (pki_dir / "minions_autosign").exists()
    assert (pki_dir / "minions_rejected").exists()
    assert sock_dir.exists()
    assert cache_dir.exists()
    assert (cache_dir / "jobs").exists()
    assert (cache_dir / "proc").exists()
    assert token_dir.exists()
    assert syndic_dir.exists()
    assert sqlite_dir.exists()

    assert cluster_dir.exists()
    assert (cluster_dir / "peers").exists()
    assert (cluster_dir / "minions").exists()
    assert (cluster_dir / "minions_pre").exists()
    assert (cluster_dir / "minions_denied").exists()
    assert (cluster_dir / "minions_autosign").exists()
    assert (cluster_dir / "minions_rejected").exists()
