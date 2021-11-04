from pathlib import Path

import pytest
import salt.loader
import salt.modules.config
import salt.modules.cp
import salt.modules.slsutil
import salt.modules.yaml
import salt.utils.files
import salt.utils.yamllint
from tests.support.mock import MagicMock


@pytest.fixture
def configure_loader_modules(minion_opts):
    cached_file = str(Path(__file__).parent / "testyaml.yaml")
    return {
        salt.modules.yaml: {
            "__salt__": {
                "config.get": salt.modules.config.get,
                "cp.cache_file": MagicMock(
                    salt.modules.cp.cache_file, autospec=True, return_value=cached_file
                ),
                "slsutil.renderer": MagicMock(
                    salt.modules.slsutil.renderer,
                    autospec=True,
                    return_value="key: value\n",
                ),
            },
            "__opts__": minion_opts,
            "__utils__": {
                "files.fopen": salt.utils.files.fopen,
                "yamllint.lint": salt.utils.yamllint.lint,
            },
        },
        salt.modules.config: {
            "__opts__": minion_opts,
        },
    }


def test_lint_yaml():
    """
    ensure that we can lint from the yaml lint utils
    """
    assert salt.modules.yaml.lint("salt://test/test.sls") == {
        "problems": [],
        "source": "key:\n  value\n",
    }


def test_lint_pre_render():
    assert salt.modules.yaml.lint("salt://test.test.sls", pre_render="jinja") == {
        "problems": [],
        "source": "key: value\n",
    }
