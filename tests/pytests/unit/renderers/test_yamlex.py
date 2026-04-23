import os
import shutil
import tempfile

import pytest

import salt.serializers.yamlex as yamlex
import salt.state
from salt.config import minion_config
from salt.template import compile_template_str


def render(template, opts=None):
    tmp = tempfile.mkdtemp(prefix="yamlex-test-")
    try:
        _config = minion_config(None)
        _config["file_client"] = "local"
        _config["root_dir"] = tmp
        _config["cachedir"] = os.path.join(tmp, "cache", "minion")
        os.makedirs(_config["cachedir"], exist_ok=True)
        if opts:
            _config.update(opts)
        _state = salt.state.State(_config)
        return compile_template_str(
            template,
            _state.rend,
            _state.opts["renderer"],
            _state.opts["renderer_blacklist"],
            _state.opts["renderer_whitelist"],
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def configure_loader_modules():
    return {yamlex: {}}


@pytest.mark.skipif(
    yamlex.available is False,
    reason="yamlex is unavailable, do prerequisites have been met?",
)
def test_basic():
    basic_template = """#!yamlex
    foo: bar
    """

    sls_obj = render(basic_template)
    assert sls_obj == {"foo": "bar"}, sls_obj


@pytest.mark.skipif(
    yamlex.available is False,
    reason="yamlex is unavailable, do prerequisites have been met?",
)
def test_complex():
    complex_template = """#!yamlex
    placeholder: {foo: !aggregate {foo: 42}}
    placeholder: {foo: !aggregate {bar: null}}
    placeholder: {foo: !aggregate {baz: inga}}
    """

    sls_obj = render(complex_template)
    assert sls_obj == {
        "placeholder": {"foo": {"foo": 42, "bar": None, "baz": "inga"}}
    }, sls_obj
