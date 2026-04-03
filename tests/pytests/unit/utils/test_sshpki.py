from datetime import datetime, timedelta

import pytest

from tests.support.mock import patch

try:
    import salt.utils.sshpki as ssh
    from salt.utils.x509 import TIME_FMT

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False


pytestmark = [
    pytest.mark.skipif(HAS_LIBS is False, reason="Needs cryptography library"),
]


class DateTimeMock(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls.strptime("2026-03-20 13:37:42", TIME_FMT)


@pytest.fixture(autouse=True)
def time_stopped():
    with patch("salt.utils.sshpki.datetime", new=DateTimeMock) as mocked_dt:
        yield mocked_dt.now()


@pytest.mark.parametrize(
    "policy,kwargs,expected",
    [
        (
            {},
            {"i_can_do": "whatever", "days_remaining": 2},
            {"i_can_do": "whatever", "days_remaining": 2},
        ),
        (
            {"key_id": None},
            {"critical_options": {"foo": "bar"}},
            {"critical_options": {"foo": "bar"}},
        ),
        (
            {"allowed_critical_options": ["*"]},
            {"critical_options": {"foo": "bar"}},
            {"critical_options": {"foo": "bar"}},
        ),
        (
            {"allowed_critical_options": ["foo"]},
            {"critical_options": {"foo": "bar"}},
            {"critical_options": {"foo": "bar"}},
        ),
        ({"allowed_critical_options": []}, {"critical_options": {"foo": "bar"}}, {}),
        (
            {"default_critical_options": {"baz": "yeah"}},
            {"critical_options": {"foo": "bar"}},
            {"critical_options": {"foo": "bar", "baz": "yeah"}},
        ),
        (
            {"default_critical_options": {"foo": "baz"}},
            {"critical_options": {"foo": "bar"}},
            {"critical_options": {"foo": "bar"}},
        ),
        (
            {"critical_options": {"foo": "baz"}},
            {"critical_options": {"foo": "bar"}},
            {"critical_options": {"foo": "baz"}},
        ),
        (
            {"critical_options": {"baz": "yeah"}},
            {"critical_options": {"foo": "bar", "baz": "no"}},
            {"critical_options": {"foo": "bar", "baz": "yeah"}},
        ),
        (
            {
                "default_critical_options": {"baz": "yeah"},
                "allowed_critical_options": [],
            },
            {"critical_options": {"foo": "bar"}},
            {"critical_options": {"baz": "yeah"}},
        ),
        (
            {"key_id": None},
            {"extensions": {"foo": "bar"}},
            {"extensions": {"foo": "bar"}},
        ),
        (
            {"allowed_extensions": ["*"]},
            {"extensions": {"foo": "bar"}},
            {"extensions": {"foo": "bar"}},
        ),
        (
            {"allowed_extensions": ["foo"]},
            {"extensions": {"foo": "bar"}},
            {"extensions": {"foo": "bar"}},
        ),
        ({"allowed_extensions": []}, {"extensions": {"foo": "bar"}}, {}),
        (
            {"default_extensions": {"baz": "yeah"}},
            {"extensions": {"foo": "bar"}},
            {"extensions": {"foo": "bar", "baz": "yeah"}},
        ),
        (
            {"default_extensions": {"foo": "baz"}},
            {"extensions": {"foo": "bar"}},
            {"extensions": {"foo": "bar"}},
        ),
        (
            {"extensions": {"foo": "baz"}},
            {"extensions": {"foo": "bar"}},
            {"extensions": {"foo": "baz"}},
        ),
        (
            {"extensions": {"baz": "yeah"}},
            {"extensions": {"foo": "bar", "baz": "no"}},
            {"extensions": {"foo": "bar", "baz": "yeah"}},
        ),
        (
            {"default_extensions": {"baz": "yeah"}, "allowed_extensions": []},
            {"extensions": {"foo": "bar"}},
            {"extensions": {"baz": "yeah"}},
        ),
        (
            {"valid_principals": ["foo", "bar"]},
            {},
            {"valid_principals": ["foo", "bar"]},
        ),
        (
            {"valid_principals": ["foo", "bar"]},
            {"valid_principals": ["baz", "blob"]},
            {"valid_principals": ["foo", "bar"]},
        ),
        (
            {"valid_principals": ["foo"]},
            {"valid_principals": ["foo"]},
            {"valid_principals": ["foo"]},
        ),
        (
            {"valid_principals": ["foo", "bar"]},
            {"valid_principals": ["foo", "baz"]},
            {"valid_principals": ["foo"]},
        ),
        (
            {"valid_principals": ["foo", "bar"]},
            {"all_principals": True},
            {"valid_principals": ["foo", "bar"]},
        ),
        (
            {
                "allowed_valid_principals": ["foo", "bar"],
                "default_valid_principals": ["foo"],
            },
            {},
            {"valid_principals": ["foo"]},
        ),
        (
            {
                "allowed_valid_principals": ["foo", "bar"],
                "default_valid_principals": ["foo"],
            },
            {"valid_principals": ["foo", "baz"]},
            {"valid_principals": ["foo"]},
        ),
        (
            {
                "allowed_valid_principals": ["foo", "bar"],
                "default_valid_principals": ["foo"],
            },
            {"all_principals": True},
            {"valid_principals": ["foo", "bar"]},
        ),
        ({"all_principals": True}, {}, {"all_principals": True}),
        (
            {"all_principals": True},
            {"valid_principals": ["foo", "bar"]},
            {"valid_principals": ["foo", "bar"], "all_principals": True},
        ),
        ({"key_id": None}, {"ttl": 86400}, {"ttl": 86400}),
        ({"ttl": "1d"}, {}, {"ttl": 86400}),
        ({"max_ttl": "1h"}, {"ttl": "1d"}, {"ttl": 3600}),
        ({"max_ttl": "1h"}, {}, {"ttl": 3600}),
        ({"max_ttl": "1h", "ttl": "30m"}, {}, {"ttl": 1800}),
        ({"max_ttl": "1h", "ttl": "30m"}, {"ttl": "2h"}, {"ttl": 3600}),
        ({"max_ttl": "1h", "ttl": "30m"}, {"ttl": "1m"}, {"ttl": 60}),
        (
            {},
            {"not_before": "2026-03-13 13:37:42", "not_after": "2027-03-20 13:37:41"},
            {"not_before": "2026-03-13 13:37:42", "not_after": "2027-03-20 13:37:41"},
        ),
        (
            {"ttl": "1h"},
            {"not_before": "2026-03-13 13:37:42", "not_after": "2027-03-13 13:37:41"},
            {
                "not_before": "2026-03-13 13:37:42",
                "not_after": "2026-03-13 14:37:42",
                "ttl": 3600,
            },
        ),
        (
            {"max_ttl": "1h"},
            {"not_before": "2026-03-13 13:37:42", "not_after": "2027-03-13 13:37:41"},
            {
                "not_before": "2026-03-13 13:37:42",
                "not_after": "2026-03-13 14:37:42",
                "ttl": 3600,
            },
        ),
        (
            {"ttl": "30m", "max_ttl": "1h"},
            {"not_before": "2026-03-13 13:37:42", "not_after": "2027-03-13 13:37:41"},
            {
                "not_before": "2026-03-13 13:37:42",
                "not_after": "2026-03-13 14:37:42",
                "ttl": 3600,
            },
        ),
        (
            {"max_ttl": "1h"},
            {"not_before": "2026-03-13 13:37:42", "not_after": "2026-03-13 14:22:00"},
            {
                "not_before": "2026-03-13 13:37:42",
                "not_after": "2026-03-13 14:22:00",
                "ttl": 2658,
            },
        ),
        (
            {"max_ttl": "1h"},
            {"not_before": "2025-03-13 13:37:42"},
            {
                "not_before": "2025-03-13 13:37:42",
                "not_after": "2025-03-13 14:37:42",
                "ttl": 3600,
            },
        ),
        (
            {"max_ttl": "1h"},
            {"not_after": "2027-03-20 13:37:42"},
            {
                "not_before": "2026-03-20 13:37:42",
                "not_after": "2026-03-20 14:37:42",
                "ttl": 3600,
            },
        ),
    ],
)
def test_merge_signing_policy(policy, kwargs, expected, time_stopped):
    res = {
        k: v
        for k, v in ssh.merge_signing_policy(policy, kwargs.copy()).items()
        if v is not None
    }
    if "ttl" in policy or "max_ttl" in policy or "ttl" in kwargs:
        expected["not_before"] = expected.get("not_before") or datetime.strftime(
            time_stopped, TIME_FMT
        )
        expected["not_after"] = expected.get("not_after") or datetime.strftime(
            time_stopped + timedelta(seconds=expected["ttl"]), TIME_FMT
        )
    assert res == expected
