import salt.modules.debian_service as debian_service
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import DEFAULT, MagicMock, patch
from tests.support.unit import TestCase


class DebianServicesTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.debian_service
    """

    def setup_loader_modules(self):
        return {debian_service: {}}

    def test_get_enabled(self):
        init_d_globs = ["/etc/init.d/S50foo", "/etc/init.d/S90bar"]
        glob_mock = MagicMock(
            side_effect=lambda x: init_d_globs if x == "/etc/rc[S3].d/S*" else DEFAULT
        )
        with patch("glob.glob", glob_mock), patch.object(
            debian_service, "_get_runlevel", MagicMock(return_value="3")
        ):
            ret = debian_service.get_enabled()
            expected = ["bar", "foo"]
            assert ret == expected, ret

    def test_get_disabled(self):
        get_all = MagicMock(return_value=["foo", "bar", "baz"])
        get_enabled = MagicMock(return_value=["bar", "baz"])
        with patch.object(debian_service, "get_all", get_all), patch.object(
            debian_service, "get_enabled", get_enabled
        ):
            ret = debian_service.get_disabled()
            expected = ["foo"]
            assert ret == expected, ret

    def test_available(self):
        get_all = MagicMock(return_value=["foo", "bar", "baz"])
        with patch.object(debian_service, "get_all", get_all):
            assert not debian_service.available("qux")
            assert debian_service.available("foo")

    def test_missing(self):
        get_all = MagicMock(return_value=["foo", "bar", "baz"])
        with patch.object(debian_service, "get_all", get_all):
            assert debian_service.missing("qux")
            assert not debian_service.missing("foo")

    def test_get_all(self):
        get_enabled = MagicMock(return_value=["baz", "hello", "world"])
        init_d_globs = ["/etc/init.d/foo", "/etc/init.d/bar"]
        glob_mock = MagicMock(
            side_effect=lambda x: init_d_globs if x == "/etc/init.d/*" else DEFAULT
        )
        with patch("glob.glob", glob_mock), patch.object(
            debian_service, "get_enabled", get_enabled
        ):
            ret = debian_service.get_all()
            expected = ["bar", "baz", "foo", "hello", "world"]
            assert ret == expected, ret

    def test_start(self):
        mock = MagicMock(return_value=0)
        with patch.dict(debian_service.__salt__, {"cmd.retcode": mock}):
            # Test successful command (0 retcode)
            assert debian_service.start("foo")
            # Confirm expected command was run
            mock.assert_called_once_with("service foo start")
            # Test unsuccessful command (nonzero retcode)
            mock.return_value = 1
            assert not debian_service.start("foo")

    def test_stop(self):
        mock = MagicMock(return_value=0)
        with patch.dict(debian_service.__salt__, {"cmd.retcode": mock}):
            # Test successful command (0 retcode)
            assert debian_service.stop("foo")
            # Confirm expected command was run
            mock.assert_called_once_with("service foo stop")
            # Test unsuccessful command (nonzero retcode)
            mock.return_value = 1
            assert not debian_service.stop("foo")

    def test_restart(self):
        mock = MagicMock(return_value=0)
        with patch.dict(debian_service.__salt__, {"cmd.retcode": mock}):
            # Test successful command (0 retcode)
            assert debian_service.restart("foo")
            # Confirm expected command was run
            mock.assert_called_once_with("service foo restart")
            # Test unsuccessful command (nonzero retcode)
            mock.return_value = 1
            assert not debian_service.restart("foo")

    def test_reload_(self):
        mock = MagicMock(return_value=0)
        with patch.dict(debian_service.__salt__, {"cmd.retcode": mock}):
            # Test successful command (0 retcode)
            assert debian_service.reload_("foo")
            # Confirm expected command was run
            mock.assert_called_once_with("service foo reload")
            # Test unsuccessful command (nonzero retcode)
            mock.return_value = 1
            assert not debian_service.reload_("foo")

    def test_force_reload(self):
        mock = MagicMock(return_value=0)
        with patch.dict(debian_service.__salt__, {"cmd.retcode": mock}):
            # Test successful command (0 retcode)
            assert debian_service.force_reload("foo")
            # Confirm expected command was run
            mock.assert_called_once_with("service foo force-reload")
            # Test unsuccessful command (nonzero retcode)
            mock.return_value = 1
            assert not debian_service.force_reload("foo")

    def test_status(self):
        mock = MagicMock(return_value="123")
        with patch.dict(debian_service.__salt__, {"status.pid": mock}):
            assert debian_service.status("foo", "foobar")

        mock = MagicMock(return_value=0)
        with patch.dict(debian_service.__salt__, {"cmd.retcode": mock}):
            # Test successful command (0 retcode)
            assert debian_service.status("foo")
            # Confirm expected command was run
            mock.assert_called_once_with("service foo status", ignore_retcode=True)
            # Test unsuccessful command (nonzero retcode)
            mock.return_value = 1
            assert not debian_service.enable("foo")

        mock = MagicMock(
            side_effect=lambda x, **y: 0 if x == "service bar status" else 1
        )
        get_all = MagicMock(return_value=["foo", "bar", "baz"])
        with patch.dict(debian_service.__salt__, {"cmd.retcode": mock}), patch.object(
            debian_service, "get_all", get_all
        ):
            ret = debian_service.status("b*")
            expected = {"bar": True, "baz": False}
            assert ret == expected, ret

    def test_enable(self):
        mock = MagicMock(return_value=0)
        with patch.dict(debian_service.__salt__, {"cmd.retcode": mock}):
            # Test successful command (0 retcode)
            assert debian_service.enable("foo")
            # Confirm expected command was run
            mock.assert_called_once_with(
                "insserv foo && update-rc.d foo enable", python_shell=True
            )
            # Test unsuccessful command (nonzero retcode)
            mock.return_value = 1
            assert not debian_service.enable("foo")

    def test_disable(self):
        mock = MagicMock(return_value=0)
        with patch.dict(debian_service.__salt__, {"cmd.retcode": mock}):
            # Test successful command (0 retcode)
            assert debian_service.disable("foo")
            # Confirm expected command was run
            mock.assert_called_once_with("update-rc.d foo disable")
            # Test unsuccessful command (nonzero retcode)
            mock.return_value = 1
            assert not debian_service.disable("foo")

    def test_enabled(self):
        mock = MagicMock(return_value=["foo"])
        with patch.object(debian_service, "get_enabled", mock):
            assert debian_service.enabled("foo")
            assert not debian_service.enabled("bar")

    def test_disabled(self):
        mock = MagicMock(return_value=["foo"])
        with patch.object(debian_service, "get_disabled", mock):
            assert debian_service.disabled("foo")
            assert not debian_service.disabled("bar")
