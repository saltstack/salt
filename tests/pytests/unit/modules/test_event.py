import pytest
import salt.modules.event as event
from tests.support.mock import patch


@pytest.fixture(autouse=True)
def setup_loader():
    setup_loader_modules = {event: {}}
    with pytest.helpers.loader_mock(setup_loader_modules) as loader_mock:
        yield loader_mock


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


@pytest.fixture
def expected_call_data(
    event_environ_data,
    event_grain_data,
    event_pillar_data,
    event_env_opt_data,
    event_override_data,
):
    call_data = {"tag": "some/tag"}
    call_data.update(event_environ_data[0])
    call_data.update(event_grain_data[0])
    call_data.update(event_pillar_data[0])
    call_data.update(event_env_opt_data[0])
    call_data.update(event_override_data[0])
    call_data.setdefault("data", event_override_data[1])
    expected_data_dict = {}
    expected_data_dict.update(event_environ_data[1])
    expected_data_dict.update(event_grain_data[1])
    expected_data_dict.update(event_pillar_data[1])
    expected_data_dict.update(event_env_opt_data[1])
    expected_data_dict.update(event_override_data[0])
    expected_data_dict.update(event_override_data[1])
    return call_data, (expected_data_dict, "some/tag"), {"preload": None, "timeout": 60}


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
