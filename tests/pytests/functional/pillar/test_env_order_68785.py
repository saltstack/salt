"""
Functional regression test for issue #68785.

When the master option ``env_order`` is configured, pillar merging must
iterate the matched environments in that order so the last environment
listed in ``env_order`` wins on conflicting pillar keys, instead of the
result depending on dict insertion order of the matched environments.
"""

import pytest

import salt.pillar

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture
def env_order_pillar_tree(tmp_path):
    """
    Build a multi-env pillar tree with each environment having a top.sls
    declaring a single conflicting ``shared.sls`` for the ``*`` target. The
    same key is written with a different value per environment so that the
    last-merged environment is observable in the final pillar.
    """
    base_root = tmp_path / "base"
    dev_root = tmp_path / "dev"
    prod_root = tmp_path / "prod"
    for root in (base_root, dev_root, prod_root):
        root.mkdir()

    # Each environment's top.sls only declares the environment that
    # contains it; the default ``smart`` pillar source merging strategy
    # then gives us a ``matches`` dict with all three envs.
    (base_root / "top.sls").write_text(
        "base:\n  '*':\n    - shared\n", encoding="utf-8"
    )
    (dev_root / "top.sls").write_text("dev:\n  '*':\n    - shared\n", encoding="utf-8")
    (prod_root / "top.sls").write_text(
        "prod:\n  '*':\n    - shared\n", encoding="utf-8"
    )

    (base_root / "shared.sls").write_text("winner: base\n", encoding="utf-8")
    (dev_root / "shared.sls").write_text("winner: dev\n", encoding="utf-8")
    (prod_root / "shared.sls").write_text("winner: prod\n", encoding="utf-8")

    return {
        "base": [str(base_root)],
        "dev": [str(dev_root)],
        "prod": [str(prod_root)],
    }


def _make_opts(salt_master, pillar_roots, env_order=None):
    opts = salt_master.config.copy()
    opts["pillar_roots"] = pillar_roots
    opts["file_roots"] = pillar_roots
    # Force the same env list to be considered for both pillar source
    # merging and top-file collection.
    opts["pillarenv"] = None
    opts["pillar_source_merging_strategy"] = "smart"
    opts["top_file_merging_strategy"] = "merge"
    if env_order is not None:
        opts["env_order"] = env_order
    return opts


def test_env_order_pillar_last_env_wins(salt_master, env_order_pillar_tree, grains):
    """
    With ``env_order: [base, dev, prod]`` configured, the ``prod`` value
    of the conflicting key must win, because ``prod`` is the last
    environment in ``env_order``.

    Before the fix in PR #69350, ``render_pillar`` iterated the
    ``matches`` dict in insertion order. ``matches`` is built from a
    ``set`` of environments inside ``get_tops`` so the resulting order
    is not guaranteed to match ``env_order``. The fix re-orders the
    iteration so the last env in ``env_order`` is processed last and
    therefore wins on conflicting keys.
    """
    opts = _make_opts(
        salt_master,
        env_order_pillar_tree,
        env_order=["base", "dev", "prod"],
    )
    pillar_obj = salt.pillar.Pillar(opts, grains, "minion", "base")
    ret = pillar_obj.compile_pillar()
    assert ret.get("_errors") is None, ret.get("_errors")
    assert ret.get("winner") == "prod", (
        "env_order [base, dev, prod] requires prod to win on conflicting "
        f"pillar keys, got winner={ret.get('winner')!r}. Full pillar: {ret!r}"
    )


def test_env_order_pillar_reversed_order(salt_master, env_order_pillar_tree, grains):
    """
    Reversing ``env_order`` must reverse which environment wins on a
    conflicting key. ``base`` is listed last so ``base`` must win.

    This rules out the trivial pass-mode where ``base`` happens to come
    out of ``matches`` last by coincidence: by switching ``env_order``
    we drive the winner in the opposite direction.
    """
    opts = _make_opts(
        salt_master,
        env_order_pillar_tree,
        env_order=["prod", "dev", "base"],
    )
    pillar_obj = salt.pillar.Pillar(opts, grains, "minion", "base")
    ret = pillar_obj.compile_pillar()
    assert ret.get("_errors") is None, ret.get("_errors")
    assert ret.get("winner") == "base", (
        "env_order [prod, dev, base] requires base to win on conflicting "
        f"pillar keys, got winner={ret.get('winner')!r}. Full pillar: {ret!r}"
    )
