import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_mako_renderer(state, state_tree):
    """
    Test mako renderer when running state.sls
    """
    sls_contents = """
    #!mako|yaml
    %for a in [1,2,3]:
    echo ${a}:
        cmd.run
    %endfor
    """
    with pytest.helpers.temp_file("issue-55124.sls", sls_contents, state_tree):
        ret = state.sls("issue-55124")
        for state_return in ret:
            assert state_return.result is True
            assert "echo" in state_return.id
