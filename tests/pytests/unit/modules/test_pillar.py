from collections import OrderedDict

import pytest

import salt.config
import salt.modules.pillar as pillarmod
import salt.utils.secret as secret
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def pillar_value():
    pillar_value = dict(a=1, b="very secret")
    return pillar_value


@pytest.fixture
def configure_loader_modules():
    return {pillarmod: {}}


def test_obfuscate_inner_recursion():
    assert pillarmod._obfuscate_inner(
        dict(a=[1, 2], b=dict(pwd="secret", deeper=("a", 1)))
    ) == dict(a=["<int>", "<int>"], b=dict(pwd="<str>", deeper=("<str>", "<int>")))


def test_obfuscate_inner_more_types():
    assert pillarmod._obfuscate_inner(OrderedDict([("key", "value")])) == OrderedDict(
        [("key", "<str>")]
    )

    assert pillarmod._obfuscate_inner({1, 2}) == {"<int>"}

    assert pillarmod._obfuscate_inner((1, 2)) == ("<int>", "<int>")


def test_obfuscate(pillar_value):
    with patch("salt.modules.pillar.items", MagicMock(return_value=pillar_value)):
        assert pillarmod.obfuscate() == dict(a="<int>", b="<str>")


def test_obfuscate_with_kwargs(pillar_value):
    with patch(
        "salt.modules.pillar.items", MagicMock(return_value=pillar_value)
    ) as pillar_items_mock:
        ret = pillarmod.obfuscate(saltenv="saltenv")
        # ensure the kwargs are passed along to pillar.items
        assert (
            call(
                pillar=None,
                pillar_enc=None,
                pillarenv=None,
                saltenv="saltenv",
                unmask=None,
            )
            in pillar_items_mock.mock_calls
        )
        assert ret == dict(a="<int>", b="<str>")


def test_ls(pillar_value):
    with patch("salt.modules.pillar.items", MagicMock(return_value=pillar_value)):
        ls = sorted(pillarmod.ls())
        assert ls == ["a", "b"]


def test_pillar_get_default_merge():
    defaults = {
        "int": 1,
        "string": "foo",
        "list": ["foo"],
        "dict": {"foo": "bar", "subkey": {"foo": "bar"}},
    }

    pillar_mock = {
        "int": 2,
        "string": "bar",
        "list": ["bar", "baz"],
        "dict": {"baz": "qux", "subkey": {"baz": "qux"}},
    }

    # Test that we raise a KeyError when pillar_raise_on_missing is True
    with patch.dict(pillarmod.__opts__, {"pillar_raise_on_missing": True}):
        pytest.raises(KeyError, pillarmod.get, "missing")
    # Test that we return an empty string when it is not
    with patch.dict(pillarmod.__opts__, {}):
        assert pillarmod.get("missing") == ""

    with patch.dict(pillarmod.__pillar__, pillar_mock):
        # Test with no default passed (it should be KeyError) and merge=True.
        # The merge should be skipped and the value returned from __pillar__
        # should be returned.
        for item in pillarmod.__pillar__:
            assert (
                pillarmod.get(item, merge=True, unmask=True)
                == pillarmod.__pillar__[item]
            )

        # Test merging when the type of the default value is not the same as
        # what was returned. Merging should be skipped and the value returned
        # from __pillar__ should be returned.
        for default_type in defaults:
            for data_type in ("dict", "list"):
                if default_type == data_type:
                    continue
                assert (
                    pillarmod.get(
                        data_type,
                        default=defaults[default_type],
                        merge=True,
                        unmask=True,
                    )
                    == pillarmod.__pillar__[data_type]
                )

        # Test recursive dict merging
        assert pillarmod.get(
            "dict", default=defaults["dict"], merge=True, unmask=True
        ) == {
            "foo": "bar",
            "baz": "qux",
            "subkey": {"foo": "bar", "baz": "qux"},
        }

        # Test list merging
        assert pillarmod.get(
            "list", default=defaults["list"], merge=True, unmask=True
        ) == [
            "foo",
            "bar",
            "baz",
        ]


