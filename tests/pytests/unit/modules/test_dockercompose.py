"""
Unit tests for salt.modules.dockercompose

Tests cover the file-management functions that do not require a running
Docker daemon, verifying the YAML read/write/parse logic and the service
definition helpers.  The python_on_whales / legacy-compose import paths are
controlled via patched module-level booleans so the tests run without either
library installed.

The ``__load_project_from_file_path`` private helper is mocked throughout
because it is the only code path that actually needs a Docker daemon or the
python_on_whales library.
"""

import os
import textwrap

import pytest

import salt.modules.dockercompose as dockercompose
from tests.support.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

SIMPLE_COMPOSE = textwrap.dedent(
    """\
    version: '3'
    services:
      web:
        image: nginx:latest
      db:
        image: postgres:14
    """
)

# Sentinel object returned by mocked __load_project_from_file_path.
# Any non-dict value satisfies the ``isinstance(project, dict)`` guard
# used throughout the module.
FAKE_PROJECT = MagicMock(name="fake_docker_project")

# Full dotted path to the private helper that touches the Docker daemon.
_LOAD_PROJECT_PATH = (
    "salt.modules.dockercompose._DockerCompose__load_project_from_file_path"
)
# The helper is a module-level function accessed via the dunder-mangled name
# inside the module; we need the actual attribute name as seen from outside.
_LOAD_PROJECT_ATTR = "salt.modules.dockercompose.__load_project_from_file_path"


def _patch_project(return_value=FAKE_PROJECT):
    """Return a context-manager that replaces __load_project_from_file_path."""
    # The function is a plain module-level function (not a class method), so
    # patch it by its public module path.
    return patch(
        "salt.modules.dockercompose.__load_project_from_file_path",
        return_value=return_value,
        create=True,
    )


@pytest.fixture
def configure_loader_modules():
    return {dockercompose: {}}


# ---------------------------------------------------------------------------
# __virtual__ tests
# ---------------------------------------------------------------------------


def test_virtual_loads_with_python_on_whales():
    with patch.object(dockercompose, "HAS_PYTHON_ON_WHALES", True):
        result = dockercompose.__virtual__()
    assert result == "dockercompose"


def test_virtual_loads_with_legacy_compose():
    compose_mock = MagicMock()
    compose_mock.__version__ = "1.29.0"
    with patch.object(dockercompose, "HAS_PYTHON_ON_WHALES", False):
        with patch.object(dockercompose, "HAS_DOCKERCOMPOSE", True):
            with patch.object(dockercompose, "compose", compose_mock, create=True):
                result = dockercompose.__virtual__()
    assert result == "dockercompose"


def test_virtual_fails_without_either_library():
    with patch.object(dockercompose, "HAS_PYTHON_ON_WHALES", False):
        with patch.object(dockercompose, "HAS_DOCKERCOMPOSE", False):
            result = dockercompose.__virtual__()
    assert result is not True
    assert isinstance(result, tuple)
    assert result[0] is False


# ---------------------------------------------------------------------------
# create() tests
# ---------------------------------------------------------------------------


def test_create_with_valid_content(tmp_path):
    """create() writes the compose file and reports success."""
    dest = str(tmp_path)
    with patch(
        "salt.modules.dockercompose.__load_project_from_file_path",
        return_value=FAKE_PROJECT,
        create=True,
    ):
        result = dockercompose.create(dest, SIMPLE_COMPOSE)
    assert result["status"] is True
    assert "Successfully created" in result["message"]
    written = os.path.join(dest, "docker-compose.yml")
    assert os.path.isfile(written)


def test_create_with_empty_content():
    """create() returns a failure when no content is supplied."""
    result = dockercompose.create("/some/path", "")
    assert result["status"] is False
    assert "valid docker-compose file" in result["message"]


# ---------------------------------------------------------------------------
# get() tests
# ---------------------------------------------------------------------------


def test_get_returns_file_contents(tmp_path):
    """get() returns the raw compose YAML when the file exists and is valid."""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(SIMPLE_COMPOSE)

    with patch(
        "salt.modules.dockercompose.__load_project_from_file_path",
        return_value=FAKE_PROJECT,
        create=True,
    ):
        result = dockercompose.get(str(tmp_path))

    assert result["status"] is True
    assert "docker-compose.yml" in result["return"]


def test_get_returns_failure_for_missing_path(tmp_path):
    """get() returns a failure when the path has no compose file."""
    result = dockercompose.get(str(tmp_path / "nonexistent"))
    assert result["status"] is False


