import pytest
import salt.states.rvm as rvm
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        rvm: {
            "__opts__": {"test": False},
            "__salt__": {
                "cmd.has_exec": MagicMock(return_value=True),
                "config.option": MagicMock(return_value=None),
            },
        }
    }


def test__check_rvm():
    mock = MagicMock(return_value=True)
    with patch.dict(
        rvm.__salt__,
        {"rvm.is_installed": MagicMock(return_value=False), "rvm.install": mock},
    ):
        rvm._check_rvm({"changes": {}})
        assert mock.call_count == 0


def test__check_and_install_ruby():
    mock_check_rvm = MagicMock(return_value={"changes": {}, "result": True})
    mock_check_ruby = MagicMock(return_value={"changes": {}, "result": False})
    mock_install_ruby = MagicMock(return_value="")
    with patch.object(rvm, "_check_rvm", new=mock_check_rvm):
        with patch.object(rvm, "_check_ruby", new=mock_check_ruby):
            with patch.dict(rvm.__salt__, {"rvm.install_ruby": mock_install_ruby}):
                rvm._check_and_install_ruby({"changes": {}}, "1.9.3")
    mock_install_ruby.assert_called_once_with("1.9.3", runas=None, opts=None, env=None)


def test__check_ruby():
    mock = MagicMock(
        return_value=[["ruby", "1.9.3-p125", False], ["jruby", "1.6.5.1", True]]
    )
    with patch.dict(rvm.__salt__, {"rvm.list": mock}):
        for ruby, result in {
            "1.9.3": True,
            "ruby-1.9.3": True,
            "ruby-1.9.3-p125": True,
            "1.9.3-p125": True,
            "1.9.3-p126": False,
            "rbx": False,
            "jruby": True,
            "jruby-1.6.5.1": True,
            "jruby-1.6": False,
            "jruby-1.9.3": False,
            "jruby-1.9.3-p125": False,
        }.items():
            ret = rvm._check_ruby({"changes": {}, "result": False}, ruby)
            assert result == ret["result"]


def test_gemset_present():
    with patch.object(rvm, "_check_rvm") as mock_method:
        mock_method.return_value = {"result": True, "changes": {}}
        gems = ["global", "foo", "bar"]
        gemset_list = MagicMock(return_value=gems)
        gemset_create = MagicMock(return_value=True)
        check_ruby = MagicMock(return_value={"result": False, "changes": {}})
        with patch.object(rvm, "_check_ruby", new=check_ruby):
            with patch.dict(
                rvm.__salt__,
                {"rvm.gemset_list": gemset_list, "rvm.gemset_create": gemset_create},
            ):
                ret = rvm.gemset_present("foo")
                assert True is ret["result"]

                ret = rvm.gemset_present("quux")
                assert True is ret["result"]
                gemset_create.assert_called_once_with("default", "quux", runas=None)


def test_installed():
    mock = MagicMock()
    with patch.object(rvm, "_check_rvm") as mock_method:
        mock_method.return_value = {"result": True}
        with patch.object(rvm, "_check_and_install_ruby", new=mock):
            rvm.installed("1.9.3", default=True)
    mock.assert_called_once_with(
        {"result": True}, "1.9.3", True, user=None, opts=None, env=None
    )


def test_installed_with_env():
    mock = MagicMock()
    with patch.object(rvm, "_check_rvm") as mock_method:
        mock_method.return_value = {"result": True}
        with patch.object(rvm, "_check_and_install_ruby", new=mock):
            rvm.installed(
                "1.9.3", default=True, env=[{"RUBY_CONFIGURE_OPTS": "--foobar"}]
            )
    mock.assert_called_once_with(
        {"result": True},
        "1.9.3",
        True,
        user=None,
        opts=None,
        env=[{"RUBY_CONFIGURE_OPTS": "--foobar"}],
    )


def test_installed_with_opts():
    mock = MagicMock()
    with patch.object(rvm, "_check_rvm") as mock_method:
        mock_method.return_value = {"result": True}
        with patch.object(rvm, "_check_and_install_ruby", new=mock):
            rvm.installed(
                "1.9.3",
                default=True,
                opts=[{"-C": "--enable-shared,--with-readline-dir=$HOME/.rvm/usr"}],
            )
    mock.assert_called_once_with(
        {"result": True},
        "1.9.3",
        True,
        user=None,
        opts=[{"-C": "--enable-shared,--with-readline-dir=$HOME/.rvm/usr"}],
        env=None,
    )
