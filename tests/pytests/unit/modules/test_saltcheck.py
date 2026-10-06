import pytest

import salt.modules.saltcheck as saltcheck
from tests.support.mock import MagicMock

xmldiff = pytest.importorskip("xmldiff.main")


@pytest.fixture()
def configure_loader_modules():
    return {saltcheck: {"__salt__": {"state.show_top": MagicMock()}}}


@pytest.mark.parametrize("saltenv", ["base", "dev", "howdy"])
def test__get_top_states_call_args(saltenv):
    saltcheck._get_top_states(saltenv=saltenv)
    saltcheck.__salt__["state.show_top"].assert_called_with(saltenv=saltenv)


def test__generate_junit_out_list():
    results = {
        "apache": {
            "echo_test_hello": {"status": "Pass", "duration": 2.5907},
            "echo_test_hello2": {
                "status": "Fail: fail expected is not equal to hello",
                "duration": 0.4503,
            },
            "echo_test_hello3": {"status": "Skip", "duration": 0.0},
        }
    }

    expected = (
        """<?xml version="1.0" ?>\n<testsuites disabled="0" errors="0" failures="1" tests="3" time="3.041">\n"""
        + """\t<testsuite disabled="0" errors="0" failures="1" name="test_results" skipped="1" tests="3" time="3.041">\n"""
        + """\t\t<testcase name="echo_test_hello" time="2.590700"/>\n"""
        + """\t\t<testcase name="echo_test_hello2" time="0.450300">\n"""
        + """\t\t\t<failure type="failure" message="Fail: fail expected is not equal to hello"/>\n\t\t</testcase>\n"""
        + """\t\t<testcase name="echo_test_hello3">\n\t\t\t<skipped type="skipped" message="Skip"/>\n\t\t</testcase>\n"""
        + """\t</testsuite>\n</testsuites>\n"""
    )
    ret = saltcheck._generate_junit_out_list(results)
    diff = xmldiff.diff_texts(ret, expected)
    assert diff == []
