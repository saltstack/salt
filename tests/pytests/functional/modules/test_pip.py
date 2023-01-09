import sys

import pytest

from tests.support.helpers import VirtualEnv


@pytest.mark.parametrize(
    "pip_version",
    (
        pytest.param(
            "pip==9.0.3",
            marks=pytest.mark.skipif(
                sys.version_info >= (3, 10),
                reason="'pip==9.0.3' is not available on Py >= 3.10",
            ),
        ),
        "pip<20.0",
        "pip<21.0",
        "pip>=21.0",
    ),
)
@pytest.mark.requires_network
def test_list_available_packages(modules, pip_version, tmp_path):
    with VirtualEnv(venv_dir=tmp_path, pip_requirement=pip_version) as virtualenv:
        virtualenv.install("-U", pip_version)
        package_name = "pep8"
        available_versions = modules.pip.list_all_versions(
            package_name, bin_env=str(virtualenv.venv_bin_dir)
        )
        assert available_versions
