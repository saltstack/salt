"""
    Test cases for salt.modules.rvm
"""

import pytest

import salt.modules.rvm as rvm
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def configure_loader_modules():
    return {
        rvm: {
            "__salt__": {
                "cmd.has_exec": MagicMock(return_value=True),
                "config.option": MagicMock(return_value=None),
            }
        }
    }


def test_rvm():
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(rvm.__salt__, {"cmd.run_all": mock}):
        rvm._rvm(["install", "1.9.3"])
        mock.assert_called_once_with(
            ["/usr/local/rvm/bin/rvm", "install", "1.9.3"],
            runas=None,
            cwd=None,
            python_shell=False,
            env=None,
        )


def test_rvm_do():
    mock = MagicMock(return_value={"retcode": 0, "stdout": "stdout"})
    with patch.dict(rvm.__salt__, {"cmd.run_all": mock}):
        rvm._rvm_do("1.9.3", ["gemset", "list"])
        mock.assert_called_once_with(
            ["/usr/local/rvm/bin/rvm", "1.9.3", "do", "gemset", "list"],
            runas=None,
            cwd=None,
            python_shell=False,
            env=None,
        )


def test_install():
    mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(rvm.__salt__, {"cmd.run_all": mock}):
        rvm.install()
        curl_cmd = (
            "curl -Ls"
            " https://raw.githubusercontent.com/rvm/rvm/master/binscripts/rvm-installer"
            " | bash -s stable"
        )
        mock.assert_called_once_with(curl_cmd, runas=None, python_shell=True)


def test_install_ruby_nonroot():
    mock = MagicMock(return_value={"retcode": 0, "stdout": "stdout"})
    expected = [
        call(
            ["/usr/local/rvm/bin/rvm", "autolibs", "disable", "2.0.0"],
            runas="rvm",
            cwd=None,
            python_shell=False,
            env=None,
        ),
        call(
            ["/usr/local/rvm/bin/rvm", "install", "2.0.0", "--disable-binary"],
            runas="rvm",
            cwd=None,
            python_shell=False,
            env=None,
        ),
    ]
    with patch.dict(rvm.__salt__, {"cmd.run_all": mock}):
        rvm.install_ruby("2.0.0", runas="rvm")
        assert mock.call_args_list == expected


def test_install_with_env():
    mock = MagicMock(return_value={"retcode": 0, "stdout": "stdout"})
    expected = [
        call(
            ["/usr/local/rvm/bin/rvm", "install", "2.0.0"],
            runas=None,
            cwd=None,
            python_shell=False,
            env=[{"RUBY_CONFIGURE_OPTS": "--foobar"}],
        )
    ]
    with patch.dict(rvm.__salt__, {"cmd.run_all": mock}):
        rvm.install_ruby("2.0.0", env=[{"RUBY_CONFIGURE_OPTS": "--foobar"}])
        assert mock.call_args_list == expected


def test_install_with_opts():
    mock = MagicMock(return_value={"retcode": 0, "stdout": "stdout"})
    expected = [
        call(
            [
                "/usr/local/rvm/bin/rvm",
                "install",
                "2.0.0",
                "-C --enable-shared,--with-readline-dir=$HOME/.rvm/usr",
                "--patch /path/to/awesome.patch",
            ],
            runas=None,
            cwd=None,
            python_shell=False,
            env=None,
        )
    ]
    with patch.dict(rvm.__salt__, {"cmd.run_all": mock}):
        rvm.install_ruby(
            "2.0.0",
            opts=[
                "-C --enable-shared,--with-readline-dir=$HOME/.rvm/usr",
                "--patch /path/to/awesome.patch",
            ],
        )
        assert mock.call_args_list == expected


def test_list():
    list_output = """
rvm rubies

   jruby-1.6.5.1 [ amd64 ]
   ree-1.8.7-2011.03 [ x86_64 ]
   ree-1.8.7-2011.12 [ x86_64 ]
=* ree-1.8.7-2012.02 [ x86_64 ]
   ruby-1.9.2-p180 [ x86_64 ]
   ruby-1.9.3-p125 [ x86_64 ]
   ruby-head [ x86_64 ]

# => - current
# =* - current && default
#  * - default

"""
    with patch.object(rvm, "_rvm") as mock_method:
        mock_method.return_value = list_output
        assert [
            ["jruby", "1.6.5.1", False],
            ["ree", "1.8.7-2011.03", False],
            ["ree", "1.8.7-2011.12", False],
            ["ree", "1.8.7-2012.02", True],
            ["ruby", "1.9.2-p180", False],
            ["ruby", "1.9.3-p125", False],
            ["ruby", "head", False],
        ] == rvm.list_()


def test_gemset_list():
    output = """
gemsets for ree-1.8.7-2012.02 (found in /usr/local/rvm/gems/ree-1.8.7-2012.02)
   global
   bar
   foo

"""
    with patch.object(rvm, "_rvm_do") as mock_method:
        mock_method.return_value = output
        assert ["global", "bar", "foo"] == rvm.gemset_list()


def test_gemset_list_all():
    output = """

gemsets for ruby-1.9.3-p125 (found in /usr/local/rvm/gems/ruby-1.9.3-p125)
   9bar
   9foo
   global


gemsets for ruby-head (found in /usr/local/rvm/gems/ruby-head)
   global
   headbar
   headfoo


gemsets for jruby-1.6.5.1 (found in /usr/local/rvm/gems/jruby-1.6.5.1)
   global
   jbar
   jfoo


gemsets for ruby-1.9.2-p180 (found in /usr/local/rvm/gems/ruby-1.9.2-p180)
   global


"""
    with patch.object(rvm, "_rvm_do") as mock_method:
        mock_method.return_value = output
        assert {
            "jruby-1.6.5.1": ["global", "jbar", "jfoo"],
            "ruby-1.9.2-p180": ["global"],
            "ruby-1.9.3-p125": ["9bar", "9foo", "global"],
            "ruby-head": ["global", "headbar", "headfoo"],
        } == rvm.gemset_list_all()
