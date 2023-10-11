"""
Tests the SaltfileMixIn.
"""

import optparse
import shutil

import pytest

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


@pytest.fixture
def parser():
    return MockSaltfileParser()


# @pytest.fixture
# def parser():
#     # Mock this because we don't need it and it causes an error
#     # if there is more than one test being run in this file
#     with patch.object(salt.utils.parsers.LogLevelMixIn, "_LogLevelMixIn__setup_logging_routines"):
#         yield salt.utils.parsers.SaltCallOptionParser()


@pytest.fixture
def saltfile(tmp_path):
    fp = tmp_path / "Saltfile"
    fp.touch()
    return fp


@pytest.fixture
def base_opts():
    # return ["--local", "test.ping"]
    return []


def test_saltfile_in_environment(parser, saltfile, base_opts):
    """
    Test setting the SALT_SALTFILE environment variable
    """
    with patched_environ(SALT_SALTFILE=str(saltfile)):
        parser.parse_args(base_opts)
        assert parser.options.saltfile == str(saltfile)


def test_saltfile_option(parser, saltfile, base_opts):
    """
    Test setting the SALT_SALTFILE environment variable
    """
    parser.parse_args(base_opts + ["--saltfile", str(saltfile)])
    assert parser.options.saltfile == str(saltfile)


def test_saltfile_cwd(parser, saltfile, base_opts, tmp_path):
    """
    Test setting the SALT_SALTFILE environment variable
    """
    with patch("os.getcwd", return_value=str(tmp_path)) as cwd_mock:
        parser.parse_args(base_opts)
        assert parser.options.saltfile == str(saltfile)
        cwd_mock.assert_called_once()


def test_saltfile_user_home(parser, saltfile, base_opts, tmp_path):
    """
    Test setting the SALT_SALTFILE environment variable
    """
    fake_dir = tmp_path / "fake_dir"
    fake_dir.mkdir()
    with patch("os.getcwd", return_value=str(fake_dir)) as cwd_mock:
        with patch("os.path.expanduser", return_value=str(tmp_path)) as eu_mock:
            salt_subdir = tmp_path / ".salt"
            salt_subdir.mkdir()
            dest = str(salt_subdir / "Saltfile")
            shutil.copy(str(saltfile), dest)
            parser.parse_args(base_opts)
            assert parser.options.saltfile == dest
            cwd_mock.assert_called_once()
            eu_mock.assert_called_with("~")
