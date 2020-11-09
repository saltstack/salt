import pytest
import salt.modules.swarm as swarm
from requests.models import Response
from tests.support.mock import DEFAULT, MagicMock, patch

HAS_DOCKER = False
try:
    import docker

    HAS_DOCKER = True
except ImportError:
    HAS_DOCKER = False

pytestmark = pytest.mark.skipif(
    HAS_DOCKER is False, reason="The docker python sdk may not be installed"
)


@pytest.fixture(autouse=True)
def setup_loader():
    setup_loader_modules = {swarm: {"__context__": {}}}
    with pytest.helpers.loader_mock(setup_loader_modules) as loader_mock:
        yield loader_mock


@pytest.fixture
def fake_context_client():
    fake_swarm_client = MagicMock()
    patch_context = patch.dict(
        swarm.__context__, {"client": fake_swarm_client, "server_name": "test swarm"}
    )
    patch_swarm_token = patch(
        "salt.modules.swarm.swarm_tokens", autospec=True, return_value="mocked_token"
    )
    with patch_context, patch_swarm_token:
        yield fake_swarm_client


def test_when_swarm_init_is_called_with_the_same_information_twice_it_should_return_the_docker_error(
    fake_context_client,
):
    error_response = Response()
    error_response._content = b'{"message":"This node is already part of a swarm. Use \\"docker swarm leave\\" to leave this swarm and join another one."}\n'
    error_response.status_code = 503
    error_response.reason = "Service Unavailable"
    swarm_error_message = 'This node is already part of a swarm. Use "docker swarm leave" to leave this swarm and join another one.'
    fake_context_client.swarm.init.side_effect = [
        DEFAULT,
        docker.errors.APIError(
            swarm_error_message,
            response=error_response,
            explanation=swarm_error_message,
        ),
    ]

    expected_good_result = {
        "Comment": "Docker swarm has been initialized on test swarm and the worker/manager Join token is below",
        "Tokens": "mocked_token",
    }
    expected_bad_result = {"Comment": swarm_error_message, "result": False}

    first_result = swarm.swarm_init("127.0.0.1", "0.0.0.0", False)
    second_result = swarm.swarm_init("127.0.0.1", "0.0.0.0", False)

    assert first_result == expected_good_result
    assert second_result == expected_bad_result
