import pytest
import salt.utils.templates as templates
from tests.support.mock import patch


@pytest.fixture(
    ids=["fixed_vars", "broken_vars"],
    params=[
        {
            "slsvar_fixes": True,
            "expected_context": {
                "slspath": "some/path/to",
                "sls_path": "some_path_to",
                "slscolonpath": "some:path:to",
                "slsdotpath": "some.path.to",
                "tpldir": "some/path/to",
                "tpldot": "some.path.to",
                "tplfile": "some/path/to/templates",
                "tplpath": "some/path/to/templates",
                "tplroot": "some",
            },
        },
        {
            "slsvar_fixes": False,
            "expected_context": {
                "sls_path": "",
                "slspath": "",
                "slscolonpath": "",
                "slsdotpath": "",
                "tpldir": ".",
                "tpldot": "",
                "tplfile": "",
                "tplpath": "some/path/to/templates",
                "tplroot": "",
            },
        },
    ],
)
def expected_context(request):
    orig = templates.features.get

    def get_var(*args, **kwargs):
        var = args[0]
        if var == "enable_slsvars_fixes":
            return request.param["slsvar_fixes"]
        return orig(*args, **kwargs)

    with patch("salt.features.features.get", autospec=True, side_effect=get_var):
        yield request.param["expected_context"]


def test_generate_sls_context_should_create_expected_values_based_on_tmplpath_and_sls(
    expected_context,
):

    context = templates.generate_sls_context(
        tmplpath="some/path/to/templates", sls="fnord"
    )

    assert context == expected_context
