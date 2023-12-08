import pathlib

import salt.loader.context
import salt.loader.lazy
import salt.utils.files
import tests.support.helpers


def xtest_opts_dunder_opts_without_import(tempdir):
    """
    Test __opts__ without being imported.

    When a loaded module uses __opts__ but does not import it from
    salt.loader.dunder the __opts__ object will be a dictionary.
    """
    opts = {"optimization_order": [0, 1, 2]}
    with salt.utils.files.fopen(pathlib.Path(tempdir.tempdir) / "mymod.py", "w") as fp:
        fp.write(
            tests.support.helpers.dedent(
                """
            def mymethod():
                return __opts__
            """
            )
        )
    loader = salt.loader.lazy.LazyLoader([tempdir.tempdir], opts)
    assert type(loader["mymod.mymethod"]()) == dict


def test_opts_dunder_opts_with_import(tempdir):
    """
    Test __opts__ when imported.

    When a loaded module uses __opts__ by importing it from
    salt.loader.dunder the __opts__ object will be a NamedLoaderContext.
    """
    opts = {"optimization_order": [0, 1, 2]}
    with salt.utils.files.fopen(pathlib.Path(tempdir.tempdir) / "mymod.py", "w") as fp:
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
    loader = salt.loader.lazy.LazyLoader([tempdir.tempdir], opts)
    assert loader["mymod.optstype"]() == salt.loader.context.NamedLoaderContext
    assert loader["mymod.opts"]() == opts
