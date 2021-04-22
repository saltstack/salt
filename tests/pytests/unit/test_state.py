import os
import tempfile

import pytest
import salt.state
from tests.support.mock import patch


@pytest.fixture
def test_state():
    with tempfile.TemporaryDirectory() as tempdir:
        cachedir = os.path.join(tempdir, "cachedir")
        os.mkdir(cachedir)
        with patch("salt.state.State._gather_pillar", autospec=True), patch(
            "salt.state.State.load_modules", autospec=True
        ), patch("salt.state.State.functions", create=True, side_effect=[]), patch(
            "salt.state.State.check_requisite", autospec=True,
        ), patch(
            "salt.state.State.states", create=True, side_effect=[]
        ):
            state = salt.state.State(
                opts={
                    "cachedir": cachedir,
                    "extension_modules": "",
                    "id": "opts id",
                    "sock_dir": tempdir,
                    "transport": "detect",
                    "local": True,
                    "failhard": False,
                }
            )
            yield state


@pytest.fixture
def unmet_status():
    return ("unmet", None)


@pytest.fixture
def met_status():
    return ("met", None)


@pytest.fixture
def change_status(test_state):
    salt.state.State.check_requisite.return_value = ("change", None)
    return test_state


@pytest.fixture
def fake_duration():
    fake_start_time = "starty mcstartface"
    fake_duration = "durable mcdurationface"
    with patch(
        "salt.state._calculate_fake_duration",
        autospec=True,
        return_value=(fake_start_time, fake_duration),
    ):
        yield fake_start_time, fake_duration


@pytest.fixture
def default_result(fake_duration):
    fake_start_time, fake_duration = fake_duration
    expected_saltfunc = "blerp.some fun"
    expected_result = {
        "changes": {},
        "result": True,
        "duration": fake_duration,
        "start_time": fake_start_time,
        "comment": "CHANGEME",
        "__run_num__": 0,  # This is the current state default
        "__sls__": "fnord",  # matches low_data
        "__saltfunc__": expected_saltfunc,
    }
    return expected_result


@pytest.fixture
def pre_status(test_state, fake_duration, default_result):
    salt.state.State.check_requisite.return_value = ("pre", None)
    tag = "blerp_|-fnord id_|-some name_|-some fun"
    return {"tag": tag, "state": test_state, "result": default_result}


@pytest.fixture
def onfail_status(test_state, fake_duration, default_result):
    salt.state.State.check_requisite.return_value = ("onfail", None)
    tag = "blerp_|-fnord id_|-some name_|-some fun"
    return {"tag": tag, "state": test_state, "result": default_result}


@pytest.fixture
def fail_status(test_state, default_result):  # not to be confused with onfail
    salt.state.State.check_requisite.return_value = ("fail", {})
    tag = "blerp_|-fnord id_|-some name_|-some fun"
    return {"tag": tag, "state": test_state, "result": default_result}


@pytest.fixture
def onchanges_status(test_state, fake_duration, default_result):
    salt.state.State.check_requisite.return_value = ("onchanges", None)
    tag = "blerp_|-fnord id_|-some name_|-some fun"
    return {"tag": tag, "state": test_state, "result": default_result}


# These are not currently statuses that we know what to do with so they
# should trigger a fallback
@pytest.fixture(params=["unknown", "whatever", "blerp", "hahahah", "fnord"])
def unknown_status(test_state, fake_duration, request):
    salt.state.State.check_requisite.return_value = (request.param, None)
    tag = "blerp_|-fnord id_|-some name_|-some fun"
    return {"tag": tag, "state": test_state, "result": {}}


@pytest.fixture(
    params=[
        "require",
        "watch",
        "prereq",
        "onfail",
        "onchanges",
        "require_any",
        "watch_any",
        "onfail_any",
        "onchanges_any",
        "prerequired",
    ],
)
def key_value(request):
    yield request.param


@pytest.fixture
def low_data():
    return {
        "state": "blerp",
        "__id__": "fnord id",
        "name": "some name",
        "fun": "some fun",
        "__sls__": "fnord",
    }


@pytest.fixture
def chunks():
    return [
        {
            "__sls__": "fizzy bubbly",
            "state": "another nonsense state",
            "__id__": "a fake id",
            "name": "totally not a real name",
            "fun": "or a real function",
            "__prerequired__": "not sure this matters",
        }
    ]


def test_call_chunk_should_not_add_saltfunc_when_status_is_unmet_and_any_lost(
    test_state, unmet_status, key_value, low_data
):

    lost_key = key_value
    salt.state.State.check_requisite.return_value = unmet_status
    low_data[lost_key] = ["blerp"]
    result = test_state.call_chunk(low=low_data, running={}, chunks=[])
    missing = object()

    assert all([result[tag].get("__saltfunc__", missing) is missing for tag in result])


