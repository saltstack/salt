import os

import pytest

import salt.loader
import salt.modules.config
import salt.modules.cp
import salt.modules.slsutil
import salt.utils.files
from tests.support.mock import MagicMock

try:
    import salt.modules.yaml
    import salt.utils.yamllint

    YAMLLINT_AVAILABLE = True
except ImportError:
    YAMLLINT_AVAILABLE = False


pytestmark = [
    pytest.mark.skip_on_windows(reason="Dam line breaks"),
    pytest.mark.skipif(
        YAMLLINT_AVAILABLE is False, reason="The 'yammllint' pacakge is not available"
    ),
]


@pytest.fixture
def configure_loader_modules(minion_opts):
    with pytest.helpers.temp_file(
        "testyaml.yaml", contents="key:\n  value\n"
    ) as cached_file:
        yield {
            salt.modules.yaml: {
                "__salt__": {
                    "config.get": salt.modules.config.get,
                    "cp.cache_file": MagicMock(
                        salt.modules.cp.cache_file,
                        autospec=True,
                        return_value=str(cached_file),
                    ),
                    "slsutil.renderer": MagicMock(
                        salt.modules.slsutil.renderer,
                        autospec=True,
                        return_value=f"key: value{os.linesep}",
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
        "source": f"key:{os.linesep}  value{os.linesep}",
    }


def test_lint_pre_render():
    assert salt.modules.yaml.lint("salt://test.test.sls", pre_render="jinja") == {
        "problems": [],
        "source": f"key: value{os.linesep}",
    }


def test_yamllint_virtual():
    assert salt.modules.yaml.__virtual__() == "yaml"
