import json

import pytest
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


def test_new_entry_points_passing_module(tmp_path, salt_extension, salt_minion_factory):
    with SaltVirtualEnv(venv_dir=tmp_path / ".venv") as venv:
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
    tmp_path, salt_extension, salt_minion_factory
):
    with SaltVirtualEnv(venv_dir=tmp_path / ".venv") as venv:
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
        loader = salt.loader.wheels(minion_config)
        print(json.dumps(list(loader)))
        """
        ret = venv.run_code(code, input=json.dumps(salt_minion_factory.config.copy()))
        loader_functions = json.loads(ret.stdout)

        # A non existing module should not appear in the loader
        assert "monty.python" not in loader_functions

        # But our extension's modules should appear on the loader
        assert "foobar.echo1" in loader_functions
        assert "foobar.echo2" in loader_functions


def test_old_entry_points(tmp_path, salt_extension, salt_minion_factory):
    with SaltVirtualEnv(venv_dir=tmp_path / ".venv") as venv:
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