def test_pillar_get_default_merge_regression_38558():
    """Test for pillar.get(key=..., default=..., merge=True)
    Do not update the ``default`` value when using ``merge=True``.
    See: https://github.com/saltstack/salt/issues/38558
    """
    with patch.dict(pillarmod.__pillar__, {"l1": {"l2": {"l3": 42}}}):
        res = pillarmod.get(key="l1")
        assert {"l2": {"l3": 42}} == res

        default = {"l2": {"l3": 43}}

        res = pillarmod.get(key="l1", default=default)
        assert {"l2": {"l3": 42}} == res
        assert {"l2": {"l3": 43}} == default

        res = pillarmod.get(key="l1", default=default, merge=True)
        assert {"l2": {"l3": 42}} == res
        assert {"l2": {"l3": 43}} == default


@pytest.fixture
def compiled_pillar():
    pillar_obj = MagicMock()
    pillar_obj.compile_pillar = MagicMock(return_value={"pin": 1234})
    grains = MagicMock()
    grains.value = MagicMock(return_value={})
    with patch(
        "salt.pillar.get_pillar", MagicMock(return_value=pillar_obj)
    ), patch.dict(pillarmod.__pillar__, {"pin": 1234}), patch.object(
        pillarmod, "__grains__", grains, create=True
    ):
        yield


@pytest.mark.parametrize("unmask", [None, True, False])
@pytest.mark.usefixtures("compiled_pillar")
def test_pillar_functions_return_real_values_with_masking_off(unmask):
    """
    With ``pillar_mask_output`` off, ``unmask`` has no effect and the functions
    return plain real values.
    """
    opts = {
        "id": "minion",
        "saltenv": "base",
        "pillarenv": None,
        "pillar_mask_output": False,
    }
    with patch.dict(pillarmod.__opts__, opts):
        results = [
            pillarmod.items(unmask=unmask),
            pillarmod.item("pin", unmask=unmask),
            pillarmod.ext({"libvirt": "_"}, unmask=unmask),
            pillarmod.raw(unmask=unmask),
        ]
        assert pillarmod.get("pin", unmask=unmask) == 1234
    for result in results:
        assert result == {"pin": 1234}
        assert type(result) is dict
        assert "1234" in repr(result)


@pytest.mark.parametrize("unmask", [None, True, False])
@pytest.mark.usefixtures("compiled_pillar")
def test_pillar_functions_return_real_values_with_masking_on(unmask):
    """
    With ``pillar_mask_output`` on, ``unmask`` still has no effect. Values read
    from the result are real, only the output of the container is redacted.
    """
    opts = {
        "id": "minion",
        "saltenv": "base",
        "pillarenv": None,
        "pillar_mask_output": True,
    }
    with patch.dict(pillarmod.__opts__, opts):
        results = [
            pillarmod.items(unmask=unmask),
            pillarmod.item("pin", unmask=unmask),
            pillarmod.ext({"libvirt": "_"}, unmask=unmask),
            pillarmod.raw(unmask=unmask),
        ]
        assert pillarmod.get("pin", unmask=unmask) == 1234
    for result in results:
        assert isinstance(result, secret.MaskedDict)
        assert result == {"pin": 1234}
        assert "1234" not in repr(result)
        assert "1234" not in str(result)


def test_pillar_mask_output_defaults_to_false():
    assert salt.config.DEFAULT_MINION_OPTS["pillar_mask_output"] is False
    assert salt.config.DEFAULT_MASTER_OPTS["pillar_mask_output"] is False


def test_pillar_get_returns_real_values_by_default():
    with patch.dict(pillarmod.__pillar__, {"pin": 1234}):
        assert pillarmod.get(key="pin") == 1234