def test_if_status_is_unmet_and_req_in_low_data_and_sls_matches_reqval_and_req_chunk_not_running_then_saltfunc_should_not_be_added(
    test_state, unmet_status, key_value, low_data, chunks
):
    # if found_key != "watch": return
    found_key = key_value
    low_data[found_key] = [{"sls": "fizzy bubbly"}]
    salt.state.State.check_requisite.return_value = unmet_status
    test_state.active = {
        "another nonsense state_|-a fake id_|-totally not a real name_|-or a real function"
    }

    result = test_state.call_chunk(low=low_data, running={}, chunks=chunks)

    missing = object()

    assert all([result[tag].get("__saltfunc__", missing) is missing for tag in result])


def test_if_status_is_unmet_and_req_in_low_data_and_sls_matches_reqval_and_req_chunk_not_running_but_in_state_pre_then_saltfunc_should_not_be_added(
    test_state, unmet_status, key_value, low_data, chunks
):
    found_key = key_value
    salt.state.State.check_requisite.return_value = unmet_status
    low_data[found_key] = [{"sls": "fizzy bubbly"}]
    test_state.active = {
        "another nonsense state_|-a fake id_|-totally not a real name_|-or a real function"
    }
    test_state.pre = {"blerp_|-fnord id_|-some name_|-some fun": None}

    result = test_state.call_chunk(low=low_data, running={}, chunks=chunks)

    missing = object()

    assert all([result[tag].get("__saltfunc__", missing) is missing for tag in result])


def test_if_status_is_unmet_and_req_in_low_data_and_sls_matches_reqval_and_req_chunk_is_running_then_saltfunc_should_not_be_added(
    test_state, unmet_status, key_value, low_data, chunks
):
    found_key = key_value
    salt.state.State.check_requisite.return_value = unmet_status
    del chunks[0]["__prerequired__"]
    low_data[found_key] = [{"sls": "fizzy bubbly"}]
    test_state.active = {
        "another nonsense state_|-a fake id_|-totally not a real name_|-or a real function"
    }
    test_state.pre = {"blerp_|-fnord id_|-some name_|-some fun": None}

    result = test_state.call_chunk(low=low_data, running={}, chunks=chunks)

    missing = object()
    assert all([result[tag].get("__saltfunc__", missing) is missing for tag in result])


def test_if_status_is_unmet_and_prereq_in_low_then_low_should_not_be_in_running(
    test_state, unmet_status, low_data, chunks
):
    salt.state.State.check_requisite.side_effect = [
        unmet_status,
        ("met", None),
        ("met", None),
    ]
    # probably need to actually run this for each requisite? Not just onfail
    low_data["require"] = [chunks[0]["__id__"]]
    low_data["__prereq__"] = "fnord"
    del chunks[0]["__prerequired__"]
    unexpected_tag = "blerp_|-fnord id_|-some name_|-some fun"

    result = test_state.call_chunk(low=low_data, running={}, chunks=chunks)

    assert unexpected_tag not in result


def test_if_status_is_unmet_with_no_prereq_in_low_and_met_after_low_call_chunked_again_then_saltfunc_should_be_in_running(
    test_state, unmet_status, low_data, chunks
):
    salt.state.State.check_requisite.side_effect = [
        unmet_status,
        ("met", None),
        ("met", None),
    ]
    # probably need to actually run this for each requisite? Not just onfail
    low_data["require"] = [chunks[0]["__id__"]]
    assert "__prereq__" not in low_data
    expected_tag = "blerp_|-fnord id_|-some name_|-some fun"
    expected_saltfunc = "blerp.some fun"

    result = test_state.call_chunk(low=low_data, running={}, chunks=chunks)

    assert result[expected_tag]["__saltfunc__"] == expected_saltfunc


def test_if_status_is_met_and_no_prereq_then_saltfunc_should_be_statefun(
    test_state, met_status, low_data, chunks
):
    expected_tag = salt.state._gen_tag(low_data)
    expected_saltfunc = "blerp.some fun"  # from the low_data
    salt.state.State.check_requisite.return_value = met_status

    result = test_state.call_chunk(low=low_data, running={}, chunks=chunks)

    assert result[expected_tag]["__saltfunc__"] == expected_saltfunc


def test_if_status_is_met_and_prereq_then_tag_should_be_in_state_pre_and_not_be_in_running(
    test_state, met_status, low_data, chunks
):
    expected_tag = salt.state._gen_tag(low_data)
    salt.state.State.check_requisite.return_value = met_status
    low_data["__prereq__"] = "some kind of something"

    result = test_state.call_chunk(low=low_data, running={}, chunks=chunks)

    missing = object()
    assert result.get(expected_tag, missing) is missing
    assert expected_tag in test_state.pre


def test_if_status_is_change_and_prereq_in_lowdata_then_tag_should_be_in_pre(
    change_status, low_data, chunks
):
    test_state = change_status
    expected_tag = salt.state._gen_tag(low_data)
    low_data["__prereq__"] = "fnord"  # literally anything

    result = test_state.call_chunk(low=low_data, running={}, chunks=chunks)

    missing = object()
    assert result.get(expected_tag, missing) is missing
    assert expected_tag in test_state.pre


