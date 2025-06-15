import pytest

import salt.utils.verify


@pytest.mark.parametrize(
    "data, result",
    [
        ("https://saltproject.io", True),
        (
            "https://mail.google.com/mail/u/0/#inbox/FMfcgzQbdrMwJwbwbPfCFLjMRQvWVcJK",
            True,
        ),
        ("http://parts.org/foo/bar=/bat", True),
        ("foobar://saltproject.io", False),
        ("http://parts.org/foo/b\nar=/bat", False),
        (
            'base ssh://fake@git/repo\n[core]\nsshCommand = touch /tmp/pwn\n[remote "origin"]\n',
            False,
        ),
        (
            'ssh://fake@git/repo\n[core]\nsshCommand = touch /tmp/pwn\n[remote "origin"]\n',
            False,
        ),
        ("https://github.com/saltstack/salt-test-pillar-gitfs.git", True),
    ],
)
def test_url_validator(data, result):
    assert salt.utils.verify.URLValidator()(data) is result


@pytest.mark.parametrize(
    "data, result",
    [
        ("asdf", True),
        ("asdf-", True),
        ("0123456789abcdefghijklmnopqrstuv-._~!$&'():@,", True),
        ("0123456789ABCDEFGHIJKLMNOPQRSTUV-._~!$&'():@,", True),
        ("abcd\\efg", False),
    ],
)
def test_pchar_validator(data, result):
    matcher = salt.utils.verify.URLValidator.pchar_matcher()
    assert bool(matcher.match(data)) == result
