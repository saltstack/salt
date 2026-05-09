"""
Tests for editable installation of salt
"""

import json
import logging
import pathlib

import pytest

import salt.utils.platform
import salt.version

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(params=[True, False], ids=["static-reqs", "pypi-reqs"])
def use_static_requirements(request):
    return request.param


@pytest.fixture
def venv(setup_tests_path, pip_temp_dir, use_static_requirements):
    from tests.support.helpers import VirtualEnv

    venv_dir = setup_tests_path / ".venv"
    # Python 3.12+ needs newer pip and setuptools
    pip_req = "pip>=24.0"
    setuptools_req = "setuptools>=69.0"

    v = VirtualEnv(
        venv_dir=venv_dir,
        env={
            "TMPDIR": str(pip_temp_dir),
            "USE_STATIC_REQUIREMENTS": "1" if use_static_requirements else "0",
        },
        pip_requirement=pip_req,
        setuptools_requirement=setuptools_req,
    )
    try:
        yield v
    finally:
        import shutil

        shutil.rmtree(str(venv_dir), ignore_errors=True)


def test_editable_install(venv, src_dir):
    """
    test installing salt in editable mode
    """
    with venv as v:
        # Run pip install -e .
        # We use --no-cache-dir to ensure we are actually hitting PyPI when requested
        v.run(
            v.venv_python, "-m", "pip", "install", "--no-cache-dir", "-e", str(src_dir)
        )

        # Let's ensure the version is correct
        cmd = v.run(v.venv_python, "-m", "pip", "list", "--format", "json")
        for details in json.loads(cmd.stdout):
            if details["name"] != "salt":
                continue
            installed_version = details["version"]
            break
        else:
            pytest.fail("Salt was not found installed")

        # Let's compare the installed version with the version salt reports
        # The version might have a '+' or other PEP440 suffix in editable mode
        assert installed_version.startswith(salt.version.__version__.split("+")[0])

        # Verify we can import salt and it's coming from the src_dir
        cmd = v.run(v.venv_python, "-c", "import salt; print(salt.__file__)")
        import_path = pathlib.Path(cmd.stdout.strip()).resolve()

        # In editable mode with some setuptools versions, it might be a redirecting
        # script or point directly to the source.
        # But for Salt, it should eventually be in the src_dir
        expected_path_parent = pathlib.Path(src_dir).resolve() / "salt"
        assert (
            expected_path_parent in import_path.parents
            or import_path.parent == expected_path_parent
        )

        # Verify dependencies are installed by trying to import a common one
        # 'requests' or 'yaml' or 'jinja2' should be installed as they are base deps
        v.run(v.venv_python, "-c", "import requests; import yaml; import jinja2")

        # Verify entry points work
        if salt.utils.platform.is_windows():
            salt_call = pathlib.Path(v.venv_dir) / "Scripts" / "salt-call.exe"
        else:
            salt_call = pathlib.Path(v.venv_dir) / "bin" / "salt-call"

        ret = v.run(str(salt_call), "--version")
        assert salt.version.__version__ in ret.stdout
