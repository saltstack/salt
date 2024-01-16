import pytest

import salt.returners.redis_return as redis_return
from tests.support.helpers import patch


@pytest.fixture
def configure_loader_modules():
    return {
        redis_return: {
            "__opts__": {
                "redis.host": "the mostest",
                "redis.port": 42,
                "redis.unix_socket_path": "the road less traveled",
                "redis.db": "13",
                "redis.password": "shibboleth",
                "redis.startup_nodes": {"lymph": "OK"},
                "redis.skip_full_coverage_check": True,
            }
        }
    }


@pytest.fixture(autouse=True)
def clean_REDIS_POOL():
    # Any unit test will want this value reset to None,
    # otherwise the values will remain set from other tests
    redis_return.REDIS_POOL = None  # pylint: disable=unmocked-patch


@pytest.fixture
def mock_strict_redis():
    with patch.object(redis_return, "redis", create=True):
        with patch(
            "salt.returners.redis_return.redis.StrictRedis"
        ) as fake_strict_redis:
            yield fake_strict_redis


@pytest.fixture
def proxy_platform():
    with patch("salt.utils.platform.is_proxy", autospec=True, return_value=True):
        yield


@pytest.fixture
def non_proxy_platform():
    with patch("salt.utils.platform.is_proxy", autospec=True, return_value=False):
        yield


@pytest.fixture
def mock_returner_options():
    options = {
        "host": "some other hosty mchostface",
        "port": 99,
        "unix_socket_path": "something socket",
        "db": "cooper",
        "password": "super secret!",
    }
    with patch(
        "salt.returners.get_returner_options", autospec=True, return_value=options
    ):
        yield options


def test_when_platform_is_proxy_redis_should_use_opts_values(
    proxy_platform, mock_strict_redis
):
    redis_return._get_serv()

    mock_strict_redis.assert_called_once_with(
        host="the mostest",
        port=42,
        unix_socket_path="the road less traveled",
        db="13",
        password="shibboleth",
        decode_responses=True,
    )


def test_when_platform_is_proxy_and_no_opts_are_set_fallback_values_should_be_used(
    proxy_platform, mock_strict_redis
):
    with patch.dict(redis_return.__opts__, {}, clear=True):
        redis_return._get_serv()

    mock_strict_redis.assert_called_once_with(
        host="salt",
        port=6379,
        unix_socket_path=None,
        db="0",
        password=None,
        decode_responses=True,
    )


def test_when_platform_is_not_proxy_it_should_use_returner_opts(
    non_proxy_platform, mock_strict_redis, mock_returner_options
):
    redis_return._get_serv()

    mock_strict_redis.assert_called_once_with(
        host="some other hosty mchostface",
        port=99,
        unix_socket_path="something socket",
        db="cooper",
        password="super secret!",
        decode_responses=True,
    )
