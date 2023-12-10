import pytest

import salt.modules.alternatives as alternatives
from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {alternatives: {}}


def test_display():
    with patch.dict(alternatives.__grains__, {"os_family": "RedHat"}):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "salt"})
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            solution = alternatives.display("better-world")
            assert "salt" == solution
            mock.assert_called_once_with(
                ["alternatives", "--display", "better-world"],
                python_shell=False,
                ignore_retcode=True,
            )

    with patch.dict(alternatives.__grains__, {"os_family": "Suse"}):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "undoubtedly-salt"})
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            solution = alternatives.display("better-world")
            assert "undoubtedly-salt" == solution
            mock.assert_called_once_with(
                ["update-alternatives", "--display", "better-world"],
                python_shell=False,
                ignore_retcode=True,
            )

    with patch.dict(alternatives.__grains__, {"os_family": "RedHat"}):
        mock = MagicMock(
            return_value={"retcode": 1, "stdout": "salt-out", "stderr": "salt-err"}
        )
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            solution = alternatives.display("better-world")
            assert "salt-err" == solution
            mock.assert_called_once_with(
                ["alternatives", "--display", "better-world"],
                python_shell=False,
                ignore_retcode=True,
            )


def test_show_current():
    mock = MagicMock(return_value="/etc/alternatives/salt")
    with patch("salt.utils.path.readlink", mock):
        ret = alternatives.show_current("better-world")
        assert "/etc/alternatives/salt" == ret
        mock.assert_called_once_with("/etc/alternatives/better-world")

        with TstSuiteLoggingHandler() as handler:
            mock.side_effect = OSError("Hell was not found!!!")
            assert not alternatives.show_current("hell")
            mock.assert_called_with("/etc/alternatives/hell")
            assert "ERROR:alternative: hell does not exist" in handler.messages


def test_check_installed():
    mock = MagicMock(return_value="/etc/alternatives/salt")
    with patch("salt.utils.path.readlink", mock):
        assert alternatives.check_installed("better-world", "/etc/alternatives/salt")
        mock.return_value = False
        assert not alternatives.check_installed("help", "/etc/alternatives/salt")


def test_install():
    with patch.dict(alternatives.__grains__, {"os_family": "RedHat"}):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "salt"})
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            solution = alternatives.install(
                "better-world", "/usr/bin/better-world", "/usr/bin/salt", 100
            )
            assert "salt" == solution
            mock.assert_called_once_with(
                [
                    "alternatives",
                    "--install",
                    "/usr/bin/better-world",
                    "better-world",
                    "/usr/bin/salt",
                    "100",
                ],
                python_shell=False,
            )

    with patch.dict(alternatives.__grains__, {"os_family": "Debian"}):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "salt"})
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            solution = alternatives.install(
                "better-world", "/usr/bin/better-world", "/usr/bin/salt", 100
            )
            assert "salt" == solution
            mock.assert_called_once_with(
                [
                    "update-alternatives",
                    "--install",
                    "/usr/bin/better-world",
                    "better-world",
                    "/usr/bin/salt",
                    "100",
                ],
                python_shell=False,
            )

    with patch.dict(alternatives.__grains__, {"os_family": "RedHat"}):
        mock = MagicMock(
            return_value={"retcode": 1, "stdout": "salt-out", "stderr": "salt-err"}
        )
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            ret = alternatives.install(
                "better-world", "/usr/bin/better-world", "/usr/bin/salt", 100
            )
            assert "salt-err" == ret
            mock.assert_called_once_with(
                [
                    "alternatives",
                    "--install",
                    "/usr/bin/better-world",
                    "better-world",
                    "/usr/bin/salt",
                    "100",
                ],
                python_shell=False,
            )


