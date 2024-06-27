import pytest

pytestmark = [
    pytest.mark.skip_unless_on_linux,
]


@pytest.mark.parametrize("output_fmt", ["yaml", "json"])
def test_salt_output(salt_cli, salt_minion, salt_master, output_fmt):
    """
    Test --output
    """
    assert salt_master.is_running()

    ret = salt_cli.run(
        f"--output={output_fmt}", "test.fib", "7", minion_tgt=salt_minion.id
    )
    if output_fmt == "json":
        assert 13 in ret.data
    else:
        ret.stdout.matcher.fnmatch_lines(["*- 13*"])
