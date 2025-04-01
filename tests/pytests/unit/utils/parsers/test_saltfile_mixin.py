"""
Tests the SaltfileMixIn.
"""

import optparse  # pylint: disable=deprecated-module
import shutil

import pytest

import salt.exceptions
import salt.utils.parsers
from tests.support.helpers import patched_environ
from tests.support.mock import patch


class MockSaltfileParser(
    salt.utils.parsers.OptionParser,
    salt.utils.parsers.SaltfileMixIn,
    metaclass=salt.utils.parsers.OptionParserMeta,
):
    def __init__(self, *args, **kwargs):
        salt.utils.parsers.OptionParser.__init__(self, *args, **kwargs)
        self.config = {}

    def _mixin_setup(self):
        self.add_option(
            "-l",
            "--log-level",
            dest="log_level",
            default="warning",
            help="The log level for salt.",
        )
        group = self.output_options_group = optparse.OptionGroup(
            self, "Output Options", "Configure your preferred output format."
        )
        self.add_option_group(group)

        group.add_option(
            "--out",
            "--output",
            dest="output",
            help=(
                "Print the output from the '{}' command using the "
                "specified outputter.".format(
                    self.get_prog_name(),
                )
            ),
        )
        group.add_option(
            "--out-file",
            "--output-file",
            dest="output_file",
            default=None,
            help="Write the output to the specified file.",
        )
        group.add_option(
            "--version-arg",
            action="version",
            help="Option to test no dest",
        )


@pytest.fixture
def parser():
    return MockSaltfileParser()


@pytest.fixture
def saltfile(tmp_path):
    fp = tmp_path / "Saltfile"
    fp.touch()
    return fp


def test_saltfile_in_environment(parser, saltfile):
    """
    Test setting the SALT_SALTFILE environment variable
    """
    with patched_environ(SALT_SALTFILE=str(saltfile)):
        parser.parse_args([])
        assert parser.options.saltfile == str(saltfile)


def test_saltfile_option(parser, saltfile):
    """
    Test setting the saltfile via the CLI
    """
    parser.parse_args(["--saltfile", str(saltfile)])
    assert parser.options.saltfile == str(saltfile)


def test_bad_saltfile_option(parser, saltfile, tmp_path):
    """
    Test setting a bad saltfile via the CLI
    """
    with pytest.raises(SystemExit):
        parser.parse_args(["--saltfile", str(tmp_path / "fake_dir")])


def test_saltfile_cwd(parser, saltfile, tmp_path):
    """
    Test using a saltfile in the cwd
    """
    with patch("os.getcwd", return_value=str(tmp_path)) as cwd_mock:
        parser.parse_args([])
        assert parser.options.saltfile == str(saltfile)
        cwd_mock.assert_called_once()


def test_saltfile_cwd_doesnt_exist(parser, saltfile, tmp_path):
    """
    Test using a saltfile in the cwd that doesn't exist
    """
    with patch("os.getcwd", return_value=str(tmp_path / "fake_dir")) as cwd_mock:
        parser.parse_args([])
        assert parser.options.saltfile is None


def test_saltfile_user_home(parser, saltfile, tmp_path):
    """
    Test using a saltfile in ~/.salt/
    """
    fake_dir = tmp_path / "fake_dir"
    fake_dir.mkdir()
    with patch("os.getcwd", return_value=str(fake_dir)) as cwd_mock:
        with patch("os.path.expanduser", return_value=str(tmp_path)) as eu_mock:
            salt_subdir = tmp_path / ".salt"
            salt_subdir.mkdir()
            dest = str(salt_subdir / "Saltfile")
            shutil.copy(str(saltfile), dest)
            parser.parse_args([])
            assert parser.options.saltfile == dest
            cwd_mock.assert_called_once()
            eu_mock.assert_called_with("~")


def test_bad_saltfile(parser, saltfile):
    """
    Test a saltfile with bad configuration
    """
    contents = """
    bad "yaml":
  - this is: bad yaml
  -       bad yaml=data:
    - {"bad": yaml, "data": "yaml"}
    """
    saltfile.write_text(contents)
    # It raises two errors, let's catch them both
    with pytest.raises(SystemExit):
        with pytest.raises(salt.exceptions.SaltConfigurationError):
            parser.parse_args(["--saltfile", str(saltfile)])


def test_saltfile_without_prog_name(parser, saltfile):
    """
    Test a saltfile with valid yaml but without the program name in it
    """
    contents = "good: yaml"
    saltfile.write_text(contents)
    # This should just run cleanly
    parser.parse_args(["--saltfile", str(saltfile)])


def test_saltfile(parser, saltfile):
    """
    Test a valid saltfile
    """
    contents = """
    __main__.py:
      log_level: debug
      output: json
    """
    saltfile.write_text(contents)
    parser.parse_args(["--saltfile", str(saltfile)])
    print(parser.option_list)
    assert parser.options.log_level == "debug"
    assert parser.options.output == "json"


def test_saltfile_unusual_option(parser, saltfile):
    """
    Test a valid saltfile
    """
    contents = """
    __main__.py:
      go: birds
    """
    saltfile.write_text(contents)
    parser.parse_args(["--saltfile", str(saltfile)])
    assert parser.options.go == "birds"


def test_saltfile_cli_override(parser, saltfile):
    """
    Test a valid saltfile
    """
    contents = """
    __main__.py:
      log_level: debug
      output: json
      output_file: /fake/file
    """
    saltfile.write_text(contents)
    parser.parse_args(
        [
            "--saltfile",
            str(saltfile),
            "--log-level",
            "info",
            "--out-file",
            "/still/fake/file",
        ]
    )
    assert parser.options.log_level == "info"
    assert parser.options.output == "json"
    assert parser.options.output_file == "/still/fake/file"