@pytest.mark.parametrize(
    "call_ret",
    [
        {"changes": True},
        {"changes": True, "skip_watch": False},
        {"changes": True, "skip_watch": True},
        {"changes": False, "skip_watch": True},
    ],
)
def test_if_status_is_change_and_prereq_not_in_lowdata_and_call_changes_or_skip_watch_then_saltfunc_should_be_statefun(
    change_status, low_data, chunks, call_ret
):
    test_state = change_status
    expected_tag = salt.state._gen_tag(low_data)
    expected_saltfunc = "blerp.some fun"  # from the low_data
    assert "__prereq__" not in low_data

    with patch.object(test_state, "call", autospec=True, return_value=call_ret):
        result = test_state.call_chunk(low=low_data, running={}, chunks=chunks)

    assert result[expected_tag]["__saltfunc__"] == expected_saltfunc


@pytest.mark.parametrize(
    "call_ret", [{"changes": False}, {"changes": False, "skip_watch": False}],
)
def test_if_status_is_change_and_prereq_not_in_lowdata_and_no_call_changes_nor_skip_watch_then_saltfunc_should_be_state_modwatch(
    change_status, low_data, chunks, call_ret
):
    test_state = change_status
    expected_tag = salt.state._gen_tag(low_data)
    expected_saltfunc = "blerp.mod_watch"  # from the low_data
    assert "__prereq__" not in low_data

    with patch.object(test_state, "call", autospec=True, return_value=call_ret):
        result = test_state.call_chunk(low=low_data, running={}, chunks=chunks)

    assert result[expected_tag]["__saltfunc__"] == expected_saltfunc


def test_if_status_is_pre_then_saltfunc_should_be_in_both_pre_and_running(
    pre_status, low_data, chunks
):
    test_state = pre_status["state"]
    expected_tag = pre_status["tag"]
    expected_result = pre_status["result"]
    expected_result.update({"comment": "No changes detected"})

    result = test_state.call_chunk(low=low_data, running={}, chunks=chunks)

    assert result[expected_tag] == expected_result
    assert test_state.pre[expected_tag] == expected_result


def test_if_status_is_onfail_then_saltfunc_should_only_be_in_running(
    onfail_status, low_data, chunks
):
    test_state = onfail_status["state"]
    expected_tag = onfail_status["tag"]
    expected_result = onfail_status["result"]
    expected_result.update(
        {
            "comment": "State was not run because onfail req did not change",
            "__state_ran__": False,
        }
    )

    result = test_state.call_chunk(low=low_data, running={}, chunks=chunks)

    assert result[expected_tag] == expected_result
    assert expected_tag not in test_state.pre


def test_if_status_is_onchanges_then_saltfunc_should_only_be_in_running(
    onchanges_status, low_data, chunks
):
    test_state = onchanges_status["state"]
    expected_tag = onchanges_status["tag"]
    expected_result = onchanges_status["result"]
    expected_result.update(
        {
            "comment": "State was not run because none of the onchanges reqs changed",
            "__state_ran__": False,
        }
    )

    result = test_state.call_chunk(low=low_data, running={}, chunks=chunks)

    assert result[expected_tag] == expected_result
    assert expected_tag not in test_state.pre


def test_when_status_is_not_any_of_the_expected_and_prereq_then_tag_should_be_in_pre_without_saltfunc_and_tag_should_not_be_in_running(
    unknown_status, low_data, chunks
):
    test_state = unknown_status["state"]
    expected_tag = unknown_status["tag"]
    expected_saltfunc = "blerp.some fun"  # comes from low_data
    low_data["__prereq__"] = "fnord"

    result = test_state.call_chunk(low=low_data, running={}, chunks=chunks)

    assert expected_tag not in result
    assert "__saltfunc__" not in test_state.pre[expected_tag]


def test_when_status_is_not_any_of_the_expected_and_not_prereq_then_saltfunc_should_be_in_running_not_in_pre(
    unknown_status, low_data, chunks
):
    test_state = unknown_status["state"]
    expected_tag = unknown_status["tag"]
    expected_saltfunc = "blerp.some fun"  # comes from low_data
    assert "__prereq__" not in low_data
    call_ret = {}

    with patch.object(test_state, "call", autospec=True, return_value=call_ret):
        result = test_state.call_chunk(low=low_data, running={}, chunks=chunks)

    assert result[expected_tag]["__saltfunc__"] == expected_saltfunc
    assert expected_tag not in test_state.pre


def test_when_status_is_fail_then_result_should_be_in_both_running_and_pre_and_have_saltfunc(
    fail_status, low_data, chunks
):
    test_state = fail_status["state"]
    expected_tag = fail_status["tag"]
    expected_saltfunc = "blerp.some fun"  # generated from low data

    result = test_state.call_chunk(low=low_data, running={}, chunks=chunks)

    assert result[expected_tag]["__saltfunc__"] == expected_saltfunc
    assert result == test_state.pre
