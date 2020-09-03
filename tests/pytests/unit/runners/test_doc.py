import pytest
import salt.runner
import salt.runners.doc as doc
from tests.support.mock import PropertyMock, patch


@pytest.fixture(autouse=True)
def setup_loader(request):
    setup_loader_modules = {doc: {}}
    with pytest.helpers.loader_mock(request, setup_loader_modules) as loader_mock:
        yield loader_mock


@pytest.fixture()
def runner_client():
    client = salt.runner.RunnerClient({})

    def fnord():
        """
        This is some docstring, OK?
        """

    def baz():
        """
        This is another docstring, OK?
        """

    functions = {
        "fnord": fnord,
        "baz": baz,
    }
    patch_rc = patch("salt.runner.RunnerClient", return_value=client)
    patch_functions = patch.object(
        type(client), "functions", PropertyMock(return_value=functions)
    )
    with patch_rc, patch_functions:
        yield


def test_when_no_mod_name_is_provided_then_default_results_should_be_returned(
    runner_client,
):
    expected_docs = {
        "fnord": "\n        This is some docstring, OK?\n        ",
        "baz": "\n        This is another docstring, OK?\n        ",
    }

    actual_docs = doc.runner()

    assert actual_docs == expected_docs


def test_when_mod_name_is_provided_then_docs_for_that_mod_should_be_returned(
    runner_client,
):
    module_name = "fnord"
    expected_docs = {module_name: "\n        This is some docstring, OK?\n        "}

    actual_docs = doc.runner(module_name)

    assert actual_docs == expected_docs


def test_when_mod_name_is_provided_and_mod_name_does_not_exist_then_empty_data_should_be_returned(
    runner_client,
):
    expected_docs = {}
    module_name = "not-da-module"

    actual_docs = doc.runner(module_name)

    assert actual_docs == expected_docs
