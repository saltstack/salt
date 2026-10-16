"""
Unit tests for the direct_call executor, in particular how it sets up pillar
value masking for the function it runs.
"""

import pytest

import salt.executors.direct_call as direct_call
import salt.modules.pillar as pillarmod
import salt.utils.secret as secret
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {pillarmod: {}}


@pytest.fixture
def pillar_data():
    with patch.dict(pillarmod.__pillar__, {"foo": 42, "db": {"password": "pw"}}):
        yield


def _run(fun, func, *args, **kwargs):
    return direct_call.execute({}, {"fun": fun}, func, args, kwargs)


def test_nested_pillar_get_returns_real_values_for_non_pillar_jobs(pillar_data):
    """
    ``test.check_pillar``-style code calling pillar.get without ``unmask`` gets
    the real value, because the executor turns the value switch off.
    """

    def job():
        return pillarmod.get("foo"), pillarmod.get("db")

    assert _run("test.check_pillar", job) == (42, {"password": "pw"})


def test_repr_stays_masked_while_job_runs(pillar_data):
    """Real values for callers must not un-redact repr()/logging."""

    def job():
        return repr(secret.hide({"password": "pw"})), secret.mask_pillar.get()

    shown, display_masked = _run("test.ping", job)
    assert display_masked is True
    assert secret.REDACT_PLACEHOLDER in shown
    assert "pw" not in shown


def test_pillar_jobs_keep_masked_default(pillar_data):
    """``salt '*' pillar.get foo`` is user-facing output and stays masked."""
    result = _run("pillar.get", pillarmod.get, "foo")
    assert result == secret.REDACT_PLACEHOLDER


def test_explicit_unmask_false_still_masks(pillar_data):
    """A caller that explicitly asks for masked output keeps getting it."""

    def job():
        return pillarmod.get("foo", unmask=False)

    assert _run("oracle.show_pillar", job) == secret.REDACT_PLACEHOLDER


def test_switch_is_restored_after_job_and_on_error(pillar_data):
    def boom():
        assert secret.mask_values.get() is False
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        _run("test.fail", boom)
    assert secret.mask_values.get() is None
    assert pillarmod.get("foo") == secret.REDACT_PLACEHOLDER


def test_missing_fun_in_data_is_treated_as_non_pillar(pillar_data):
    """Some callers pass data without ``fun``; that must not raise."""

    def job():
        return pillarmod.get("foo")

    assert direct_call.execute({}, {}, job, (), {}) == 42
    assert direct_call.execute({}, None, job, (), {}) == 42
