import tempfile

import pytest
import salt.utils.parsers as parsers
from tests.support.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def setup_loader(request):
    setup_loader_modules = {parsers: {}}
    with pytest.helpers.loader_mock(request, setup_loader_modules) as loader_mock:
        yield loader_mock


def test_when_process_config_dir_is_called_and_config_dir_exists_but_not_filename_it_should_write_a_warning_to_stderr(
    capsys,
):
    mixin = parsers.ConfigDirMixIn()
    mixin.options = MagicMock()
    mixin._default_config_dir_ = "/foo/bar/"
    bad_config_filename = "blarp"
    expected_message = "WARNING: CONFIG 'blarp' file does not exist. Falling back to default '/foo/bar/blarp'.\n"
    with tempfile.TemporaryDirectory() as tempdir:
        mixin.options.config_dir = tempdir

        with patch.object(
            mixin,
            "get_config_file_path",
            autospec=True,
            return_value=bad_config_filename,
        ):
            mixin.process_config_dir()
            captured = capsys.readouterr()

            assert captured.err == expected_message
