import json
import logging

import pytest

from tests.support.helpers import SaltVirtualEnv
from tests.support.pytest.helpers import FakeSaltExtension

pytestmark = [
    # These are slow because they create a virtualenv and install salt in it
    pytest.mark.slow_test,
    pytest.mark.timeout_unless_on_windows(240),
]

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def salt_extension(tmp_path_factory):
    with FakeSaltExtension(
        tmp_path_factory=tmp_path_factory, name="salt-ext-version-test"
    ) as extension:
        yield extension


def test_salt_extensions_in_versions_report(tmp_path, salt_extension):
    with SaltVirtualEnv(venv_dir=tmp_path / ".venv") as venv:
        # Install our extension into the virtualenv
        venv.install(str(salt_extension.srcdir))
        installed_packages = venv.get_installed_packages()
        assert salt_extension.name in installed_packages
        ret = venv.run_code(
            """
            import json
            import salt.version

            print(json.dumps(salt.version.versions_information()))
            """
        )
    versions_information = json.loads(ret.stdout)
    assert "Salt Extensions" in versions_information
    assert salt_extension.name in versions_information["Salt Extensions"]


def test_salt_extensions_absent_in_versions_report(tmp_path, salt_extension):
    """
    Ensure that the 'Salt Extensions' header does not show up when no extension is installed
    """
    with SaltVirtualEnv(venv_dir=tmp_path / ".venv") as venv:
        installed_packages = venv.get_installed_packages()
        assert salt_extension.name not in installed_packages
        ret = venv.run_code(
            """
            import json
            import salt.version

            print(json.dumps(salt.version.versions_information()))
            """
        )
    versions_information = json.loads(ret.stdout)
    assert "Salt Extensions" not in versions_information
