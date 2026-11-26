"""
Verify that every pillar module function emits a DeprecationWarning
when the caller passes ``unmask=``, and that the return value is
always real (plain, not masked).
"""

import warnings

import pytest

import salt.modules.pillar as pillar_mod


@pytest.fixture(autouse=True)
def _reset_warning_cache():
    # The module tracks which functions have already warned in-process;
    # clear it so each test can observe its own warning.
    pillar_mod._UNMASK_DEPRECATION_EMITTED.clear()
    yield
    pillar_mod._UNMASK_DEPRECATION_EMITTED.clear()


@pytest.fixture
def pillar_globals(monkeypatch):
    """Populate the dunders the module functions rely on."""
    opts = {
        "pillar_raise_on_missing": False,
        "pillar_merge_lists": False,
        "pillarenv": None,
        "saltenv": "base",
        "pillarenv_from_saltenv": False,
        "pillar_mask_output": False,
        "id": "testminion",
    }
    pillar = {
        "db": {"root_password": "hunter2"},
        "api_key": "sk-abc",
        "plain": "ok",
    }
    monkeypatch.setattr(pillar_mod, "__opts__", opts, raising=False)
    monkeypatch.setattr(pillar_mod, "__pillar__", pillar, raising=False)
    monkeypatch.setattr(pillar_mod, "__grains__", {}, raising=False)
    monkeypatch.setattr(pillar_mod, "__salt__", {}, raising=False)
    return opts, pillar


class TestUnmaskDeprecated:
    @pytest.mark.parametrize(
        "func_name,call",
        [
            ("get", lambda: pillar_mod.get("plain", unmask=True)),
            ("item", lambda: pillar_mod.item("plain", unmask=True)),
            ("raw", lambda: pillar_mod.raw(unmask=True)),
            ("keys", lambda: pillar_mod.keys("db", unmask=True)),
        ],
    )
    def test_deprecation_warning_fires(self, pillar_globals, func_name, call):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            call()
        unmask_warnings = [
            w for w in caught if issubclass(w.category, DeprecationWarning)
        ]
        assert unmask_warnings, f"no DeprecationWarning from pillar.{func_name}"
        msg = str(unmask_warnings[0].message)
        assert f"pillar.{func_name}" in msg
        assert "unmask" in msg

    def test_only_fires_once_per_func(self, pillar_globals):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            pillar_mod.get("plain", unmask=True)
            pillar_mod.get("plain", unmask=False)
            pillar_mod.get("plain", unmask=True)
        dep = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(dep) == 1

    def test_no_warning_when_unmask_is_none(self, pillar_globals):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            pillar_mod.get("plain")
            pillar_mod.item("plain")
            pillar_mod.raw()
            pillar_mod.keys("db")
        dep = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        # Deprecation should be about unmask=; shouldn't fire when kwarg
        # is omitted / None.
        for w in dep:
            assert "unmask" not in str(w.message)


class TestReturnValuesAlwaysReal:
    """unmask=True/False/None all return the same (plain) value."""

    def test_get_plain(self, pillar_globals):
        assert pillar_mod.get("plain") == "ok"
        assert pillar_mod.get("plain", unmask=False) == "ok"
        assert pillar_mod.get("plain", unmask=True) == "ok"

    def test_get_nested(self, pillar_globals):
        assert pillar_mod.get("db:root_password") == "hunter2"
        assert pillar_mod.get("db:root_password", unmask=False) == "hunter2"

    def test_item(self, pillar_globals):
        ret = pillar_mod.item("api_key", unmask=False)
        assert ret == {"api_key": "sk-abc"}

    def test_raw(self, pillar_globals):
        ret = pillar_mod.raw(unmask=False)
        assert ret["api_key"] == "sk-abc"
        assert ret["db"]["root_password"] == "hunter2"

    def test_keys(self, pillar_globals):
        assert sorted(pillar_mod.keys("db", unmask=False)) == ["root_password"]


class TestWarningFiresForForwardingFuncs:
    """``data``, ``obfuscate``, ``ls``, ``ext``, and ``items`` forward
    to ``items`` or rebuild pillar.  Each still owns its own warning."""

    def test_items_warns(self, pillar_globals, monkeypatch):
        # Short-circuit the pillar rebuild; return what we've already
        # stubbed in __pillar__ so the test is hermetic.
        def _fake_get_pillar(*args, **kwargs):
            class _P:
                def compile_pillar(self):
                    return dict(pillar_mod.__pillar__)

                def destroy(self):
                    pass

            return _P()

        monkeypatch.setattr("salt.pillar.get_pillar", _fake_get_pillar, raising=False)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            pillar_mod.items(unmask=True)
        assert any(
            "pillar.items" in str(w.message)
            and issubclass(w.category, DeprecationWarning)
            for w in caught
        )

    def test_data_warns(self, pillar_globals, monkeypatch):
        def _fake_get_pillar(*args, **kwargs):
            class _P:
                def compile_pillar(self):
                    return dict(pillar_mod.__pillar__)

                def destroy(self):
                    pass

            return _P()

        monkeypatch.setattr("salt.pillar.get_pillar", _fake_get_pillar, raising=False)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            pillar_mod.data(unmask=False)
        assert any(
            "pillar.data" in str(w.message)
            and issubclass(w.category, DeprecationWarning)
            for w in caught
        )

    def test_ls_warns(self, pillar_globals, monkeypatch):
        def _fake_get_pillar(*args, **kwargs):
            class _P:
                def compile_pillar(self):
                    return dict(pillar_mod.__pillar__)

                def destroy(self):
                    pass

            return _P()

        monkeypatch.setattr("salt.pillar.get_pillar", _fake_get_pillar, raising=False)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            pillar_mod.ls(unmask=True)
        assert any(
            "pillar.ls" in str(w.message) and issubclass(w.category, DeprecationWarning)
            for w in caught
        )

    def test_obfuscate_warns(self, pillar_globals, monkeypatch):
        def _fake_get_pillar(*args, **kwargs):
            class _P:
                def compile_pillar(self):
                    return dict(pillar_mod.__pillar__)

                def destroy(self):
                    pass

            return _P()

        monkeypatch.setattr("salt.pillar.get_pillar", _fake_get_pillar, raising=False)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            pillar_mod.obfuscate(unmask=True)
        assert any(
            "pillar.obfuscate" in str(w.message)
            and issubclass(w.category, DeprecationWarning)
            for w in caught
        )

    def test_ext_warns(self, pillar_globals, monkeypatch):
        class _Grains:
            def value(self):
                return {}

        monkeypatch.setattr(pillar_mod, "__grains__", _Grains(), raising=False)

        def _fake_get_pillar(*args, **kwargs):
            class _P:
                def compile_pillar(self):
                    return dict(pillar_mod.__pillar__)

                def destroy(self):
                    pass

            return _P()

        monkeypatch.setattr("salt.pillar.get_pillar", _fake_get_pillar, raising=False)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            pillar_mod.ext({"libvirt": "_"}, unmask=True)
        assert any(
            "pillar.ext" in str(w.message)
            and issubclass(w.category, DeprecationWarning)
            for w in caught
        )


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
