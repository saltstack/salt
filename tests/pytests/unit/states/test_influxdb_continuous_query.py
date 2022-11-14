import pytest

import salt.modules.influxdbmod as influx_mod
import salt.states.influxdb_continuous_query as influx
from tests.support.mock import create_autospec, patch


@pytest.fixture
def configure_loader_modules():
    return {influx: {"__salt__": {}, "__opts__": {"test": False}}}


@pytest.mark.parametrize(
    "expected_kwargs",
    (
        {},
        {"something": "extra"},
        {"something": "extra", "even": "more"},
        {"something": "extra", "still": "more and more and more", "and": "more"},
        {
            "something": "extra",
            "what": "in tarnation",
            "do": "you want",
            "to": "add here?",
        },
    ),
)
def test_when_present_is_called_it_should_pass_client_args_to_create_module(
    expected_kwargs,
):
    influx_module = create_autospec(influx_mod)
    influx_module.continuous_query_exists.return_value = False
    with patch.dict(
        influx.__salt__,
        {
            "influxdb.continuous_query_exists": influx_module.continuous_query_exists,
            "influxdb.create_continuous_query": influx_module.create_continuous_query,
        },
    ):
        influx.present(
            name="foo",
            database="fnord",
            query="fnord",
            resample_time="whatever",
            coverage_period="fnord",
            **expected_kwargs
        )

    actual_kwargs = influx_module.create_continuous_query.mock_calls[0].kwargs

    assert actual_kwargs == expected_kwargs