def test_unmasked_results_remove_nested_wrappers_before_output():
    compiled = secret.hide({"nested": {"children": [{"password": "hunter2"}]}})
    pillar_obj = MagicMock()
    pillar_obj.compile_pillar.return_value = compiled
    grains = MagicMock()
    grains.value.return_value = {}
    with patch("salt.pillar.get_pillar", return_value=pillar_obj), patch.dict(
        pillarmod.__pillar__, compiled
    ), patch.dict(
        pillarmod.__opts__,
        {
            "id": "minion",
            "saltenv": "base",
            "pillarenv": None,
            "pillar_mask_output": False,
        },
    ), patch.object(
        pillarmod, "__grains__", grains, create=True
    ):
        results = [
            pillarmod.get("nested"),
            pillarmod.get("nested", default={}, merge=True),
            pillarmod.item("nested"),
            pillarmod.items(),
            pillarmod.ext({}),
            pillarmod.raw(),
        ]
    for result in results:
        assert "hunter2" in repr(result)
        assert secret.mask_output(result) == result


def test_pillar_get_default_merge_regression_39062():
    """
    Confirm that we do not raise an exception if default is None and
    merge=True.
    See https://github.com/saltstack/salt/issues/39062 for more info.
    """
    with patch.dict(pillarmod.__pillar__, {"foo": "bar"}):

        assert pillarmod.get(key="foo", default=None, merge=True, unmask=True) == "bar"


def test_pillar_get_int_key():
    """
    Confirm that we can access pillar keys that are integers
    """
    with patch.dict(pillarmod.__pillar__, {12345: "luggage_code"}):

        assert (
            pillarmod.get(key=12345, default=None, merge=True, unmask=True)
            == "luggage_code"
        )

    with patch.dict(pillarmod.__pillar__, {12345: {"l2": {"l3": "my_luggage_code"}}}):

        res = pillarmod.get(key=12345, unmask=True)
        assert {"l2": {"l3": "my_luggage_code"}} == res

        default = {"l2": {"l3": "your_luggage_code"}}

        res = pillarmod.get(key=12345, default=default, unmask=True)
        assert {"l2": {"l3": "my_luggage_code"}} == res
        assert {"l2": {"l3": "your_luggage_code"}} == default

        res = pillarmod.get(key=12345, default=default, merge=True, unmask=True)
        assert {"l2": {"l3": "my_luggage_code"}} == res
        assert {"l2": {"l3": "your_luggage_code"}} == default


def test_pillar_keys():
    """
    Confirm that we can access pillar keys
    """
    with patch.dict(pillarmod.__pillar__, {"pkg": {"apache": "httpd"}}):
        test_key = "pkg"
        assert pillarmod.keys(test_key) == ["apache"]

    with patch.dict(
        pillarmod.__pillar__,
        {"12345": {"xyz": "my_luggage_code"}, "7": {"11": {"12": "13"}}},
    ):
        test_key = "7:11"
        res = pillarmod.keys(test_key)
        assert res == ["12"]


def test_ls_pass_kwargs(pillar_value):
    with patch("salt.modules.pillar.items", MagicMock(return_value=pillar_value)):
        ls = sorted(pillarmod.ls(pillarenv="base"))
        assert ls == ["a", "b"]


def test_ls_accepts_and_forwards_unmask(pillar_value):
    """``pillar.ls`` accepts ``unmask`` and forwards it to ``items``."""
    with patch(
        "salt.modules.pillar.items", MagicMock(return_value=pillar_value)
    ) as items_mock:
        result = sorted(pillarmod.ls(unmask=True))
        assert result == ["a", "b"]
        assert (
            call(
                pillar=None,
                pillar_enc=None,
                pillarenv=None,
                saltenv=None,
                unmask=True,
            )
            in items_mock.mock_calls
        )


def test_obfuscate_forwards_unmask(pillar_value):
    """``pillar.obfuscate`` forwards ``unmask`` to ``items``."""
    with patch(
        "salt.modules.pillar.items", MagicMock(return_value=pillar_value)
    ) as items_mock:
        pillarmod.obfuscate(unmask=False)
        assert (
            call(
                pillar=None,
                pillar_enc=None,
                pillarenv=None,
                saltenv=None,
                unmask=False,
            )
            in items_mock.mock_calls
        )


