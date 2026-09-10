import logging
from collections import OrderedDict

import pytest

import salt.renderers.pyobjects as pyobjects
from tests.support.mock import MagicMock

log = logging.getLogger(__name__)


@pytest.fixture()
def configure_loader_modules(minion_opts):
    minion_opts["file_client"] = "local"
    minion_opts["id"] = "testminion"
    pillar = MagicMock(return_value={})
    return {
        pyobjects: {
            "__opts__": minion_opts,
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
                "File.directory(state_id, name='/tmp', mode='1777', owner=passed_owner, group=passed_group)",
            ]

    return Template


@pytest.mark.slow_test
def test_opts_and_sls_access(pyobjects_template):
    context = {"passed_owner": "root", "passed_group": "root"}

    ret = pyobjects.render(pyobjects_template, sls="pyobj.runtest", context=context)
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


def test_map_merge_pillar_values_are_unmasked():
    """
    Map ``merge`` pillar reads happen at class-definition (render) time,
    outside the mask_pillar=False context that string-template renderers
    get from salt.utils.templates.wrap_tmpl_func, so the read must pass
    unmask=True to receive real pillar values instead of the redact
    placeholder. See issue #69711.
    """
    import salt.utils.pyobjects as pyobjects_utils
    import salt.utils.secret

    pillar_data = {"nginx:lookup": {"package": "nginx-full", "api_token": "hunter2"}}

    def fake_pillar_get(key, default=None, unmask=None, **kwargs):
        # Mimic salt.modules.pillar.get masking semantics under the
        # default mask_pillar=True context.
        value = pillar_data.get(key, default)
        if unmask is None:
            unmask = not salt.utils.secret.mask_pillar.get()
        if unmask:
            return salt.utils.secret.expose(value)
        return salt.utils.secret.serial(value)

    orig_salt = pyobjects_utils.Map.__salt__
    # Pin the contextvar to its default (masked) so the test is
    # deterministic regardless of what earlier tests did.
    token = salt.utils.secret.mask_pillar.set(True)
    pyobjects_utils.Map.__salt__ = {
        "grains.filter_by": MagicMock(),
        "grains.item": MagicMock(return_value={}),
        "pillar.get": fake_pillar_get,
    }
    try:

        class Nginx(pyobjects_utils.Map):
            merge = "nginx:lookup"

        assert Nginx.package == "nginx-full"
        assert Nginx.api_token == "hunter2"
        assert salt.utils.secret.REDACT_PLACEHOLDER not in (
            Nginx.package,
            Nginx.api_token,
        )
    finally:
        pyobjects_utils.Map.__salt__ = orig_salt
        salt.utils.secret.mask_pillar.reset(token)
