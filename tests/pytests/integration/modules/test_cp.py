"""
Integration tests for the cp execution module.
"""

import pytest

import salt.utils.files
import salt.utils.stringutils


@pytest.fixture
def issue_68572_template_tree(base_env_state_tree_root_dir):
    main = base_env_state_tree_root_dir / "issue-68572-main.j2"
    mapfile = base_env_state_tree_root_dir / "issue-68572-map.jinja"
    main.write_text(
        "{%- from 'issue-68572-map.jinja' import defaults with context -%}\n"
        "{{ defaults['foo'] }}\n"
    )
    mapfile.write_text("{% set defaults = {'foo': 'bar'} %}\n")
    try:
        yield "salt://issue-68572-main.j2"
    finally:
        main.unlink(missing_ok=True)
        mapfile.unlink(missing_ok=True)


def test_get_template_with_imported_context(
    salt_call_cli, issue_68572_template_tree, tmp_path
):
    """
    Regression test for #68572.

    ``cp.get_template`` against a Jinja template that contains a
    ``{% from '...' import ... with context %}`` statement must render
    successfully. Prior to the fix the loader-backed dunders passed to the
    template rendering machinery were left wrapped in
    ``NamedLoaderContext``; the file client and channel constructed by
    ``SaltCacheLoader`` for the imported template then ran on the tornado
    IO loop where the loader context is not set, causing
    ``NamedLoaderContext.value()`` to return ``None`` and the channel's
    ``self.opts.get(...)`` call to raise
    ``AttributeError: 'NoneType' object has no attribute 'get'``.
    """
    dest = tmp_path / "issue-68572.out"
    ret = salt_call_cli.run("cp.get_template", issue_68572_template_tree, str(dest))
    assert ret.returncode == 0, ret
    assert ret.data, ret
    with salt.utils.files.fopen(str(dest), "r") as fp_:
        rendered = salt.utils.stringutils.to_unicode(fp_.read())
    assert "bar" in rendered
