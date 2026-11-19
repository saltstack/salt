"""
Tests for salt.types -- custom pydantic types for Salt module signatures.
"""

from datetime import timedelta

import pytest

import salt.types as salt_types

pytestmark = pytest.mark.skipif(
    not salt_types.HAS_PYDANTIC, reason="pydantic not installed"
)


try:
    from pydantic import BaseModel, ValidationError
except ImportError:  # pragma: no cover
    BaseModel = object


class _MinionTarget(BaseModel):
    target: salt_types.MinionID


class _PortOnly(BaseModel):
    port: salt_types.Port


class _DurationModel(BaseModel):
    interval: salt_types.Duration


class _ByteSizeModel(BaseModel):
    size: salt_types.ByteSize


class TestMinionID:
    @pytest.mark.parametrize(
        "value", ["minion1", "web-01.example.com", "*", "db?", "A_B.c"]
    )
    def test_accepts_valid(self, value):
        assert _MinionTarget(target=value).target == value

    def test_rejects_empty(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            _MinionTarget(target="")

    def test_rejects_space(self):
        with pytest.raises(ValidationError, match="outside"):
            _MinionTarget(target="minion 1")

    def test_rejects_too_long(self):
        with pytest.raises(ValidationError, match="too long"):
            _MinionTarget(target="a" * 254)

    def test_rejects_slash(self):
        with pytest.raises(ValidationError, match="outside"):
            _MinionTarget(target="minion/1")


class TestPort:
    @pytest.mark.parametrize("value", [1, 80, 8080, 65535, "443"])
    def test_accepts_valid(self, value):
        assert _PortOnly(port=value).port == int(value)

    @pytest.mark.parametrize("value", [0, -1, 65536, 100000])
    def test_rejects_out_of_range(self, value):
        with pytest.raises(ValidationError):
            _PortOnly(port=value)


class TestDuration:
    @pytest.mark.parametrize(
        "value,expected_seconds",
        [
            ("30s", 30),
            ("5m", 300),
            ("2h", 7200),
            ("1d", 86400),
            ("1.5h", 5400),
            ("0.5m", 30),
            (3600, 3600),
            (30.5, 30.5),
            ("PT1H30M", 5400),  # ISO-8601 via pydantic's built-in
        ],
    )
    def test_coerces(self, value, expected_seconds):
        got = _DurationModel(interval=value).interval
        assert isinstance(got, timedelta)
        assert got.total_seconds() == pytest.approx(expected_seconds)

    def test_timedelta_passes_through(self):
        td = timedelta(minutes=10)
        got = _DurationModel(interval=td).interval
        assert got == td

    def test_rejects_garbage_string(self):
        with pytest.raises(ValidationError):
            _DurationModel(interval="not-a-duration")


class TestByteSize:
    @pytest.mark.parametrize(
        "value,expected_bytes",
        [
            ("500MB", 500 * 10**6),
            ("1.5GiB", int(1.5 * 2**30)),
            ("4096", 4096),
            ("4096B", 4096),
            ("2KB", 2000),
            ("2KiB", 2048),
            ("1TB", 10**12),
            ("1TiB", 2**40),
            (1048576, 1048576),
            ("500mb", 500 * 10**6),  # case-insensitive
            ("  500 MB  ", 500 * 10**6),  # whitespace tolerant
        ],
    )
    def test_coerces(self, value, expected_bytes):
        got = _ByteSizeModel(size=value).size
        assert got == expected_bytes

    def test_rejects_unknown_unit(self):
        with pytest.raises(ValidationError, match="unknown unit"):
            _ByteSizeModel(size="500XB")

    def test_rejects_garbage(self):
        with pytest.raises(ValidationError, match="cannot parse"):
            _ByteSizeModel(size="not a size")

    def test_rejects_bool(self):
        # bool-is-int would be a nasty footgun.
        with pytest.raises(ValidationError, match="bool"):
            _ByteSizeModel(size=True)

    def test_rejects_negative_from_ge_constraint(self):
        with pytest.raises(ValidationError):
            _ByteSizeModel(size=-100)


class TestJsonSchemaEmission:
    def test_duration_schema_has_title_and_examples(self):
        js = _DurationModel.model_json_schema()
        prop = js["properties"]["interval"]
        assert prop.get("title") == "Duration"
        assert "30s" in prop.get("examples", [])

    def test_bytesize_schema_has_title_and_examples(self):
        js = _ByteSizeModel.model_json_schema()
        prop = js["properties"]["size"]
        assert prop.get("title") == "ByteSize"
        assert "500MB" in prop.get("examples", [])

    def test_port_schema_has_range_constraints(self):
        js = _PortOnly.model_json_schema()
        prop = js["properties"]["port"]
        assert prop.get("minimum") == 1
        assert prop.get("maximum") == 65535


class TestLoaderIntegration:
    """Roll it up: a function using salt.types goes through the loader's
    validate_inputs() and the custom-type coercion happens end-to-end."""

    def test_duration_coerced_through_validate_inputs(self):
        import salt.loader.validation as validation

        def retry(interval: salt_types.Duration = timedelta(seconds=30)):
            return interval

        _args, kwargs = validation.validate_inputs(
            retry, (), {"interval": "5m"}, "enforce"
        )
        assert isinstance(kwargs["interval"], timedelta)
        assert kwargs["interval"].total_seconds() == 300

    def test_bytesize_coerced_through_validate_inputs(self):
        import salt.loader.validation as validation

        def cap(max_memory: salt_types.ByteSize = 0):
            return max_memory

        _args, kwargs = validation.validate_inputs(
            cap, (), {"max_memory": "500MB"}, "enforce"
        )
        assert kwargs["max_memory"] == 500 * 10**6
