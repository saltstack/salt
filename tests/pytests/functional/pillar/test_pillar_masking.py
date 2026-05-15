"""
Functional tests for pillar masking behaviour: render_pillar() must set
mask_pillar=False so that pillar.get() calls inside pillar SLS renderers
return plain values instead of **********-redacted ones.
"""

import salt.loader
import salt.pillar
import salt.utils.secret


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
