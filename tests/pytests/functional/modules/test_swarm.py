import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
]

# The swarm module need the docker-py library installed
pytest.importorskip("docker")


@pytest.fixture
def swarm(modules):
    try:
        yield modules.swarm
    finally:
        modules.swarm.leave_swarm(force=True)


def test_swarm_init(swarm):
    """
    check that swarm.swarm_init works when a swarm exists
    """
    ret = swarm.swarm_init("127.0.0.1", "0.0.0.0", False)
    for key in ("Comment", "Tokens"):
        assert key in ret
    assert ret["Comment"].startswith("Docker swarm has been initialized on ")

    ret = swarm.swarm_init("127.0.0.1", "0.0.0.0", False)
    expected = {
        "Comment": (
            'This node is already part of a swarm. Use "docker swarm leave" to'
            " leave this swarm and join another one."
        ),
        "result": False,
    }
    assert ret == expected
