import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_pyobjects_renderer(state, state_tree, tmp_path):
    """
    Test pyobjects renderer when running state.sls
    """
    file_path = str(tmp_path).replace("\\", "/")
    sls1_contents = f"""
    #!pyobjects
    import pathlib
    import salt://test_pyobjects2.sls
    test_file = pathlib.Path("{file_path}", "test")
    File.managed(str(test_file))
    """
    sls2_contents = f"""
    #!pyobjects
    import pathlib
    test_file = pathlib.Path("{file_path}", "test2")
    File.managed(str(test_file))
    """

    with pytest.helpers.temp_file(
        "test_pyobjects.sls", sls1_contents, state_tree
    ) as state1:
        with pytest.helpers.temp_file(
            "test_pyobjects2.sls", sls2_contents, state_tree
        ) as state2:
            ret = state.sls("test_pyobjects")
            assert not ret.errors
            for state_return in ret:
                assert state_return.result is True
                assert str(tmp_path) in state_return.name
