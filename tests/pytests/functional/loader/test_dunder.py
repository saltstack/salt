import shutil
from collections.abc import MutableMapping

import pytest

import salt.loader.context
import salt.loader.lazy
import salt.utils.files
import tests.support.helpers


def test_opts_dunder_opts_without_import(tmp_path):
    """
    Test __opts__ without being imported.

    When a loaded module uses __opts__ but does not import it from
    salt.loader.dunder the __opts__ object will be a MutableMapping
    (dict or OptsDict for memory optimization).
    """
    opts = {"optimization_order": [0, 1, 2]}
    with salt.utils.files.fopen(tmp_path / "mymod.py", "w") as fp:
        fp.write(
            tests.support.helpers.dedent(
                """
            def mymethod():
                return __opts__
            """
            )
        )
    loader = salt.loader.lazy.LazyLoader([tmp_path], opts)
    assert isinstance(loader["mymod.mymethod"](), MutableMapping)


def test_opts_dunder_opts_with_import(tmp_path):
    """
    Test __opts__ when imported.

    When a loaded module uses __opts__ by importing it from
    salt.loader.dunder the __opts__ object will be a NamedLoaderContext.
    """
    opts = {"optimization_order": [0, 1, 2]}
    with salt.utils.files.fopen(tmp_path / "mymod.py", "w") as fp:
        fp.write(
            tests.support.helpers.dedent(
                """
            from salt.loader.dunder import __opts__
            def optstype():
                return type(__opts__)
            def opts():
                return __opts__
            """
            )
        )
    loader = salt.loader.lazy.LazyLoader([tmp_path], opts)
    assert loader["mymod.optstype"]() == salt.loader.context.NamedLoaderContext
    assert loader["mymod.opts"]() == opts


@pytest.fixture
def child_mod(tmp_path_factory):
    mod_contents = tests.support.helpers.dedent(
        """
    def run():
        return "foo" in __opts__
    """
    )
    tmp = tmp_path_factory.mktemp("child")
    with salt.utils.files.fopen(tmp / "child.py", "w") as fp:
        fp.write(mod_contents)
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def parent_mod(child_mod, tmp_path_factory):
    mod_contents = tests.support.helpers.dedent(
        f"""
    import salt.loader.lazy
    from salt.loader.dunder import __opts__

    def run():
        loader = salt.loader.lazy.LazyLoader([{salt.utils.json.dumps(str(child_mod))}], __opts__)
        return loader["child.run"]()
    """
    )
    tmp = tmp_path_factory.mktemp("parent")
    with salt.utils.files.fopen(tmp / "parent.py", "w") as fp:
        fp.write(mod_contents)
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_opts_dunder_optsdict(parent_mod):
    """
    The introduction of the copy-on-write OptsDict did not correctly account for a module having
    a NamedLoaderContext reference to __opts__, which resulted in an OptsDict having itself
    as its base (transitively via the NamedLoaderContext).
    This caused circular reference issues, such as when its __contains__ was called.

    Issue #68973.
    """
    opts = {"foo": True}
    loader = salt.loader.lazy.LazyLoader([parent_mod], opts)
    assert loader["parent.run"]() is True