def test_keys_accepts_unmask():
    """``pillar.keys`` accepts ``unmask`` (no-op since keys aren't masked)."""
    with patch.dict(pillarmod.__pillar__, {"pkg": {"apache": "httpd"}}):
        # Both calls should return the same list regardless of unmask value.
        assert pillarmod.keys("pkg", unmask=True) == ["apache"]
        assert pillarmod.keys("pkg", unmask=False) == ["apache"]
        assert pillarmod.keys("pkg") == ["apache"]


def test_raw_default_returns_unmasked_values():
    """``pillar.raw`` defaults to unmasked, preserving historical behavior."""
    with patch.dict(pillarmod.__pillar__, {"secret": "swordfish"}):
        assert pillarmod.raw() == {"secret": "swordfish"}
        assert pillarmod.raw(key="secret") == "swordfish"


def test_raw_returns_masked_container_when_masking_is_on():
    """With masking on, ``pillar.raw`` returns real values in a container that
    is redacted on output."""
    with patch.dict(pillarmod.__pillar__, {"secret": "swordfish"}), patch.dict(
        pillarmod.__opts__, {"pillar_mask_output": True}
    ):
        value = pillarmod.raw(unmask=False)
        assert value["secret"] == "swordfish"
        assert "swordfish" not in repr(value)
        assert secret.mask_output(value) == {"secret": secret.REDACT_PLACEHOLDER}
        # A single value is a plain string.
        assert pillarmod.raw(key="secret", unmask=False) == "swordfish"


def test_ext_ignores_unmask():
    """``pillar.ext`` returns the compiled pillar whatever ``unmask`` is."""
    compiled = {"a": "plain", "b": "secret"}
    pillar_obj = MagicMock()
    pillar_obj.compile_pillar = MagicMock(return_value=compiled)
    grains = MagicMock()
    grains.value = MagicMock(return_value={})
    with patch(
        "salt.pillar.get_pillar", MagicMock(return_value=pillar_obj)
    ), patch.dict(
        pillarmod.__opts__,
        {"id": "minion", "saltenv": "base", "pillar_mask_output": True},
    ), patch.object(
        pillarmod, "__grains__", grains, create=True
    ):
        assert pillarmod.ext({"libvirt": "_"}, unmask=True) == compiled
        assert pillarmod.ext({"libvirt": "_"}, unmask=False) == compiled


@pytest.mark.parametrize("func", ["items", "ext"])
def test_pillar_object_is_destroyed(func):
    """
    ``items`` and ``ext`` build a ``RemotePillar`` that owns a ``ReqChannel``.
    It must be destroyed explicitly, otherwise the channel's ``SyncWrapper``
    is only reclaimed at interpreter shutdown and logs
    ``unclosed SyncWrapper`` (#70355).
    """
    pillar_obj = MagicMock()
    pillar_obj.compile_pillar = MagicMock(return_value={"a": 1})
    grains = MagicMock()
    grains.value = MagicMock(return_value={})
    with patch(
        "salt.pillar.get_pillar", MagicMock(return_value=pillar_obj)
    ), patch.object(pillarmod, "__grains__", grains, create=True):
        with patch.dict(
            pillarmod.__opts__,
            {"id": "minion", "saltenv": "base", "pillarenv": None},
        ):
            getattr(pillarmod, func)(**({"external": {}} if func == "ext" else {}))
    pillar_obj.destroy.assert_called_once_with()


def test_items_destroys_pillar_object_on_error():
    pillar_obj = MagicMock()
    pillar_obj.compile_pillar = MagicMock(side_effect=RuntimeError("boom"))
    grains = MagicMock()
    grains.value = MagicMock(return_value={})
    with patch(
        "salt.pillar.get_pillar", MagicMock(return_value=pillar_obj)
    ), patch.object(pillarmod, "__grains__", grains, create=True):
        with patch.dict(
            pillarmod.__opts__,
            {"id": "minion", "saltenv": "base", "pillarenv": None},
        ):
            with pytest.raises(RuntimeError):
                pillarmod.items()
    pillar_obj.destroy.assert_called_once_with()