# ---------------------------------------------------------------------------
# service_create() tests
# ---------------------------------------------------------------------------


def test_service_create_adds_new_service(tmp_path):
    """service_create() adds a new service definition to the compose file."""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(SIMPLE_COMPOSE)
    definition = "image: redis:7\nports:\n  - '6379:6379'\n"

    with patch(
        "salt.modules.dockercompose.__load_project_from_file_path",
        return_value=FAKE_PROJECT,
        create=True,
    ):
        result = dockercompose.service_create(str(tmp_path), "cache", definition)

    assert result["status"] is True
    assert "cache" in result["message"]
    content = compose_file.read_text()
    assert "cache" in content
    assert "redis" in content


def test_service_create_rejects_duplicate(tmp_path):
    """service_create() fails when the service already exists."""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(SIMPLE_COMPOSE)

    with patch(
        "salt.modules.dockercompose.__load_project_from_file_path",
        return_value=FAKE_PROJECT,
        create=True,
    ):
        result = dockercompose.service_create(
            str(tmp_path), "web", "image: nginx:alpine"
        )

    assert result["status"] is False
    assert "already exists" in result["message"]


# ---------------------------------------------------------------------------
# service_upsert() tests
# ---------------------------------------------------------------------------


def test_service_upsert_adds_service(tmp_path):
    """service_upsert() adds a service that does not yet exist."""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(SIMPLE_COMPOSE)

    with patch(
        "salt.modules.dockercompose.__load_project_from_file_path",
        return_value=FAKE_PROJECT,
        create=True,
    ):
        result = dockercompose.service_upsert(
            str(tmp_path), "queue", "image: rabbitmq:3"
        )

    assert result["status"] is True
    content = compose_file.read_text()
    assert "queue" in content


# ---------------------------------------------------------------------------
# service_remove() tests
# ---------------------------------------------------------------------------


def test_service_remove_deletes_existing_service(tmp_path):
    """service_remove() removes an existing service from the compose file."""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(SIMPLE_COMPOSE)

    with patch(
        "salt.modules.dockercompose.__load_project_from_file_path",
        return_value=FAKE_PROJECT,
        create=True,
    ):
        result = dockercompose.service_remove(str(tmp_path), "db")

    assert result["status"] is True
    content = compose_file.read_text()
    assert "db:" not in content
    assert "web:" in content


def test_service_remove_rejects_missing_service(tmp_path):
    """service_remove() fails gracefully when the service does not exist."""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(SIMPLE_COMPOSE)

    with patch(
        "salt.modules.dockercompose.__load_project_from_file_path",
        return_value=FAKE_PROJECT,
        create=True,
    ):
        result = dockercompose.service_remove(str(tmp_path), "nonexistent")

    assert result["status"] is False
    assert "did not exists" in result["message"]


# ---------------------------------------------------------------------------
# service_set_tag() tests
# ---------------------------------------------------------------------------


def test_service_set_tag_updates_image_tag(tmp_path):
    """service_set_tag() replaces the image tag for the named service."""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(SIMPLE_COMPOSE)

    with patch(
        "salt.modules.dockercompose.__load_project_from_file_path",
        return_value=FAKE_PROJECT,
        create=True,
    ):
        result = dockercompose.service_set_tag(str(tmp_path), "web", "1.25")

    assert result["status"] is True
    content = compose_file.read_text()
    assert "nginx:1.25" in content


def test_service_set_tag_fails_for_missing_service(tmp_path):
    """service_set_tag() returns failure when the service is not found."""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(SIMPLE_COMPOSE)

    with patch(
        "salt.modules.dockercompose.__load_project_from_file_path",
        return_value=FAKE_PROJECT,
        create=True,
    ):
        result = dockercompose.service_set_tag(str(tmp_path), "ghost", "1.0")

    assert result["status"] is False


def test_service_set_tag_fails_for_service_without_image(tmp_path):
    """service_set_tag() returns failure when the service has no 'image' key."""
    compose_content = textwrap.dedent(
        """\
        version: '3'
        services:
          builder:
            build: .
        """
    )
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(compose_content)

    with patch(
        "salt.modules.dockercompose.__load_project_from_file_path",
        return_value=FAKE_PROJECT,
        create=True,
    ):
        result = dockercompose.service_set_tag(str(tmp_path), "builder", "2.0")

    assert result["status"] is False
    assert "image" in result["message"]
