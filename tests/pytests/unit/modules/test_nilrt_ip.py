import io

import pytest

import salt.modules.nilrt_ip as nilrt_ip
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {nilrt_ip: {}}


@pytest.fixture
def patched_config_file():
    config_file = io.StringIO(
        """
    [some_section]
    name = thing
    fnord = bar
    icanhazquotes = "this string is quoted"
    icannothazquotes = this string is unquoted
    number_value = 42
    """
    )
    with patch("salt.utils.files.fopen", return_value=config_file):
        yield


def test_when_config_has_quotes_around_string_they_should_be_removed(
    patched_config_file,
):
    expected_value = "this string is quoted"
    option = "icanhazquotes"

    actual_value = nilrt_ip._load_config("some_section", [option])[option]

    assert actual_value == expected_value


def test_when_config_has_no_quotes_around_string_it_should_be_returned_as_is(
    patched_config_file,
):
    expected_value = "this string is unquoted"
    option = "icannothazquotes"

    actual_value = nilrt_ip._load_config("some_section", [option])[option]

    assert actual_value == expected_value


@pytest.mark.parametrize(
    "default_value",
    [
        42,
        -99.9,
        ('"', "some value", 42, '"'),
        ['"', "a weird list of values", '"'],
        {"this": "dictionary", "has": "multiple values", 0: '"', -1: '"'},
    ],
)
def test_when_default_value_is_not_a_string_and_option_is_missing_the_default_value_should_be_returned(
    patched_config_file, default_value
):
    option = "non existent option"

    actual_value = nilrt_ip._load_config(
        "some_section", options=[option], default_value=default_value
    )[option]

    assert actual_value == default_value
