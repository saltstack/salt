import pytest


@pytest.mark.slow_test
def test_saltcheck_render_pyobjects_state(salt_master, salt_call_cli):
    with pytest.helpers.temp_file("pyobj_touched.txt") as tpath:
        sls_content = """
        #!pyobjects

        File.touch("{}")
        """.format(
            tpath
        )

        tst_content = """
        is_stuff_there:
          module_and_function: file.file_exists
          args:
            - "{}"
          assertion: assertTrue
        """.format(
            tpath
        )

        with salt_master.state_tree.base.temp_file(
            "pyobj_touched/init.sls", sls_content
        ):
            with salt_master.state_tree.base.temp_file(
                "pyobj_touched/saltcheck-tests/init.tst", tst_content
            ):
                ret = salt_call_cli.run(
                    "--local",
                    "saltcheck.run_state_tests",
                    "pyobj_touched",
                )
                assert (
                    ret.data[0]["pyobj_touched"]["is_stuff_there"]["status"] == "Pass"
                )
                assert ret.data[1]["TEST RESULTS"]["Passed"] == 1
                assert ret.data[1]["TEST RESULTS"]["Missing Tests"] == 0
                assert ret.data[1]["TEST RESULTS"]["Failed"] == 0
                assert ret.data[1]["TEST RESULTS"]["Skipped"] == 0


@pytest.mark.slow_test
def test_saltcheck_allow_remote_fileclient(salt_master, salt_call_cli):
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

    with salt_master.state_tree.base.temp_file("sltchk_remote/init.sls", sls_content):
        with salt_master.state_tree.base.temp_file(
            "sltchk_remote/saltcheck-tests/init.tst", tst_content
        ):
            with salt_master.state_tree.base.temp_file(
                "sltchk_remote/download_me.txt", "salty"
            ):
                ret = salt_call_cli.run(
                    "saltcheck.run_state_tests",
                    "sltchk_remote",
                )
                assert (
                    ret.data[0]["sltchk_remote"]["test cp.cache_file"]["status"]
                    == "Pass"
                )
                assert ret.data[1]["TEST RESULTS"]["Passed"] == 1
                assert ret.data[1]["TEST RESULTS"]["Missing Tests"] == 0
                assert ret.data[1]["TEST RESULTS"]["Failed"] == 0
                assert ret.data[1]["TEST RESULTS"]["Skipped"] == 0
