import logging
import pathlib
import shutil

import pytest
from saltfactories.daemons.container import Container
from saltfactories.utils.functional import Loaders

try:
    import docker
except ImportError:
    # Test suites depending on docker should be using
    #     docker = pytest.importorskip("docker")
    # so any fixtures using docker shouldn't ever be called or used.
    pass

log = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def minion_id():
    return "func-tests-minion"


@pytest.fixture(scope="module")
def state_tree(tmp_path_factory):
    state_tree_path = tmp_path_factory.mktemp("state-tree-base")
    try:
        yield state_tree_path
    finally:
        shutil.rmtree(str(state_tree_path), ignore_errors=True)


@pytest.fixture(scope="module")
def state_tree_prod(tmp_path_factory):
    state_tree_path = tmp_path_factory.mktemp("state-tree-prod")
    try:
        yield state_tree_path
    finally:
        shutil.rmtree(str(state_tree_path), ignore_errors=True)


@pytest.fixture(scope="module")
def minion_config_defaults():
    """
    Functional test modules can provide this fixture to tweak the default configuration dictionary
    passed to the minion factory
    """
    return {}


@pytest.fixture(scope="module")
def minion_config_overrides():
    """
    Functional test modules can provide this fixture to tweak the configuration overrides dictionary
    passed to the minion factory
    """
    return {}


@pytest.fixture(scope="module")
def minion_opts(
    salt_factories,
    minion_id,
    state_tree,
    state_tree_prod,
    minion_config_defaults,
    minion_config_overrides,
):
    minion_config_overrides.update(
        {
            "file_client": "local",
            "file_roots": {"base": [str(state_tree)], "prod": [str(state_tree_prod)]},
        }
    )
    factory = salt_factories.salt_minion_daemon(
        minion_id,
        defaults=minion_config_defaults or None,
        overrides=minion_config_overrides,
    )
    return factory.config.copy()


@pytest.fixture(scope="module")
def loaders(minion_opts):
    return Loaders(minion_opts)


@pytest.fixture(autouse=True)
def reset_loaders_state(loaders):
    # Delete the files cache after each test
    cachedir = pathlib.Path(loaders.opts["cachedir"])
    shutil.rmtree(str(cachedir), ignore_errors=True)
    cachedir.mkdir(parents=True, exist_ok=True)
    # The above can be deleted after pytest-salt-factories>=1.0.0rc7 has been merged
    try:
        # Run the tests
        yield
    finally:
        # Reset the loaders state
        loaders.reset_state()


@pytest.fixture(scope="module")
def docker_client():
    try:
        client = docker.from_env()
    except docker.errors.DockerException:
        pytest.skip("Failed to get a connection to docker running on the system")
    connectable = Container.client_connectable(client)
    if connectable is not True:  # pragma: nocover
        pytest.skip(connectable)
    return client


def pull_or_skip(image_name, docker_client):
    try:
        docker_client.images.pull(image_name)
    except docker.errors.APIError as exc:
        pytest.skip("Failed to pull docker image {!r}: {}".format(image_name, exc))
    except ImportError:
        pytest.skip("docker module was not installed")
    return image_name


@pytest.fixture(scope="module")
def docker_redis_image(docker_client):
    return pull_or_skip("redis:alpine", docker_client)


@pytest.fixture(scope="module")
def docker_consul_image(docker_client):
    return pull_or_skip("consul:latest", docker_client)


# Pytest does not have the ability to parametrize fixtures with parametriezed
# fixtures, which is super annoying. In other words, in order to have a `cache`
# test fixture that takes different versions of the cache that depend on
# different docker images, I've gotta make up fixtures for each
# image+container. When https://github.com/pytest-dev/pytest/issues/349 is
# actually fixed then we can go ahead and refactor all of these mysql images
# (and container fixtures depending on it) into a single fixture.


@pytest.fixture(scope="module")
def docker_mysql_5_6_image(docker_client):
    return pull_or_skip("mysql/mysql-server:5.6", docker_client)


@pytest.fixture(scope="module")
def docker_mysql_5_7_image(docker_client):
    return pull_or_skip("mysql/mysql-server:5.7", docker_client)


@pytest.fixture(scope="module")
def docker_mysql_8_0_image(docker_client):
    return pull_or_skip("mysql/mysql-server:8.0", docker_client)


@pytest.fixture(scope="module")
def docker_mariadb_10_1_image(docker_client):
    return pull_or_skip("mariadb:10.1", docker_client)


@pytest.fixture(scope="module")
def docker_mariadb_10_2_image(docker_client):
    return pull_or_skip("mariadb:10.2", docker_client)


@pytest.fixture(scope="module")
def docker_mariadb_10_3_image(docker_client):
    return pull_or_skip("mariadb:10.3", docker_client)


@pytest.fixture(scope="module")
def docker_mariadb_10_4_image(docker_client):
    return pull_or_skip("mariadb:10.4", docker_client)


@pytest.fixture(scope="module")
def docker_mariadb_10_5_image(docker_client):
    return pull_or_skip("mariadb:10.5", docker_client)


@pytest.fixture(scope="module")
def docker_percona_5_5_image(docker_client):
    return pull_or_skip("percona:5.5", docker_client)


@pytest.fixture(scope="module")
def docker_percona_5_6_image(docker_client):
    return pull_or_skip("percona:5.6", docker_client)


@pytest.fixture(scope="module")
def docker_percona_5_7_image(docker_client):
    return pull_or_skip("percona:5.7", docker_client)


@pytest.fixture(scope="module")
def docker_percona_8_0_image(docker_client):
    return pull_or_skip("percona:8.0", docker_client)
