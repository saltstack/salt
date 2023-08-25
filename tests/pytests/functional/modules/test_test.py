def test_deprecation_warnings_ignore(salt_call_cli):
    """
    Test to ensure when env variable PYTHONWARNINGS=ignore
    is set that we do not add warning to output.
    """
    ret = salt_call_cli.run(
        "--local", "test.deprecation_warning", env={"PYTHONWARNINGS": "ignore"}
    )
    assert "DeprecationWarning" not in ret.stderr