def test_remove():
    with patch.dict(alternatives.__grains__, {"os_family": "RedHat"}):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "salt"})
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            solution = alternatives.remove(
                "better-world",
                "/usr/bin/better-world",
            )
            assert "salt" == solution
            mock.assert_called_once_with(
                ["alternatives", "--remove", "better-world", "/usr/bin/better-world"],
                python_shell=False,
            )

    with patch.dict(alternatives.__grains__, {"os_family": "Debian"}):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "salt"})
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            solution = alternatives.remove(
                "better-world",
                "/usr/bin/better-world",
            )
            assert "salt" == solution
            mock.assert_called_once_with(
                [
                    "update-alternatives",
                    "--remove",
                    "better-world",
                    "/usr/bin/better-world",
                ],
                python_shell=False,
            )

    with patch.dict(alternatives.__grains__, {"os_family": "RedHat"}):
        mock = MagicMock(
            return_value={"retcode": 1, "stdout": "salt-out", "stderr": "salt-err"}
        )
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            solution = alternatives.remove(
                "better-world",
                "/usr/bin/better-world",
            )
            assert "salt-err" == solution
            mock.assert_called_once_with(
                ["alternatives", "--remove", "better-world", "/usr/bin/better-world"],
                python_shell=False,
            )


ALTERNATIVE_QUERY_EDITOR = """\
Name: editor
Link: /usr/bin/editor
Slaves:
 editor.1.gz /usr/share/man/man1/editor.1.gz
 editor.da.1.gz /usr/share/man/da/man1/editor.1.gz
 editor.de.1.gz /usr/share/man/de/man1/editor.1.gz
 editor.fr.1.gz /usr/share/man/fr/man1/editor.1.gz
 editor.it.1.gz /usr/share/man/it/man1/editor.1.gz
 editor.ja.1.gz /usr/share/man/ja/man1/editor.1.gz
 editor.pl.1.gz /usr/share/man/pl/man1/editor.1.gz
 editor.ru.1.gz /usr/share/man/ru/man1/editor.1.gz
Status: manual
Best: /bin/nano
Value: /usr/bin/vim.basic

Alternative: /bin/nano
Priority: 40
Slaves:
 editor.1.gz /usr/share/man/man1/nano.1.gz

Alternative: /usr/bin/mcedit
Priority: 25
Slaves:
 editor.1.gz /usr/share/man/man1/mcedit.1.gz

Alternative: /usr/bin/vim.basic
Priority: 30
Slaves:
 editor.1.gz /usr/share/man/man1/vim.1.gz
 editor.da.1.gz /usr/share/man/da/man1/vim.1.gz
 editor.de.1.gz /usr/share/man/de/man1/vim.1.gz
 editor.fr.1.gz /usr/share/man/fr/man1/vim.1.gz
 editor.it.1.gz /usr/share/man/it/man1/vim.1.gz
 editor.ja.1.gz /usr/share/man/ja/man1/vim.1.gz
 editor.pl.1.gz /usr/share/man/pl/man1/vim.1.gz
 editor.ru.1.gz /usr/share/man/ru/man1/vim.1.gz
"""


def test_show_link_debian():
    """Test alternatives.show_link on Debian 10."""
    run_all_mock = MagicMock(
        return_value={"retcode": 0, "stderr": "", "stdout": ALTERNATIVE_QUERY_EDITOR}
    )
    with patch.dict(alternatives.__grains__, {"os_family": "Debian"}), patch.dict(
        alternatives.__salt__, {"cmd.run_all": run_all_mock}
    ):
        assert alternatives.show_link("editor") == "/usr/bin/editor"


def test_show_link_redhat():
    """Test alternatives.show_link on CentOS 8."""
    ld_data = b"auto\n/usr/bin/ld\n\n/usr/bin/ld.bfd\n50\n/usr/bin/ld.gold\n30\n"
    with patch.dict(alternatives.__grains__, {"os_family": "RedHat"}), patch(
        "salt.utils.files.fopen",
        mock_open(read_data={"/var/lib/alternatives/ld": ld_data}),
    ):
        assert alternatives.show_link("ld") == "/usr/bin/ld"


def test_show_link_suse():
    """Test alternatives.show_link on openSUSE Leap 42.3."""
    ld_data = b"auto\n/usr/bin/ld\n\n/usr/bin/ld.bfd\n2\n\n"
    with patch.dict(alternatives.__grains__, {"os_family": "Suse"}), patch(
        "salt.utils.files.fopen",
        mock_open(read_data={"/var/lib/rpm/alternatives/ld": ld_data}),
    ):
        assert alternatives.show_link("ld") == "/usr/bin/ld"
