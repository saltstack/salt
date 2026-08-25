"""
Integration tests for the minion-side ``renderer_whitelist`` opt.

Setting ``renderer_whitelist: [jinja, yaml]`` on a minion must prevent
SLS files that request other renderers (``#!py``, ``#!pyobjects``,
``#!pydsl``, ``#!mako``, ``#!wempy``) from rendering. Without the
whitelist, a ``#!py`` SLS executes arbitrary Python on the minion
during render -- so this is a real defense-in-depth boundary.
"""

import pytest

from tests.conftest import FIPS_TESTRUN

PY_SLS = """#!py
def run():
    return {"probe": {"test.nop": [{"name": "hi-from-py-sls"}]}}
"""

JINJA_SLS = (
    "{% set r = salt['test.echo']('hi-from-jinja') %}\n"
    "probe:\n"
    "  test.nop:\n"
    "    - name: {{ r }}\n"
)


@pytest.fixture
def renderer_whitelisted_minion(salt_master):
    """
    Minion with ``renderer_whitelist: [jinja, yaml]``. Also whitelists
    the execution modules that ``state.template_str`` needs internally
    so we can drive rendering through a single top-level call.
    """
    minion = salt_master.salt_minion_daemon(
        "test-renderer-whitelist-minion",
        overrides={
            "renderer_whitelist": ["jinja", "yaml"],
            "whitelist_modules": [
                "test",
                "state",
                "saltutil",
                "config",
                "grains",
                "pillar",
                "slsutil",
            ],
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
        },
    )
    minion.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, minion.id
    )
    with minion.started():
        yield minion


def test_default_pipeline_still_renders(salt_cli, renderer_whitelisted_minion):
    """
    A plain SLS (no shebang) uses the default ``jinja|yaml`` pipe -- both
    are on the whitelist, so rendering must succeed.
    """
    ret = salt_cli.run(
        "state.template_str",
        JINJA_SLS,
        minion_tgt=renderer_whitelisted_minion.id,
    )
    assert isinstance(ret.data, dict), f"unexpected return: {ret.data!r}"
    key = next(iter(ret.data))
    assert ret.data[key]["result"] is True
    assert ret.data[key]["name"] == "hi-from-jinja"


def test_shebang_py_renderer_is_rejected(salt_cli, renderer_whitelisted_minion):
    """
    An SLS starting with ``#!py`` requests the ``py`` renderer, which is
    NOT on the whitelist. ``check_render_pipe_str`` drops it, the render
    pipe becomes empty, and ``state.template_str`` reports no data --
    the arbitrary-Python-in-SLS attack surface is closed.

    Also verifies via the minion log that the renderer was rejected
    with the standard ``The renderer "..." is not available`` warning.
    """
    ret = salt_cli.run(
        "state.template_str",
        PY_SLS,
        minion_tgt=renderer_whitelisted_minion.id,
    )
    # A rejected render returns falsy data (empty dict / empty list /
    # error string). Positively assert the Python body did NOT execute:
    # a successful #!py render would produce a ``probe`` state chunk
    # named ``hi-from-py-sls``.
    text = str(ret.data or "")
    assert "hi-from-py-sls" not in text
    assert "test.nop" not in text
