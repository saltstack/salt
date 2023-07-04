import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
]


@pytest.mark.parametrize("output_fmt", ["yaml", "json"])
def test_salt_output(salt_cli, salt_minion, output_fmt):
    """
    Test --output
    """
    ret = salt_cli.run(
        f"--output={output_fmt}", "test.fib", "7", minion_tgt=salt_minion.id
    )
    if output_fmt == "json":
        assert 13 in ret.data
    else:
        ret.stdout.matcher.fnmatch_lines(["*- 13*"])
