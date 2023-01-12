def test_deprecation_warning_emits_deprecation_warnings(salt_call_cli):
    ret = salt_call_cli.run("test.deprecation_warning")
    assert ret.stderr.count("DeprecationWarning") >= 2
    assert "This is a test deprecation warning by version." in ret.stderr
    assert (
        "This is a test deprecation warning by date very far into the future (3000-01-01)"
        in ret.stderr
    )
