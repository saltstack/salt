import logging
import pathlib
import shutil
import textwrap

import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
]

log = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def _skip_on_non_relenv(install_salt):
    if not install_salt.relenv:
        pytest.skip("This test is for relenv versions of salt")


def test_check_no_import_error(salt_call_cli, salt_master):
    """
    Test that we don't have any errors on teardown of python when using a py-rendered sls file
    This is a package test because the issue was not reproducible in our normal test suite
    """
    init_sls = textwrap.dedent(
        """#!py


def run():
    return {
        "file_foobar": {
            "file.managed": [
                {
                    "name": "/foobar"
                },
                {
                    "template": "jinja"
                },
                {
                    "context": {
                        "foobar": "baz",
                    }
                },
                {
                    "source": "salt://breaks/foobar.jinja",
                }
            ]
        }
    }
    """
    )
    base_tree = pathlib.Path(salt_master.config["file_roots"]["base"][0])
    breaks_tree = base_tree / "breaks"
    breaks_tree.mkdir(exist_ok=True)
    (breaks_tree / "init.sls").write_text(init_sls)
    (breaks_tree / "foobar.jinja").write_text("{{ foobar }}")
    output = salt_call_cli.run("state.apply", "breaks", "--output-diff", "test=true")
    log.debug(output.stderr)
    shutil.rmtree(str(breaks_tree), ignore_errors=True)
    assert not output.stderr
