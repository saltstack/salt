import pytest


@pytest.fixture
def saltcheck(modules):
    return modules.saltcheck


@pytest.mark.slow_test
def test_saltcheck_render_pyobjects_state(state_tree, saltcheck):
    with pytest.helpers.temp_file("pyobj_touched.txt") as tpath:
        sls_content = f"""
        #!pyobjects

        File.touch("{tpath}")
        """
        tst_content = f"""
        is_stuff_there:
          module_and_function: file.file_exists
          args:
            - "{tpath}"
          assertion: assertTrue
        """
        with pytest.helpers.temp_file(
            "pyobj_touched/init.sls", sls_content, state_tree
        ), pytest.helpers.temp_file(
            "pyobj_touched/saltcheck-tests/init.tst", tst_content, state_tree
        ):
            ret = saltcheck.run_state_tests("pyobj_touched")
            assert ret[0]["pyobj_touched"]["is_stuff_there"]["status"] == "Pass"
            assert ret[1]["TEST RESULTS"]["Passed"] == 1
            assert ret[1]["TEST RESULTS"]["Missing Tests"] == 0
            assert ret[1]["TEST RESULTS"]["Failed"] == 0
            assert ret[1]["TEST RESULTS"]["Skipped"] == 0


@pytest.mark.slow_test
def test_saltcheck_allow_remote_fileclient(state_tree, saltcheck):
    sls_content = """
    test_state:
      test.show_notification:
        - text: The test state
    """

    tst_content = """
    test cp.cache_file:
      module_and_function: cp.cache_file
      args:
        - salt://sltchk_remote/download_me.txt
      kwargs:
        saltenv: base
      assertion: assertNotEmpty
      output_details: True
    """

    with pytest.helpers.temp_file(
        "sltchk_remote/init.sls", sls_content, state_tree
    ), pytest.helpers.temp_file(
        "sltchk_remote/saltcheck-tests/init.tst", tst_content, state_tree
    ), pytest.helpers.temp_file(
        "sltchk_remote/download_me.txt", "salty", state_tree
    ):

        ret = saltcheck.run_state_tests("sltchk_remote")
        assert ret[0]["sltchk_remote"]["test cp.cache_file"]["status"] == "Pass"
        assert ret[1]["TEST RESULTS"]["Passed"] == 1
        assert ret[1]["TEST RESULTS"]["Missing Tests"] == 0
        assert ret[1]["TEST RESULTS"]["Failed"] == 0
        assert ret[1]["TEST RESULTS"]["Skipped"] == 0
