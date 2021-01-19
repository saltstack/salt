# pylint: disable=confusing-with-statement
import pytest
import salt.modules.event as event
from tests.support.mock import patch


@pytest.fixture(autouse=True)
def setup_loader():
    setup_loader_modules = {event: {}}
    with pytest.helpers.loader_mock(setup_loader_modules) as loader_mock:
        yield loader_mock


@pytest.fixture
def fake_crypto():
    with patch("salt.crypt.SAuth", autospec=True) as fake_sauth:
        yield fake_sauth


@pytest.fixture
def fake_get_event():
    patch_get_event = patch("salt.utils.event.get_event", autospec=True)
    patch_opts = patch.dict(
        event.__opts__, {"sock_dir": "/tmp/sock", "transport": "tachyon"}
    )
    with patch_get_event as fake_event, patch_opts:
        yield fake_event


@pytest.fixture
def fake_fire():
    with patch("salt.modules.event.fire", create_autospec=True) as fake:
        yield fake


@pytest.fixture
def fake_fire_master():
    with patch("salt.modules.event.fire_master", create_autospec=True) as fake:
        yield fake


@pytest.fixture(
    params=[
        {"local": False, "file_client": "local", "master_type": "something"},
        {"local": False, "file_client": "remote", "master_type": "disable"},
        {"local": False, "file_client": "local", "master_type": "something"},
        {"local": True, "file_client": "local", "master_type": "disable"},
        {"local": True, "file_client": "remote", "master_type": "something"},
        {"local": True, "file_client": "remote", "master_type": "disable"},
    ]
)
def local_opts(request):
    with patch.dict(event.__opts__, request.param):
        yield


@pytest.fixture(
    params=[{"local": False, "file_client": "remote", "master_type": "something"}]
)
def non_local_opts(request):
    with patch.dict(event.__opts__, request.param):
        yield


def test_when_local_opts_then_use_master_when_local_fire_master_should_always_be_used(
    fake_fire, fake_fire_master, local_opts
):

    with patch.dict(event.__opts__, {"use_master_when_local": True}):
        event.send("some/tag")

    fake_fire.assert_not_called()
    fake_fire_master.assert_called()


@pytest.fixture(
    params=[
        ({"with_env": False}, {}, {}),
        (
            {"with_env": True},
            {"environ": {"foo": "bar", "bang": "quux"}},
            {"foo": "bar", "bang": "quux"},
        ),
        (
            {"with_env": ["foo"]},
            {"environ": {"foo": "bar"}},
            {"foo": "bar", "bang": "quux"},
        ),
    ]
)
def event_environ_data(request):
    call_data, expected_data, environ_data = request.param
    with patch("salt.modules.event.os.environ", environ_data):
        yield call_data, expected_data


@pytest.fixture(
    params=[
        ({"with_grains": False}, {}, {}),
        (
            {"with_grains": True},
            {"grains": {"corn": "maize", "wheat": "gluten"}},
            {"corn": "maize", "wheat": "gluten"},
        ),
        (
            {"with_grains": ["corn"]},
            {"grains": {"corn": "maize"}},
            {"corn": "maize", "wheat": "gluten"},
        ),
    ]
)
def event_grain_data(request):
    call_data, expected_data, grain_data = request.param
    with patch("salt.modules.event.__grains__", grain_data):
        yield call_data, expected_data


@pytest.fixture(
    params=[
        ({"with_pillar": False}, {}, {}),
        (
            {"with_pillar": True},
            {"pillar": {"salt": "NaCl", "dorian": "ionic"}},
            {"salt": "NaCl", "dorian": "ionic"},
        ),
        (
            {"with_pillar": ["salt"]},
            {"pillar": {"salt": "NaCl"}},
            {"salt": "NaCl", "dorian": "ionic"},
        ),
    ]
)
def event_pillar_data(request):
    call_data, expected_data, pillar_data = request.param
    with patch("salt.modules.event.__pillar__", pillar_data):
        yield call_data, expected_data


@pytest.fixture(
    params=[
        ({"with_env_opts": False}, {}, {}),
        ({"with_env_opts": True}, {"saltenv": "base", "pillarenv": None}, {}),
        (
            {"with_env_opts": True},
            {"saltenv": "awesome", "pillarenv": "kewl"},
            {"saltenv": "awesome", "pillarenv": "kewl"},
        ),
    ]
)
def event_env_opt_data(request):
    call_data, expected_data, opts = request.param
    with patch.dict("salt.modules.event.__opts__", opts):
        yield call_data, expected_data


