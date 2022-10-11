import pytest

from tests.support.helpers import SaltVirtualEnv

pytestmark = [
    # These are slow because they create a virtualenv and install salt in it
    pytest.mark.slow_test,
]


@pytest.fixture()
def venv(tmp_path):
    with SaltVirtualEnv(venv_dir=tmp_path / ".venv") as _venv:
        yield _venv


@pytest.mark.parametrize("version", ["<5", ">=5"])
def test_iter_entry_points_importlib_metadata_versions(version, venv):
    """
    importlib_metadata >= v5 does not return a dictionary anymore.
    Issue #62851
    """
    venv.install(f"importlib-metadata{version}")
    code = """
    import salt.utils.entrypoints

    salt.utils.entrypoints.iter_entry_points("salt.loader")
    """
    ret = venv.run_code(code)
    assert ret.returncode == 0
