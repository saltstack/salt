import pytest
import salt.output.highstate as highstate


@pytest.fixture
def configure_loader_modules():
    return {highstate: {"__opts__": {"strip_colors": True}}}


@pytest.mark.parametrize("data", [None, {"return": None}, {"return": {"data": None}}])
def test_when_data_result_is_None_output_should_be_string_None(data):
    expected_output = "None"

    actual_output = highstate.output(data=data)

    assert actual_output == expected_output


def test_when_data_is_dict_with_return_key_and_return_value_has_data_key_and_data_dict_has_one_dict_element_with_jid_and_fun_keys_and_return_value_is_None_then_output_should_return_literal_None_string():

    expected_output = "None"
    data = {
        "return": {
            "data": {
                "foo bar quux fnord": {
                    "jid": "fnordy fnordy fnordy",
                    "fun": "fnordy fnordy fnord",
                    "return": {"data": None},
                },
            }
        },
    }

    actual_output = highstate.output(data=data)

    assert actual_output == expected_output


@pytest.mark.parametrize(
    "return_value",
    [42, "fnord"],
)
def test_when_data_is_dict_with_return_key_and_return_value_has_data_key_and_data_dict_has_one_dict_element_with_jid_and_fun_keys_and_return_value_is_int_or_str_that_value_should_be_returned(
    return_value,
):

    expected_output = return_value
    data = {
        "return": {
            "data": {
                "foo bar quux fnord": {
                    "jid": "fnordy fnordy fnordy",
                    "fun": "fnordy fnordy fnord",
                    "return": {"data": return_value},
                },
            }
        },
    }

    actual_output = highstate.output(data=data)

    assert actual_output == expected_output


def test_when_orchestrator_output_retcode_in_data_the_retcode_should_be_removed():
    data = {"something_master": None, "retcode": 42}

    actual_output = highstate.output(data)

    assert "retcode" not in data


def test_when_more_than_one_local_master_retcode_should_not_be_removed():
    expected_retcode = 42
    data = {
        "something_master": None,
        "another_master": None,
        "retcode": expected_retcode,
    }

    actual_output = highstate.output(data)

    assert data["retcode"] == expected_retcode