@pytest.fixture(
    params=[
        ({"extra_kwargs": {}, "data": {}}),
        ({"extra_kwargs": {"saltenv": "frobnosticate"}, "data": {}}),
        (
            {
                "extra_kwargs": {"saltenv": "frobnosticate"},
                "data": {"saltenv": "cool dude", "pillarenv": "sweet action"},
            }
        ),
    ]
)
def event_override_data(request):
    yield request.param["extra_kwargs"], request.param["data"]


@pytest.fixture(params=[None, 10, 6000])
def event_timeout(request):
    yield request.param


@pytest.fixture
def expected_call_data(
    event_environ_data,
    event_grain_data,
    event_pillar_data,
    event_env_opt_data,
    event_override_data,
    event_timeout,
):
    call_data = {"tag": "some/tag"}
    call_data.update(event_environ_data[0])
    call_data.update(event_grain_data[0])
    call_data.update(event_pillar_data[0])
    call_data.update(event_env_opt_data[0])
    call_data.update(event_override_data[0])
    call_data.setdefault("data", event_override_data[1])
    call_data["timeout"] = event_timeout
    expected_data_dict = {}
    expected_data_dict.update(event_environ_data[1])
    expected_data_dict.update(event_grain_data[1])
    expected_data_dict.update(event_pillar_data[1])
    expected_data_dict.update(event_env_opt_data[1])
    expected_data_dict.update(event_override_data[0])
    expected_data_dict.update(event_override_data[1])
    return (
        call_data,
        (expected_data_dict, "some/tag"),
        {"preload": None, "timeout": event_timeout},
    )


@pytest.mark.parametrize("use_master_when_local", [True, False])
def test_when_non_local_opts_then_fire_master_should_always_be_used(
    fake_fire,
    fake_fire_master,
    non_local_opts,
    use_master_when_local,
    expected_call_data,
):
    event_data, expected_args, expected_kwargs = expected_call_data

    with patch.dict(event.__opts__, {"use_master_when_local": use_master_when_local}):
        # Plz no setting this env var during this test, pytest!
        del event.os.environ["PYTEST_CURRENT_TEST"]
        event.send(**event_data)

    fake_fire.assert_not_called()
    fake_fire_master.assert_called_with(*expected_args, **expected_kwargs)


def test_when_local_opts_and_not_use_master_then_fire_should_be_called(
    fake_fire, fake_fire_master, local_opts
):

    with patch.dict(event.__opts__, {"use_master_when_local": False}):
        event.send("some/tag")

    fake_fire.assert_called()
    fake_fire_master.assert_not_called()


def test_when_opts_has_no_role_then_default_to_minion_for_get_event(fake_get_event):
    expected_node = "minion"
    event.fire(data="Fnord", tag="fnord/fnord")

    actual_node = fake_get_event.mock_calls[0].args[0]

    assert actual_node == expected_node


def test_when_opts_has_a_role_it_should_be_used_for_get_event(fake_get_event):
    expected_node = "fnord"

    with patch.dict(event.__opts__, {"__role": expected_node}):
        event.fire(data="Fnord", tag="fnord/fnord")

    actual_node = fake_get_event.mock_calls[0].args[0]

    assert actual_node == expected_node


# Not 100% sure that 0 is a valid timeout. Also unsure if negative values are
# allowable.
@pytest.mark.parametrize(
    "timeout,expected_timeout", [(None, 60_000), (10, 10_000), (60, 60_000), (0, 0)],
)
def test_when_timeout_is_None_then_default_should_be_60000_millis(
    timeout, expected_timeout, fake_get_event
):
    event.fire(data="fnord", tag="fnord/fnord", timeout=timeout)

    actual_timeout = fake_get_event.return_value.fire_event.mock_calls[0].kwargs[
        "timeout"
    ]
    assert actual_timeout == expected_timeout


@pytest.mark.parametrize(
    "expected_timeout", [60, 0, None, 10, 1000],
)
def test_fire_master_should_use_the_provided_timeout(expected_timeout, fake_crypto):

    with patch(
        "salt.transport.client.ReqChannel.factory", autospec=True
    ) as fake_factory, patch.dict(
        event.__opts__,
        {
            "master_uri_list": ["fnord://fnord.fnord"],
            "interface": "127.0.0.1",
            "pki_dir": "/tmp",
            "id": "fnord",
            "keysize": 1024,
        },
    ):
        event.fire_master(
            data="fnord", tag="fnord/fnord", preload=True, timeout=expected_timeout
        )

        actual_timeout = fake_factory.return_value.__enter__.return_value.send.mock_calls[
            0
        ].kwargs[
            "timeout"
        ]

    assert actual_timeout == expected_timeout
