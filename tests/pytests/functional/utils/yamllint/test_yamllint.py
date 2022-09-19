from pathlib import Path

import pytest

import salt.utils.versions as versions

try:
    import salt.utils.yamllint as yamllint

    YAMLLINT_AVAILABLE = True
except ImportError:
    YAMLLINT_AVAILABLE = False


pytestmark = [
    pytest.mark.skipif(
        YAMLLINT_AVAILABLE is False, reason="The 'yammllint' pacakge is not available"
    ),
]


def test_good_yaml():
    good_yaml = "key: value\n"

    assert yamllint.lint(good_yaml) == {"source": good_yaml, "problems": []}


def test_bad_yaml():
    bad_yaml = "key: value"
    assert yamllint.lint(bad_yaml) == {
        "source": bad_yaml,
        "problems": [
            {
                "column": 11,
                "comment": "no new line character at the end of file (new-line-at-end-of-file)",
                "level": "error",
                "line": 1,
            }
        ],
    }


def test_input_bytes():
    good_yaml = "key: 😳\n"
    assert yamllint.lint(good_yaml) == {"source": good_yaml, "problems": []}


def test_config():
    good_yaml = "key: this line is long according to config\n"
    config_file = str(Path(__file__).parent / "relaxed.yaml")
    assert yamllint.lint(good_yaml) == {"source": good_yaml, "problems": []}
    assert yamllint.lint(good_yaml, config_file) == {
        "source": good_yaml,
        "problems": [
            {
                "column": 5,
                "comment": "line too long (42 > 4 characters) (line-length)",
                "level": "error",
                "line": 1,
            }
        ],
    }


def test_version():
    assert versions.version_cmp(yamllint.version(), "1.26.3") >= 0


def test_has_yamllint():
    assert yamllint.has_yamllint() is True
