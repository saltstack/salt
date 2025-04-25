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
    ],
)
def test_url_validator(data, result):
    assert salt.utils.verify.URLValidator()(data) is result
