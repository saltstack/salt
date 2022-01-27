import json
import sys

import pytest
import salt.utils.versions
from tests.support.helpers import SaltVirtualEnv
from tests.support.pytest.helpers import FakeSaltExtension

pytestmark = [
    # These are slow because they create a virtualenv and install salt in it
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def salt_extension(tmp_path_factory):
    with FakeSaltExtension(
        tmp_path_factory=tmp_path_factory, name="salt-ext-loader-test"
    ) as extension:
        yield extension


@pytest.fixture
def venv(tmp_path):
    with SaltVirtualEnv(venv_dir=tmp_path / ".venv") as _venv:
        yield _venv


def test_new_entry_points_passing_module(venv, salt_extension, salt_minion_factory):
    # Install our extension into the virtualenv
    venv.install(str(salt_extension.srcdir))
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name in installed_packages
    code = """
    import sys
    import json

    # If the test fails, for debugging purposes, comment out the following 2 lines
    #import salt.log.setup
    #salt.log.setup.setup_console_logger(log_level="debug")

    import salt.loader

    minion_config = json.loads(sys.stdin.read())
    loader = salt.loader.minion_mods(minion_config)
    print(json.dumps(list(loader)))
    """
    ret = venv.run_code(code, input=json.dumps(salt_minion_factory.config.copy()))
    loader_functions = json.loads(ret.stdout)

    # A non existing module should not appear in the loader
    assert "monty.python" not in loader_functions

    # But our extension's modules should appear on the loader
    assert "foobar.echo1" in loader_functions
    assert "foobar.echo2" in loader_functions


def test_new_entry_points_passing_func_returning_a_dict(
    venv, salt_extension, salt_minion_factory
):
    # Install our extension into the virtualenv
    venv.install(str(salt_extension.srcdir))
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name in installed_packages
    code = """
    import sys
    import json

    # If the test fails, for debugging purposes, comment out the following 2 lines
    #import salt.log.setup
    #salt.log.setup.setup_console_logger(log_level="debug")

    import salt.loader

    minion_config = json.loads(sys.stdin.read())
    loader = salt.loader.runner(minion_config)
    print(json.dumps(list(loader)))
    """
    ret = venv.run_code(code, input=json.dumps(salt_minion_factory.config.copy()))
    loader_functions = json.loads(ret.stdout)

    # A non existing module should not appear in the loader
    assert "monty.python" not in loader_functions

    # But our extension's modules should appear on the loader
    assert "foobar.echo1" in loader_functions
    assert "foobar.echo2" in loader_functions


def test_old_entry_points_yielding_paths(venv, salt_extension, salt_minion_factory):
    # Install our extension into the virtualenv
    venv.install(str(salt_extension.srcdir))
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name in installed_packages
    code = """
    import sys
    import json

    # If the test fails, for debugging purposes, comment out the following 2 lines
    import salt.log.setup
    salt.log.setup.setup_console_logger(log_level="debug")

    import salt.loader

    minion_config = json.loads(sys.stdin.read())
    functions = salt.loader.minion_mods(minion_config)
    utils = salt.loader.utils(minion_config)
    serializers = salt.loader.serializers(minion_config)
    loader = salt.loader.states(minion_config, functions, utils, serializers)
    print(json.dumps(list(loader)))
    """
    ret = venv.run_code(code, input=json.dumps(salt_minion_factory.config.copy()))
    loader_functions = json.loads(ret.stdout)

    # A non existing module should not appear in the loader
    assert "monty.python" not in loader_functions

    # But our extension's modules should appear on the loader
    assert "foobar.echoed" in loader_functions


def test_utils_loader_does_not_load_extensions(
    venv, salt_extension, salt_minion_factory
):
    # Install our extension into the virtualenv
    venv.install(str(salt_extension.srcdir))
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name in installed_packages
    code = """
    import sys
    import json

    # If the test fails, for debugging purposes, comment out the following 2 lines
    #import salt.log.setup
    #salt.log.setup.setup_console_logger(log_level="debug")

    import salt.loader

    minion_config = json.loads(sys.stdin.read())
    loader = salt.loader.utils(minion_config)
    print(json.dumps(list(loader)))
    """
    ret = venv.run_code(code, input=json.dumps(salt_minion_factory.config.copy()))
    loader_functions = json.loads(ret.stdout)

    # A non existing module should not appear in the loader
    assert "monty.python" not in loader_functions

    # But our extension's modules should appear on the loader
    assert "foobar.echo" not in loader_functions


@pytest.mark.skipif(
    sys.version_info < (3, 6),
    reason="importlib-metadata>=3.3.0 does not exist for Py3.5",
)
def test_extension_discovery_without_reload_with_importlib_metadata_installed(
    venv, salt_extension, salt_minion_factory
):
    # Install our extension into the virtualenv
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name not in installed_packages
    venv.install("importlib-metadata>=3.3.0")
    code = """
    import sys
    import json
    import subprocess

    # If the test fails, for debugging purposes, comment out the following 2 lines
    import salt.log.setup
    salt.log.setup.setup_console_logger(log_level="debug")

    extension_path = "{}"

    import salt.loader

    minion_config = json.loads(sys.stdin.read())
    loader = salt.loader.minion_mods(minion_config)
    if "foobar.echo1" in loader:
        sys.exit(1)

    # Install the extension
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", extension_path],
        check=False,
        shell=False,
        stdout=subprocess.PIPE,
    )
    if proc.returncode != 0:
        sys.exit(2)

    loader = salt.loader.minion_mods(minion_config)
    if "foobar.echo1" not in loader:
        sys.exit(3)

    print(json.dumps(list(loader)))
    """.format(
        salt_extension.srcdir
    )
    ret = venv.run_code(
        code, input=json.dumps(salt_minion_factory.config.copy()), check=False
    )
    # Exitcode 1 - Extension was already installed
    # Exitcode 2 - Failed to install the extension
    # Exitcode 3 - Extension was not found within the same python process after being installed
    assert ret.exitcode == 0
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name in installed_packages

    loader_functions = json.loads(ret.stdout)

    # A non existing module should not appear in the loader
    assert "monty.python" not in loader_functions

    # But our extension's modules should appear on the loader
    assert "foobar.echo1" in loader_functions
    assert "foobar.echo2" in loader_functions


def test_extension_discovery_without_reload_with_bundled_importlib_metadata(
    venv, salt_extension, salt_minion_factory
):
    # Install our extension into the virtualenv
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name not in installed_packages
    if "importlib-metadata" in installed_packages:
        importlib_metadata_version = installed_packages["importlib-metadata"]
        if salt.utils.versions.StrictVersion(importlib_metadata_version) >= "3.3.0":
            venv.install("-U", "importlib-metadata<3.3.0")
    code = """
    import sys
    import json
    import subprocess

    # If the test fails, for debugging purposes, comment out the following 2 lines
    import salt.log.setup
    salt.log.setup.setup_console_logger(log_level="debug")

    extension_path = "{}"

    import salt.loader

    minion_config = json.loads(sys.stdin.read())
    loader = salt.loader.minion_mods(minion_config)
    if "foobar.echo1" in loader:
        sys.exit(1)

    # Install the extension
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", extension_path],
        check=False,
        shell=False,
        stdout=subprocess.PIPE,
    )
    if proc.returncode != 0:
        sys.exit(2)

    loader = salt.loader.minion_mods(minion_config)
    if "foobar.echo1" not in loader:
        sys.exit(3)

    print(json.dumps(list(loader)))
    """.format(
        salt_extension.srcdir
    )
    ret = venv.run_code(
        code, input=json.dumps(salt_minion_factory.config.copy()), check=False
    )
    # Exitcode 1 - Extension was already installed
    # Exitcode 2 - Failed to install the extension
    # Exitcode 3 - Extension was not found within the same python process after being installed
    assert ret.exitcode == 0
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name in installed_packages

    loader_functions = json.loads(ret.stdout)

    # A non existing module should not appear in the loader
    assert "monty.python" not in loader_functions

    # But our extension's modules should appear on the loader
    assert "foobar.echo1" in loader_functions
    assert "foobar.echo2" in loader_functions
