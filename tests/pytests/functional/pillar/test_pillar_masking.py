"""
Functional tests for pillar masking behaviour: render_pillar() must set
mask_pillar=False so that pillar.get() calls inside pillar SLS renderers
return plain values instead of **********-redacted ones.
"""

import salt.loader
import salt.pillar
import salt.utils.secret
import salt.utils.templates


def test_render_pillar_py_renderer_sees_unmasked_values(
    temp_salt_master, temp_salt_minion
):
    """Pillar SLS files using the #!py renderer must receive plain pillar
    values from pillar.get(), not **********-redacted ones.

    Without the fix, render_pillar() never sets mask_pillar=False.  The
    Python renderer calls mod.run() directly with no render_tmpl() wrapper,
    so mask_pillar stays True and pillar.get() calls serial(), replacing all
    string values (even in plain Python lists) with **********.
    """
    py_pillar_sls = """\
#!py
def run():
    # Without render_pillar() setting mask_pillar=False, pillar.get()
    # calls serial() and returns ['**********', ...] for list values.
    return {"derived_list": __salt__["pillar.get"]("base_list")}
"""
    top_sls = """
base:
  '*':
    - py_pillar
"""
    opts = temp_salt_master.config.copy()
    # plain Python list — serial() redacts string elements when mask_pillar=True
    # even without any MaskedDict/MaskedList wrapping.
    opts["pillar"] = {"base_list": ["a", "b", "c"]}

    with temp_salt_master.pillar_tree.base.temp_file(
        "top.sls", top_sls
    ), temp_salt_master.pillar_tree.base.temp_file("py_pillar.sls", py_pillar_sls):
        grains = salt.loader.grains(opts)
        pillar_obj = salt.pillar.Pillar(opts, grains, temp_salt_minion.id, "base")
        result = pillar_obj.compile_pillar()

    assert result.get("derived_list") == ["a", "b", "c"], (
        f"Expected plain list values but got: {result.get('derived_list')!r}. "
        "render_pillar() must set mask_pillar=False so that pillar.get() "
        "inside #!py SLS files returns expose()d values instead of "
        "serial()-redacted ones."
    )


def test_jinja_state_render_against_masked_pillar(minion_opts):
    """A state SLS Jinja template that interpolates a pillar list/dict value
    via ``{{ pillar['key'] }}`` must produce plain values on the minion.

    Reproduces the minion-side shape of issue 69160. The minion's __pillar__
    is a MaskedDict (wrapped by salt.utils.secret.hide on receive), so
    ``pillar['list_key']`` returns a MaskedList. Without the ContextVar gate
    on MaskedDict/MaskedList __str__, Jinja's ``{{ }}`` call to str() returns
    ``['**********', ...]`` even though templates.wrap_tmpl_func brackets the
    render with mask_pillar=False.
    """
    pillar = salt.utils.secret.hide(
        {
            "hosts": ["host1", "host2"],
            "creds": {"user": "bob"},
            "secret_scalar": "topsecret",
        }
    )
    context = {
        "opts": minion_opts,
        "saltenv": "base",
        "pillar": pillar,
    }
    # Bare ``{{ pillar['hosts'] }}`` — the shape from the bug report.
    result = salt.utils.templates.JINJA(
        "{{ pillar['hosts'] }}",
        from_str=True,
        to_str=True,
        context=context,
    )
    assert result["result"] is True
    rendered = result["data"]
    assert "host1" in rendered and "host2" in rendered
    assert salt.utils.secret.REDACT_PLACEHOLDER not in rendered

    # Nested dict interpolation
    result = salt.utils.templates.JINJA(
        "{{ pillar['creds'] }}",
        from_str=True,
        to_str=True,
        context=context,
    )
    assert "bob" in result["data"]
    assert salt.utils.secret.REDACT_PLACEHOLDER not in result["data"]

    # Scalar leaves were always plain — sanity check we didn't regress that.
    result = salt.utils.templates.JINJA(
        "{{ pillar['secret_scalar'] }}",
        from_str=True,
        to_str=True,
        context=context,
    )
    assert "topsecret" in result["data"]


def test_masked_pillar_redacts_outside_render_bracket():
    """Outside a render bracket (mask_pillar default True), MaskedDict/MaskedList
    must still redact on repr — the safety net for logging and outputters.
    """
    pillar = salt.utils.secret.hide({"hosts": ["host1", "host2"]})
    # Default ContextVar state is True (masked)
    assert salt.utils.secret.REDACT_PLACEHOLDER in repr(pillar)
    assert "host1" not in repr(pillar)
    assert salt.utils.secret.REDACT_PLACEHOLDER in str(pillar["hosts"])
