import importlib
import importlib.machinery
import os.path
import sys

import pytest

import salt.utils.lazy
import tests.pytests.unit.utils._lazy_test_module as m


def test_lazy_import(subtests):
    pkg_name = f"{m.__name__}.pkg"
    sub_name = f"{pkg_name}.sub"

    with subtests.test("initial state"):
        assert m.evaluation_counts == {}

    with subtests.test("lazy import"):
        sub_mod = salt.utils.lazy.lazy_import(sub_name)

    with subtests.test("updates sys.modules"):
        assert sub_name in sys.modules
        assert sys.modules[sub_name] is sub_mod

    with subtests.test("parent module is created"):
        assert pkg_name in sys.modules
        pkg_mod = salt.utils.lazy.lazy_import(pkg_name)
        assert sys.modules[pkg_name] is pkg_mod

    with subtests.test("nothing loaded yet"):
        assert m.evaluation_counts == {}

    with subtests.test("idempotent"):
        assert salt.utils.lazy.lazy_import(sub_name) is sub_mod
        assert m.evaluation_counts == {}

    with subtests.test("normal import returns the same module without loading"):
        sub_mod2 = importlib.import_module(sub_name)
        assert sub_mod2 is sub_mod
        assert sys.modules[sub_name] is sub_mod
        assert m.evaluation_counts == {}

    with subtests.test("attributes that don't trigger load"):
        pkgdir = os.path.join(os.path.dirname(m.__file__), "pkg")
        want_known_attrs = {
            pkg_mod: {
                "__file__": os.path.join(pkgdir, "__init__.py"),
                "__loader__": object,
                "__name__": pkg_name,
                "__path__": list,
                "__spec__": importlib.machinery.ModuleSpec,
            },
            sub_mod: {
                "__file__": os.path.join(pkgdir, "sub.py"),
                "__loader__": object,
                "__name__": sub_name,
                "__path__": AttributeError,
                "__spec__": importlib.machinery.ModuleSpec,
            },
        }
        for mod, wants in want_known_attrs.items():
            with subtests.test(mod=mod):
                with subtests.test("complete coverage"):
                    for attr in salt.utils.lazy._LazyModuleLoader._known:
                        with subtests.test(attr=attr):
                            assert attr in wants
                for attr, want in wants.items():
                    with subtests.test(attr=attr):
                        if isinstance(want, type) and issubclass(want, Exception):
                            with pytest.raises(want):
                                getattr(mod, attr)
                        else:
                            got = getattr(mod, attr)
                            if isinstance(want, type):
                                assert isinstance(got, want)
                            else:
                                assert got == want
                        assert m.evaluation_counts == {}

    with subtests.test("loading submodule loads parent"):
        assert sub_mod.mutated_from_parent
        assert m.evaluation_counts == {pkg_name: 1, sub_name: 1}

    with subtests.test("loading does not affect sys.modules"):
        assert sys.modules[pkg_name] is pkg_mod
        assert sys.modules[sub_name] is sub_mod

    with subtests.test("still idempotent after load"):
        assert salt.utils.lazy.lazy_import(pkg_name) is pkg_mod
        assert salt.utils.lazy.lazy_import(sub_name) is sub_mod
