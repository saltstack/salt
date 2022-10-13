import logging

import pytest

import salt.config
import salt.renderers.pyobjects as pyobjects
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock

log = logging.getLogger(__name__)


@pytest.fixture
def cache_dir(tmp_path):
    cachedir = tmp_path / "cachedir"
    cachedir.mkdir()
    return cachedir


@pytest.fixture
def minion_config(cache_dir):
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["cachedir"] = str(cache_dir)
    opts["file_client"] = "local"
    opts["id"] = "testminion"
    return opts


@pytest.fixture()
def configure_loader_modules(minion_config):
    pillar = MagicMock(return_value={})
    return {
        pyobjects: {
            "__opts__": minion_config,
            "__pillar__": pillar,
            "__salt__": {
                "config.get": MagicMock(),
                "grains.get": MagicMock(),
                "mine.get": MagicMock(),
                "pillar.get": MagicMock(),
            },
        },
    }


@pytest.fixture
def pyobjects_template():
    class Template:
        def readlines():  # pylint: disable=no-method-argument
            return [
                "#!pyobjects",
                "state_id = __sls__ + '_' + __opts__['id']",
                "File.directory(state_id, name='/tmp', mode='1777', owner='root', group='root')",
            ]

    return Template


@pytest.mark.slow_test
def test_opts_and_sls_access(pyobjects_template):
    ret = pyobjects.render(pyobjects_template, sls="pyobj.runtest")
    assert ret == OrderedDict(
        [
            (
                "pyobj.runtest_testminion",
                {
                    "file.directory": [
                        {"group": "root"},
                        {"mode": "1777"},
                        {"name": "/tmp"},
                        {"owner": "root"},
                    ]
                },
            ),
        ]
    )
