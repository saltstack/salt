import pytest
import salt.cli.batch as batch
import salt.client
import salt.defaults.exitcodes
from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.mock import MagicMock, create_autospec, patch


@pytest.fixture(autouse=True)
def setup_loader(request):
    setup_loader_modules = {batch: {}}
    with pytest.helpers.loader_mock(request, setup_loader_modules) as loader_mock:
        yield loader_mock


@pytest.fixture()
def fake_local_client():
    fake_client = create_autospec(salt.client.LocalClient)
    with patch("salt.client.get_local_client", autospec=True, return_value=fake_client):
        yield fake_client


@pytest.fixture()
def common_opts():
    return {
        "conf_file": "/tmp/fnord",
        "tgt": "fnord",
        "timeout": 13,
        "gather_job_timeout": 42,
    }


def test_when_batch_is_created_it_should_pass_the_correct_arguments_to_test_ping(
    fake_local_client, common_opts
):
    expected_target = "fnord"
    expected_fun = "test.ping"
    # expected_arg should be free to change. This was how it was when we got here.
    expected_arg = []
    expected_target_type = "glob"
    expected_gather_job_timeout = 42
    expected_timeout = 42
    expected_yield_pub_data = True
    common_opts.update(
        {
            "tgt": expected_target,
            "timeout": expected_timeout,
            "gather_job_timeout": expected_gather_job_timeout,
        }
    )

    test_batch = batch.Batch(opts=common_opts)

    fake_local_client.cmd_iter.assert_called_with(
        expected_target,
        expected_fun,
        expected_arg,
        expected_timeout,
        expected_target_type,
        gather_job_timeout=expected_gather_job_timeout,
        yield_pub_data=expected_yield_pub_data,
    )


def test_when_batch_is_created_and_selected_target_option_is_set_it_should_be_used(
    fake_local_client, common_opts
):
    expected_tgt_type = "quuxy"
    common_opts["selected_target_option"] = expected_tgt_type
    test_batch = batch.Batch(opts=common_opts)

    fake_local_client.cmd_iter.assert_called_with(
        "fnord",
        "test.ping",
        [],
        13,
        expected_tgt_type,
        gather_job_timeout=42,
        yield_pub_data=True,
    )


def test_when_batch_is_created_and_selected_target_option_and_tgt_type_is_not_set_it_should_fall_back_to_glob(
    fake_local_client, common_opts
):
    expected_tgt_type = "glob"
    test_batch = batch.Batch(opts=common_opts)

    fake_local_client.cmd_iter.assert_called_with(
        "fnord",
        "test.ping",
        [],
        13,
        expected_tgt_type,
        gather_job_timeout=42,
        yield_pub_data=True,
    )


def test_when_batch_is_created_and_selected_target_option_is_not_set_it_should_use_tgt_type(
    fake_local_client, common_opts
):
    expected_tgt_type = "this is a set target type"
    common_opts["tgt_type"] = expected_tgt_type
    test_batch = batch.Batch(opts=common_opts)

    fake_local_client.cmd_iter.assert_called_with(
        "fnord",
        "test.ping",
        [],
        13,
        expected_tgt_type,
        gather_job_timeout=42,
        yield_pub_data=True,
    )


def test_when_minion_id_is_literally_jid_then_minion_should_be_added_to_minions(
    fake_local_client, common_opts
):
    fake_local_client.cmd_iter.return_value = [{"jid": "that was the minion id"}]
    test_batch = batch.Batch(opts=common_opts)

    assert test_batch.minions == ["jid"]


def test_when_no_minions_are_returned_nothing_should_be_in_minions_or_down_minions(
    fake_local_client, common_opts
):
    fake_local_client.cmd_iter.return_value = []
    test_batch = batch.Batch(opts=common_opts)

    assert test_batch.minions == []
    assert test_batch.down_minions == set()


def test_when_minion_is_in_minions_return_and_has_returned_then_minion_should_only_be_in_minions(
    fake_local_client, common_opts
):
    expected_minion_id = "jid"  # ha ha, yes this is a malicious minion id
    fake_local_client.cmd_iter.return_value = [
        {"minions": {expected_minion_id: "fnord"}, "jid": 42},
        {expected_minion_id: "some other fnord"},
    ]
    test_batch = batch.Batch(opts=common_opts)

    assert test_batch.minions == [expected_minion_id]
    assert test_batch.down_minions == set()


def test_when_minion_is_in_minions_return_but_has_not_returned_then_minion_should_be_in_down_minions(
    fake_local_client, common_opts
):
    expected_minion_id = "jid"  # ha ha, yes this is a malicious minion id
    fake_local_client.cmd_iter.return_value = [
        {"minions": {expected_minion_id: "fnord"}, "jid": 42},
        {"some other minion id": "some other fnord"},
    ]
    test_batch = batch.Batch(opts=common_opts)

    assert test_batch.minions == ["some other minion id"]
    assert test_batch.down_minions == {expected_minion_id}


def test_if_minion_return_key_is_None_then_it_should_not_be_added_to_minions_list(
    fake_local_client, common_opts
):
    fake_local_client.cmd_iter.return_value = [{None: "some other fnord"}]
    test_batch = batch.Batch(opts=common_opts)

    assert test_batch.minions == []
